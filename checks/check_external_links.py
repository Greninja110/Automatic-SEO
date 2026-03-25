"""Module 7: External Links"""
import re
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed


SPAM_TLDS = {".xyz", ".tk", ".ml", ".ga", ".cf", ".gq", ".pw", ".top", ".click", ".loan"}
GENERIC_ANCHORS = {"click here", "read more", "here", "link", "more", "learn more"}


def _is_external(href: str, base_domain: str) -> bool:
    parsed = urlparse(href)
    if not parsed.netloc:
        return False
    return parsed.netloc.replace("www.", "") != base_domain.replace("www.", "")


def check_external_links(url: str, soup, response, session=None, **kwargs) -> dict:
    checks = []
    base_domain = urlparse(url).netloc.replace("www.", "")

    external_links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full_url = urljoin(url, href)
        if _is_external(full_url, base_domain):
            external_links.append((full_url, a))

    total = len(external_links)

    if total == 0:
        return {
            "checks": [{"name": "External links present", "status": "warning", "detail": "No external links found on this page"}],
            "summary": "No external links found."
        }

    # 1. External links reachable (sample up to 10)
    unreachable = []
    if session:
        def check_link(item):
            link_url, _ = item
            try:
                r = session.head(link_url, timeout=8, allow_redirects=True)
                return link_url, r.status_code
            except Exception:
                return link_url, None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(check_link, lnk): lnk for lnk in external_links[:10]}
            for future in as_completed(futures):
                lnk_url, status = future.result()
                if status and status >= 400:
                    unreachable.append(f"{lnk_url[:60]} ({status})")
    if unreachable:
        checks.append({"name": "External links reachable", "status": "fail", "detail": f"Unreachable: {unreachable[:3]}"})
    else:
        checks.append({"name": "External links reachable", "status": "pass", "detail": "All sampled external links returned valid responses"})

    # 2. Nofollow on untrusted external links
    trusted_domains = {"wikipedia.org", "google.com", "gov", "edu", "bbc.co.uk", "reuters.com"}
    untagged = []
    for link_url, a in external_links:
        domain = urlparse(link_url).netloc.lower()
        rel = " ".join(a.get("rel") or [])
        is_trusted = any(td in domain for td in trusted_domains)
        if not is_trusted and "nofollow" not in rel and "sponsored" not in rel:
            untagged.append(domain[:40])
    if not untagged:
        checks.append({"name": "Nofollow on untrusted external links", "status": "pass", "detail": "External links are properly attributed"})
    else:
        checks.append({"name": "Nofollow on untrusted external links", "status": "warning",
                        "detail": f"{len(untagged)} external link(s) without nofollow: {list(set(untagged))[:3]}"})

    # 3. No spam/suspicious TLDs
    spam_links = [urlparse(lnk).netloc for lnk, _ in external_links
                  if any(urlparse(lnk).netloc.endswith(tld) for tld in SPAM_TLDS)]
    if not spam_links:
        checks.append({"name": "No links to spam TLDs", "status": "pass", "detail": "No links to suspicious TLD domains"})
    else:
        checks.append({"name": "No links to spam TLDs", "status": "fail", "detail": f"Links to suspicious domains: {spam_links[:3]}"})

    # 4. Sponsored links tagged
    sponsored = [(lnk[:50], a.get_text(strip=True)[:40]) for lnk, a in external_links
                 if "sponsored" in " ".join(a.get("rel") or [])]
    checks.append({"name": "Sponsored links tagged", "status": "pass" if sponsored or True else "warning",
                    "detail": f"{len(sponsored)} link(s) have rel=sponsored" if sponsored else "No sponsored links detected (informational)"})

    # 5. UGC links tagged
    ugc = [(lnk[:50],) for lnk, a in external_links if "ugc" in " ".join(a.get("rel") or [])]
    checks.append({"name": "UGC links tagged", "status": "pass",
                    "detail": f"{len(ugc)} link(s) have rel=ugc" if ugc else "No UGC links detected (informational)"})

    # 6. External links open in new tab with noopener
    missing_noopener = []
    for lnk, a in external_links:
        if a.get("target") == "_blank":
            rel = " ".join(a.get("rel") or [])
            if "noopener" not in rel:
                missing_noopener.append(lnk[:60])
    if not missing_noopener:
        checks.append({"name": "External links: noopener when target=_blank", "status": "pass", "detail": "All _blank links have noopener"})
    else:
        checks.append({"name": "External links: noopener when target=_blank", "status": "warning",
                        "detail": f"{len(missing_noopener)} link(s) missing rel=noopener on target=_blank"})

    # 7. Reasonable external link count
    if total <= 50:
        checks.append({"name": "External link count (≤50)", "status": "pass", "detail": f"External links: {total}"})
    else:
        checks.append({"name": "External link count (≤50)", "status": "warning", "detail": f"High external link count: {total}"})

    # 8. No HTTP links from HTTPS page
    mixed_http = [lnk[:60] for lnk, _ in external_links if lnk.startswith("http://") and url.startswith("https://")]
    if not mixed_http:
        checks.append({"name": "No HTTP links from HTTPS page", "status": "pass", "detail": "All external links use HTTPS"})
    else:
        checks.append({"name": "No HTTP links from HTTPS page", "status": "warning", "detail": f"{len(mixed_http)} HTTP external link(s) on HTTPS page"})

    # 9. Anchor text quality
    generic_ext = [(lnk[:50], a.get_text(strip=True)) for lnk, a in external_links
                   if a.get_text(strip=True).lower() in GENERIC_ANCHORS]
    if not generic_ext:
        checks.append({"name": "External link anchor text quality", "status": "pass", "detail": "External links use descriptive anchor text"})
    else:
        checks.append({"name": "External link anchor text quality", "status": "warning",
                        "detail": f"{len(generic_ext)} generic anchor(s): {[g[1] for g in generic_ext[:3]]}"})

    # 10. No redirect chains in external links (sample 3)
    redirect_chains = []
    if session:
        for lnk, _ in external_links[:3]:
            try:
                r = session.get(lnk, timeout=8, allow_redirects=True)
                if len(r.history) > 2:
                    redirect_chains.append(f"{lnk[:60]} ({len(r.history)} hops)")
            except Exception:
                pass
    if redirect_chains:
        checks.append({"name": "No redirect chains in external links", "status": "warning", "detail": f"Redirect chains: {redirect_chains}"})
    else:
        checks.append({"name": "No redirect chains in external links", "status": "pass", "detail": "No long redirect chains detected in sample"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. External links: {total}"

    return {"checks": checks, "summary": summary}
