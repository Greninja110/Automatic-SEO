"""Module 15: Pagination & Canonicals"""
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def check_pagination_canonicals(url: str, soup, response,
                                  all_urls: list = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # Detect if this is a paginated URL
    page_param = None
    page_num = None
    for param in ["page", "p", "pg", "paged", "pagenum"]:
        if param in query_params:
            page_param = param
            try:
                page_num = int(query_params[param][0])
            except (ValueError, IndexError):
                pass
            break

    # Also detect /page/N pattern
    path_page_match = re.search(r'/page/(\d+)', parsed.path)
    if path_page_match:
        page_num = int(path_page_match.group(1))

    is_paginated = page_num is not None

    # 1. Paginated URL pattern detected (informational)
    if is_paginated:
        checks.append({"name": "Pagination pattern detected", "status": "pass",
                        "detail": f"Paginated URL detected — page {page_num}"})
    else:
        checks.append({"name": "Pagination pattern detected", "status": "pass",
                        "detail": "Not a paginated URL (or non-standard pagination)"})

    # 2. First page canonical points to base URL (not ?page=1)
    canonical = soup.find("link", rel="canonical")
    canonical_href = canonical.get("href", "") if canonical else ""

    if is_paginated and page_num == 1 and page_param:
        # page=1 should canonicalize to the base URL
        if page_param not in canonical_href:
            checks.append({"name": "Page 1 canonical = base URL", "status": "pass",
                            "detail": f"Page 1 canonical correctly omits {page_param} param: {canonical_href[:80]}"})
        else:
            checks.append({"name": "Page 1 canonical = base URL", "status": "warning",
                            "detail": f"Page 1 canonical still includes {page_param} param — should point to base URL"})
    else:
        checks.append({"name": "Page 1 canonical = base URL", "status": "pass",
                        "detail": "Not page 1 — check not applicable"})

    # 3. Canonical present on paginated pages
    if is_paginated:
        if canonical_href:
            checks.append({"name": "Canonical present on paginated page", "status": "pass",
                            "detail": f"Canonical: {canonical_href[:80]}"})
        else:
            checks.append({"name": "Canonical present on paginated page", "status": "fail",
                            "detail": "Paginated page missing canonical tag"})
    else:
        if canonical_href:
            checks.append({"name": "Canonical present on paginated page", "status": "pass",
                            "detail": f"Canonical: {canonical_href[:80]}"})
        else:
            checks.append({"name": "Canonical present on paginated page", "status": "warning",
                            "detail": "No canonical tag found on page"})

    # 4. No noindex on paginated pages
    robots_meta = soup.find("meta", attrs={"name": "robots"})
    if robots_meta and "noindex" in robots_meta.get("content", "").lower():
        if is_paginated and page_num and page_num > 1:
            checks.append({"name": "Paginated pages not noindexed", "status": "warning",
                            "detail": "Paginated page is marked noindex — verify this is intentional"})
        else:
            checks.append({"name": "Paginated pages not noindexed", "status": "pass",
                            "detail": "noindex present but not on a detected paginated page"})
    else:
        checks.append({"name": "Paginated pages not noindexed", "status": "pass",
                        "detail": "No noindex on this page"})

    # 5. rel=prev/next usage (informational — deprecated by Google but harmless)
    prev_link = soup.find("link", rel="prev")
    next_link = soup.find("link", rel="next")
    if prev_link or next_link:
        details = []
        if prev_link:
            details.append(f"prev: {prev_link.get('href', '')[:60]}")
        if next_link:
            details.append(f"next: {next_link.get('href', '')[:60]}")
        checks.append({"name": "rel=prev/next pagination hints", "status": "pass",
                        "detail": f"Found: {', '.join(details)}"})
    else:
        if is_paginated:
            checks.append({"name": "rel=prev/next pagination hints", "status": "warning",
                            "detail": "Paginated page lacks rel=prev/next (deprecated but harmless to add)"})
        else:
            checks.append({"name": "rel=prev/next pagination hints", "status": "pass",
                            "detail": "Not a paginated page — rel=prev/next not required"})

    # 6. Self-referencing canonical (each page canonicalizes to itself)
    if canonical_href:
        url_normalized = url.rstrip("/")
        canonical_normalized = canonical_href.rstrip("/")
        if url_normalized == canonical_normalized:
            checks.append({"name": "Self-referencing canonical", "status": "pass",
                            "detail": "Canonical correctly points to this page"})
        else:
            checks.append({"name": "Self-referencing canonical", "status": "warning",
                            "detail": f"Canonical points away: {canonical_href[:80]}"})
    else:
        checks.append({"name": "Self-referencing canonical", "status": "warning",
                        "detail": "No canonical to verify"})

    # 7. Canonical uses HTTPS
    if canonical_href:
        if canonical_href.startswith("https://"):
            checks.append({"name": "Canonical uses HTTPS", "status": "pass",
                            "detail": "Canonical URL is HTTPS"})
        elif canonical_href.startswith("http://"):
            checks.append({"name": "Canonical uses HTTPS", "status": "fail",
                            "detail": f"Canonical uses HTTP: {canonical_href[:80]}"})
        else:
            checks.append({"name": "Canonical uses HTTPS", "status": "warning",
                            "detail": f"Canonical is relative: {canonical_href[:80]}"})
    else:
        checks.append({"name": "Canonical uses HTTPS", "status": "warning",
                        "detail": "No canonical to check"})

    # 8. Trailing slash consistency in canonical
    if canonical_href and url:
        url_slash = urlparse(url).path.endswith("/")
        canon_slash = canonical_href.split("?")[0].endswith("/")
        if url_slash == canon_slash:
            checks.append({"name": "Canonical trailing slash consistent", "status": "pass",
                            "detail": "URL and canonical agree on trailing slash"})
        else:
            checks.append({"name": "Canonical trailing slash consistent", "status": "warning",
                            "detail": "URL and canonical disagree on trailing slash"})
    else:
        checks.append({"name": "Canonical trailing slash consistent", "status": "warning",
                        "detail": "Cannot check — no canonical or URL"})

    # 9. No duplicate canonicals across pages
    if all_urls and canonical_href:
        from collections import defaultdict
        # Count how many pages have seen this canonical (only available if shared dict passed)
        seen_canonicals = kwargs.get("seen_canonicals", {})
        if canonical_href in seen_canonicals and seen_canonicals[canonical_href] != url:
            checks.append({"name": "No duplicate canonicals", "status": "warning",
                            "detail": f"Same canonical shared with {seen_canonicals[canonical_href][:60]}"})
        else:
            if isinstance(seen_canonicals, dict):
                seen_canonicals[canonical_href] = url
            checks.append({"name": "No duplicate canonicals", "status": "pass",
                            "detail": "Canonical URL is unique to this page"})
    else:
        checks.append({"name": "No duplicate canonicals", "status": "warning",
                        "detail": "Single page audit — cross-page duplicate check not available"})

    # 10. URL parameter pages have clean canonical
    if query_params and canonical_href:
        # If page has ?sort= or ?filter=, canonical should be the clean URL
        tracking_params = {"utm_source", "utm_medium", "utm_campaign", "sort", "filter", "order"}
        has_tracking = bool(set(query_params.keys()) & tracking_params)
        if has_tracking:
            clean_url = urlunparse(parsed._replace(query="")).rstrip("/")
            if canonical_href.rstrip("/") == clean_url:
                checks.append({"name": "Parameter URL canonicalizes to clean URL", "status": "pass",
                                "detail": f"Parameters ({list(query_params.keys())[:3]}) properly canonicalized"})
            else:
                checks.append({"name": "Parameter URL canonicalizes to clean URL", "status": "warning",
                                "detail": f"URL has tracking params but canonical does not point to clean URL"})
        else:
            checks.append({"name": "Parameter URL canonicalizes to clean URL", "status": "pass",
                            "detail": "No tracking parameters detected"})
    else:
        checks.append({"name": "Parameter URL canonicalizes to clean URL", "status": "pass",
                        "detail": "No query parameters to check"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    paged_str = f"page {page_num}" if is_paginated else "non-paginated"
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Page type: {paged_str}"

    return {"checks": checks, "summary": summary}
