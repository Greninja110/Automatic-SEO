"""Module 21: Content Accessibility"""
import re


def _hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        return None
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(r, g, b) -> float:
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(rgb1, rgb2) -> float:
    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_content_accessibility(url: str, soup, response, **kwargs) -> dict:
    checks = []

    # 1. ARIA landmark roles
    roles = [el.get("role") for el in soup.find_all(role=True)]
    key_roles = {"main", "navigation", "banner", "contentinfo", "search"}
    found_roles = key_roles & set(roles)
    # Also check semantic elements
    has_main = soup.find("main") or "main" in found_roles
    has_nav = soup.find("nav") or "navigation" in found_roles
    has_header = soup.find("header") or "banner" in found_roles
    if has_main and has_nav:
        checks.append({"name": "ARIA landmark roles present", "status": "pass",
                        "detail": f"Found landmarks: {list(found_roles)} + semantic HTML on {url}"})
    else:
        missing = []
        if not has_main:
            missing.append("main")
        if not has_nav:
            missing.append("navigation/nav")
        checks.append({"name": "ARIA landmark roles present", "status": "warning",
                        "detail": f"Missing landmark role(s): {missing} on {url}"})

    # 2. All images have alt
    imgs = soup.find_all("img")
    missing_alt = [img.get("src", "unknown")[:80] for img in imgs if img.get("alt") is None]
    if not missing_alt:
        checks.append({"name": "All images have alt attribute", "status": "pass",
                        "detail": f"All {len(imgs)} images have alt attributes on {url}"})
    else:
        checks.append({"name": "All images have alt attribute", "status": "fail",
                        "detail": f"{len(missing_alt)} image(s) missing alt on {url}: {missing_alt[:3]}"})

    # 3. Form inputs have labels
    inputs = soup.find_all("input", type=lambda t: t not in ["hidden", "submit", "button", "image", "reset"])
    unlabeled = []
    for inp in inputs:
        inp_id = inp.get("id")
        inp_name = inp.get("name", "")
        has_aria_label = bool(inp.get("aria-label") or inp.get("aria-labelledby"))
        has_label = bool(inp_id and soup.find("label", attrs={"for": inp_id}))
        is_wrapped = bool(inp.find_parent("label"))
        if not (has_aria_label or has_label or is_wrapped):
            unlabeled.append(f"<input name=\"{inp_name[:40]}\" type=\"{inp.get('type','text')}\">"
                              f" on {url}")
    if not unlabeled:
        checks.append({"name": "Form inputs have labels", "status": "pass",
                        "detail": f"All {len(inputs)} form input(s) have labels"})
    else:
        checks.append({"name": "Form inputs have labels", "status": "fail",
                        "detail": f"{len(unlabeled)} unlabeled input(s): {unlabeled[:3]}"})

    # 4. Skip navigation link
    all_links = soup.find_all("a", href=True)
    skip_link = None
    if all_links:
        first_link = all_links[0]
        href = first_link.get("href", "")
        text = first_link.get_text(strip=True).lower()
        if href.startswith("#") and ("skip" in text or "main" in text or "content" in text):
            skip_link = first_link
    if skip_link:
        checks.append({"name": "Skip navigation link present", "status": "pass",
                        "detail": f"Skip link: \"{skip_link.get_text(strip=True)}\" → {skip_link.get('href')} on {url}"})
    else:
        checks.append({"name": "Skip navigation link present", "status": "warning",
                        "detail": f"No skip navigation link found on {url} — important for keyboard users"})

    # 5. Semantic HTML elements
    semantic = {}
    for tag in ["header", "main", "footer", "nav", "article", "section"]:
        semantic[tag] = bool(soup.find(tag))
    present = [t for t, v in semantic.items() if v]
    if len(present) >= 4:
        checks.append({"name": "Semantic HTML elements used", "status": "pass",
                        "detail": f"Semantic elements found: {present} on {url}"})
    else:
        missing = [t for t, v in semantic.items() if not v]
        checks.append({"name": "Semantic HTML elements used", "status": "warning",
                        "detail": f"Missing semantic elements: {missing} on {url}"})

    # 6. No positive tabindex
    positive_tabs = [f"<{el.name} tabindex=\"{el.get('tabindex')}\">" for el in soup.find_all(tabindex=True)
                     if str(el.get("tabindex", "0")).strip().lstrip("-").isdigit()
                     and int(el.get("tabindex", 0)) > 0]
    if not positive_tabs:
        checks.append({"name": "No positive tabindex values", "status": "pass",
                        "detail": "No positive tabindex found — natural tab order preserved"})
    else:
        checks.append({"name": "No positive tabindex values", "status": "warning",
                        "detail": f"{len(positive_tabs)} positive tabindex on {url}: {positive_tabs[:3]}"})

    # 7. Buttons have accessible names
    buttons = soup.find_all("button")
    nameless_buttons = []
    for btn in buttons:
        has_text = bool(btn.get_text(strip=True))
        has_aria = bool(btn.get("aria-label") or btn.get("aria-labelledby"))
        has_title = bool(btn.get("title"))
        has_img_alt = bool(btn.find("img", alt=True))
        if not (has_text or has_aria or has_title or has_img_alt):
            nameless_buttons.append(str(btn)[:80] + f" on {url}")
    if not nameless_buttons:
        checks.append({"name": "Buttons have accessible names", "status": "pass",
                        "detail": f"All {len(buttons)} button(s) have accessible names"})
    else:
        checks.append({"name": "Buttons have accessible names", "status": "fail",
                        "detail": f"{len(nameless_buttons)} nameless button(s): {nameless_buttons[:3]}"})

    # 8. Descriptive link text
    generic_texts = {"click here", "read more", "here", "link", "more", "learn more", "this page"}
    generic_links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if text in generic_texts:
            generic_links.append(f"\"{text}\" → {a.get('href','')[:60]} on {url}")
    if not generic_links:
        checks.append({"name": "Descriptive link text", "status": "pass",
                        "detail": "All links use descriptive anchor text"})
    else:
        checks.append({"name": "Descriptive link text", "status": "warning",
                        "detail": f"{len(generic_links)} generic link(s): {generic_links[:3]}"})

    # 9. HTML lang attribute
    html_tag = soup.find("html")
    lang = html_tag.get("lang", "") if html_tag else ""
    if lang:
        checks.append({"name": "HTML lang attribute set", "status": "pass",
                        "detail": f"lang=\"{lang}\" on {url}"})
    else:
        checks.append({"name": "HTML lang attribute set", "status": "fail",
                        "detail": f"Missing lang attribute on <html> — {url}"})

    # 10. Color contrast heuristic (inline styles only)
    contrast_issues = []
    elements_with_color = soup.find_all(style=re.compile(r'color\s*:', re.I))
    for el in elements_with_color[:10]:
        style = el.get("style", "")
        fg_match = re.search(r'(?<![background-])color\s*:\s*#([0-9a-fA-F]{3,6})', style)
        bg_match = re.search(r'background-color\s*:\s*#([0-9a-fA-F]{3,6})', style)
        if fg_match and bg_match:
            fg_rgb = _hex_to_rgb(fg_match.group(1))
            bg_rgb = _hex_to_rgb(bg_match.group(1))
            if fg_rgb and bg_rgb:
                ratio = _contrast_ratio(fg_rgb, bg_rgb)
                if ratio < 4.5:
                    contrast_issues.append(
                        f"<{el.name}> contrast {ratio:.1f}:1 "
                        f"(fg #{fg_match.group(1)} / bg #{bg_match.group(1)}) on {url}"
                    )
    if not contrast_issues:
        checks.append({"name": "Color contrast heuristic (WCAG AA)", "status": "pass",
                        "detail": "No contrast issues detected in inline styles"})
    else:
        checks.append({"name": "Color contrast heuristic (WCAG AA)", "status": "warning",
                        "detail": f"{len(contrast_issues)} potential contrast issue(s): {contrast_issues[:3]}"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
