"""Module 19: Core Web Vitals"""
import json
from urllib.parse import urljoin


def check_core_web_vitals(url: str, soup, response,
                            pagespeed_api_key: str = None, session=None, **kwargs) -> dict:
    checks = []
    imgs = soup.find_all("img")

    # 1. LCP proxy: largest above-fold image < 500KB
    largest_img = {"src": None, "size": 0}
    if session and imgs:
        for img in imgs[:8]:
            src = img.get("src") or img.get("data-src", "")
            if not src or src.startswith("data:"):
                continue
            img_url = urljoin(url, src)
            try:
                head = session.head(img_url, timeout=5, allow_redirects=True)
                size = int(head.headers.get("content-length", 0))
                if size > largest_img["size"]:
                    largest_img = {"src": img_url, "size": size}
            except Exception:
                pass

    if largest_img["src"]:
        size_kb = largest_img["size"] / 1024
        if size_kb < 200:
            checks.append({"name": "LCP proxy: largest image < 200KB", "status": "pass",
                            "detail": f"Largest image: {size_kb:.0f}KB — {largest_img['src']}"})
        elif size_kb < 500:
            checks.append({"name": "LCP proxy: largest image < 200KB", "status": "warning",
                            "detail": f"Largest image: {size_kb:.0f}KB (recommended <200KB) — {largest_img['src']}"})
        else:
            checks.append({"name": "LCP proxy: largest image < 200KB", "status": "fail",
                            "detail": f"LCP candidate is very large: {size_kb:.0f}KB — Page: {url} — Image: {largest_img['src']}"})
    else:
        checks.append({"name": "LCP proxy: largest image < 200KB", "status": "warning",
                        "detail": "Could not measure image sizes (no session or no images)"})

    # 2. LCP: above-fold image uses loading=eager
    above_fold_imgs = imgs[:3]  # First 3 images are likely above fold
    eager_issues = []
    for img in above_fold_imgs:
        loading = img.get("loading", "")
        src = img.get("src", "")[:80]
        if loading == "lazy":
            eager_issues.append(f"{src} (has loading=lazy)")
    if not eager_issues:
        checks.append({"name": "Above-fold images not lazy-loaded", "status": "pass",
                        "detail": "First 3 images do not use lazy loading (good for LCP)"})
    else:
        checks.append({"name": "Above-fold images not lazy-loaded", "status": "warning",
                        "detail": f"Above-fold images with lazy loading (hurts LCP): {eager_issues}"})

    # 3. CLS proxy: all images have explicit dimensions
    imgs_no_dims = []
    for img in imgs:
        if not img.get("width") or not img.get("height"):
            src = img.get("src", "")[:80]
            imgs_no_dims.append(f"{src} on page {url}")
    if not imgs_no_dims:
        checks.append({"name": "CLS proxy: images have width/height (no layout shift)", "status": "pass",
                        "detail": f"All {len(imgs)} images have explicit dimensions"})
    else:
        checks.append({"name": "CLS proxy: images have width/height (no layout shift)", "status": "fail",
                        "detail": f"{len(imgs_no_dims)} image(s) missing dimensions: {imgs_no_dims[:3]}"})

    # 4. CLS proxy: no unsized ad slots
    ad_slots = soup.find_all("ins", class_="adsbygoogle")
    unsized_ads = [str(ad)[:100] for ad in ad_slots if not (ad.get("style") and "height" in ad.get("style", ""))]
    if not unsized_ads:
        checks.append({"name": "CLS proxy: no unsized ad slots", "status": "pass",
                        "detail": "No unsized AdSense slots detected"})
    else:
        checks.append({"name": "CLS proxy: no unsized ad slots", "status": "warning",
                        "detail": f"{len(unsized_ads)} unsized ad slot(s) may cause layout shift"})

    # 5. INP/FID proxy: render-blocking JS count
    head = soup.find("head")
    blocking_scripts = []
    if head:
        for s in head.find_all("script", src=True):
            if not s.get("defer") and not s.get("async"):
                blocking_scripts.append(s.get("src", "")[:80])
    if not blocking_scripts:
        checks.append({"name": "INP proxy: no render-blocking scripts", "status": "pass",
                        "detail": "No render-blocking scripts in <head>"})
    elif len(blocking_scripts) <= 2:
        checks.append({"name": "INP proxy: no render-blocking scripts", "status": "warning",
                        "detail": f"{len(blocking_scripts)} blocking script(s): {blocking_scripts}"})
    else:
        checks.append({"name": "INP proxy: no render-blocking scripts", "status": "fail",
                        "detail": f"{len(blocking_scripts)} blocking script(s) delay interactivity: {blocking_scripts[:3]}"})

    # 6-10: PageSpeed API checks
    api_metrics = {
        "largest-contentful-paint": "LCP (Largest Contentful Paint)",
        "cumulative-layout-shift": "CLS (Cumulative Layout Shift)",
        "interaction-to-next-paint": "INP (Interaction to Next Paint)",
        "first-contentful-paint": "FCP (First Contentful Paint)",
    }

    if pagespeed_api_key and session:
        try:
            api_url = (f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
                       f"?url={url}&key={pagespeed_api_key}&strategy=mobile")
            r = session.get(api_url, timeout=30)
            data = r.json()
            audits = data.get("lighthouseResult", {}).get("audits", {})
            perf_score = data.get("categories", {}).get("performance", {}).get("score")

            for audit_key, label in api_metrics.items():
                audit = audits.get(audit_key, {})
                score = audit.get("score")
                display_value = audit.get("displayValue", "N/A")
                if score is not None:
                    status = "pass" if score >= 0.9 else "warning" if score >= 0.5 else "fail"
                    checks.append({"name": f"PageSpeed: {label}", "status": status,
                                    "detail": f"Score: {int(score*100)}/100 — Value: {display_value} — URL: {url}"})
                else:
                    checks.append({"name": f"PageSpeed: {label}", "status": "warning",
                                    "detail": f"{label} not available in API response"})

            if perf_score is not None:
                pct = int(perf_score * 100)
                status = "pass" if pct >= 90 else "warning" if pct >= 50 else "fail"
                checks.append({"name": "PageSpeed: Overall Performance Score", "status": status,
                                "detail": f"Mobile performance: {pct}/100 — URL: {url}"})
            else:
                checks.append({"name": "PageSpeed: Overall Performance Score", "status": "warning",
                                "detail": "No performance score in API response"})

        except Exception as e:
            for _, label in api_metrics.items():
                checks.append({"name": f"PageSpeed: {label}", "status": "warning",
                                "detail": f"API error: {str(e)[:60]}"})
            checks.append({"name": "PageSpeed: Overall Performance Score", "status": "warning",
                            "detail": f"API error: {str(e)[:60]}"})
    else:
        for _, label in api_metrics.items():
            checks.append({"name": f"PageSpeed: {label}", "status": "warning",
                            "detail": "Add PAGESPEED_API_KEY to .env for real CWV measurements"})
        checks.append({"name": "PageSpeed: Overall Performance Score", "status": "warning",
                        "detail": "Add PAGESPEED_API_KEY to .env for real CWV measurements"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
