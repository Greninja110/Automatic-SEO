"""Module 8: Mobile Friendliness"""
import re


def check_mobile_friendliness(url: str, soup, response, **kwargs) -> dict:
    checks = []
    html = response.text

    # 1. Viewport meta tag present
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport:
        checks.append({"name": "Viewport meta tag present", "status": "pass", "detail": f"Viewport: {viewport.get('content', '')[:100]}"})
    else:
        checks.append({"name": "Viewport meta tag present", "status": "fail", "detail": "No <meta name=\"viewport\"> — critical for mobile rendering"})

    # 2. Viewport contains width=device-width
    viewport_content = (viewport.get("content", "") if viewport else "").lower()
    if "width=device-width" in viewport_content:
        checks.append({"name": "Viewport width=device-width", "status": "pass", "detail": "Viewport correctly set to device width"})
    else:
        checks.append({"name": "Viewport width=device-width", "status": "fail" if viewport else "warning",
                        "detail": "width=device-width not found in viewport content"})

    # 3. Viewport initial-scale=1
    if "initial-scale=1" in viewport_content:
        checks.append({"name": "Viewport initial-scale=1", "status": "pass", "detail": "initial-scale=1 set correctly"})
    else:
        checks.append({"name": "Viewport initial-scale=1", "status": "warning", "detail": "initial-scale=1 not set in viewport"})

    # 4. No fixed pixel widths causing overflow (body/container)
    fixed_wide = re.findall(r'(?:width\s*:\s*)(\d{4,})px', html)
    if not fixed_wide:
        checks.append({"name": "No fixed wide pixel widths", "status": "pass", "detail": "No large fixed-width elements detected in inline styles"})
    else:
        checks.append({"name": "No fixed wide pixel widths", "status": "warning",
                        "detail": f"Fixed widths found: {fixed_wide[:3]}px — may cause horizontal scroll on mobile"})

    # 5. No horizontal scroll triggers (overflow)
    overflow_hidden = re.search(r'overflow\s*:\s*hidden', html)
    overflow_x = re.search(r'overflow-x\s*:\s*hidden', html)
    if overflow_hidden or overflow_x:
        checks.append({"name": "Horizontal overflow managed", "status": "warning", "detail": "overflow:hidden found — verify it doesn't clip content on mobile"})
    else:
        checks.append({"name": "Horizontal overflow managed", "status": "pass", "detail": "No overflow:hidden issues detected in inline styles"})

    # 6. Font sizes readable (no tiny inline fonts)
    tiny_fonts = re.findall(r'font-size\s*:\s*([0-9]+)px', html)
    tiny_fonts = [int(f) for f in tiny_fonts if int(f) < 12]
    if not tiny_fonts:
        checks.append({"name": "Font size readable (≥12px)", "status": "pass", "detail": "No font sizes below 12px detected in inline styles"})
    else:
        checks.append({"name": "Font size readable (≥12px)", "status": "warning",
                        "detail": f"{len(tiny_fonts)} inline font size(s) below 12px: {tiny_fonts[:3]}px"})

    # 7. Tap target size heuristic (buttons/links)
    small_targets = []
    for el in soup.find_all(["a", "button"]):
        style = el.get("style", "")
        w = re.search(r'width\s*:\s*(\d+)px', style)
        h = re.search(r'height\s*:\s*(\d+)px', style)
        if w and int(w.group(1)) < 44:
            small_targets.append(f"<{el.name}> width:{w.group(1)}px")
        elif h and int(h.group(1)) < 44:
            small_targets.append(f"<{el.name}> height:{h.group(1)}px")
    if not small_targets:
        checks.append({"name": "Tap target size (≥44px)", "status": "pass", "detail": "No undersized tap targets detected in inline styles"})
    else:
        checks.append({"name": "Tap target size (≥44px)", "status": "warning",
                        "detail": f"Small tap targets: {small_targets[:3]}"})

    # 8. No Flash / plugin content
    flash_tags = soup.find_all(["object", "embed", "applet"])
    flash_refs = [t.get("type", "") or t.get("classid", "") for t in flash_tags]
    flash_active = [f for f in flash_refs if "flash" in f.lower() or "shockwave" in f.lower()]
    if flash_active:
        checks.append({"name": "No Flash/plugin content", "status": "fail", "detail": f"Flash/plugin content detected: {flash_active[:2]}"})
    elif flash_tags:
        checks.append({"name": "No Flash/plugin content", "status": "warning", "detail": f"{len(flash_tags)} <object>/<embed> tag(s) found — verify they're not Flash"})
    else:
        checks.append({"name": "No Flash/plugin content", "status": "pass", "detail": "No Flash or plugin elements found"})

    # 9. Touch icons / favicons
    apple_icon = soup.find("link", rel=lambda r: r and "apple-touch-icon" in r)
    favicon = soup.find("link", rel=lambda r: r and "icon" in r)
    if apple_icon:
        checks.append({"name": "Touch/favicon icons present", "status": "pass", "detail": "Apple touch icon found"})
    elif favicon:
        checks.append({"name": "Touch/favicon icons present", "status": "pass", "detail": "Favicon found (consider adding Apple touch icon)"})
    else:
        checks.append({"name": "Touch/favicon icons present", "status": "warning", "detail": "No favicon or touch icon found"})

    # 10. Responsive images (srcset or <picture>)
    imgs = soup.find_all("img")
    responsive = [img for img in imgs if img.get("srcset")]
    picture_tags = soup.find_all("picture")
    if picture_tags or (imgs and len(responsive) >= len(imgs) * 0.5):
        checks.append({"name": "Responsive images (srcset/picture)", "status": "pass",
                        "detail": f"{len(responsive)} responsive images, {len(picture_tags)} <picture> elements"})
    else:
        checks.append({"name": "Responsive images (srcset/picture)", "status": "warning",
                        "detail": f"Only {len(responsive)}/{len(imgs)} images use srcset — consider responsive images"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
