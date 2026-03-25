"""Module 16: Analytics & Tracking"""
import re


def check_analytics_tracking(url: str, soup, response, **kwargs) -> dict:
    checks = []
    html = response.text
    head = soup.find("head") or soup

    # 1. Google Analytics 4 (GA4) detected
    ga4_matches = re.findall(r"gtag\(['\"]config['\"],\s*['\"]G-[A-Z0-9]+['\"]", html)
    if ga4_matches:
        checks.append({"name": "Google Analytics 4 (GA4) detected", "status": "pass",
                        "detail": f"GA4 property found: {ga4_matches[0][:80]}"})
    else:
        checks.append({"name": "Google Analytics 4 (GA4) detected", "status": "warning",
                        "detail": "GA4 not detected — may be using another analytics platform"})

    # 2. Universal Analytics (UA) detected
    ua_matches = re.findall(r"(?:gtag\(['\"]config['\"],\s*['\"]UA-[\d-]+['\"]|ga\(['\"]create['\"])", html)
    if ua_matches:
        checks.append({"name": "Universal Analytics (UA) detected", "status": "warning",
                        "detail": f"Legacy UA detected — Google sunset UA in July 2023: {ua_matches[0][:60]}"})
    else:
        checks.append({"name": "Universal Analytics (UA) detected", "status": "pass",
                        "detail": "No legacy UA code detected"})

    # 3. Google Tag Manager detected
    gtm_matches = re.findall(r'GTM-[A-Z0-9]+', html)
    gtm_unique = list(set(gtm_matches))
    if gtm_unique:
        checks.append({"name": "Google Tag Manager (GTM) detected", "status": "pass",
                        "detail": f"GTM container(s): {gtm_unique[:3]}"})
    else:
        checks.append({"name": "Google Tag Manager (GTM) detected", "status": "warning",
                        "detail": "GTM not detected (may use another tag management system)"})

    # 4. No duplicate GA codes
    all_ga_properties = re.findall(r"['\"]G-[A-Z0-9]+['\"]", html) + re.findall(r"['\"]UA-[\d-]+['\"]", html)
    unique_ga = list(set(all_ga_properties))
    if len(unique_ga) <= 1:
        checks.append({"name": "No duplicate GA tracking codes", "status": "pass",
                        "detail": f"Single GA property: {unique_ga[0] if unique_ga else 'none'}"})
    else:
        checks.append({"name": "No duplicate GA tracking codes", "status": "warning",
                        "detail": f"Multiple GA properties found: {unique_ga[:3]}"})

    # 5. No duplicate GTM containers
    if len(gtm_unique) <= 1:
        checks.append({"name": "No duplicate GTM containers", "status": "pass",
                        "detail": f"Single GTM container: {gtm_unique[0] if gtm_unique else 'none'}"})
    else:
        checks.append({"name": "No duplicate GTM containers", "status": "warning",
                        "detail": f"Multiple GTM containers: {gtm_unique[:3]}"})

    # 6. Tracking script in <head>
    head_html = str(head) if head else ""
    tracking_in_head = (
        bool(re.search(r'GTM-[A-Z0-9]+', head_html)) or
        bool(re.search(r'gtag\(', head_html)) or
        bool(re.search(r'ga\(', head_html))
    )
    if tracking_in_head:
        checks.append({"name": "Tracking code in <head>", "status": "pass",
                        "detail": "Analytics/GTM code found in <head>"})
    elif ga4_matches or gtm_matches:
        checks.append({"name": "Tracking code in <head>", "status": "warning",
                        "detail": "Tracking code found but not in <head> — may delay data collection"})
    else:
        checks.append({"name": "Tracking code in <head>", "status": "warning",
                        "detail": "No tracking code detected in <head>"})

    # 7. GA script loads from official CDN
    ga_scripts = [s.get("src", "") for s in soup.find_all("script", src=True)
                  if "google" in s.get("src", "").lower() and "tag" in s.get("src", "").lower()]
    gtm_scripts = [s.get("src", "") for s in soup.find_all("script", src=True)
                   if "googletagmanager.com" in s.get("src", "")]
    analytics_scripts = ga_scripts + gtm_scripts
    if analytics_scripts:
        checks.append({"name": "Analytics script from official CDN", "status": "pass",
                        "detail": f"Official CDN: {analytics_scripts[0][:80]}"})
    elif ga4_matches or gtm_matches:
        checks.append({"name": "Analytics script from official CDN", "status": "warning",
                        "detail": "Tracking detected inline — consider loading from official CDN"})
    else:
        checks.append({"name": "Analytics script from official CDN", "status": "warning",
                        "detail": "No analytics scripts detected"})

    # 8. No debug mode in GA
    if re.search(r"debug_mode\s*:\s*true", html, re.IGNORECASE):
        checks.append({"name": "No GA debug mode on production", "status": "warning",
                        "detail": "GA debug_mode: true detected — remove before production"})
    else:
        checks.append({"name": "No GA debug mode on production", "status": "pass",
                        "detail": "No GA debug mode detected"})

    # 9. Other tracking platforms detected (informational)
    other_trackers = []
    if re.search(r'fbq\(', html):
        other_trackers.append("Facebook Pixel")
    if re.search(r'_linkedin_partner_id', html):
        other_trackers.append("LinkedIn Insight")
    if re.search(r'hj\(', html) or re.search(r'hotjar', html, re.IGNORECASE):
        other_trackers.append("Hotjar")
    if re.search(r'clarity\(', html) or re.search(r'Microsoft Clarity', html, re.IGNORECASE):
        other_trackers.append("MS Clarity")
    if other_trackers:
        checks.append({"name": "Other tracking platforms (informational)", "status": "pass",
                        "detail": f"Also detected: {', '.join(other_trackers)}"})
    else:
        checks.append({"name": "Other tracking platforms (informational)", "status": "pass",
                        "detail": "No other tracking platforms detected"})

    # 10. Consent mode implementation
    if re.search(r"gtag\(['\"]consent['\"],\s*['\"]default['\"]", html):
        checks.append({"name": "Consent mode implemented", "status": "pass",
                        "detail": "Google Consent Mode v2 default state found"})
    else:
        checks.append({"name": "Consent mode implemented", "status": "warning",
                        "detail": "No consent mode detected — required for GDPR compliance with GA4"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
