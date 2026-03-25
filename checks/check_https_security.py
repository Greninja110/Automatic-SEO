"""Module 14: HTTPS & Security"""
import ssl
import socket
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import certifi


def _get_ssl_expiry(hostname: str) -> tuple:
    """Returns (expiry_date, days_remaining) or (None, None) on error."""
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(10)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            expiry_str = cert.get("notAfter", "")
            expiry_dt = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            days = (expiry_dt - datetime.now(timezone.utc)).days
            return expiry_dt, days
    except Exception as e:
        return None, None


def check_https_security(url: str, soup, response, session=None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    hostname = parsed.netloc.split(":")[0]

    # 1. URL uses HTTPS
    if url.startswith("https://"):
        checks.append({"name": "URL uses HTTPS", "status": "pass", "detail": "Page is served over HTTPS"})
    else:
        checks.append({"name": "URL uses HTTPS", "status": "fail", "detail": "Page is served over HTTP — HTTPS required for SEO"})

    # 2. SSL certificate valid
    try:
        import requests
        test_r = requests.get(url, verify=certifi.where(), timeout=10)
        checks.append({"name": "SSL certificate valid", "status": "pass", "detail": "SSL certificate is valid and trusted"})
    except requests.exceptions.SSLError as e:
        checks.append({"name": "SSL certificate valid", "status": "fail", "detail": f"SSL error: {str(e)[:100]}"})
    except Exception:
        checks.append({"name": "SSL certificate valid", "status": "warning", "detail": "Could not verify SSL certificate"})

    # 3. HSTS header present
    hsts = response.headers.get("Strict-Transport-Security", "")
    if hsts:
        checks.append({"name": "HSTS header present", "status": "pass", "detail": f"HSTS: {hsts[:100]}"})
    else:
        checks.append({"name": "HSTS header present", "status": "warning",
                        "detail": "No Strict-Transport-Security header — consider adding HSTS"})

    # 4. HSTS max-age sufficient (≥1 year)
    if hsts:
        max_age_match = re.search(r'max-age=(\d+)', hsts)
        if max_age_match:
            max_age = int(max_age_match.group(1))
            if max_age >= 31536000:
                checks.append({"name": "HSTS max-age ≥1 year", "status": "pass",
                                "detail": f"max-age={max_age} ({max_age//86400} days)"})
            else:
                checks.append({"name": "HSTS max-age ≥1 year", "status": "warning",
                                "detail": f"HSTS max-age={max_age} is below recommended 31536000 (1 year)"})
        else:
            checks.append({"name": "HSTS max-age ≥1 year", "status": "warning",
                            "detail": "HSTS header present but no max-age found"})
    else:
        checks.append({"name": "HSTS max-age ≥1 year", "status": "warning",
                        "detail": "No HSTS header to check max-age"})

    # 5. HTTP redirects to HTTPS
    if session and url.startswith("https://"):
        try:
            http_url = url.replace("https://", "http://", 1)
            r = session.get(http_url, timeout=10, allow_redirects=False)
            if r.status_code in (301, 302) and "https" in r.headers.get("Location", "").lower():
                checks.append({"name": "HTTP redirects to HTTPS", "status": "pass",
                                "detail": f"HTTP → HTTPS redirect: {r.status_code}"})
            else:
                checks.append({"name": "HTTP redirects to HTTPS", "status": "fail",
                                "detail": f"HTTP does not redirect to HTTPS (status {r.status_code})"})
        except Exception as e:
            checks.append({"name": "HTTP redirects to HTTPS", "status": "warning",
                            "detail": f"Could not test: {str(e)[:60]}"})
    else:
        checks.append({"name": "HTTP redirects to HTTPS", "status": "warning",
                        "detail": "No session available to test HTTP→HTTPS redirect"})

    # 6. No mixed content (HTTP assets on HTTPS page)
    if url.startswith("https://"):
        mixed = []
        for tag in soup.find_all(["img", "script", "link", "iframe", "source"]):
            for attr in ["src", "href", "data-src"]:
                val = tag.get(attr, "")
                if val.startswith("http://"):
                    mixed.append(f"<{tag.name} {attr}={val[:60]}>")
        if not mixed:
            checks.append({"name": "No mixed content (HTTP on HTTPS)", "status": "pass",
                            "detail": "No HTTP assets found on HTTPS page"})
        else:
            checks.append({"name": "No mixed content (HTTP on HTTPS)", "status": "fail",
                            "detail": f"{len(mixed)} mixed content item(s): {mixed[:3]}"})
    else:
        checks.append({"name": "No mixed content (HTTP on HTTPS)", "status": "warning",
                        "detail": "Page is on HTTP — mixed content not applicable"})

    # 7. Secure cookie flag
    set_cookie = response.headers.get("Set-Cookie", "")
    if set_cookie:
        if "secure" in set_cookie.lower():
            checks.append({"name": "Secure cookie flag set", "status": "pass",
                            "detail": "Cookies have Secure flag"})
        else:
            checks.append({"name": "Secure cookie flag set", "status": "warning",
                            "detail": "Cookies found without Secure flag"})
    else:
        checks.append({"name": "Secure cookie flag set", "status": "pass",
                        "detail": "No cookies set on this page"})

    # 8. X-Content-Type-Options header
    xcto = response.headers.get("X-Content-Type-Options", "")
    if xcto.lower() == "nosniff":
        checks.append({"name": "X-Content-Type-Options: nosniff", "status": "pass",
                        "detail": "X-Content-Type-Options: nosniff present"})
    else:
        checks.append({"name": "X-Content-Type-Options: nosniff", "status": "warning",
                        "detail": "X-Content-Type-Options header missing or incorrect"})

    # 9. X-Frame-Options or Content-Security-Policy
    xfo = response.headers.get("X-Frame-Options", "")
    csp = response.headers.get("Content-Security-Policy", "")
    if xfo:
        checks.append({"name": "X-Frame-Options or CSP present", "status": "pass",
                        "detail": f"X-Frame-Options: {xfo[:60]}"})
    elif csp:
        checks.append({"name": "X-Frame-Options or CSP present", "status": "pass",
                        "detail": f"Content-Security-Policy present"})
    else:
        checks.append({"name": "X-Frame-Options or CSP present", "status": "warning",
                        "detail": "No X-Frame-Options or CSP header — clickjacking protection missing"})

    # 10. SSL certificate expiry
    expiry_dt, days_remaining = _get_ssl_expiry(hostname)
    if days_remaining is not None:
        if days_remaining > 90:
            checks.append({"name": "SSL certificate expiry (>30 days)", "status": "pass",
                            "detail": f"Certificate valid for {days_remaining} more days (expires {expiry_dt.date()})"})
        elif days_remaining > 30:
            checks.append({"name": "SSL certificate expiry (>30 days)", "status": "warning",
                            "detail": f"Certificate expires in {days_remaining} days — renew soon"})
        else:
            checks.append({"name": "SSL certificate expiry (>30 days)", "status": "fail",
                            "detail": f"Certificate expires in {days_remaining} days — URGENT renewal needed"})
    else:
        checks.append({"name": "SSL certificate expiry (>30 days)", "status": "warning",
                        "detail": "Could not retrieve SSL certificate expiry date"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings."

    return {"checks": checks, "summary": summary}
