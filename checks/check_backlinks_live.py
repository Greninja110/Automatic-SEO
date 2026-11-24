"""Module 25: Backlinks (Live Data)

Scores real backlink-profile data for the domain. The data is supplied from
outside the crawler — normally by an AI agent running Agensi's
`agensi:web.backlinks.summary` tool — via `main.py --backlinks-json FILE`.

Accepted input: the tool's JSON answer as-is, e.g.
  {"backlinks": 1234, "referring_domains": 56, "summary": {...provider row...}}
or the same object nested under "result" / "data". Provider field names vary
(DataForSEO, SE Ranking, Serpstat, Moz), so several spellings are recognised.
Only metrics actually present produce checks.
"""

# Each metric: list of accepted key spellings (case-insensitive, first hit wins).
FIELDS = {
    "backlinks":         ["backlinks", "total_backlinks", "backlinks_count", "external_links", "links"],
    "referring_domains": ["referring_domains", "refdomains", "ref_domains", "referring_domains_count", "domains"],
    "ref_domains_nofollow": ["referring_domains_nofollow", "refdomains_nofollow", "nofollow_domains"],
    "backlinks_nofollow":   ["backlinks_nofollow", "nofollow_backlinks", "external_links_nofollow"],
    "referring_ips":     ["referring_ips", "refips", "ref_ips"],
    "referring_subnets": ["referring_subnets", "refclass_c", "ref_subnets"],
    "authority":         ["domain_rating", "rank", "domain_authority", "authority_score", "domain_rank", "dr", "da", "ascore"],
    "spam_score":        ["backlinks_spam_score", "spam_score", "spam"],
    "broken_backlinks":  ["broken_backlinks", "broken_links"],
}


def _flatten(data) -> dict:
    """Merge top-level, 'summary', 'result', 'data' and 'metrics' objects into one lowercase-key dict."""
    out = {}

    def absorb(obj, depth=0):
        if depth > 3:
            return
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            obj = obj[0]
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                if k.lower() in ("summary", "result", "results", "data", "metrics", "items"):
                    absorb(v, depth + 1)
            else:
                out.setdefault(k.lower(), v)

    absorb(data)
    return out


def _num(flat: dict, metric: str):
    for key in FIELDS[metric]:
        v = flat.get(key)
        if v is None or isinstance(v, bool):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _fmt(n: float) -> str:
    return f"{int(n):,}" if float(n).is_integer() else f"{n:,.1f}"


def check_backlinks_live(url: str, soup, response, backlinks_data=None, **kwargs) -> dict:
    if not backlinks_data:
        return {
            "checks": [{"name": "Live backlink data", "status": "warning",
                        "detail": "Not supplied. Run this audit through the Agensi skill (it fetches the data with "
                                  "agensi:web.backlinks.summary) or pass --backlinks-json FILE."}],
            "summary": "Skipped — no live backlink data supplied.",
        }

    flat = _flatten(backlinks_data)
    m = {k: _num(flat, k) for k in FIELDS}
    checks = []

    rd, bl = m["referring_domains"], m["backlinks"]
    if rd is None and bl is None:
        return {
            "checks": [{"name": "Live backlink data", "status": "warning",
                        "detail": f"Backlink data supplied but no backlink/referring-domain counts recognised "
                                  f"(keys: {sorted(flat)[:12]})"}],
            "summary": "Backlink data could not be interpreted.",
        }

    # 1. Referring domains — the strongest single authority signal
    if rd is not None:
        if rd >= 50:
            status, note = "pass", "solid base of linking sites"
        elif rd >= 10:
            status, note = "warning", "modest — build links from more distinct sites"
        else:
            status, note = "fail", "very few sites link here — link building is a priority"
        checks.append({"name": "Referring domains", "status": status,
                       "detail": f"{_fmt(rd)} referring domain(s): {note}"})

    # 2. Total backlinks
    if bl is not None:
        status = "pass" if bl >= 100 else "warning" if bl > 0 else "fail"
        checks.append({"name": "Total backlinks", "status": status,
                       "detail": f"{_fmt(bl)} backlink(s)"})

    # 3. Links per domain — very high ratios mean sitewide/footer or spammy links
    if rd and bl is not None:
        ratio = bl / rd
        status = "pass" if ratio <= 50 else "warning"
        detail = f"{ratio:.1f} backlinks per referring domain"
        if status == "warning":
            detail += " — profile is dominated by sitewide/footer links; diversity is low"
        checks.append({"name": "Link diversity (backlinks per domain ≤50)", "status": status, "detail": detail})

    # 4. Authority / rank (scale differs by provider)
    if m["authority"] is not None:
        a = m["authority"]
        # DataForSEO "rank" runs 0–1000; DR/DA/AS run 0–100.
        scale = 1000 if a > 100 else 100
        pct = a / scale * 100
        status = "pass" if pct >= 30 else "warning" if pct >= 10 else "fail"
        checks.append({"name": "Domain authority / rank", "status": status,
                       "detail": f"{_fmt(a)} on a 0–{scale} scale"})

    # 5. Spam score
    if m["spam_score"] is not None:
        s = m["spam_score"]
        status = "pass" if s < 30 else "warning" if s < 60 else "fail"
        checks.append({"name": "Backlink spam score (<30)", "status": status,
                       "detail": f"Spam score {_fmt(s)}" + (" — audit and disavow toxic links" if s >= 30 else "")})

    # 6. Nofollow share
    if m["ref_domains_nofollow"] is not None and rd:
        share = m["ref_domains_nofollow"] / rd * 100
        status = "pass" if share <= 70 else "warning"
        checks.append({"name": "Dofollow share of referring domains", "status": status,
                       "detail": f"{share:.0f}% of referring domains are nofollow-only"})
    elif m["backlinks_nofollow"] is not None and bl:
        share = m["backlinks_nofollow"] / bl * 100
        status = "pass" if share <= 70 else "warning"
        checks.append({"name": "Dofollow share of backlinks", "status": status,
                       "detail": f"{share:.0f}% of backlinks are nofollow"})

    # 7. IP / subnet diversity (many domains on few IPs = link network)
    if m["referring_ips"] is not None and rd:
        ip_ratio = m["referring_ips"] / rd
        status = "pass" if ip_ratio >= 0.5 else "warning"
        checks.append({"name": "Referring IP diversity", "status": status,
                       "detail": f"{_fmt(m['referring_ips'])} IPs for {_fmt(rd)} domains"
                                 + ("" if status == "pass" else " — many linking sites share IPs (possible PBN)")})

    # 8. Broken backlinks (link equity lost to 404s)
    if m["broken_backlinks"] is not None:
        b = m["broken_backlinks"]
        status = "pass" if b == 0 else "warning"
        checks.append({"name": "No broken backlinks", "status": status,
                       "detail": f"{_fmt(b)} backlink(s) point to missing pages"
                                 + (" — 301-redirect those URLs to reclaim link equity" if b else "")})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = (f"{passed} passed, {failed} failed, {warned} warnings. "
               f"Referring domains: {_fmt(rd) if rd is not None else 'n/a'}, "
               f"backlinks: {_fmt(bl) if bl is not None else 'n/a'}")
    return {"checks": checks, "summary": summary}
