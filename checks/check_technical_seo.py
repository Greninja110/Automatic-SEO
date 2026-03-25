"""Module 20: Technical SEO"""
import re
from urllib.parse import urlparse, urljoin


def check_technical_seo(url: str, soup, response, session=None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)

    # 1. Canonical tag present
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        checks.append({"name": "Canonical tag present", "status": "pass",
                        "detail": f"Canonical: {canonical['href'][:100]} — on page: {url}"})
    else:
        checks.append({"name": "Canonical tag present", "status": "fail",
                        "detail": f"No canonical tag on: {url}"})

    # 2. Canonical is self-referencing
    if canonical and canonical.get("href"):
        canon = canonical["href"].rstrip("/")
        curr = url.rstrip("/")
        if canon == curr:
            checks.append({"name": "Canonical self-referencing", "status": "pass",
                            "detail": f"Canonical correctly points to self: {canon[:80]}"})
        else:
            checks.append({"name": "Canonical self-referencing", "status": "warning",
                            "detail": f"Canonical points elsewhere — page: {url[:60]} → canonical: {canon[:60]}"})
    else:
        checks.append({"name": "Canonical self-referencing", "status": "warning",
                        "detail": "No canonical to check"})

    # 3. hreflang tags present
    hreflang_tags = soup.find_all("link", rel="alternate", hreflang=True)
    if hreflang_tags:
        langs = [t.get("hreflang") for t in hreflang_tags]
        checks.append({"name": "hreflang tags present", "status": "pass",
                        "detail": f"hreflang languages: {langs[:5]} — page: {url}"})
    else:
        checks.append({"name": "hreflang tags present", "status": "warning",
                        "detail": "No hreflang tags — add if site has multilingual versions"})

    # 4. hreflang has x-default
    if hreflang_tags:
        has_x_default = any(t.get("hreflang") == "x-default" for t in hreflang_tags)
        if has_x_default:
            checks.append({"name": "hreflang has x-default", "status": "pass",
                            "detail": "x-default hreflang found"})
        else:
            checks.append({"name": "hreflang has x-default", "status": "warning",
                            "detail": "hreflang present but missing x-default variant"})
    else:
        checks.append({"name": "hreflang has x-default", "status": "pass",
                        "detail": "No hreflang — x-default check not applicable"})

    # 5. AMP page linked
    amp_link = soup.find("link", rel="amphtml")
    if amp_link and amp_link.get("href"):
        amp_url = urljoin(url, amp_link["href"])
        amp_ok = False
        if session:
            try:
                r = session.head(amp_url, timeout=8)
                amp_ok = r.status_code < 400
            except Exception:
                pass
        status = "pass" if amp_ok else "warning"
        detail = f"AMP URL: {amp_url}" + (" (reachable)" if amp_ok else " (could not verify)")
        checks.append({"name": "AMP page linked and reachable", "status": status, "detail": detail})
    else:
        checks.append({"name": "AMP page linked and reachable", "status": "pass",
                        "detail": "No AMP version linked (not required)"})

    # 6. X-Robots-Tag header
    x_robots = response.headers.get("X-Robots-Tag", "")
    if x_robots:
        if "noindex" in x_robots.lower():
            checks.append({"name": "X-Robots-Tag not noindex", "status": "fail",
                            "detail": f"X-Robots-Tag: {x_robots} on {url} — page will be deindexed!"})
        else:
            checks.append({"name": "X-Robots-Tag not noindex", "status": "pass",
                            "detail": f"X-Robots-Tag: {x_robots}"})
    else:
        checks.append({"name": "X-Robots-Tag not noindex", "status": "pass",
                        "detail": "No X-Robots-Tag header (defaults to indexable)"})

    # 7. HTML lang attribute
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""
    if lang:
        # Basic ISO 639 validation (2-3 letter code, optional region)
        if re.match(r'^[a-zA-Z]{2,3}(-[a-zA-Z]{2,4})?$', lang):
            checks.append({"name": "HTML lang attribute valid", "status": "pass",
                            "detail": f"lang=\"{lang}\" on {url}"})
        else:
            checks.append({"name": "HTML lang attribute valid", "status": "warning",
                            "detail": f"lang=\"{lang}\" may be invalid format on {url}"})
    else:
        checks.append({"name": "HTML lang attribute valid", "status": "fail",
                        "detail": f"No lang attribute on <html> tag — {url}"})

    # 8. UTF-8 charset declared
    charset_meta = (soup.find("meta", charset=True) or
                    soup.find("meta", attrs={"http-equiv": "Content-Type"}))
    if charset_meta:
        charset_val = charset_meta.get("charset", "") or charset_meta.get("content", "")
        if "utf-8" in charset_val.lower():
            checks.append({"name": "UTF-8 charset declared", "status": "pass",
                            "detail": f"Charset: {charset_val}"})
        else:
            checks.append({"name": "UTF-8 charset declared", "status": "warning",
                            "detail": f"Non-UTF-8 charset: {charset_val} on {url}"})
    else:
        # Check Content-Type header
        ct = response.headers.get("Content-Type", "")
        if "utf-8" in ct.lower():
            checks.append({"name": "UTF-8 charset declared", "status": "pass",
                            "detail": f"Charset from header: {ct}"})
        else:
            checks.append({"name": "UTF-8 charset declared", "status": "warning",
                            "detail": f"No charset meta tag found on {url}"})

    # 9. Content-Type is text/html
    ct_header = response.headers.get("Content-Type", "")
    if "text/html" in ct_header:
        checks.append({"name": "Content-Type is text/html", "status": "pass",
                        "detail": f"Content-Type: {ct_header[:80]}"})
    else:
        checks.append({"name": "Content-Type is text/html", "status": "warning",
                        "detail": f"Unexpected Content-Type: {ct_header[:80]}"})

    # 10. Breadcrumbs present
    breadcrumb_nav = soup.find("nav", attrs={"aria-label": re.compile("breadcrumb", re.I)})
    breadcrumb_ol = soup.find("ol", class_=re.compile("breadcrumb", re.I))
    breadcrumb_schema = any("BreadcrumbList" in str(s) for s in soup.find_all("script", type="application/ld+json"))
    if breadcrumb_nav or breadcrumb_ol or breadcrumb_schema:
        checks.append({"name": "Breadcrumbs present", "status": "pass",
                        "detail": f"Breadcrumbs found on {url}"})
    else:
        depth = len([s for s in parsed.path.strip("/").split("/") if s])
        if depth > 1:
            checks.append({"name": "Breadcrumbs present", "status": "warning",
                            "detail": f"No breadcrumbs on deep URL (depth {depth}): {url}"})
        else:
            checks.append({"name": "Breadcrumbs present", "status": "pass",
                            "detail": "Top-level URL — breadcrumbs not required"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Canonical: {(canonical['href'][:60] if canonical and canonical.get('href') else 'none')}"

    return {"checks": checks, "summary": summary}
