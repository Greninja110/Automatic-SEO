"""Module 12: Robots.txt"""
import re
from urllib.parse import urlparse


def check_robots_txt(url: str, soup, response, session=None,
                     robots_txt_content: str = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    robots_text = robots_txt_content or ""
    robots_status = None

    robots_ctype = ""
    if not robots_text and session:
        try:
            r = session.get(f"{base_url}/robots.txt", timeout=10)
            robots_status = r.status_code
            robots_ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "html" not in robots_ctype.lower():
                robots_text = r.text
        except Exception as e:
            checks.append({"name": "robots.txt accessible", "status": "fail",
                            "detail": f"Error fetching robots.txt: {str(e)[:80]}"})
            return {"checks": checks, "summary": "robots.txt could not be fetched."}

    # 1. robots.txt exists
    if robots_text:
        checks.append({"name": "robots.txt exists", "status": "pass",
                        "detail": f"robots.txt found at {base_url}/robots.txt"})
    else:
        checks.append({"name": "robots.txt exists", "status": "fail",
                        "detail": "No robots.txt found — search engines cannot read crawl directives"})
        # Fill remaining checks as warnings
        for name in ["robots.txt is text/plain", "Not blocking all crawlers", "Not blocking CSS/JS",
                      "Allows Googlebot", "Sitemap directive present", "No syntax errors in robots.txt",
                      "Crawl-delay reasonable", "Root path not blocked", "Admin paths blocked"]:
            checks.append({"name": name, "status": "warning", "detail": "robots.txt missing — cannot verify"})
        return {"checks": checks, "summary": "robots.txt not found."}

    # 2. Content-Type is text/plain
    if robots_status:
        if "text/plain" in robots_ctype.lower():
            checks.append({"name": "robots.txt is text/plain", "status": "pass",
                            "detail": f"Content-Type: {robots_ctype}"})
        else:
            checks.append({"name": "robots.txt is text/plain", "status": "warning",
                            "detail": f"Unexpected Content-Type: {robots_ctype or 'none'}"})
    else:
        checks.append({"name": "robots.txt is text/plain", "status": "pass",
                        "detail": "robots.txt content retrieved (Content-Type assumed text/plain)"})

    # Parse rules into user-agent groups. Consecutive User-agent lines share
    # the rules that follow them (RFC 9309), e.g.
    #   User-agent: a
    #   User-agent: b
    #   Disallow: /x      ← applies to both a and b
    rules = {}  # {user_agent: [{"type": allow/disallow, "path": ...}]}
    group = []
    last_was_ua = False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (p.strip() for p in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if not last_was_ua:
                group = []
            ua = value.lower()
            group.append(ua)
            rules.setdefault(ua, [])
            last_was_ua = True
        elif field in ("allow", "disallow"):
            last_was_ua = False
            if not value and field == "disallow":
                continue  # empty Disallow = allow everything
            for ua in group:
                rules[ua].append({"type": field, "path": value})
        else:
            last_was_ua = False

    star_rules = rules.get("*", [])

    # 3. Not blocking all crawlers
    blocking_all = any(r["type"] == "disallow" and r["path"] == "/" for r in star_rules)
    if blocking_all:
        checks.append({"name": "Not blocking all crawlers", "status": "fail",
                        "detail": "Disallow: / for User-agent: * — entire site is blocked!"})
    else:
        checks.append({"name": "Not blocking all crawlers", "status": "pass",
                        "detail": "Site is not globally disallowed"})

    # 4. Not blocking CSS/JS
    asset_patterns = ["/static", "/assets", "/css", "/js", "/wp-content/themes", "/wp-includes"]
    blocked_assets = [r["path"] for r in star_rules
                      if r["type"] == "disallow" and any(r["path"].startswith(p) for p in asset_patterns)]
    if blocked_assets:
        checks.append({"name": "CSS/JS not blocked in robots.txt", "status": "fail",
                        "detail": f"Asset paths blocked: {blocked_assets[:3]}"})
    else:
        checks.append({"name": "CSS/JS not blocked in robots.txt", "status": "pass",
                        "detail": "No CSS/JS paths blocked"})

    # 5. Allows Googlebot
    googlebot_rules = rules.get("googlebot", [])
    googlebot_blocked = any(r["type"] == "disallow" and r["path"] == "/" for r in googlebot_rules)
    if googlebot_blocked:
        checks.append({"name": "Allows Googlebot", "status": "fail",
                        "detail": "Googlebot is explicitly disallowed from /"})
    else:
        checks.append({"name": "Allows Googlebot", "status": "pass",
                        "detail": "Googlebot is not blocked"})

    # 6. Sitemap directive present
    if re.search(r'^sitemap\s*:', robots_text, re.IGNORECASE | re.MULTILINE):
        sitemap_line = re.search(r'^sitemap\s*:(.+)', robots_text, re.IGNORECASE | re.MULTILINE)
        detail = sitemap_line.group(1).strip()[:80] if sitemap_line else "found"
        checks.append({"name": "Sitemap directive in robots.txt", "status": "pass",
                        "detail": f"Sitemap: {detail}"})
    else:
        checks.append({"name": "Sitemap directive in robots.txt", "status": "warning",
                        "detail": "No Sitemap: directive found in robots.txt"})

    # 7. No syntax errors
    valid_prefixes = ("user-agent:", "disallow:", "allow:", "sitemap:", "crawl-delay:", "#", "")
    raw_lines = [l.strip() for l in robots_text.splitlines()]
    invalid = [l for l in raw_lines if l and not any(l.lower().startswith(p) for p in valid_prefixes)]
    if not invalid:
        checks.append({"name": "No syntax errors in robots.txt", "status": "pass",
                        "detail": "robots.txt syntax appears valid"})
    else:
        checks.append({"name": "No syntax errors in robots.txt", "status": "warning",
                        "detail": f"Unrecognized lines: {invalid[:3]}"})

    # 8. Crawl-delay reasonable
    crawl_delay = re.search(r'^crawl-delay\s*:\s*(\d+)', robots_text, re.IGNORECASE | re.MULTILINE)
    if crawl_delay:
        delay = int(crawl_delay.group(1))
        if delay <= 10:
            checks.append({"name": "Crawl-delay reasonable (≤10s)", "status": "pass",
                            "detail": f"Crawl-delay: {delay}s"})
        else:
            checks.append({"name": "Crawl-delay reasonable (≤10s)", "status": "warning",
                            "detail": f"High Crawl-delay: {delay}s (may slow indexing)"})
    else:
        checks.append({"name": "Crawl-delay reasonable (≤10s)", "status": "pass",
                        "detail": "No Crawl-delay set (default behavior)"})

    # 9. Root path not blocked
    root_blocked = any(r["type"] == "disallow" and r["path"] == "/" for r in star_rules)
    if not root_blocked:
        checks.append({"name": "Root path not blocked", "status": "pass",
                        "detail": "Root / is not disallowed"})
    else:
        checks.append({"name": "Root path not blocked", "status": "fail",
                        "detail": "Root / is disallowed — entire site blocked"})

    # 10. Admin/sensitive paths blocked
    admin_paths = ["/admin", "/wp-admin", "/login", "/dashboard", "/cpanel"]
    all_disallowed = [r["path"] for rules_list in rules.values() for r in rules_list if r["type"] == "disallow"]
    blocked_admin = [p for p in admin_paths if any(d.startswith(p) for d in all_disallowed)]
    if blocked_admin:
        checks.append({"name": "Admin paths blocked in robots.txt", "status": "pass",
                        "detail": f"Admin paths blocked: {blocked_admin}"})
    else:
        checks.append({"name": "Admin paths blocked in robots.txt", "status": "warning",
                        "detail": "No admin path blocks found — consider blocking /admin, /wp-admin etc."})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
