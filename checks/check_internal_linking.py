"""Module 6: Internal Linking"""
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed


GENERIC_ANCHORS = {"click here", "read more", "here", "link", "more", "learn more", "this", "page", "website"}


def _is_internal(href: str, base_domain: str) -> bool:
    parsed = urlparse(href)
    return not parsed.netloc or parsed.netloc.replace("www.", "") == base_domain.replace("www.", "")


def check_internal_linking(url: str, soup, response, base_url: str = None, session=None, **kwargs) -> dict:
    checks = []
    if not base_url:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

    base_domain = urlparse(base_url).netloc.replace("www.", "")
    all_links = soup.find_all("a", href=True)
    internal_links = []

    for a in all_links:
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full_url = urljoin(url, href)
        if _is_internal(full_url, base_domain):
            internal_links.append((full_url, a))

    total_internal = len(internal_links)

    # 1. Has internal links
    if total_internal >= 2:
        checks.append({"name": "Has internal links", "status": "pass", "detail": f"Found {total_internal} internal links"})
    elif total_internal == 1:
        checks.append({"name": "Has internal links", "status": "warning", "detail": "Only 1 internal link found — page may be isolated"})
    else:
        checks.append({"name": "Has internal links", "status": "fail", "detail": "No internal links found — page is an orphan"})

    # 2 & 3. Check for broken internal links (sample up to 10)
    broken_404 = []
    broken_other = []
    if session and internal_links:
        def check_link(item):
            link_url, _ = item
            try:
                r = session.head(link_url, timeout=5, allow_redirects=True)
                return link_url, r.status_code
            except Exception:
                return link_url, None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(check_link, lnk): lnk for lnk in internal_links[:10]}
            for future in as_completed(futures):
                lnk_url, status = future.result()
                if status == 404:
                    broken_404.append(lnk_url[:80])
                elif status and status >= 400:
                    broken_other.append(f"{lnk_url[:60]} ({status})")

    if broken_404:
        checks.append({"name": "No broken internal links (404)", "status": "fail", "detail": f"404 links: {broken_404[:3]}"})
    else:
        checks.append({"name": "No broken internal links (404)", "status": "pass", "detail": "No 404 internal links found in sample"})

    if broken_other:
        checks.append({"name": "No broken internal links (other 4xx/5xx)", "status": "warning", "detail": f"Error links: {broken_other[:3]}"})
    else:
        checks.append({"name": "No broken internal links (other 4xx/5xx)", "status": "pass", "detail": "No other error codes in internal link sample"})

    # 4. No generic anchor text
    generic_found = [(href[:60], a.get_text(strip=True)) for href, a in internal_links
                     if a.get_text(strip=True).lower() in GENERIC_ANCHORS]
    if not generic_found:
        checks.append({"name": "No generic anchor text", "status": "pass", "detail": "All internal links use descriptive anchor text"})
    else:
        checks.append({"name": "No generic anchor text", "status": "warning",
                        "detail": f"{len(generic_found)} generic anchor(s): {[g[1] for g in generic_found[:3]]}"})

    # 5. No empty anchor text
    empty_anchors = [href[:60] for href, a in internal_links if not a.get_text(strip=True) and not a.find("img")]
    if not empty_anchors:
        checks.append({"name": "No empty anchor text", "status": "pass", "detail": "All internal links have descriptive text or images"})
    else:
        checks.append({"name": "No empty anchor text", "status": "warning", "detail": f"{len(empty_anchors)} empty anchor(s) found"})

    # 6. No nofollow on internal links
    nofollow_internal = [(href[:60], a.get_text(strip=True)[:40]) for href, a in internal_links
                         if "nofollow" in (a.get("rel") or [])]
    if not nofollow_internal:
        checks.append({"name": "No nofollow on internal links", "status": "pass", "detail": "No internal links marked nofollow"})
    else:
        checks.append({"name": "No nofollow on internal links", "status": "warning",
                        "detail": f"{len(nofollow_internal)} internal nofollow link(s) found (reduces PageRank flow)"})

    # 7. Reasonable internal link count
    if 2 <= total_internal <= 100:
        checks.append({"name": "Reasonable internal link count (2–100)", "status": "pass", "detail": f"Internal link count: {total_internal}"})
    elif total_internal > 100:
        checks.append({"name": "Reasonable internal link count (2–100)", "status": "warning", "detail": f"High internal link count: {total_internal} (PageRank dilution risk)"})
    else:
        checks.append({"name": "Reasonable internal link count (2–100)", "status": "warning", "detail": f"Very few internal links: {total_internal}"})

    # 8. Links to important pages (heuristic)
    all_hrefs = [href for href, _ in internal_links]
    has_home = any(urlparse(h).path in ["/", ""] for h in all_hrefs)
    important_patterns = ["/about", "/contact", "/services", "/products", "/blog"]
    linked_important = [p for p in important_patterns if any(p in h for h in all_hrefs)]
    if has_home or linked_important:
        checks.append({"name": "Links to important pages", "status": "pass", "detail": f"Links to: home={has_home}, others={linked_important[:3]}"})
    else:
        checks.append({"name": "Links to important pages", "status": "warning", "detail": "No links to home, about, contact, or services pages detected"})

    # 9. No self-referential links (linking to own URL)
    self_ref = [href for href, _ in internal_links if href.rstrip("/") == url.rstrip("/")]
    if not self_ref:
        checks.append({"name": "No self-referential links", "status": "pass", "detail": "Page does not link to itself"})
    else:
        checks.append({"name": "No self-referential links", "status": "warning", "detail": f"Page links to itself {len(self_ref)} time(s)"})

    # 10. Consistent URL protocol in internal links
    mixed = [href for href, _ in internal_links if href.startswith("http://") and url.startswith("https://")]
    if not mixed:
        checks.append({"name": "Consistent URL protocol", "status": "pass", "detail": "All internal links use consistent protocol"})
    else:
        checks.append({"name": "Consistent URL protocol", "status": "warning", "detail": f"{len(mixed)} internal HTTP link(s) on HTTPS page"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Internal links: {total_internal}"

    return {"checks": checks, "summary": summary}
