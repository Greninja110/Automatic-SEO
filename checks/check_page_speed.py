"""Module 9: Page Speed & Performance"""
import re
import json
from urllib.parse import urlparse


def check_page_speed(url: str, soup, response, pagespeed_api_key: str = None, session=None, **kwargs) -> dict:
    checks = []
    html = response.text

    # 1. TTFB proxy — response elapsed time
    elapsed = response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
    if elapsed is not None:
        if elapsed < 0.5:
            checks.append({"name": "Server response time (TTFB <0.5s)", "status": "pass", "detail": f"Response time: {elapsed:.2f}s"})
        elif elapsed < 1.5:
            checks.append({"name": "Server response time (TTFB <0.5s)", "status": "warning", "detail": f"Slow response: {elapsed:.2f}s (target <0.5s)"})
        else:
            checks.append({"name": "Server response time (TTFB <0.5s)", "status": "fail", "detail": f"Very slow response: {elapsed:.2f}s"})
    else:
        checks.append({"name": "Server response time (TTFB <0.5s)", "status": "warning", "detail": "Could not measure response time"})

    # 2. Page response size
    size_bytes = len(response.content)
    size_kb = size_bytes / 1024
    if size_kb < 500:
        checks.append({"name": "Page size (<500KB)", "status": "pass", "detail": f"Page size: {size_kb:.1f}KB"})
    elif size_kb < 1024:
        checks.append({"name": "Page size (<500KB)", "status": "warning", "detail": f"Large page: {size_kb:.1f}KB (recommended <500KB)"})
    else:
        checks.append({"name": "Page size (<500KB)", "status": "fail", "detail": f"Very large page: {size_kb:.1f}KB"})

    # 3. Render-blocking scripts in <head>
    head = soup.find("head")
    if head:
        blocking_scripts = [s.get("src", "inline")[:60] for s in head.find_all("script")
                            if not s.get("defer") and not s.get("async") and s.get("src")]
        if not blocking_scripts:
            checks.append({"name": "No render-blocking scripts in <head>", "status": "pass", "detail": "All scripts in <head> have defer or async"})
        else:
            checks.append({"name": "No render-blocking scripts in <head>", "status": "fail",
                            "detail": f"{len(blocking_scripts)} blocking script(s): {blocking_scripts[:3]}"})
    else:
        checks.append({"name": "No render-blocking scripts in <head>", "status": "warning", "detail": "No <head> found"})

    # 4. Render-blocking CSS
    head = soup.find("head")
    if head:
        blocking_css = [l.get("href", "")[:60] for l in head.find_all("link", rel="stylesheet")
                        if l.get("media") not in ["print"] and not l.get("as")]
        if not blocking_css:
            checks.append({"name": "Minimal render-blocking CSS", "status": "pass", "detail": "No excessive render-blocking stylesheets detected"})
        else:
            checks.append({"name": "Minimal render-blocking CSS", "status": "warning",
                            "detail": f"{len(blocking_css)} render-blocking stylesheet(s) in <head>"})
    else:
        checks.append({"name": "Minimal render-blocking CSS", "status": "warning", "detail": "No <head> found"})

    # 5. Browser caching headers
    cache_control = response.headers.get("Cache-Control", "")
    expires = response.headers.get("Expires", "")
    if cache_control:
        checks.append({"name": "Browser caching (Cache-Control header)", "status": "pass", "detail": f"Cache-Control: {cache_control[:80]}"})
    elif expires:
        checks.append({"name": "Browser caching (Cache-Control header)", "status": "warning", "detail": "Uses Expires header instead of Cache-Control"})
    else:
        checks.append({"name": "Browser caching (Cache-Control header)", "status": "fail", "detail": "No caching headers — every visit re-fetches resources"})

    # 6. GZIP/Brotli compression
    encoding = response.headers.get("Content-Encoding", "")
    if encoding in ("gzip", "br", "deflate"):
        checks.append({"name": "HTTP compression (gzip/br)", "status": "pass", "detail": f"Compression: {encoding}"})
    else:
        checks.append({"name": "HTTP compression (gzip/br)", "status": "warning", "detail": "No HTTP compression detected — enable gzip or Brotli"})

    # 7. Lazy loading for images
    imgs = soup.find_all("img")
    lazy_imgs = [img for img in imgs if img.get("loading") == "lazy"]
    if len(imgs) <= 2:
        checks.append({"name": "Lazy loading images", "status": "pass", "detail": "Few images — lazy loading not critical"})
    elif len(lazy_imgs) >= len(imgs) * 0.5:
        checks.append({"name": "Lazy loading images", "status": "pass", "detail": f"{len(lazy_imgs)}/{len(imgs)} images use lazy loading"})
    else:
        checks.append({"name": "Lazy loading images", "status": "warning",
                        "detail": f"Only {len(lazy_imgs)}/{len(imgs)} images use loading=\"lazy\""})

    # 8. HTML minification heuristic
    newline_ratio = html.count("\n") / len(html) if html else 0
    if newline_ratio < 0.02:
        checks.append({"name": "HTML appears minified", "status": "pass", "detail": f"Low newline ratio: {newline_ratio:.3f}"})
    else:
        checks.append({"name": "HTML appears minified", "status": "warning", "detail": f"HTML may not be minified (newline ratio: {newline_ratio:.3f})"})

    # 9. External script count
    ext_domain = urlparse(url).netloc
    external_scripts = [s.get("src", "") for s in soup.find_all("script", src=True)
                        if urlparse(s.get("src", "")).netloc and urlparse(s.get("src", "")).netloc != ext_domain]
    if len(external_scripts) <= 10:
        checks.append({"name": "External script count (≤10)", "status": "pass", "detail": f"External scripts: {len(external_scripts)}"})
    else:
        checks.append({"name": "External script count (≤10)", "status": "warning",
                        "detail": f"High external script count: {len(external_scripts)} (adds latency)"})

    # 10. PageSpeed Insights API
    if pagespeed_api_key and session:
        try:
            api_url = (f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
                       f"?url={url}&key={pagespeed_api_key}&strategy=mobile")
            r = session.get(api_url, timeout=30)
            data = r.json()
            perf_score = data.get("categories", {}).get("performance", {}).get("score", None)
            if perf_score is not None:
                pct = int(perf_score * 100)
                status = "pass" if pct >= 90 else "warning" if pct >= 50 else "fail"
                checks.append({"name": "PageSpeed Insights performance score", "status": status,
                                "detail": f"Mobile performance score: {pct}/100"})
            else:
                checks.append({"name": "PageSpeed Insights performance score", "status": "warning",
                                "detail": "PageSpeed API returned data but no performance score found"})
        except Exception as e:
            checks.append({"name": "PageSpeed Insights performance score", "status": "warning",
                            "detail": f"PageSpeed API error: {str(e)[:80]}"})
    else:
        checks.append({"name": "PageSpeed Insights performance score", "status": "warning",
                        "detail": "No PageSpeed API key — add PAGESPEED_API_KEY to .env for real CWV data"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    elapsed_str = f"{elapsed:.2f}s" if elapsed else "N/A"
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Response time: {elapsed_str}, page size: {size_kb:.1f}KB"

    return {"checks": checks, "summary": summary}
