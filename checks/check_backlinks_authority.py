"""Module 23: Backlinks & Authority"""
import re
from urllib.parse import urlparse, urljoin


SPAM_ANCHORS = re.compile(
    r'\b(buy cheap|casino|poker|viagra|cialis|payday loan|free money|'
    r'weight loss|make money fast|click here to win|free iphone)\b',
    re.IGNORECASE
)


def _is_external(href: str, base_domain: str) -> bool:
    parsed = urlparse(href)
    return bool(parsed.netloc) and parsed.netloc.replace("www.", "") != base_domain.replace("www.", "")


def check_backlinks_authority(url: str, soup, response, **kwargs) -> dict:
    checks = []
    base_domain = urlparse(url).netloc.replace("www.", "")

    all_links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full_href = urljoin(url, href)
        rel = " ".join(a.get("rel") or [])
        text = a.get_text(strip=True)
        is_ext = _is_external(full_href, base_domain)
        all_links.append({
            "href": full_href,
            "rel": rel,
            "text": text,
            "is_external": is_ext,
            "is_nofollow": "nofollow" in rel,
            "is_sponsored": "sponsored" in rel,
            "is_ugc": "ugc" in rel,
        })

    total_links = len(all_links)
    external_links = [l for l in all_links if l["is_external"]]
    internal_links = [l for l in all_links if not l["is_external"]]
    total_external = len(external_links)

    # 1. Outbound dofollow link count
    dofollow_ext = [l for l in external_links if not l["is_nofollow"] and not l["is_sponsored"]]
    checks.append({"name": "Outbound dofollow links count", "status": "pass",
                    "detail": (f"{len(dofollow_ext)} dofollow external link(s) on {url}. "
                               f"Targets: {[l['href'][:60] for l in dofollow_ext[:3]]}")})

    # 2. Outbound nofollow link count
    nofollow_ext = [l for l in external_links if l["is_nofollow"]]
    checks.append({"name": "Outbound nofollow links count", "status": "pass",
                    "detail": (f"{len(nofollow_ext)} nofollow external link(s) on {url}. "
                               f"Targets: {[l['href'][:60] for l in nofollow_ext[:3]]}")})

    # 3. No nofollow on internal links
    nofollow_internal = [l for l in internal_links if l["is_nofollow"]]
    if not nofollow_internal:
        checks.append({"name": "No nofollow on internal links", "status": "pass",
                        "detail": f"No internal links marked nofollow on {url}"})
    else:
        details = [f"\"{l['text'][:40]}\" → {l['href'][:60]}" for l in nofollow_internal[:3]]
        checks.append({"name": "No nofollow on internal links", "status": "warning",
                        "detail": f"{len(nofollow_internal)} internal nofollow link(s) on {url}: {details}"})

    # 4. Sponsored links tagged
    sponsored_links = [l for l in external_links if l["is_sponsored"]]
    if sponsored_links:
        details = [f"\"{l['text'][:40]}\" → {l['href'][:60]}" for l in sponsored_links[:3]]
        checks.append({"name": "Sponsored links properly tagged", "status": "pass",
                        "detail": f"{len(sponsored_links)} rel=sponsored link(s) on {url}: {details}"})
    else:
        checks.append({"name": "Sponsored links properly tagged", "status": "pass",
                        "detail": f"No sponsored links found on {url}"})

    # 5. UGC links tagged
    ugc_links = [l for l in all_links if l["is_ugc"]]
    if ugc_links:
        details = [f"\"{l['text'][:40]}\" → {l['href'][:60]}" for l in ugc_links[:3]]
        checks.append({"name": "UGC links properly tagged", "status": "pass",
                        "detail": f"{len(ugc_links)} rel=ugc link(s) on {url}: {details}"})
    else:
        checks.append({"name": "UGC links properly tagged", "status": "pass",
                        "detail": f"No UGC-tagged links on {url}"})

    # 6. No spam anchor text patterns
    spam_found = []
    for l in all_links:
        if SPAM_ANCHORS.search(l["text"]):
            spam_found.append(f"\"{l['text'][:60]}\" → {l['href'][:60]} on {url}")
    if not spam_found:
        checks.append({"name": "No spam anchor text patterns", "status": "pass",
                        "detail": "No spam-like anchor text found in outbound links"})
    else:
        checks.append({"name": "No spam anchor text patterns", "status": "fail",
                        "detail": f"Spam-like anchor text: {spam_found[:3]}"})

    # 7. External link ratio
    if total_links > 0:
        ext_ratio = total_external / total_links
        if ext_ratio <= 0.5:
            checks.append({"name": "External link ratio (≤50%)", "status": "pass",
                            "detail": f"External: {total_external}/{total_links} ({ext_ratio*100:.0f}%) on {url}"})
        elif ext_ratio <= 0.8:
            checks.append({"name": "External link ratio (≤50%)", "status": "warning",
                            "detail": f"High external ratio: {total_external}/{total_links} ({ext_ratio*100:.0f}%) on {url}"})
        else:
            checks.append({"name": "External link ratio (≤50%)", "status": "fail",
                            "detail": f"Very high external ratio: {total_external}/{total_links} ({ext_ratio*100:.0f}%) on {url}"})
    else:
        checks.append({"name": "External link ratio (≤50%)", "status": "warning",
                        "detail": f"No links found on {url}"})

    # 8. No self-referencing nofollow (internal links without nofollow)
    self_ref_nofollow = [l for l in internal_links
                          if l["href"].rstrip("/") == url.rstrip("/") and l["is_nofollow"]]
    if not self_ref_nofollow:
        checks.append({"name": "No self-referencing nofollow", "status": "pass",
                        "detail": "No self-referencing nofollow links found"})
    else:
        checks.append({"name": "No self-referencing nofollow", "status": "warning",
                        "detail": f"Self-ref nofollow links: {[l['href'][:60] for l in self_ref_nofollow[:3]]}"})

    # 9. Link attribute consistency
    has_nofollow = len(nofollow_ext) > 0
    has_dofollow = len(dofollow_ext) > 0
    if has_nofollow and has_dofollow:
        checks.append({"name": "Link attribute consistency", "status": "warning",
                        "detail": (f"Mixed: {len(dofollow_ext)} dofollow + {len(nofollow_ext)} nofollow "
                                   f"external links on {url} — review consistency policy")})
    else:
        checks.append({"name": "Link attribute consistency", "status": "pass",
                        "detail": f"Consistent link policy: {'nofollow' if has_nofollow else 'dofollow'}"})

    # 10. Authority signals (manual verification notice)
    checks.append({"name": "Domain authority (manual verification)", "status": "warning",
                    "detail": (f"Automated DA/DR scores require Ahrefs or Moz API. "
                               f"This page has {len(dofollow_ext)} outbound dofollow links. "
                               f"Manual check recommended at: https://ahrefs.com/backlink-checker")})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = (f"{passed} passed, {failed} failed, {warned} warnings. "
               f"Total links: {total_links} ({total_external} external, {len(internal_links)} internal)")

    return {"checks": checks, "summary": summary}
