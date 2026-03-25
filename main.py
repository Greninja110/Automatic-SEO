"""
SEO Audit Tool — Main Controller

Input priority:
  1. target_website variable below  — set this for quick single-site testing
  2. targets.txt file               — one URL per line; prefix with # to skip
  3. --url CLI argument             — overrides everything when passed

Usage examples:
  python main.py                          # uses target_website or targets.txt
  python main.py --url https://site.com  # one-off override via CLI
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import date
from urllib.parse import urlparse, urljoin

import aiohttp
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ===========================================================================
# CONFIGURATION — edit these variables for quick testing
# ===========================================================================

# Set a single URL here to test just one site without editing targets.txt.
# Leave as empty string "" to use targets.txt instead.
target_website = "https://abhijeetsahoo.in/"

# Primary SEO keyword for density and heading checks.
# Leave as empty string "" if you don't want keyword analysis.
# Examples: "humic acid", "humic acid fertilizer", "buy humic acid"
target_keyword = ""

# Path to the targets file (one URL per line, # prefix = skip that line)
TARGET_FILE = "targets.txt"

# ===========================================================================


# ---------------------------------------------------------------------------
# CLI (optional — overrides the variables above when --url is passed)
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SEO Audit Tool")
    parser.add_argument("--url",       default=None,        help="Single URL override (ignores target_website and targets.txt)")
    parser.add_argument("--depth",     type=int, default=1, help="Crawl depth (default 1)")
    parser.add_argument("--keyword",   default=None,        help="Target keyword for density check")
    parser.add_argument("--output",    default=None,        help="Output filename prefix (without .docx) — only used with --url")
    parser.add_argument("--delay",     type=float, default=0.3, help="Delay between requests in seconds")
    parser.add_argument("--max-pages", type=int, default=0,     help="Max pages to crawl per site (0 = unlimited)")
    parser.add_argument("--concurrency", type=int, default=10,  help="Max concurrent async fetch connections (default 10)")
    return parser.parse_args()


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
    # 1. CLI --url flag
    if args.url:
        url = _normalise_url(args.url)
        print(f"[TARGET] Mode: CLI --url override → {url}")
        return [(url, args.output)]

    # 2. target_website variable
    if target_website.strip():
        url = _normalise_url(target_website.strip())
        print(f"[TARGET] Mode: target_website variable → {url}")
        return [(url, None)]

    # 3. targets.txt
    if not os.path.exists(TARGET_FILE):
        print(f"[ERROR] No target specified.")
        print(f"        → Set the 'target_website' variable in main.py, or")
        print(f"        → Create '{TARGET_FILE}' with one URL per line, or")
        print(f"        → Pass --url https://example.com")
        sys.exit(1)

    targets = []
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue                      # blank or commented-out
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

async def _fetch_async(url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore):
    """Fetch a single URL asynchronously. Returns (url, text, status) or (url, None, None)."""
    async with semaphore:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; SEOAuditBot/1.0; "
                    "+https://github.com/seo-audit-tool)"
                )
            }
            async with session.get(url, headers=headers, allow_redirects=True,
                                   timeout=aiohttp.ClientTimeout(total=15)) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" in content_type:
                    text = await resp.text(errors="replace")
                    return url, text, resp.status, dict(resp.headers), str(resp.url)
                return url, None, resp.status, dict(resp.headers), str(resp.url)
        except Exception as e:
            print(f"  [WARN] Could not fetch {url}: {e}")
            return url, None, None, {}, url


async def crawl_site_async(start_url: str, depth: int = 1,
                           max_pages: int = 0, delay: float = 0.3,
                           concurrency: int = 10) -> list:
    """
    Async BFS crawl of same-domain pages up to `depth` levels.
    max_pages=0 means unlimited.
    Returns list of {"url", "response_stub", "soup"} dicts compatible with sync code.
    """
    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.replace("www.", "")

    visited = set()
    # queue items: (url, depth_level)
    current_level = [(start_url, 0)]
    pages = []

    limit_str = f"max={max_pages}" if max_pages > 0 else "unlimited"
    print(f"\n[CRAWL] Starting async crawl of {start_url} "
          f"(depth={depth}, {limit_str}, concurrency={concurrency})")

    ssl_context = False  # skip SSL verification (same as sync version)

    connector = aiohttp.TCPConnector(ssl=ssl_context, limit=concurrency)
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession(connector=connector) as session:
        while current_level:
            # Filter out already-visited
            to_fetch = []
            for url, d in current_level:
                norm = url.rstrip("/")
                if norm not in visited:
                    visited.add(norm)
                    to_fetch.append((url, d))

            if not to_fetch:
                break

            # Respect max_pages cap
            if max_pages > 0:
                remaining = max_pages - len(pages)
                if remaining <= 0:
                    break
                to_fetch = to_fetch[:remaining]

            print(f"  [CRAWL] Fetching {len(to_fetch)} URL(s) at depth "
                  f"{to_fetch[0][1] if to_fetch else '?'} "
                  f"(total so far: {len(pages)}) ...")

            tasks = [_fetch_async(url, session, semaphore) for url, _ in to_fetch]
            results = await asyncio.gather(*tasks)

            next_level = []
            for (orig_url, orig_depth), (fetched_url, text, status, headers, final_url) in zip(to_fetch, results):
                if text is None:
                    continue

                soup = BeautifulSoup(text, "lxml")

                # Build a lightweight response stub so check modules keep working
                # (they expect .status_code, .headers, .url, .text, .elapsed)
                class _ResponseStub:
                    def __init__(self):
                        self.status_code = status or 200
                        self.headers     = headers
                        self.url         = final_url
                        self.text        = text
                        self.content     = text.encode("utf-8", errors="replace")
                        # Provide a minimal elapsed timedelta-like object
                        class _Elapsed:
                            total_seconds = lambda self: 0.0
                        self.elapsed = _Elapsed()

                pages.append({
                    "url":      orig_url,
                    "response": _ResponseStub(),
                    "soup":     soup,
                })

                # Discover links for next depth level
                if orig_depth < depth:
                    for a in soup.find_all("a", href=True):
                        href = a.get("href", "").strip()
                        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                            continue
                        full_url = urljoin(orig_url, href).split("#")[0].split("?")[0]
                        parsed = urlparse(full_url)
                        if (parsed.scheme in ("http", "https") and
                                parsed.netloc.replace("www.", "") == base_domain and
                                full_url.rstrip("/") not in visited):
                            next_level.append((full_url, orig_depth + 1))

                if delay > 0:
                    await asyncio.sleep(delay)

            current_level = next_level

            # Stop if we've hit the cap
            if max_pages > 0 and len(pages) >= max_pages:
                break

    print(f"[CRAWL] Completed: {len(pages)} page(s) crawled\n")
    return pages


def crawl_site(start_url: str, session: requests.Session,
               depth: int = 1, max_pages: int = 0, delay: float = 0.3,
               concurrency: int = 10) -> list:
    """Sync wrapper around the async crawler."""
    return asyncio.run(crawl_site_async(start_url, depth=depth, max_pages=max_pages,
                                        delay=delay, concurrency=concurrency))


# ---------------------------------------------------------------------------
# Sync fallback fetcher (used by check modules that still use requests.Session)
# ---------------------------------------------------------------------------

def fetch_page(url: str, session: requests.Session, timeout: int = 15):
    """Fetch a single URL. Returns (response, soup) or (None, None)."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SEOAuditBot/1.0; "
                "+https://github.com/seo-audit-tool)"
            )
        }
        r = session.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        if "text/html" in r.headers.get("Content-Type", ""):
            soup = BeautifulSoup(r.text, "lxml")
            return r, soup
        return r, None
    except Exception as e:
        print(f"  [WARN] Could not fetch {url}: {e}")
        return None, None


# ---------------------------------------------------------------------------
# Check Runner
# ---------------------------------------------------------------------------

def run_all_checks(pages: list, shared_state: dict) -> dict:
    """Run all 23 SEO check modules across crawled pages."""
    from checks import ALL_CHECKS, SITE_WIDE_CHECKS

    all_results = {}
    first_page  = pages[0] if pages else None
    total_mods  = len(ALL_CHECKS)

    for idx, (module_name, check_fn) in enumerate(ALL_CHECKS, start=1):
        scope = "site-wide" if module_name in SITE_WIDE_CHECKS else f"{len(pages)} page(s)"
        print(f"  [CHECK {idx:>2}/{total_mods}] {module_name} ({scope}) ...", end=" ", flush=True)
        start = time.time()

        if module_name in SITE_WIDE_CHECKS:
            try:
                result = check_fn(
                    url=first_page["url"],
                    soup=first_page["soup"],
                    response=first_page["response"],
                    **shared_state
                )
            except Exception as e:
                result = {
                    "checks": [{"name": "Module error", "status": "warning",
                                 "detail": f"Error in {module_name}: {str(e)}"}],
                    "summary": f"Module failed: {e}"
                }
            for check in result.get("checks", []):
                check.setdefault("page", first_page["url"] if first_page else "N/A")
            all_results[module_name] = result
        else:
            # Heavy network modules: sample first 10 pages to avoid very long runtimes
            SAMPLED_MODULES = {"image_optimization", "external_links", "internal_linking"}
            page_list = pages[:10] if module_name in SAMPLED_MODULES else pages

            merged_checks = []
            for page in page_list:
                try:
                    result = check_fn(
                        url=page["url"],
                        soup=page["soup"],
                        response=page["response"],
                        **shared_state
                    )
                    for check in result.get("checks", []):
                        check.setdefault("page", page["url"])
                    merged_checks.extend(result.get("checks", []))
                except Exception as e:
                    merged_checks.append({
                        "name": "Module error",
                        "status": "warning",
                        "detail": f"Error on {page['url']}: {str(e)}",
                        "page": page["url"]
                    })

            passed  = sum(1 for c in merged_checks if c["status"] == "pass")
            failed  = sum(1 for c in merged_checks if c["status"] == "fail")
            warned  = sum(1 for c in merged_checks if c["status"] == "warning")
            sampled = len(page_list)
            all_results[module_name] = {
                "checks":  merged_checks,
                "summary": (f"{passed} passed, {failed} failed, {warned} warnings "
                             f"across {sampled} page(s)"
                             + (f" (sampled from {len(pages)})" if sampled < len(pages) else "") + ".")
            }

        elapsed  = time.time() - start
        n_checks = len(all_results[module_name].get("checks", []))
        fails    = sum(1 for c in all_results[module_name].get("checks", []) if c["status"] == "fail")
        warns    = sum(1 for c in all_results[module_name].get("checks", []) if c["status"] == "warning")
        print(f"done  ({n_checks} checks | {fails} fail | {warns} warn | {elapsed:.1f}s)")

    return all_results


def compute_score(all_results: dict) -> dict:
    total = passed = failed = warnings = 0
    for result in all_results.values():
        for check in result.get("checks", []):
            total += 1
            s = check.get("status")
            if s == "pass":       passed   += 1
            elif s == "fail":     failed   += 1
            elif s == "warning":  warnings += 1
    score_pct = round((passed / total * 100) if total > 0 else 0, 1)
    return {"total": total, "passed": passed, "failed": failed,
            "warnings": warnings, "score_pct": score_pct}


# ---------------------------------------------------------------------------
# Single-site audit
# ---------------------------------------------------------------------------

def audit_one(target_url: str, output_hint: str | None,
              args: argparse.Namespace, pagespeed_key: str,
              site_index: int, total_sites: int,
              keyword_override: str = "") -> None:
    """Run the full audit pipeline for a single URL."""
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
    print("=" * 60)

    # Async crawl (no session needed — uses aiohttp internally)
    pages = crawl_site(
        start_url=target_url,
        session=None,       # kept for signature compat; unused by async crawler
        depth=args.depth,
        max_pages=args.max_pages,
        delay=args.delay,
        concurrency=args.concurrency,
    )

    if not pages:
        print(f"[SKIP] Could not fetch {target_url} — skipping.\n")
        return

    all_urls = [p["url"] for p in pages]

    # Build a sync requests.Session for check modules that still need it
    sync_session = requests.Session()
    sync_session.verify = False
    requests.packages.urllib3.disable_warnings()

    shared_state = {
        "base_url":           f"{urlparse(target_url).scheme}://{urlparse(target_url).netloc}",
        "session":            sync_session,
        "all_urls":           all_urls,
        "pagespeed_api_key":  pagespeed_key,
        "keyword":            effective_keyword,
        "seen_titles":        set(),
        "seen_h1s":           set(),
        "seen_canonicals":    {},
        "content_hashes":     {},
        "sitemap_urls":       [],
        "robots_txt_content": "",
    }

    from checks import ALL_CHECKS
    print(f"\n[CHECKS] Running all {len(ALL_CHECKS)} SEO modules across {len(pages)} page(s)...")
    all_results = run_all_checks(pages, shared_state)

    score = compute_score(all_results)
    print(f"\n[SCORE] {score['score_pct']}/100  "
          f"(passed: {score['passed']}, failed: {score['failed']}, "
          f"warnings: {score['warnings']}, total: {score['total']})")

    import report_generator
    import report_generator_html
    os.makedirs("reports", exist_ok=True)

    domain = urlparse(target_url).netloc.replace("www.", "").replace(":", "_")
    base_name = output_hint or f"{domain}_{date.today()}"
    base_name = base_name.replace(".docx", "").replace(".html", "")

    docx_path = os.path.join("reports", base_name + ".docx")
    html_path = os.path.join("reports", base_name + ".html")

    metadata = {
        "url":           target_url,
        "date":          time.strftime("%Y-%m-%d %H:%M:%S"),
        "depth":         args.depth,
        "pages_crawled": len(pages),
        "pages_list":    all_urls,
        "keyword":       effective_keyword or "",
    }

    print(f"\n[REPORT] Generating reports...")
    docx_path = report_generator.generate_report(all_results, score, metadata, docx_path)
    print(f"[REPORT] DOCX saved: {os.path.abspath(docx_path)}")
    html_path = report_generator_html.generate_html_report(all_results, score, metadata, html_path)
    print(f"[REPORT] HTML saved: {os.path.abspath(html_path)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    pagespeed_key = os.getenv("PAGESPEED_API_KEY", "").strip()
    if pagespeed_key == "your_key_here":
        pagespeed_key = ""

    targets = load_targets(args)
    total   = len(targets)

    for i, (url, output_hint) in enumerate(targets, start=1):
        audit_one(url, output_hint, args, pagespeed_key, i, total,
                  keyword_override=target_keyword)

    print(f"\n{'='*60}")
    print(f"  All done — {total} site(s) audited.")
    print(f"  Reports saved in: {os.path.abspath('reports')}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
