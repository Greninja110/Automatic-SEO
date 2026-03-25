"""Module 18: Error Pages"""
import time
from urllib.parse import urlparse
import re


def check_error_pages(url: str, soup, response, session=None,
                       all_urls: list = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    ghost_path = "/this-page-definitely-does-not-exist-seo-test-abc123xyz"
    ghost_url = base_url + ghost_path

    # 1 & 2 & 3. Custom 404, correct status, no soft 404
    ghost_response = None
    ghost_soup = None
    if session:
        try:
            from bs4 import BeautifulSoup
            start = time.time()
            ghost_response = session.get(ghost_url, timeout=10)
            ghost_load_time = time.time() - start
            ghost_html = ghost_response.text
            ghost_soup = BeautifulSoup(ghost_html, "lxml")

            # 2. Correct HTTP 404 status
            if ghost_response.status_code == 404:
                checks.append({"name": "404 returns correct HTTP status", "status": "pass",
                                "detail": f"Non-existent URL correctly returns 404: {ghost_url}"})
                # 3. No soft 404 (page returns 200 but looks like error page)
                checks.append({"name": "No soft 404 (200 for missing pages)", "status": "pass",
                                "detail": "Server returns genuine 404 status"})
            elif ghost_response.status_code == 200:
                # Soft 404
                checks.append({"name": "404 returns correct HTTP status", "status": "fail",
                                "detail": f"Missing page returns 200 (soft 404): {ghost_url}"})
                soft_indicators = re.search(r'(not found|404|page does not exist|cannot be found)',
                                             ghost_html, re.IGNORECASE)
                checks.append({"name": "No soft 404 (200 for missing pages)", "status": "fail",
                                "detail": f"Soft 404 detected — page shows '{soft_indicators.group() if soft_indicators else 'no error text'}' but returns HTTP 200"})
            else:
                checks.append({"name": "404 returns correct HTTP status", "status": "warning",
                                "detail": f"Non-existent URL returns HTTP {ghost_response.status_code}: {ghost_url}"})
                checks.append({"name": "No soft 404 (200 for missing pages)", "status": "warning",
                                "detail": f"Unexpected status {ghost_response.status_code} for missing page"})

            # 1. Custom 404 page exists (has body content)
            has_content = len(ghost_html.strip()) > 500
            if has_content and ghost_response.status_code == 404:
                checks.append({"name": "Custom 404 page exists", "status": "pass",
                                "detail": f"404 page has content ({len(ghost_html)} bytes): {ghost_url}"})
            elif ghost_response.status_code == 404:
                checks.append({"name": "Custom 404 page exists", "status": "warning",
                                "detail": f"404 page exists but has minimal content ({len(ghost_html)} bytes)"})
            else:
                checks.append({"name": "Custom 404 page exists", "status": "warning",
                                "detail": f"Could not confirm custom 404 page (HTTP {ghost_response.status_code})"})

        except Exception as e:
            for name in ["Custom 404 page exists", "404 returns correct HTTP status", "No soft 404 (200 for missing pages)"]:
                checks.append({"name": name, "status": "warning",
                                "detail": f"Error testing 404: {str(e)[:60]}"})
            ghost_load_time = None
    else:
        for name in ["Custom 404 page exists", "404 returns correct HTTP status", "No soft 404 (200 for missing pages)"]:
            checks.append({"name": name, "status": "warning", "detail": "No session available to test 404 behavior"})
        ghost_load_time = None

    # 4. 404 page has navigation
    if ghost_soup:
        has_nav = bool(ghost_soup.find("nav")) or len(ghost_soup.find_all("a", href=True)) > 2
        if has_nav:
            checks.append({"name": "404 page has navigation links", "status": "pass",
                            "detail": "404 page contains navigation elements"})
        else:
            checks.append({"name": "404 page has navigation links", "status": "warning",
                            "detail": "404 page lacks navigation — users cannot find other content"})
    else:
        checks.append({"name": "404 page has navigation links", "status": "warning",
                        "detail": "404 page not accessible for navigation check"})

    # 5. 404 page has search box
    if ghost_soup:
        has_search = bool(ghost_soup.find("input", attrs={"type": "search"})) or \
                     bool(ghost_soup.find("input", attrs={"name": "q"})) or \
                     bool(ghost_soup.find("input", attrs={"name": "search"}))
        if has_search:
            checks.append({"name": "404 page has search box", "status": "pass",
                            "detail": "Search input found on 404 page"})
        else:
            checks.append({"name": "404 page has search box", "status": "warning",
                            "detail": "No search box on 404 page — consider adding one"})
    else:
        checks.append({"name": "404 page has search box", "status": "warning",
                        "detail": "404 page not accessible for search check"})

    # 6. 410 Gone pages (informational from crawl)
    gone_pages = []
    if all_urls and session:
        for check_url in all_urls[:20]:
            try:
                r = session.head(check_url, timeout=5)
                if r.status_code == 410:
                    gone_pages.append(check_url)
            except Exception:
                pass
    if gone_pages:
        checks.append({"name": "410 Gone pages (informational)", "status": "warning",
                        "detail": f"410 Gone pages found: {gone_pages[:3]}"})
    else:
        checks.append({"name": "410 Gone pages (informational)", "status": "pass",
                        "detail": "No 410 Gone pages detected in crawl"})

    # 7. 500 error pages handled
    checks.append({"name": "500 error pages handled (advisory)", "status": "warning",
                    "detail": "Cannot trigger 500 errors safely — manually verify that server errors show a branded page"})

    # 8. No 5xx pages in crawl
    five_xx_pages = []
    if all_urls and session:
        for check_url in (all_urls or [])[:30]:
            try:
                r = session.head(check_url, timeout=5, allow_redirects=True)
                if r.status_code >= 500:
                    five_xx_pages.append(f"{check_url} (HTTP {r.status_code})")
            except Exception:
                pass
    if five_xx_pages:
        checks.append({"name": "No 5xx server errors in crawl", "status": "fail",
                        "detail": f"5xx errors found: {five_xx_pages[:3]}"})
    else:
        checks.append({"name": "No 5xx server errors in crawl", "status": "pass",
                        "detail": "No 5xx server errors detected in crawled pages"})

    # 9. 404 page load time < 3s
    if ghost_load_time is not None:
        if ghost_load_time < 3:
            checks.append({"name": "404 page loads quickly (<3s)", "status": "pass",
                            "detail": f"404 page load time: {ghost_load_time:.2f}s"})
        else:
            checks.append({"name": "404 page loads quickly (<3s)", "status": "warning",
                            "detail": f"Slow 404 page: {ghost_load_time:.2f}s"})
    else:
        checks.append({"name": "404 page loads quickly (<3s)", "status": "warning",
                        "detail": "Could not measure 404 page load time"})

    # 10. 404 page branded (title not generic)
    if ghost_soup:
        ghost_title = ghost_soup.find("title")
        ghost_title_text = ghost_title.get_text(strip=True) if ghost_title else ""
        generic_titles = {"404", "page not found", "not found", "error"}
        if ghost_title_text and ghost_title_text.lower().strip() not in generic_titles:
            checks.append({"name": "404 page is branded", "status": "pass",
                            "detail": f"404 page title: \"{ghost_title_text[:80]}\""})
        elif not ghost_title_text:
            checks.append({"name": "404 page is branded", "status": "warning",
                            "detail": "404 page has no title"})
        else:
            checks.append({"name": "404 page is branded", "status": "warning",
                            "detail": f"404 page title is generic: \"{ghost_title_text}\" — add site branding"})
    else:
        checks.append({"name": "404 page is branded", "status": "warning",
                        "detail": "404 page not accessible for branding check"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Tested 404 URL: {ghost_url}"

    return {"checks": checks, "summary": summary}
