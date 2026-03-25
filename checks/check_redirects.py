"""Module 13: Redirects"""
import re
import time
from urllib.parse import urlparse, urlunparse


def check_redirects(url: str, soup, response, session=None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    base_domain = parsed.netloc
    scheme = parsed.scheme

    # 1. HTTP → HTTPS redirect
    if session and scheme == "https":
        try:
            http_url = url.replace("https://", "http://", 1)
            r = session.get(http_url, timeout=10, allow_redirects=True)
            if r.url.startswith("https://"):
                checks.append({"name": "HTTP redirects to HTTPS", "status": "pass",
                                "detail": f"HTTP → HTTPS redirect works correctly"})
            else:
                checks.append({"name": "HTTP redirects to HTTPS", "status": "fail",
                                "detail": f"HTTP does not redirect to HTTPS; final URL: {r.url[:80]}"})
        except Exception as e:
            checks.append({"name": "HTTP redirects to HTTPS", "status": "warning",
                            "detail": f"Could not test HTTP redirect: {str(e)[:60]}"})
    elif scheme != "https":
        checks.append({"name": "HTTP redirects to HTTPS", "status": "fail",
                        "detail": "Page is served over HTTP — should redirect to HTTPS"})
    else:
        checks.append({"name": "HTTP redirects to HTTPS", "status": "warning",
                        "detail": "No session available to test redirect"})

    # 2. WWW consistency
    if session:
        try:
            if base_domain.startswith("www."):
                non_www = url.replace(f"://{base_domain}", f"://{base_domain[4:]}", 1)
                r = session.get(non_www, timeout=10, allow_redirects=True)
                final_domain = urlparse(r.url).netloc
                if final_domain == base_domain:
                    checks.append({"name": "WWW/non-WWW consistency", "status": "pass",
                                    "detail": "Non-WWW redirects to WWW consistently"})
                else:
                    checks.append({"name": "WWW/non-WWW consistency", "status": "warning",
                                    "detail": f"Inconsistent redirect — final: {final_domain}"})
            else:
                www_url = url.replace(f"://{base_domain}", f"://www.{base_domain}", 1)
                r = session.get(www_url, timeout=10, allow_redirects=True)
                final_domain = urlparse(r.url).netloc
                if final_domain == base_domain:
                    checks.append({"name": "WWW/non-WWW consistency", "status": "pass",
                                    "detail": "WWW redirects to non-WWW consistently"})
                else:
                    checks.append({"name": "WWW/non-WWW consistency", "status": "warning",
                                    "detail": f"Inconsistent redirect — final: {final_domain}"})
        except Exception as e:
            checks.append({"name": "WWW/non-WWW consistency", "status": "warning",
                            "detail": f"Could not test WWW redirect: {str(e)[:60]}"})
    else:
        checks.append({"name": "WWW/non-WWW consistency", "status": "warning",
                        "detail": "No session to test WWW redirect"})

    # 3. Redirect is 301 (permanent) vs 302
    if response.history:
        first_redirect_status = response.history[0].status_code
        if first_redirect_status == 301:
            checks.append({"name": "Redirects use 301 (permanent)", "status": "pass",
                            "detail": f"First redirect is 301 Permanent"})
        elif first_redirect_status == 302:
            checks.append({"name": "Redirects use 301 (permanent)", "status": "warning",
                            "detail": "Redirect is 302 (temporary) — use 301 unless truly temporary"})
        else:
            checks.append({"name": "Redirects use 301 (permanent)", "status": "warning",
                            "detail": f"Redirect status: {first_redirect_status}"})
    else:
        checks.append({"name": "Redirects use 301 (permanent)", "status": "pass",
                        "detail": "No redirects — direct page load"})

    # 4. No redirect chains (≤1 hop)
    hop_count = len(response.history)
    if hop_count == 0:
        checks.append({"name": "No redirect chain (≤1 hop)", "status": "pass",
                        "detail": "Direct response — no redirects"})
    elif hop_count == 1:
        checks.append({"name": "No redirect chain (≤1 hop)", "status": "pass",
                        "detail": "Single redirect hop (acceptable)"})
    elif hop_count == 2:
        checks.append({"name": "No redirect chain (≤1 hop)", "status": "warning",
                        "detail": f"Redirect chain: {hop_count} hops"})
    else:
        checks.append({"name": "No redirect chain (≤1 hop)", "status": "fail",
                        "detail": f"Long redirect chain: {hop_count} hops"})

    # 5. No redirect loops
    history_urls = [r.url for r in response.history]
    if len(history_urls) != len(set(history_urls)):
        checks.append({"name": "No redirect loop", "status": "fail",
                        "detail": f"Redirect loop detected in history: {history_urls[:5]}"})
    else:
        checks.append({"name": "No redirect loop", "status": "pass",
                        "detail": "No redirect loops detected"})

    # 6. Trailing slash consistency
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        canon_href = canonical["href"]
        # Both should agree on trailing slash
        url_has_slash = parsed.path.endswith("/")
        canon_has_slash = canon_href.rstrip("?#").endswith("/")
        if url_has_slash == canon_has_slash:
            checks.append({"name": "Trailing slash consistency", "status": "pass",
                            "detail": f"URL and canonical agree on trailing slash"})
        else:
            checks.append({"name": "Trailing slash consistency", "status": "warning",
                            "detail": f"URL trailing slash mismatch with canonical"})
    else:
        checks.append({"name": "Trailing slash consistency", "status": "warning",
                        "detail": "No canonical to compare trailing slash"})

    # 7. No meta refresh redirects
    meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    if meta_refresh:
        content = meta_refresh.get("content", "")
        if "url=" in content.lower():
            checks.append({"name": "No meta refresh redirect", "status": "fail",
                            "detail": f"Meta refresh redirect found: {content[:80]}"})
        else:
            checks.append({"name": "No meta refresh redirect", "status": "warning",
                            "detail": f"Meta refresh present (not a redirect, but review): {content[:80]}"})
    else:
        checks.append({"name": "No meta refresh redirect", "status": "pass",
                        "detail": "No meta refresh redirects found"})

    # 8. Final destination is indexable (200)
    if response.status_code == 200:
        checks.append({"name": "Final URL returns 200 OK", "status": "pass",
                        "detail": f"Final URL status: 200"})
    else:
        checks.append({"name": "Final URL returns 200 OK", "status": "fail",
                        "detail": f"Final URL status: {response.status_code}"})

    # 9. Redirect latency
    if response.history:
        total_time = sum(h.elapsed.total_seconds() for h in response.history if hasattr(h, 'elapsed'))
        total_time += response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
        if total_time <= 2:
            checks.append({"name": "Redirect latency (<2s total)", "status": "pass",
                            "detail": f"Total redirect time: {total_time:.2f}s"})
        else:
            checks.append({"name": "Redirect latency (<2s total)", "status": "warning",
                            "detail": f"Slow redirect chain: {total_time:.2f}s total"})
    else:
        checks.append({"name": "Redirect latency (<2s total)", "status": "pass",
                        "detail": "No redirects — no latency penalty"})

    # 10. Link equity preserved (informational — all redirects reach canonical)
    if response.history:
        chain = " → ".join([r.url[:50] for r in response.history] + [response.url[:50]])
        checks.append({"name": "Link equity preserved (redirects reach canonical)", "status": "warning",
                        "detail": f"Redirect chain: {chain}"})
    else:
        checks.append({"name": "Link equity preserved (redirects reach canonical)", "status": "pass",
                        "detail": "Direct load — full link equity preserved"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Redirect hops: {len(response.history)}"

    return {"checks": checks, "summary": summary}
