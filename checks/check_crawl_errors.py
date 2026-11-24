"""Module 22: Crawl Errors"""
import time

from checks._http import head_status, parallel_map


def check_crawl_errors(url: str, soup, response, all_urls: list = None,
                        session=None, sitemap_urls: list = None, crawl_statuses: dict = None,
                        crawl_times: dict = None, linked_urls: set = None, **kwargs) -> dict:
    checks = []
    pages_to_check = all_urls or [url]

    # 1. Current page is 200 OK
    if response.status_code == 200:
        checks.append({"name": "Current page returns 200 OK", "status": "pass",
                        "detail": f"HTTP 200 OK: {url}"})
    else:
        checks.append({"name": "Current page returns 200 OK", "status": "fail",
                        "detail": f"Unexpected status {response.status_code}: {url}"})

    # 2 & 3. 4xx and 5xx in crawl — the crawler already recorded every status
    # and timing; only URLs it lacks are requested again.
    four_xx = []
    five_xx = []
    response_times = []
    sample = pages_to_check[:50]
    crawl_statuses = crawl_statuses or {}
    crawl_times = crawl_times or {}

    def check_one(check_url):
        if crawl_statuses.get(check_url) is not None:
            return check_url, crawl_statuses[check_url], crawl_times.get(check_url)
        start = time.time()
        status, _ = head_status(session, check_url, timeout=8)
        return check_url, status, (time.time() - start) if status else None

    if session and len(pages_to_check) > 1:
        for u, status, elapsed in parallel_map(check_one, sample):
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

    # 8. Orphan candidates: URLs listed in the sitemap that no crawled page links to
    if sitemap_urls and linked_urls is not None and len(pages_to_check) > 1:
        linked = {u.rstrip("/").replace("://www.", "://") for u in linked_urls}
        linked.update(u.rstrip("/").replace("://www.", "://") for u in pages_to_check)
        orphans = [u for u in sitemap_urls
                   if u.strip().rstrip("/").replace("://www.", "://") not in linked]
        if not orphans:
            checks.append({"name": "No orphan pages detected", "status": "pass",
                            "detail": f"All {len(sitemap_urls)} sitemap URLs checked are linked from crawled pages"})
        else:
            checks.append({"name": "No orphan pages detected", "status": "warning",
                            "detail": (f"{len(orphans)} sitemap URL(s) not linked from the {len(pages_to_check)} "
                                       f"crawled page(s) — possible orphans (crawl deeper to confirm): {orphans[:3]}")})
    else:
        checks.append({"name": "No orphan pages detected", "status": "warning",
                        "detail": "Needs a sitemap and a multi-page crawl to compare against"})

    # 9. Sitemap URLs all return 200
    sitemap_errors = []
    if sitemap_urls and session:
        sm_sample = [u.strip() for u in sitemap_urls[:30]]
        for sm_u, st in parallel_map(lambda u: (u, check_one(u)[1]), sm_sample):
            if st and st >= 400:
                sitemap_errors.append(f"{sm_u} (HTTP {st})")

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
