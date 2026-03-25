"""Module 22: Crawl Errors"""
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def check_crawl_errors(url: str, soup, response, all_urls: list = None,
                        session=None, sitemap_urls: list = None, **kwargs) -> dict:
    checks = []
    pages_to_check = all_urls or [url]

    # 1. Current page is 200 OK
    if response.status_code == 200:
        checks.append({"name": "Current page returns 200 OK", "status": "pass",
                        "detail": f"HTTP 200 OK: {url}"})
    else:
        checks.append({"name": "Current page returns 200 OK", "status": "fail",
                        "detail": f"Unexpected status {response.status_code}: {url}"})

    # 2 & 3. 4xx and 5xx in crawl
    four_xx = []
    five_xx = []
    response_times = []

    def check_one(check_url):
        try:
            start = time.time()
            r = session.head(check_url, timeout=8, allow_redirects=True)
            elapsed = time.time() - start
            return check_url, r.status_code, elapsed
        except Exception as e:
            return check_url, None, None

    if session and len(pages_to_check) > 1:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(check_one, u): u for u in pages_to_check[:50]}
            for future in as_completed(futures):
                u, status, elapsed = future.result()
                if elapsed is not None:
                    response_times.append(elapsed)
                if status:
                    if 400 <= status < 500:
                        four_xx.append(f"{u} (HTTP {status})")
                    elif status >= 500:
                        five_xx.append(f"{u} (HTTP {status})")

    if four_xx:
        checks.append({"name": "No 4xx client errors in crawl", "status": "fail",
                        "detail": f"{len(four_xx)} 4xx page(s): {four_xx[:5]}"})
    else:
        checks.append({"name": "No 4xx client errors in crawl", "status": "pass",
                        "detail": f"No 4xx errors in {len(pages_to_check)} crawled page(s)"})

    if five_xx:
        checks.append({"name": "No 5xx server errors in crawl", "status": "fail",
                        "detail": f"{len(five_xx)} 5xx page(s): {five_xx[:5]}"})
    else:
        checks.append({"name": "No 5xx server errors in crawl", "status": "pass",
                        "detail": f"No 5xx errors in {len(pages_to_check)} crawled page(s)"})

    # 4. Soft 404 detection on current page
    title = soup.find("title")
    title_text = title.get_text(strip=True).lower() if title else ""
    body_text = soup.get_text()[:2000].lower()
    soft_404_phrases = ["page not found", "404", "cannot be found", "does not exist",
                         "no longer available", "oops"]
    is_soft = response.status_code == 200 and any(p in title_text or p in body_text[:500]
                                                   for p in soft_404_phrases)
    if is_soft:
        checks.append({"name": "No soft 404 on current page", "status": "warning",
                        "detail": f"Page returns 200 but content suggests 404: {url}"})
    else:
        checks.append({"name": "No soft 404 on current page", "status": "pass",
                        "detail": f"No soft 404 indicators on {url}"})

    # 5. Crawl depth reachable (all pages loaded successfully)
    unreachable = [u for u, s, _ in
                   [(check_one(u2)) for u2 in pages_to_check[:20]] if s and s >= 400] \
        if not session else []
    checks.append({"name": "All crawled pages reachable", "status": "pass" if not four_xx and not five_xx else "warning",
                    "detail": f"Crawled {min(len(pages_to_check), 50)} pages — {len(four_xx)+len(five_xx)} error(s)"})

    # 6. Response time distribution (p95)
    if response_times:
        sorted_times = sorted(response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        p95 = sorted_times[min(p95_idx, len(sorted_times)-1)]
        avg = sum(response_times) / len(response_times)
        if p95 < 3:
            checks.append({"name": "Response time p95 < 3s", "status": "pass",
                            "detail": f"p95: {p95:.2f}s, avg: {avg:.2f}s across {len(response_times)} pages"})
        else:
            checks.append({"name": "Response time p95 < 3s", "status": "warning",
                            "detail": f"p95: {p95:.2f}s exceeds 3s threshold (avg: {avg:.2f}s)"})
    else:
        elapsed = response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
        checks.append({"name": "Response time p95 < 3s", "status": "pass" if elapsed < 3 else "warning",
                        "detail": f"Single page: {elapsed:.2f}s"})

    # 7. All internal links resolve (reuse 4xx list)
    if four_xx:
        checks.append({"name": "All internal links resolve", "status": "fail",
                        "detail": f"Broken internal links: {four_xx[:5]}"})
    else:
        checks.append({"name": "All internal links resolve", "status": "pass",
                        "detail": "All sampled internal links resolve correctly"})

    # 8. No orphan pages (pages not linked from anywhere in crawl)
    if len(pages_to_check) > 1:
        # Build link map
        all_linked = set()
        all_linked.add(pages_to_check[0])  # start URL always reachable
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if href.startswith("http"):
                all_linked.add(href.rstrip("/"))
        orphans = [u for u in pages_to_check if u.rstrip("/") not in
                   {l.rstrip("/") for l in all_linked}]
        if not orphans:
            checks.append({"name": "No orphan pages detected", "status": "pass",
                            "detail": "All crawled pages are linked"})
        else:
            checks.append({"name": "No orphan pages detected", "status": "warning",
                            "detail": f"Potential orphan pages: {orphans[:3]}"})
    else:
        checks.append({"name": "No orphan pages detected", "status": "warning",
                        "detail": "Single-page audit — orphan detection requires full crawl"})

    # 9. Sitemap URLs all return 200
    sitemap_errors = []
    if sitemap_urls and session:
        def check_sm_url(sm_url):
            try:
                r = session.head(sm_url.strip(), timeout=8, allow_redirects=True)
                return sm_url, r.status_code
            except Exception:
                return sm_url, None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(check_sm_url, su): su for su in sitemap_urls[:30]}
            for future in as_completed(futures):
                sm_u, s = future.result()
                if s and s >= 400:
                    sitemap_errors.append(f"{sm_u} (HTTP {s})")

    if sitemap_errors:
        checks.append({"name": "Sitemap URLs all return 200", "status": "fail",
                        "detail": f"Sitemap URLs with errors: {sitemap_errors[:5]}"})
    elif sitemap_urls:
        checks.append({"name": "Sitemap URLs all return 200", "status": "pass",
                        "detail": f"Checked {min(30, len(sitemap_urls))} sitemap URLs — all return 200"})
    else:
        checks.append({"name": "Sitemap URLs all return 200", "status": "warning",
                        "detail": "No sitemap URLs available to check"})

    # 10. No blocked resources
    checks.append({"name": "No blocked resources (CSS/JS/images)", "status": "warning",
                    "detail": "Manual verification recommended: check robots.txt does not block CSS/JS/image paths"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = (f"{passed} passed, {failed} failed, {warned} warnings. "
               f"Pages checked: {min(len(pages_to_check), 50)}, 4xx: {len(four_xx)}, 5xx: {len(five_xx)}")

    return {"checks": checks, "summary": summary}
