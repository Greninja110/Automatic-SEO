"""Module 11: XML Sitemap"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


def _robots_sitemaps(robots_text: str) -> list:
    return [m.strip() for m in re.findall(r"^\s*sitemap\s*:\s*(\S+)", robots_text or "", re.I | re.M)]


def _same_site(a: str, b: str) -> bool:
    return a.lower().removeprefix("www.") == b.lower().removeprefix("www.")


def check_xml_sitemap(url: str, soup, response, session=None,
                      sitemap_urls: list = None, robots_txt_content: str = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    base_domain = parsed.netloc

    sitemap_content = ""

    # robots.txt first: its Sitemap: directive says where the sitemap really lives
    robots_content = robots_txt_content or ""
    if not robots_content and session:
        try:
            r = session.get(f"{base_url}/robots.txt", timeout=10)
            robots_content = r.text if r.status_code == 200 else ""
        except Exception:
            pass
    declared = _robots_sitemaps(robots_content)

    # 1. Sitemap exists (robots.txt location, then /sitemap.xml, then /sitemap_index.xml)
    sitemap_location = None
    if session:
        candidates = list(dict.fromkeys(declared[:3] + [f"{base_url}/sitemap.xml", f"{base_url}/sitemap_index.xml"]))
        last_status = None
        for cand in candidates:
            try:
                resp = session.get(cand, timeout=10)
                last_status = resp.status_code
                if resp.status_code == 200 and "<" in resp.text[:500]:
                    sitemap_content, sitemap_location = resp.text, cand
                    break
            except Exception as e:
                last_status = str(e)[:60]
        if sitemap_location:
            checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "pass",
                            "detail": f"Sitemap found: {sitemap_location}"})
        else:
            checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "fail",
                            "detail": f"No sitemap found (tried {len(candidates)} location(s), last result: {last_status})"})
    else:
        checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "warning",
                        "detail": "No session available to check sitemap"})

    # 2. Sitemap referenced in robots.txt
    if declared:
        checks.append({"name": "Sitemap referenced in robots.txt", "status": "pass",
                        "detail": f"Sitemap directive found in robots.txt: {declared[0][:80]}"})
    else:
        checks.append({"name": "Sitemap referenced in robots.txt", "status": "warning",
                        "detail": "No Sitemap: directive in robots.txt"})

    # 3. Sitemap is valid XML
    if sitemap_content:
        try:
            from lxml import etree
            etree.fromstring(sitemap_content.encode("utf-8", errors="replace"))
            checks.append({"name": "Sitemap is valid XML", "status": "pass", "detail": "Sitemap parsed as valid XML"})
        except Exception as e:
            checks.append({"name": "Sitemap is valid XML", "status": "fail", "detail": f"XML parse error: {str(e)[:80]}"})
    else:
        checks.append({"name": "Sitemap is valid XML", "status": "warning", "detail": "No sitemap content to validate"})

    # 4. Sitemap has <urlset> or <sitemapindex>
    if sitemap_content:
        has_urlset = "<urlset" in sitemap_content
        has_index = "<sitemapindex" in sitemap_content
        if has_urlset or has_index:
            type_str = "urlset" if has_urlset else "sitemapindex"
            checks.append({"name": "Sitemap has correct root element", "status": "pass",
                            "detail": f"Root element: <{type_str}>"})
        else:
            checks.append({"name": "Sitemap has correct root element", "status": "fail",
                            "detail": "Neither <urlset> nor <sitemapindex> found"})
    else:
        checks.append({"name": "Sitemap has correct root element", "status": "warning", "detail": "No sitemap to check"})

    # 5. Sitemap URLs use correct domain
    if sitemap_content:
        loc_urls = [u.strip() for u in re.findall(r'<loc>(.*?)</loc>', sitemap_content, re.DOTALL)]
        wrong_domain = [u for u in loc_urls if not _same_site(urlparse(u).netloc, base_domain)]
        if not wrong_domain:
            checks.append({"name": "Sitemap URLs use correct domain", "status": "pass",
                            "detail": f"All {len(loc_urls)} URLs use {base_domain}"})
        else:
            checks.append({"name": "Sitemap URLs use correct domain", "status": "warning",
                            "detail": f"{len(wrong_domain)} URL(s) use different domain: {wrong_domain[:2]}"})
        # Share page URLs with other modules (crawl_errors). For a sitemap index,
        # read the first child sitemap so they get pages, not sitemap files.
        if sitemap_urls is not None:
            page_urls = loc_urls
            if "<sitemapindex" in sitemap_content and loc_urls and session:
                try:
                    child = session.get(loc_urls[0], timeout=10)
                    if child.status_code == 200:
                        page_urls = [u.strip() for u in re.findall(r'<loc>(.*?)</loc>', child.text, re.DOTALL)]
                except Exception:
                    page_urls = []
            sitemap_urls.extend(page_urls[:100])
    else:
        checks.append({"name": "Sitemap URLs use correct domain", "status": "warning", "detail": "No sitemap to check"})

    # 6. Sitemap has <lastmod> dates
    if sitemap_content:
        all_urls_in_sitemap = re.findall(r'<url>(.*?)</url>', sitemap_content, re.DOTALL)
        lastmod_count = sum(1 for u in all_urls_in_sitemap if "<lastmod>" in u)
        if all_urls_in_sitemap:
            ratio = lastmod_count / len(all_urls_in_sitemap)
            if ratio >= 0.5:
                checks.append({"name": "Sitemap has <lastmod> dates", "status": "pass",
                                "detail": f"{lastmod_count}/{len(all_urls_in_sitemap)} URLs have lastmod"})
            else:
                checks.append({"name": "Sitemap has <lastmod> dates", "status": "warning",
                                "detail": f"Only {lastmod_count}/{len(all_urls_in_sitemap)} URLs have lastmod"})
        else:
            checks.append({"name": "Sitemap has <lastmod> dates", "status": "warning",
                            "detail": "No <url> entries found in sitemap"})
    else:
        checks.append({"name": "Sitemap has <lastmod> dates", "status": "warning", "detail": "No sitemap to check"})

    # 7. <lastmod> dates are recent (within 365 days)
    if sitemap_content:
        lastmods = re.findall(r'<lastmod>(.*?)</lastmod>', sitemap_content)
        stale = []
        for lm in lastmods[:20]:
            try:
                lm_clean = lm.strip()[:10]
                dt = datetime.strptime(lm_clean, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - dt).days
                if days_ago > 365:
                    stale.append(f"{lm_clean} ({days_ago}d ago)")
            except Exception:
                pass
        if not stale:
            checks.append({"name": "Sitemap lastmod dates are recent", "status": "pass",
                            "detail": "All checked lastmod dates are within 365 days"})
        else:
            checks.append({"name": "Sitemap lastmod dates are recent", "status": "warning",
                            "detail": f"Stale entries: {stale[:3]}"})
    else:
        checks.append({"name": "Sitemap lastmod dates are recent", "status": "warning", "detail": "No sitemap to check"})

    # 8. No noindex pages in sitemap (advisory)
    checks.append({"name": "No noindex pages in sitemap", "status": "warning",
                    "detail": "Manual verification recommended: cross-check sitemap URLs with meta robots"})
    
    # 9. Sitemap size within limits
    if sitemap_content:
        url_count = len(re.findall(r'<loc>', sitemap_content))
        size_mb = len(sitemap_content.encode()) / (1024 * 1024)
        if url_count <= 50000 and size_mb <= 50:
            checks.append({"name": "Sitemap within Google limits (<50k URLs, <50MB)", "status": "pass",
                            "detail": f"URLs: {url_count}, size: {size_mb:.2f}MB"})
        else:
            checks.append({"name": "Sitemap within Google limits (<50k URLs, <50MB)", "status": "fail",
                            "detail": f"Exceeds limits — URLs: {url_count}, size: {size_mb:.2f}MB"})
    else:
        checks.append({"name": "Sitemap within Google limits (<50k URLs, <50MB)", "status": "warning",
                        "detail": "No sitemap to check"})

    # 10. Sitemapindex sub-sitemaps reachable
    if sitemap_content and "<sitemapindex" in sitemap_content:
        sub_locs = re.findall(r'<loc>(.*?)</loc>', sitemap_content)
        unreachable = []
        if session:
            from checks._http import head_status, parallel_map
            for sub_url, st in parallel_map(lambda u: (u, head_status(session, u.strip())[0]), sub_locs[:5]):
                if not st or st >= 400:
                    unreachable.append(sub_url[:60])
        if unreachable:
            checks.append({"name": "Sitemapindex sub-sitemaps reachable", "status": "fail",
                            "detail": f"Unreachable sub-sitemaps: {unreachable}"})
        else:
            checks.append({"name": "Sitemapindex sub-sitemaps reachable", "status": "pass",
                            "detail": f"Checked {min(5, len(sub_locs))} sub-sitemaps — all reachable"})
    else:
        checks.append({"name": "Sitemapindex sub-sitemaps reachable", "status": "pass",
                        "detail": "Not a sitemapindex — check not applicable"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
