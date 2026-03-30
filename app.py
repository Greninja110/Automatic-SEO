"""
SEO Audit Tool — Flask Web GUI
Run: python app.py   → opens http://localhost:5000
CLI: python main.py  → terminal mode
"""

import json
import os
import queue
import sys
import threading
import time
import uuid
from datetime import date
from urllib.parse import urlparse

import requests as req_lib
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, send_file

load_dotenv()

# ---------------------------------------------------------------------------
# Thread-aware stdout interceptor
# Captures ALL print() output from registered audit threads and routes it
# to that thread's log queue (so crawl_site prints appear in the web GUI).
# ---------------------------------------------------------------------------

class _ThreadAwareLogger:
    """
    Wraps sys.stdout so that print() calls from a registered audit thread
    are forwarded line-by-line to that thread's log function.
    Every other thread writes normally to the original stdout.
    """

    def __init__(self, original):
        self._orig     = original
        self._registry = {}   # thread_id -> (log_fn, line_buffer)
        self._lock     = threading.Lock()

    def register(self, tid: int, log_fn) -> None:
        with self._lock:
            self._registry[tid] = (log_fn, "")

    def unregister(self, tid: int) -> None:
        with self._lock:
            entry = self._registry.pop(tid, None)
        if entry:
            log_fn, buf = entry
            if buf.strip():   # flush any unterminated partial line
                log_fn(buf)

    def write(self, s: str) -> None:
        self._orig.write(s)   # always mirror to real stdout / terminal
        tid = threading.current_thread().ident
        with self._lock:
            entry = self._registry.get(tid)
        if not entry:
            return
        log_fn, buf = entry
        buf += s
        # Emit each completed line immediately
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            stripped = line.rstrip()
            if stripped:          # skip blank lines to reduce noise
                log_fn(stripped)
        with self._lock:
            if tid in self._registry:
                self._registry[tid] = (self._registry[tid][0], buf)

    def flush(self) -> None:
        self._orig.flush()

    # passthrough attributes Flask/Werkzeug may check
    def fileno(self):
        try:
            return self._orig.fileno()
        except Exception:
            raise io.UnsupportedOperation("fileno")

    @property
    def encoding(self):
        return getattr(self._orig, "encoding", "utf-8")

    @property
    def errors(self):
        return getattr(self._orig, "errors", "replace")


import io   # noqa: E402 – needed for UnsupportedOperation above

_original_stdout = sys.stdout
_thread_logger   = _ThreadAwareLogger(_original_stdout)
sys.stdout       = _thread_logger   # install globally

# ---------------------------------------------------------------------------
app = Flask(__name__)

# In-memory job store  {job_id: {status, log_queue, result, error}}
_jobs: dict      = {}
_jobs_lock       = threading.Lock()


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


# ---------------------------------------------------------------------------
# Background audit worker
# ---------------------------------------------------------------------------

def _run_audit(job_id: str, config: dict) -> None:
    """Runs the full SEO audit in a background thread, streaming logs via queue."""
    job   = _get_job(job_id)
    log_q: queue.Queue = job["log_queue"]

    def log(msg: str) -> None:
        log_q.put(str(msg))

    tid = threading.current_thread().ident
    _thread_logger.register(tid, log)   # capture ALL print() from this thread

    try:
        job["status"] = "running"

        urls        = config["urls"]
        depth       = int(config.get("depth", 1))
        max_pages   = int(config.get("max_pages", 0))
        delay       = float(config.get("delay", 0.3))
        concurrency = int(config.get("concurrency", 10))
        keyword     = config.get("keyword", "").strip() or None
        ps_key      = config.get("pagespeed_key", "").strip()
        selected    = config.get("selected_checks", None)   # None → run all
        formats     = config.get("report_formats", ["docx"])

        import main as seo_main
        from checks import ALL_CHECKS, MODULE_TITLES, SITE_WIDE_CHECKS
        import report_generator
        import report_generator_html

        all_reports = []

        for url_idx, target_url in enumerate(urls):
            log(f"{'═' * 60}")
            log(f"AUDIT [{url_idx + 1}/{len(urls)}]: {target_url}")
            log(f"{'═' * 60}")

            # ── Crawl ──────────────────────────────────────────────
            limit = max_pages or "unlimited"
            log(f"[CRAWL] Starting — depth={depth}  max_pages={limit}  concurrency={concurrency}")

            # crawl_site prints go to stdout → intercepted → routed to log_q
            pages = seo_main.crawl_site(
                start_url=target_url,
                session=None,
                depth=depth,
                max_pages=max_pages,
                delay=delay,
                concurrency=concurrency,
            )

            if not pages:
                log(f"[SKIP] Could not crawl {target_url} — skipping.")
                continue

            log(f"[CRAWL] Done — {len(pages)} page(s) collected")

            # ── Build shared_state ─────────────────────────────────
            sync_session = req_lib.Session()
            sync_session.verify = False
            req_lib.packages.urllib3.disable_warnings()

            parsed = urlparse(target_url)
            shared_state = {
                "base_url":           f"{parsed.scheme}://{parsed.netloc}",
                "session":            sync_session,
                "all_urls":           [p["url"] for p in pages],
                "pagespeed_api_key":  ps_key,
                "keyword":            keyword,
                "seen_titles":        set(),
                "seen_h1s":           set(),
                "seen_canonicals":    {},
                "content_hashes":     {},
                "sitemap_urls":       [],
                "robots_txt_content": "",
            }

            # ── Filter checks ──────────────────────────────────────
            checks_to_run = ALL_CHECKS
            if selected:
                checks_to_run = [(n, fn) for n, fn in ALL_CHECKS if n in selected]

            # ── Run checks ─────────────────────────────────────────
            all_results: dict = {}
            first_page  = pages[0]
            total_mods  = len(checks_to_run)
            SAMPLED     = {"image_optimization", "external_links", "internal_linking"}

            log(f"[CHECKS] Running {total_mods} module(s) across {len(pages)} page(s)...")

            for idx, (mod_name, check_fn) in enumerate(checks_to_run, 1):
                scope = "site-wide" if mod_name in SITE_WIDE_CHECKS else f"{len(pages)} page(s)"
                title = MODULE_TITLES.get(mod_name, mod_name)
                log(f"[{idx:>2}/{total_mods}] {title}  ({scope})")

                t0 = time.time()

                if mod_name in SITE_WIDE_CHECKS:
                    try:
                        res = check_fn(
                            url=first_page["url"],
                            soup=first_page["soup"],
                            response=first_page["response"],
                            **shared_state,
                        )
                    except Exception as exc:
                        res = {
                            "checks":  [{"name": "Module error", "status": "warning",
                                         "detail": str(exc)}],
                            "summary": f"Module failed: {exc}",
                        }
                    for c in res.get("checks", []):
                        c.setdefault("page", first_page["url"])
                    all_results[mod_name] = res

                else:
                    page_list = pages[:10] if mod_name in SAMPLED else pages
                    merged: list = []
                    for page in page_list:
                        try:
                            res = check_fn(
                                url=page["url"],
                                soup=page["soup"],
                                response=page["response"],
                                **shared_state,
                            )
                            for c in res.get("checks", []):
                                c.setdefault("page", page["url"])
                            merged.extend(res.get("checks", []))
                        except Exception as exc:
                            merged.append({
                                "name": "Module error", "status": "warning",
                                "detail": str(exc), "page": page["url"],
                            })

                    p = sum(1 for c in merged if c["status"] == "pass")
                    f = sum(1 for c in merged if c["status"] == "fail")
                    w = sum(1 for c in merged if c["status"] == "warning")
                    all_results[mod_name] = {
                        "checks":  merged,
                        "summary": (f"{p} passed, {f} failed, {w} warnings "
                                    f"across {len(page_list)} page(s)."),
                    }

                elapsed = time.time() - t0
                chks    = all_results[mod_name].get("checks", [])
                n_pass  = sum(1 for c in chks if c["status"] == "pass")
                n_fail  = sum(1 for c in chks if c["status"] == "fail")
                n_warn  = sum(1 for c in chks if c["status"] == "warning")
                log(f"       ✓ {len(chks)} checks | {n_pass} pass | {n_fail} fail | {n_warn} warn | {elapsed:.1f}s")

            # ── Score ──────────────────────────────────────────────
            score = seo_main.compute_score(all_results)
            log(f"")
            log(f"[SCORE] {score['score_pct']}/100  —  "
                f"passed: {score['passed']}  |  "
                f"failed: {score['failed']}  |  "
                f"warnings: {score['warnings']}  |  "
                f"total: {score['total']}")

            # ── Generate reports ───────────────────────────────────
            os.makedirs("reports", exist_ok=True)
            domain    = parsed.netloc.replace("www.", "").replace(":", "_")
            base_name = f"{domain}_{date.today()}"

            metadata = {
                "url":           target_url,
                "date":          time.strftime("%Y-%m-%d %H:%M:%S"),
                "depth":         depth,
                "pages_crawled": len(pages),
                "pages_list":    [p["url"] for p in pages],
                "keyword":       keyword or "",
            }

            gen_files: dict = {}

            if "docx" in formats:
                path = os.path.join("reports", base_name + ".docx")
                log("")
                log("[REPORT] Generating DOCX report ...")
                path = report_generator.generate_report(all_results, score, metadata, path)
                log(f"[REPORT] DOCX saved → {os.path.abspath(path)}")
                gen_files["docx"] = os.path.abspath(path)

            if "html" in formats:
                path = os.path.join("reports", base_name + ".html")
                if "docx" not in formats:
                    log("")
                log("[REPORT] Generating HTML report ...")
                path = report_generator_html.generate_html_report(
                    all_results, score, metadata, path)
                log(f"[REPORT] HTML saved → {os.path.abspath(path)}")
                gen_files["html"] = os.path.abspath(path)

            # Compact module summary for UI rendering
            modules_summary: dict = {}
            for mod, res in all_results.items():
                chks = res.get("checks", [])
                modules_summary[mod] = {
                    "title":   MODULE_TITLES.get(mod, mod),
                    "summary": res.get("summary", ""),
                    "pass":    sum(1 for c in chks if c["status"] == "pass"),
                    "fail":    sum(1 for c in chks if c["status"] == "fail"),
                    "warn":    sum(1 for c in chks if c["status"] == "warning"),
                    "total":   len(chks),
                    "top_issues": [
                        {"name":   c["name"],
                         "status": c["status"],
                         "detail": c.get("detail", ""),
                         "page":   c.get("page", "")}
                        for c in chks if c["status"] in ("fail", "warning")
                    ][:10],
                }

            all_reports.append({
                "url":     target_url,
                "score":   score,
                "files":   gen_files,
                "modules": modules_summary,
            })

        job["status"] = "done"
        job["result"] = all_reports
        log("")
        log(f"{'═' * 60}")
        log(f"  All done — {len(all_reports)} site(s) audited.")
        log(f"{'═' * 60}")

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        job["status"] = "error"
        job["error"]  = str(exc)
        for line in tb.splitlines():
            log(f"[ERROR] {line}")

    finally:
        _thread_logger.unregister(tid)   # flush remaining buffer before __DONE__
        log("__DONE__")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start_audit():
    data = request.get_json(force=True)

    raw_urls = data.get("urls", [])
    if isinstance(raw_urls, str):
        raw_urls = [raw_urls]

    urls = []
    for u in raw_urls:
        u = u.strip()
        if not u or u.startswith("#"):
            continue
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        urls.append(u)

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    job_id = str(uuid.uuid4())
    job = {
        "status":    "queued",
        "log_queue": queue.Queue(),
        "result":    None,
        "error":     None,
    }
    with _jobs_lock:
        _jobs[job_id] = job

    env_ps_key = os.getenv("PAGESPEED_API_KEY", "").strip()
    if env_ps_key in ("", "your_key_here"):
        env_ps_key = ""

    config = {
        "urls":            urls,
        "depth":           data.get("depth", 1),
        "max_pages":       data.get("max_pages", 0),
        "delay":           data.get("delay", 0.3),
        "concurrency":     data.get("concurrency", 10),
        "keyword":         data.get("keyword", ""),
        "pagespeed_key":   data.get("pagespeed_key", "") or env_ps_key,
        "selected_checks": data.get("selected_checks", None),
        "report_formats":  data.get("report_formats", ["docx"]),
    }

    t = threading.Thread(target=_run_audit, args=(job_id, config), daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id: str):
    job = _get_job(job_id)
    if not job:
        return "Job not found", 404

    def generate():
        log_q: queue.Queue = job["log_queue"]
        while True:
            try:
                msg = log_q.get(timeout=30)
                yield f"data: {json.dumps({'log': msg})}\n\n"
                if msg == "__DONE__":
                    payload = json.dumps({
                        "done":   True,
                        "status": job.get("status"),
                        "result": job.get("result", []),
                        "error":  job.get("error"),
                    })
                    yield f"data: {payload}\n\n"
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/download/<job_id>/<int:report_idx>/<fmt>")
def download(job_id: str, report_idx: int, fmt: str):
    job = _get_job(job_id)
    if not job or not job.get("result"):
        return "Not found", 404

    reports = job["result"]
    if report_idx >= len(reports):
        return "Report index out of range", 404

    path = reports[report_idx].get("files", {}).get(fmt)
    if not path or not os.path.exists(path):
        return "File not found", 404

    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/reports-list")
def reports_list():
    os.makedirs("reports", exist_ok=True)
    files = []
    for fname in sorted(os.listdir("reports"), reverse=True):
        fpath = os.path.join("reports", fname)
        if os.path.isfile(fpath):
            files.append({
                "name":  fname,
                "size":  os.path.getsize(fpath),
                "mtime": os.path.getmtime(fpath),
            })
    return jsonify(files)


@app.route("/reports-download/<path:filename>")
def reports_download(filename: str):
    reports_dir = os.path.abspath("reports")
    fpath = os.path.abspath(os.path.join("reports", filename))
    if not fpath.startswith(reports_dir + os.sep):
        return "Forbidden", 403
    if not os.path.exists(fpath):
        return "Not found", 404
    return send_file(fpath, as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import webbrowser
    print("\n" + "=" * 60)
    print("  SEO Audit Tool — Web GUI")
    print("  http://localhost:5000")
    print("  (CLI mode: python main.py --url <url>)")
    print("=" * 60 + "\n")
    webbrowser.open("http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
