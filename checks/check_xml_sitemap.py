"""Module 11: XML Sitemap"""
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone


def check_xml_sitemap(url: str, soup, response, session=None,
                      sitemap_urls: list = None, robots_txt_content: str = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    base_domain = parsed.netloc

    sitemap_response = None
    sitemap_content = ""

    # 1. Sitemap exists at /sitemap.xml
    if session:
        try:
            sitemap_response = session.get(f"{base_url}/sitemap.xml", timeout=10)
            if sitemap_response.status_code == 200:
                sitemap_content = sitemap_response.text
                checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "pass",
                                "detail": f"Sitemap found: {base_url}/sitemap.xml"})
            else:
                # Try /sitemap_index.xml
                alt = session.get(f"{base_url}/sitemap_index.xml", timeout=10)
                if alt.status_code == 200:
                    sitemap_content = alt.text
                    checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "pass",
                                    "detail": f"Sitemap found at /sitemap_index.xml"})
                else:
                    checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "fail",
                                    "detail": f"Sitemap not found (status {sitemap_response.status_code})"})
        except Exception as e:
            checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "fail",
                            "detail": f"Error fetching sitemap: {str(e)[:80]}"})
    else:
        checks.append({"name": "Sitemap exists at /sitemap.xml", "status": "warning",
                        "detail": "No session available to check sitemap"})

    # 2. Sitemap referenced in robots.txt
    robots_content = robots_txt_content or ""
    if not robots_content and session:
        try:
            r = session.get(f"{base_url}/robots.txt", timeout=10)
            robots_content = r.text if r.status_code == 200 else ""
        except Exception:
            pass
    if "sitemap:" in robots_content.lower():
        checks.append({"name": "Sitemap referenced in robots.txt", "status": "pass",
                        "detail": "Sitemap directive found in robots.txt"})
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
        import re
        loc_urls = re.findall(r'<loc>(.*?)</loc>', sitemap_content)
        wrong_domain = [u for u in loc_urls if base_domain not in u]
        if not wrong_domain:
            checks.append({"name": "Sitemap URLs use correct domain", "status": "pass",
                            "detail": f"All {len(loc_urls)} URLs use {base_domain}"})
        else:
            checks.append({"name": "Sitemap URLs use correct domain", "status": "warning",
                            "detail": f"{len(wrong_domain)} URL(s) use different domain: {wrong_domain[:2]}"})
        # Populate sitemap_urls for other modules
        if sitemap_urls is not None:
            sitemap_urls.extend(loc_urls[:100])
    else:
        checks.append({"name": "Sitemap URLs use correct domain", "status": "warning", "detail": "No sitemap to check"})

    # 6. Sitemap has <lastmod> dates
    if sitemap_content:
        import re
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
        import re
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
        import re
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
        import re
        sub_locs = re.findall(r'<loc>(.*?)</loc>', sitemap_content)
        unreachable = []
        if session:
            for sub_url in sub_locs[:5]:
                try:
                    r = session.head(sub_url.strip(), timeout=8)
                    if r.status_code >= 400:
                        unreachable.append(sub_url[:60])
                except Exception:
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
