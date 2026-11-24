"""Shared HTTP helpers for check modules.

CachedSession: a requests.Session that remembers every GET/HEAD response for
the duration of one audit. Many modules request the same URLs (nav links on
every page, robots.txt, sitemap.xml, the same images, PageSpeed) — with the
cache each URL is fetched once per audit instead of once per module/page.

parallel_map: run a function over items with a small thread pool.
get_pagespeed: one cached PageSpeed Insights call shared by page_speed and
core_web_vitals.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter

USER_AGENT = ("Mozilla/5.0 (compatible; SEOAuditBot/2.0; "
              "+https://github.com/seo-audit-tool)")


class CachedSession(requests.Session):
    """requests.Session with a per-audit response cache for GET and HEAD.

    Failed requests are cached too (the exception is re-raised on every
    lookup) so a slow/unreachable URL only costs one timeout per audit.
    """

    def __init__(self, pool_size: int = 32):
        super().__init__()
        self.headers["User-Agent"] = USER_AGENT
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        self.mount("http://", adapter)
        self.mount("https://", adapter)
        self._cache: dict = {}
        self._key_locks: dict = {}
        self._lock = threading.Lock()

    def request(self, method, url, *args, **kwargs):
        method_u = method.upper()
        if method_u not in ("GET", "HEAD") or kwargs.get("stream"):
            return super().request(method, url, *args, **kwargs)

        # requests defaults: GET follows redirects, HEAD does not.
        allow = kwargs.get("allow_redirects", method_u == "GET")
        key = (method_u, url, bool(allow), repr(sorted((kwargs.get("params") or {}).items())))

        with self._lock:
            if key in self._cache:
                return self._unwrap(self._cache[key])
            key_lock = self._key_locks.setdefault(key, threading.Lock())

        # Only one thread fetches a given key; the others wait and reuse it.
        with key_lock:
            with self._lock:
                if key in self._cache:
                    return self._unwrap(self._cache[key])
            try:
                result = super().request(method, url, *args, **kwargs)
            except Exception as exc:  # cache the failure as well
                result = exc
            with self._lock:
                self._cache[key] = result
        return self._unwrap(result)

    @staticmethod
    def _unwrap(result):
        if isinstance(result, Exception):
            raise result
        return result


def make_session() -> CachedSession:
    """Session used by all check modules for one audit."""
    s = CachedSession()
    s.verify = False  # audits must still run on sites with broken TLS
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
    return s


def parallel_map(fn, items, workers: int = 8) -> list:
    """Apply fn to every item concurrently; results keep the input order."""
    items = list(items)
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(fn, items))


def head_status(session, url: str, timeout: int = 8):
    """(status_code, response) for a HEAD request, falling back to GET when
    the server rejects HEAD (405/501). Returns (None, None) on network error."""
    try:
        r = session.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code in (405, 501):
            r = session.get(url, timeout=timeout, allow_redirects=True)
        return r.status_code, r
    except Exception:
        return None, None


_PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def get_pagespeed(session, url: str, api_key: str, strategy: str = "mobile") -> dict:
    """Run PageSpeed Insights once per URL per audit (cached by the session).

    Returns the parsed JSON. Raises RuntimeError with Google's own error
    message when the API reports one (bad key, quota, unreachable URL).
    """
    r = session.get(_PSI_ENDPOINT, timeout=60,
                    params={"url": url, "key": api_key, "strategy": strategy,
                            "category": "performance"})
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"PageSpeed API returned non-JSON (HTTP {r.status_code})")
    if "error" in data:
        msg = data["error"].get("message", "unknown error") if isinstance(data["error"], dict) else str(data["error"])
        raise RuntimeError(f"PageSpeed API: {msg[:120]}")
    return data
