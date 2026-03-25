"""Module 1: URL Structure"""
import re
from urllib.parse import urlparse, parse_qs


def check_url_structure(url: str, soup, response, all_urls: list = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    path = parsed.path
    query = parsed.query

    # 1. Clean URL - no/minimal query params
    params = parse_qs(query)
    if not query:
        checks.append({"name": "Clean URL (no query params)", "status": "pass", "detail": "URL has no query string"})
    elif len(params) <= 2:
        checks.append({"name": "Clean URL (no query params)", "status": "warning", "detail": f"URL has {len(params)} query parameter(s): {query[:80]}"})
    else:
        checks.append({"name": "Clean URL (no query params)", "status": "fail", "detail": f"URL has {len(params)} query parameters which may dilute crawl equity"})

    # 2. URL length
    url_len = len(url)
    if url_len <= 115:
        checks.append({"name": "URL length (≤115 chars)", "status": "pass", "detail": f"URL length: {url_len} characters"})
    elif url_len <= 200:
        checks.append({"name": "URL length (≤115 chars)", "status": "warning", "detail": f"URL is long: {url_len} characters (recommended ≤115)"})
    else:
        checks.append({"name": "URL length (≤115 chars)", "status": "fail", "detail": f"URL is very long: {url_len} characters"})

    # 3. Lowercase URL
    if url == url.lower():
        checks.append({"name": "Lowercase URL", "status": "pass", "detail": "URL is fully lowercase"})
    else:
        checks.append({"name": "Lowercase URL", "status": "fail", "detail": f"URL contains uppercase characters: {url}"})

    # 4. No underscores in path
    if "_" not in path:
        checks.append({"name": "No underscores in path", "status": "pass", "detail": "Path uses hyphens (preferred by Google)"})
    else:
        checks.append({"name": "No underscores in path", "status": "warning", "detail": f"Path contains underscores; use hyphens instead: {path}"})

    # 5. No special/encoded characters
    special = re.search(r'[^a-zA-Z0-9/._~:@!$&\'()*+,;=\-#%?]', url)
    if not special:
        checks.append({"name": "No special characters", "status": "pass", "detail": "URL contains only safe characters"})
    else:
        checks.append({"name": "No special characters", "status": "warning", "detail": f"URL may contain unusual characters: {special.group()}"})

    # 6. Canonical URL present
    canonical_tag = soup.find("link", rel="canonical")
    if canonical_tag and canonical_tag.get("href"):
        checks.append({"name": "Canonical tag present", "status": "pass", "detail": f"Canonical: {canonical_tag['href'][:100]}"})

        # 7. Canonical matches current URL
        canonical_href = canonical_tag["href"].rstrip("/")
        current_normalized = url.rstrip("/")
        if canonical_href == current_normalized:
            checks.append({"name": "Canonical matches current URL", "status": "pass", "detail": "Self-referencing canonical is correct"})
        else:
            checks.append({"name": "Canonical matches current URL", "status": "warning", "detail": f"Canonical points elsewhere: {canonical_href[:100]}"})
    else:
        checks.append({"name": "Canonical tag present", "status": "fail", "detail": "No canonical tag found on this page"})
        checks.append({"name": "Canonical matches current URL", "status": "fail", "detail": "Cannot check — canonical tag is missing"})

    # 8. Duplicate URL detection
    if all_urls:
        normalized_current = url.rstrip("/").lower()
        duplicates = [u for u in all_urls if u != url and u.rstrip("/").lower() == normalized_current]
        if duplicates:
            checks.append({"name": "No duplicate URLs", "status": "fail", "detail": f"Duplicate URLs found: {duplicates[:3]}"})
        else:
            checks.append({"name": "No duplicate URLs", "status": "pass", "detail": "No duplicate URLs detected in crawl"})
    else:
        checks.append({"name": "No duplicate URLs", "status": "warning", "detail": "Single-page audit; duplicate detection requires crawl"})

    # 9. URL depth (path segments)
    segments = [s for s in path.strip("/").split("/") if s]
    depth = len(segments)
    if depth <= 4:
        checks.append({"name": "URL depth (≤4 levels)", "status": "pass", "detail": f"URL depth: {depth} level(s)"})
    else:
        checks.append({"name": "URL depth (≤4 levels)", "status": "warning", "detail": f"URL is deeply nested: {depth} levels deep"})

    # 10. No session IDs / tracking params
    session_patterns = re.search(r'(sid=|sessionid=|PHPSESSID=|jsessionid=)', query, re.IGNORECASE)
    if session_patterns:
        checks.append({"name": "No session IDs in URL", "status": "fail", "detail": f"Session ID found in URL: {session_patterns.group()}"})
    else:
        checks.append({"name": "No session IDs in URL", "status": "pass", "detail": "No session IDs detected in URL"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. URL: {url[:80]}"

    return {"checks": checks, "summary": summary}
