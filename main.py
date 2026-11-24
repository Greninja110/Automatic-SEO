"""
SEO Audit Tool — Main Controller

Input priority:
  1. --url CLI argument             — overrides everything when passed
  2. target_website variable below  — set this for quick single-site testing
  3. targets.txt file               — one URL per line; prefix with # to skip

Usage examples:
  python main.py                          # uses target_website or targets.txt
  python main.py --url https://site.com  # one-off override via CLI
  python main.py --url site.com --format json --max-pages 20
  python main.py --url site.com --backlinks-json backlinks.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date
from urllib.parse import urlparse, urljoin

import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from requests.structures import CaseInsensitiveDict

from checks._http import USER_AGENT

load_dotenv()

# Windows consoles and piped output (e.g. when an AI agent runs this script)
# often default to cp1252, which cannot print the arrows and check marks below.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ===========================================================================
# CONFIGURATION — edit these variables for quick testing
# ===========================================================================

# Set a single URL here to test just one site without editing targets.txt.
# Leave as empty string "" to use targets.txt instead.
target_website = ""

# Primary SEO keyword for density and heading checks.
# Leave as empty string "" if you don't want keyword analysis.
# Examples: "running shoes", "trail running shoes", "buy running shoes"
target_keyword = ""

# Path to the targets file (one URL per line, # prefix = skip that line)
TARGET_FILE = "targets.txt"

REPORT_FORMATS = ("docx", "html", "json")

# Modules that make many network requests: run on the first N pages only.
SAMPLED_MODULES = {"image_optimization", "external_links", "internal_linking"}
SAMPLE_SIZE = 10

# ===========================================================================


# ---------------------------------------------------------------------------
# CLI (optional — overrides the variables above when --url is passed)
# ---------------------------------------------------------------------------

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SEO Audit Tool")
    parser.add_argument("--url",       default=None,        help="Single URL override (ignores target_website and targets.txt)")
    parser.add_argument("--depth",     type=int, default=1, help="Crawl depth (default 1)")
    parser.add_argument("--keyword",   default=None,        help="Target keyword or phrase for density check")
    parser.add_argument("--output",    default=None,        help="Output filename prefix (no extension) — only used with --url")
    parser.add_argument("--output-dir", default="reports",  help="Folder for generated reports (default: reports)")
    parser.add_argument("--delay",     type=float, default=0.3, help="Delay between requests in seconds")
    parser.add_argument("--max-pages", type=int, default=0,     help="Max pages to crawl per site (0 = unlimited)")
    parser.add_argument("--concurrency", type=int, default=10,  help="Max concurrent async fetch connections (default 10)")
    parser.add_argument("--format",    default="docx,html",
                        help="Comma-separated report formats: docx, html, json (default: docx,html)")
    parser.add_argument("--json",      action="store_true", help="Also write a machine-readable JSON report")
    parser.add_argument("--backlinks-json", default=None,
                        help="Path to a JSON file with live backlink data (e.g. from Agensi's "
                             "backlink summary tool) used by the Backlinks (Live Data) module")
    args = parser.parse_args(argv)

    formats = [f.strip().lower() for f in args.format.split(",") if f.strip()]
    if args.json and "json" not in formats:
        formats.append("json")
    bad = [f for f in formats if f not in REPORT_FORMATS]
    if bad or not formats:
        parser.error(f"--format must be a comma-separated list of {', '.join(REPORT_FORMATS)}")
    args.formats = formats
    return args


# ---------------------------------------------------------------------------
# Target resolution
# ---------------------------------------------------------------------------

def _normalise_url(raw: str) -> str:
    raw = raw.strip().rstrip("/")
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def load_targets(args: argparse.Namespace) -> list:
    """
    Returns a list of (url, output_name_or_None) tuples to audit.
    Priority: --url CLI  >  target_website variable  >  targets.txt
    """
    if args.url:
        url = _normalise_url(args.url)
        print(f"[TARGET] Mode: CLI --url override → {url}")
        return [(url, args.output)]

    if target_website.strip():
        url = _normalise_url(target_website.strip())
        print(f"[TARGET] Mode: target_website variable → {url}")
        return [(url, None)]

    if not os.path.exists(TARGET_FILE):
        print("[ERROR] No target specified.")
        print("        → Set the 'target_website' variable in main.py, or")
        print(f"        → Create '{TARGET_FILE}' with one URL per line, or")
        print("        → Pass --url https://example.com")
        sys.exit(1)

    targets = []
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            targets.append((_normalise_url(line), None))

    if not targets:
        print(f"[ERROR] '{TARGET_FILE}' exists but contains no active URLs "
              f"(all lines are blank or start with #).")
        sys.exit(1)

    print(f"[TARGET] Mode: {TARGET_FILE} → {len(targets)} URL(s) to audit")
    for url, _ in targets:
        print(f"           • {url}")
    return targets


# ---------------------------------------------------------------------------
# Async Crawler
# ---------------------------------------------------------------------------

class _Elapsed:
    """Minimal stand-in for datetime.timedelta used by check modules."""
    def __init__(self, seconds: float):
        self._s = seconds

    def total_seconds(self) -> float:
        return self._s


class _HistoryStub:
    """One redirect hop (mirrors the parts of requests.Response checks use)."""
    def __init__(self, status: int, url: str):
        self.status_code = status
        self.url = url
        self.elapsed = _Elapsed(0.0)


class ResponseStub:
    """requests.Response-compatible view of an aiohttp fetch.

    Check modules use .status_code, .headers, .url, .text, .content,
    .elapsed and .history.
    """
    def __init__(self, status, headers, final_url, text, elapsed, history):
        self.status_code = status or 200
        self.headers     = headers
        self.url         = final_url
        self.text        = text
        self.content     = text.encode("utf-8", errors="replace")
        self.elapsed     = _Elapsed(elapsed)
        self.history     = history


def _merge_headers(raw_headers) -> CaseInsensitiveDict:
    """Case-insensitive headers; repeated headers (e.g. Set-Cookie) are joined."""
    merged = CaseInsensitiveDict()
    for k, v in raw_headers.items():
        merged[k] = f"{merged[k]}, {v}" if k in merged else v
    return merged


async def _fetch_async(url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
    """Fetch one URL. Returns a dict with status, headers, text (HTML only), timing and redirects."""
    async with semaphore:
        start = time.perf_counter()
        try:
            async with session.get(url, allow_redirects=True,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                content_type = resp.headers.get("Content-Type", "")
                text = await resp.text(errors="replace") if "text/html" in content_type else None
                return {
                    "status":  resp.status,
                    "headers": _merge_headers(resp.headers),
                    "final":   str(resp.url),
                    "text":    text,
                    "elapsed": time.perf_counter() - start,
                    "history": [_HistoryStub(h.status, str(h.url)) for h in resp.history],
                }
        except Exception as e:
            print(f"  [WARN] Could not fetch {url}: {e}")
            return {"status": None, "headers": CaseInsensitiveDict(), "final": url,
                    "text": None, "elapsed": time.perf_counter() - start, "history": []}


def _extract_internal_links(soup, page_url: str, base_domain: str) -> list:
    """Internal links in document order, de-duplicated (order keeps --max-pages deterministic)."""
    links = {}
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full_url = urljoin(page_url, href).split("#")[0].split("?")[0]
        parsed = urlparse(full_url)
        if parsed.scheme in ("http", "https") and parsed.netloc.replace("www.", "") == base_domain:
            links.setdefault(full_url, None)
    return list(links)


async def crawl_site_async(start_url: str, depth: int = 1,
                           max_pages: int = 0, delay: float = 0.3,
                           concurrency: int = 10, crawl_info: dict | None = None) -> list:
    """
    Async BFS crawl of same-domain pages up to `depth` levels.
    max_pages=0 means unlimited.

    Returns a list of {"url", "response", "soup"} dicts. When `crawl_info` is
    given it is filled with:
      statuses     {url: HTTP status or None}  for every URL fetched
      times        {url: seconds}
      linked_urls  set of every internal URL linked from any crawled page
    """
    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.replace("www.", "")

    info = crawl_info if crawl_info is not None else {}
    info.setdefault("statuses", {})
    info.setdefault("times", {})
    info.setdefault("linked_urls", set())

    visited = set()
    current_level = [(start_url, 0)]
    pages = []

    limit_str = f"max={max_pages}" if max_pages > 0 else "unlimited"
    print(f"\n[CRAWL] Starting async crawl of {start_url} "
          f"(depth={depth}, {limit_str}, concurrency={concurrency})")

    connector = aiohttp.TCPConnector(ssl=False, limit=concurrency)  # audit sites with broken TLS too
    semaphore = asyncio.Semaphore(concurrency)
    headers = {"User-Agent": USER_AGENT}

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        while current_level:
            to_fetch = []
            for url, d in current_level:
                norm = url.rstrip("/")
                if norm not in visited:
                    visited.add(norm)
                    to_fetch.append((url, d))

            if not to_fetch:
                break

            if max_pages > 0:
                remaining = max_pages - len(pages)
                if remaining <= 0:
                    break
                to_fetch = to_fetch[:remaining]

            print(f"  [CRAWL] Fetching {len(to_fetch)} URL(s) at depth "
                  f"{to_fetch[0][1]} (total so far: {len(pages)}) ...")

            results = await asyncio.gather(*[_fetch_async(u, session, semaphore) for u, _ in to_fetch])

            next_level = []
            for (orig_url, orig_depth), res in zip(to_fetch, results):
                info["statuses"][orig_url] = res["status"]
                info["times"][orig_url] = res["elapsed"]
                if res["text"] is None:
                    continue

                soup = BeautifulSoup(res["text"], "lxml")
                pages.append({
                    "url":      orig_url,
                    "response": ResponseStub(res["status"], res["headers"], res["final"],
                                             res["text"], res["elapsed"], res["history"]),
                    "soup":     soup,
                })

                links = _extract_internal_links(soup, orig_url, base_domain)
                info["linked_urls"].update(links)
                if orig_depth < depth:
                    next_level.extend((u, orig_depth + 1) for u in links
                                      if u.rstrip("/") not in visited)

            if delay > 0:
                await asyncio.sleep(delay)   # politeness pause between crawl levels

            current_level = next_level
            if max_pages > 0 and len(pages) >= max_pages:
                break

    print(f"[CRAWL] Completed: {len(pages)} page(s) crawled\n")
    return pages


def crawl_site(start_url: str, session=None, depth: int = 1, max_pages: int = 0,
               delay: float = 0.3, concurrency: int = 10, crawl_info: dict | None = None) -> list:
    """Sync wrapper around the async crawler (`session` is unused, kept for compatibility)."""
    return asyncio.run(crawl_site_async(start_url, depth=depth, max_pages=max_pages,
                                        delay=delay, concurrency=concurrency,
                                        crawl_info=crawl_info))


# ---------------------------------------------------------------------------
# Shared state + check runner (used by both CLI and the web GUI)
# ---------------------------------------------------------------------------

def load_backlinks_file(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Could not read --backlinks-json {path}: {e}")
        return None


def build_shared_state(target_url: str, pages: list, crawl_info: dict,
                       pagespeed_key: str = "", keyword: str | None = None,
                       backlinks_data: dict | None = None) -> dict:
    from checks._http import make_session
    parsed = urlparse(target_url)
    return {
        "base_url":           f"{parsed.scheme}://{parsed.netloc}",
        "session":            make_session(),
        "all_urls":           [p["url"] for p in pages],
        "pagespeed_api_key":  pagespeed_key,
        "keyword":            keyword,
        "seen_titles":        set(),
        "seen_h1s":           set(),
        "seen_canonicals":    {},
        "content_hashes":     {},
        "sitemap_urls":       [],
        "robots_txt_content": "",
        "crawl_statuses":     crawl_info.get("statuses", {}),
        "crawl_times":        crawl_info.get("times", {}),
        "linked_urls":        crawl_info.get("linked_urls", set()),
        "backlinks_data":     backlinks_data,
    }


def _count(checks: list) -> tuple:
    p = sum(1 for c in checks if c["status"] == "pass")
    f = sum(1 for c in checks if c["status"] == "fail")
    w = sum(1 for c in checks if c["status"] == "warning")
    return p, f, w


def _run_module(module_name, check_fn, pages, shared_state, site_wide: bool) -> dict:
    if site_wide:
        first_page = pages[0]
        try:
            result = check_fn(url=first_page["url"], soup=first_page["soup"],
                              response=first_page["response"], **shared_state)
        except Exception as e:
            result = {"checks": [{"name": "Module error", "status": "warning",
                                  "detail": f"Error in {module_name}: {e}"}],
                      "summary": f"Module failed: {e}"}
        for check in result.get("checks", []):
            check.setdefault("page", first_page["url"])
        return result

    page_list = pages[:SAMPLE_SIZE] if module_name in SAMPLED_MODULES else pages
    merged = []
    for page in page_list:
        try:
            result = check_fn(url=page["url"], soup=page["soup"],
                              response=page["response"], **shared_state)
            for check in result.get("checks", []):
                check.setdefault("page", page["url"])
            merged.extend(result.get("checks", []))
        except Exception as e:
            merged.append({"name": "Module error", "status": "warning",
                           "detail": f"Error on {page['url']}: {e}", "page": page["url"]})

    p, f, w = _count(merged)
    sampled = len(page_list)
    return {"checks": merged,
            "summary": (f"{p} passed, {f} failed, {w} warnings across {sampled} page(s)"
                        + (f" (sampled from {len(pages)})" if sampled < len(pages) else "") + ".")}


def run_all_checks(pages: list, shared_state: dict, selected: list | None = None,
                   on_start=None, on_done=None) -> dict:
    """Run the SEO check modules across crawled pages.

    selected: optional list of module names to run (default: all).
    on_start(idx, total, module_name, scope) / on_done(idx, total, module_name, result, seconds):
    optional progress callbacks; default prints CLI progress lines.
    """
    from checks import ALL_CHECKS, SITE_WIDE_CHECKS

    to_run = [(n, fn) for n, fn in ALL_CHECKS if not selected or n in selected]
    total = len(to_run)
    all_results = {}

    for idx, (module_name, check_fn) in enumerate(to_run, start=1):
        site_wide = module_name in SITE_WIDE_CHECKS
        scope = "site-wide" if site_wide else f"{len(pages)} page(s)"
        if on_start:
            on_start(idx, total, module_name, scope)
        else:
            print(f"  [CHECK {idx:>2}/{total}] {module_name} ({scope}) ...", end=" ", flush=True)

        start = time.time()
        result = _run_module(module_name, check_fn, pages, shared_state, site_wide)
        all_results[module_name] = result
        elapsed = time.time() - start

        if on_done:
            on_done(idx, total, module_name, result, elapsed)
        else:
            checks = result.get("checks", [])
            _, f, w = _count(checks)
            print(f"done  ({len(checks)} checks | {f} fail | {w} warn | {elapsed:.1f}s)")

    return all_results


def compute_score(all_results: dict) -> dict:
    total = passed = failed = warnings = 0
    for result in all_results.values():
        for check in result.get("checks", []):
            total += 1
            s = check.get("status")
            if s == "pass":
                passed += 1
            elif s == "fail":
                failed += 1
            elif s == "warning":
                warnings += 1
    score_pct = round((passed / total * 100) if total > 0 else 0, 1)
    return {"total": total, "passed": passed, "failed": failed,
            "warnings": warnings, "score_pct": score_pct}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def generate_json_report(all_results: dict, score: dict, metadata: dict, path: str) -> str:
    """Machine-readable report: score, metadata and every check grouped by module."""
    from checks import MODULE_TITLES, SITE_WIDE_CHECKS, __version__
    modules = {}
    for name, res in all_results.items():
        checks = res.get("checks", [])
        p, f, w = _count(checks)
        modules[name] = {
            "title":   MODULE_TITLES.get(name, name),
            "scope":   "site-wide" if name in SITE_WIDE_CHECKS else "per-page",
            "summary": res.get("summary", ""),
            "pass": p, "fail": f, "warning": w, "total": len(checks),
            "checks":  checks,
        }
    payload = {"tool": "automatic-seo-audit", "version": __version__,
               "metadata": metadata, "score": score, "modules": modules}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
    return path


def write_reports(all_results: dict, score: dict, metadata: dict, base_path: str,
                  formats, log=print) -> dict:
    """Write the requested report formats; returns {format: absolute_path}."""
    files = {}
    if "docx" in formats:
        import report_generator
        p = report_generator.generate_report(all_results, score, metadata, base_path + ".docx")
        files["docx"] = os.path.abspath(p)
        log(f"[REPORT] DOCX saved: {files['docx']}")
    if "html" in formats:
        import report_generator_html
        p = report_generator_html.generate_html_report(all_results, score, metadata, base_path + ".html")
        files["html"] = os.path.abspath(p)
        log(f"[REPORT] HTML saved: {files['html']}")
    if "json" in formats:
        p = generate_json_report(all_results, score, metadata, base_path + ".json")
        files["json"] = os.path.abspath(p)
        log(f"[REPORT] JSON saved: {files['json']}")
    return files


# ---------------------------------------------------------------------------
# Single-site audit
# ---------------------------------------------------------------------------

def audit_one(target_url: str, output_hint: str | None,
              args: argparse.Namespace, pagespeed_key: str,
              site_index: int, total_sites: int,
              keyword_override: str = "", backlinks_data: dict | None = None) -> dict | None:
    """Run the full audit pipeline for a single URL. Returns {format: path} or None."""
    effective_keyword = keyword_override or args.keyword or None
    max_pages_display = args.max_pages if args.max_pages > 0 else "unlimited"
    print()
    print("=" * 60)
    print(f"  SEO AUDIT  [{site_index}/{total_sites}]")
    print("=" * 60)
    print(f"  Target URL : {target_url}")
    print(f"  Depth      : {args.depth}")
    print(f"  Max Pages  : {max_pages_display}")
    print(f"  Concurrency: {args.concurrency} async connections")
    print(f"  Keyword    : {effective_keyword or 'not set'}")
    print(f"  PageSpeed  : {'API key set' if pagespeed_key else 'not set (heuristics only)'}")
    print(f"  Backlinks  : {'live data supplied' if backlinks_data else 'not supplied'}")
    print(f"  Formats    : {', '.join(args.formats)}")
    print("=" * 60)

    crawl_info: dict = {}
    pages = crawl_site(target_url, depth=args.depth, max_pages=args.max_pages,
                       delay=args.delay, concurrency=args.concurrency, crawl_info=crawl_info)

    if not pages:
        print(f"[SKIP] Could not fetch {target_url} — skipping.\n")
        return None

    shared_state = build_shared_state(target_url, pages, crawl_info, pagespeed_key,
                                      effective_keyword, backlinks_data)

    from checks import ALL_CHECKS
    print(f"\n[CHECKS] Running all {len(ALL_CHECKS)} SEO modules across {len(pages)} page(s)...")
    all_results = run_all_checks(pages, shared_state)

    score = compute_score(all_results)
    print(f"\n[SCORE] {score['score_pct']}/100  "
          f"(passed: {score['passed']}, failed: {score['failed']}, "
          f"warnings: {score['warnings']}, total: {score['total']})")

    os.makedirs(args.output_dir, exist_ok=True)
    domain = urlparse(target_url).netloc.replace("www.", "").replace(":", "_")
    base_name = output_hint or f"{domain}_{date.today()}"
    for ext in (".docx", ".html", ".json"):
        base_name = base_name.replace(ext, "")

    metadata = {
        "url":           target_url,
        "date":          time.strftime("%Y-%m-%d %H:%M:%S"),
        "depth":         args.depth,
        "pages_crawled": len(pages),
        "pages_list":    shared_state["all_urls"],
        "keyword":       effective_keyword or "",
    }

    print("\n[REPORT] Generating reports...")
    return write_reports(all_results, score, metadata,
                         os.path.join(args.output_dir, base_name), args.formats)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    pagespeed_key = os.getenv("PAGESPEED_API_KEY", "").strip()
    if pagespeed_key == "your_key_here":
        pagespeed_key = ""

    backlinks_data = load_backlinks_file(args.backlinks_json)

    targets = load_targets(args)
    total   = len(targets)

    for i, (url, output_hint) in enumerate(targets, start=1):
        audit_one(url, output_hint, args, pagespeed_key, i, total,
                  keyword_override=target_keyword, backlinks_data=backlinks_data)

    print(f"\n{'='*60}")
    print(f"  All done — {total} site(s) audited.")
    print(f"  Reports saved in: {os.path.abspath(args.output_dir)}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
