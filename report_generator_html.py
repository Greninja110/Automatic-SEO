"""
HTML Report Generator — SEO Audit
Generates a self-contained .html file saved to the reports/ folder.
Color coded: red = fail, yellow = warning, green = pass.
Each check row with many pages has its own individual "View more" toggle.
"""

import os
import json
from collections import OrderedDict

from checks import MODULE_TITLES

# ---------------------------------------------------------------------------
# Grouping logic (same as docx version)
# ---------------------------------------------------------------------------

STATUS_RANK = {"fail": 0, "warning": 1, "pass": 2}

def _group_checks(checks: list) -> list:
    groups = OrderedDict()
    for c in checks:
        key = (c.get("name", ""), c.get("status", "pass"))
        if key not in groups:
            groups[key] = {
                "name":   c.get("name", ""),
                "status": c.get("status", "pass"),
                "detail": c.get("detail", ""),
                "pages":  [],
                "count":  0,
            }
        groups[key]["count"] += 1
        page = c.get("page", "")
        if page and page not in groups[key]["pages"]:
            groups[key]["pages"].append(page)

    # merge duplicate names, keep worst status
    merged = {}
    for (name, status), g in groups.items():
        if name not in merged or STATUS_RANK[status] < STATUS_RANK[merged[name]["status"]]:
            merged[name] = g
        else:
            merged[name]["count"] += g["count"]
            for p in g["pages"]:
                if p not in merged[name]["pages"]:
                    merged[name]["pages"].append(p)

    return sorted(merged.values(), key=lambda g: STATUS_RANK[g["status"]])


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
    background: #f4f6f9;
    color: #222;
}

/* ── Header ── */
.header {
    background: linear-gradient(135deg, #1a2e5a 0%, #2c4a8a 100%);
    color: #fff;
    padding: 36px 48px 28px;
}
.header h1 { font-size: 26px; letter-spacing: 1px; margin-bottom: 6px; }
.header .meta { font-size: 13px; opacity: .75; margin-bottom: 24px; }

.score-badge {
    display: inline-block;
    font-size: 52px;
    font-weight: 700;
    line-height: 1;
    padding: 12px 28px;
    border-radius: 12px;
    margin-bottom: 20px;
}
.score-good    { background: #1e7e34; color: #fff; }
.score-medium  { background: #d39e00; color: #fff; }
.score-poor    { background: #bd2130; color: #fff; }

.stats-row { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px; }
.stat-box {
    background: rgba(255,255,255,.12);
    border-radius: 8px;
    padding: 12px 20px;
    min-width: 110px;
    text-align: center;
}
.stat-box .val { font-size: 28px; font-weight: 700; }
.stat-box .lbl { font-size: 11px; opacity: .8; text-transform: uppercase; letter-spacing: .5px; }
.stat-fail  .val { color: #ff8080; }
.stat-warn  .val { color: #ffd060; }
.stat-pass  .val { color: #7de07d; }
.stat-total .val { color: #fff; }

/* ── Layout ── */
.container { max-width: 1200px; margin: 0 auto; padding: 28px 24px; }

/* ── Summary table ── */
.summary-section { background: #fff; border-radius: 10px; padding: 24px; margin-bottom: 28px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.summary-section h2 { font-size: 16px; color: #1a2e5a; margin-bottom: 14px; }

.summary-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.summary-table th {
    background: #1a2e5a; color: #fff; padding: 8px 12px;
    text-align: left; font-weight: 600;
}
.summary-table th:nth-child(2),
.summary-table th:nth-child(3),
.summary-table th:nth-child(4) { text-align: center; width: 70px; }
.summary-table th:last-child { width: 160px; }

.summary-table td { padding: 7px 12px; border-bottom: 1px solid #eee; }
.summary-table tr:last-child td { border-bottom: none; }
.summary-table tr:hover td { background: #f9f9f9; }

.cnt-fail { color: #c0392b; font-weight: 700; text-align: center; }
.cnt-warn { color: #b7770d; font-weight: 700; text-align: center; }
.cnt-pass { color: #1e7e34; text-align: center; }
.cnt-zero { color: #bbb; text-align: center; }

.bar-wrap { display: flex; align-items: center; gap: 6px; }
.bar-track { flex: 1; height: 8px; background: #e8e8e8; border-radius: 4px; overflow: hidden; }
.bar-fill  { height: 100%; border-radius: 4px; }
.bar-good   .bar-fill { background: #28a745; }
.bar-medium .bar-fill { background: #ffc107; }
.bar-poor   .bar-fill { background: #dc3545; }
.bar-pct { font-size: 12px; color: #555; min-width: 32px; text-align: right; }

/* ── Module sections ── */
.module {
    background: #fff;
    border-radius: 10px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    overflow: hidden;
}
.module-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    border-bottom: 1px solid #eee;
    cursor: pointer;
    user-select: none;
}
.module-header:hover { background: #fafafa; }
.module-title { font-size: 15px; font-weight: 700; color: #1a2e5a; }
.module-badges { display: flex; gap: 6px; align-items: center; }
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}
.badge-fail { background: #fde8e8; color: #c0392b; }
.badge-warn { background: #fef9e7; color: #b7770d; }
.badge-pass { background: #eafaf1; color: #1e7e34; }
.badge-zero { background: #f0f0f0; color: #999; }
.chevron { font-size: 13px; color: #aaa; transition: transform .2s; }
.chevron.open { transform: rotate(180deg); }

.module-body { padding: 0 20px 16px; display: none; }
.module-body.open { display: block; }

.module-summary {
    font-size: 12px; color: #666; font-style: italic;
    padding: 10px 0 10px;
    border-bottom: 1px solid #f0f0f0;
    margin-bottom: 12px;
}

.all-pass {
    padding: 10px 0;
    color: #1e7e34;
    font-weight: 600;
    font-size: 13px;
}

/* ── Check table ── */
.check-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.check-table th {
    background: #f0f4fa; color: #1a2e5a;
    padding: 7px 10px; text-align: left;
    font-size: 12px; font-weight: 700;
    border-bottom: 2px solid #d0d8ea;
}
.check-table td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.check-table tr:last-child td { border-bottom: none; }

/* status column */
.status-cell { width: 60px; text-align: center; }
.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .4px;
}
.tag-fail { background: #fde8e8; color: #c0392b; border: 1px solid #f5c6cb; }
.tag-warn { background: #fef9e7; color: #b7770d; border: 1px solid #ffeeba; }
.tag-pass { background: #eafaf1; color: #1e7e34; border: 1px solid #c3e6cb; }

.row-fail td { background: #fffafa; }
.row-warn td { background: #fffef5; }
.row-pass td { background: #f9fdf9; }
.row-fail:hover td { background: #fff0f0; }
.row-warn:hover td { background: #fffde8; }

/* check name column */
.check-name { font-weight: 600; width: 200px; }
.check-count { font-size: 11px; color: #888; font-weight: 400; }

/* detail column */
.detail-cell { color: #333; }

/* pages column */
.pages-cell { width: 220px; }
.page-list { list-style: none; }
.page-list li { margin-bottom: 3px; }
.page-list a { color: #2c6fad; text-decoration: none; font-size: 11px; word-break: break-all; }
.page-list a:hover { text-decoration: underline; }
.view-more-btn {
    background: none; border: none; cursor: pointer;
    color: #2c6fad; font-size: 11px; padding: 2px 0;
    text-decoration: underline;
}
.view-more-btn:hover { color: #1a4f80; }
.hidden-pages { display: none; }
.hidden-pages.open { display: block; }

/* collapsed pass row */
.pass-row td {
    background: #f0faf3;
    color: #1e7e34;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
    padding: 7px;
}

/* ── Footer ── */
.footer {
    text-align: center;
    font-size: 12px;
    color: #aaa;
    padding: 24px;
    border-top: 1px solid #e0e0e0;
    margin-top: 12px;
}
"""

# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

JS = """
// Toggle individual module bodies
function toggleModule(id) {
    const body    = document.getElementById('body-' + id);
    const chevron = document.getElementById('chev-' + id);
    body.classList.toggle('open');
    chevron.classList.toggle('open');
}

// Toggle individual "view more" page lists
function togglePages(btnId, hiddenId) {
    const hidden = document.getElementById(hiddenId);
    const btn    = document.getElementById(btnId);
    if (hidden.classList.contains('open')) {
        hidden.classList.remove('open');
        btn.textContent = btn.dataset.more;
    } else {
        hidden.classList.add('open');
        btn.textContent = 'View less';
    }
}

// Expand all / Collapse all
function expandAll()  { document.querySelectorAll('.module-body').forEach(el => { el.classList.add('open'); }); document.querySelectorAll('.chevron').forEach(el => el.classList.add('open')); }
function collapseAll(){ document.querySelectorAll('.module-body').forEach(el => { el.classList.remove('open'); }); document.querySelectorAll('.chevron').forEach(el => el.classList.remove('open')); }

// Auto-open modules that have failures on page load
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.module-body').forEach(function(body) {
        if (body.dataset.hasfail === '1') {
            body.classList.add('open');
            const id = body.id.replace('body-', '');
            const chev = document.getElementById('chev-' + id);
            if (chev) chev.classList.add('open');
        }
    });
});
"""

# ---------------------------------------------------------------------------
# HTML builders
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _short_url(url: str, n: int = 60) -> str:
    return url if len(url) <= n else "…" + url[-(n-1):]


def _bar_class(pct: float) -> str:
    if pct >= 80: return "bar-good"
    if pct >= 50: return "bar-medium"
    return "bar-poor"


def _build_header(metadata: dict, score: dict) -> str:
    pct = score["score_pct"]
    if pct >= 80:
        cls, grade = "score-good", "Good"
    elif pct >= 60:
        cls, grade = "score-medium", "Needs Work"
    else:
        cls, grade = "score-poor", "Poor"

    crawled_pages = metadata.get("pages_crawled", "?")
    keyword = metadata.get("keyword") or "N/A"

    return f"""
<div class="header">
  <h1>SEO AUDIT REPORT</h1>
  <div class="meta">
    {_esc(metadata['url'])} &nbsp;|&nbsp; {_esc(metadata['date'])} &nbsp;|&nbsp;
    Pages crawled: {crawled_pages} &nbsp;|&nbsp; Keyword: {_esc(keyword)}
  </div>
  <div class="score-badge {cls}">{pct:.0f}<span style="font-size:24px">/100</span> &nbsp;{grade}</div>
  <div class="stats-row">
    <div class="stat-box stat-total"><div class="val">{score['total']}</div><div class="lbl">Total</div></div>
    <div class="stat-box stat-pass"> <div class="val">{score['passed']}</div><div class="lbl">Passed</div></div>
    <div class="stat-box stat-fail"> <div class="val">{score['failed']}</div><div class="lbl">Failed</div></div>
    <div class="stat-box stat-warn"> <div class="val">{score['warnings']}</div><div class="lbl">Warnings</div></div>
  </div>
</div>
"""


def _build_summary(all_results: dict) -> str:
    rows = ""
    for module_name, result in all_results.items():
        checks  = result.get("checks", [])
        n_fail  = sum(1 for c in checks if c["status"] == "fail")
        n_warn  = sum(1 for c in checks if c["status"] == "warning")
        n_pass  = sum(1 for c in checks if c["status"] == "pass")
        total   = len(checks)
        pct     = (n_pass / total * 100) if total else 0
        title   = MODULE_TITLES.get(module_name, module_name)
        bc      = _bar_class(pct)

        fc = f'<span class="cnt-fail">{n_fail}</span>' if n_fail else f'<span class="cnt-zero">0</span>'
        wc = f'<span class="cnt-warn">{n_warn}</span>' if n_warn else f'<span class="cnt-zero">0</span>'
        pc = f'<span class="cnt-pass">{n_pass}</span>'

        bar = f"""
<div class="bar-wrap {bc}">
  <div class="bar-track"><div class="bar-fill" style="width:{pct:.0f}%"></div></div>
  <span class="bar-pct">{pct:.0f}%</span>
</div>"""

        rows += f"""
<tr>
  <td>{_esc(title)}</td>
  <td style="text-align:center">{fc}</td>
  <td style="text-align:center">{wc}</td>
  <td style="text-align:center">{pc}</td>
  <td>{bar}</td>
</tr>"""

    return f"""
<div class="summary-section">
  <h2>Module Overview</h2>
  <div style="text-align:right;margin-bottom:8px">
    <button onclick="expandAll()" style="font-size:12px;padding:4px 10px;cursor:pointer;margin-right:6px">Expand all</button>
    <button onclick="collapseAll()" style="font-size:12px;padding:4px 10px;cursor:pointer">Collapse all</button>
  </div>
  <table class="summary-table">
    <thead>
      <tr>
        <th>Module</th><th>FAIL</th><th>WARN</th><th>PASS</th><th>Pass rate</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def _build_pages_cell(pages: list, count: int, uid: str) -> str:
    """Build the pages cell with individual view-more toggle."""
    if not pages:
        return ""

    visible   = pages[:3]
    remaining = pages[3:]

    visible_html = "".join(
        f'<li><a href="{_esc(p)}" target="_blank">{_esc(_short_url(p, 55))}</a></li>'
        for p in visible
    )

    if not remaining:
        extra = count - len(visible)
        suffix = f'<li style="color:#888;font-size:11px">+{extra} more occurrence(s)</li>' if extra > 0 else ""
        return f'<ul class="page-list">{visible_html}{suffix}</ul>'

    btn_id    = f"btn-{uid}"
    hidden_id = f"hid-{uid}"
    more_text = f"View {len(remaining)} more page(s)"

    hidden_html = "".join(
        f'<li><a href="{_esc(p)}" target="_blank">{_esc(_short_url(p, 55))}</a></li>'
        for p in remaining
    )
    extra_count = count - len(pages)
    extra_suffix = f'<li style="color:#888;font-size:11px">+{extra_count} more occurrence(s)</li>' if extra_count > 0 else ""

    return f"""
<ul class="page-list">
  {visible_html}
  <li>
    <button class="view-more-btn" id="{btn_id}"
            data-more="{_esc(more_text)}"
            onclick="togglePages('{btn_id}', '{hidden_id}')">{_esc(more_text)}</button>
    <ul class="page-list hidden-pages" id="{hidden_id}">
      {hidden_html}
      {extra_suffix}
    </ul>
  </li>
</ul>
"""


def _build_module(module_name: str, result: dict, idx: int) -> str:
    title   = MODULE_TITLES.get(module_name, module_name)
    checks  = result.get("checks", [])
    summary = result.get("summary", "")
    grouped = _group_checks(checks)

    n_fail = sum(1 for c in checks if c["status"] == "fail")
    n_warn = sum(1 for c in checks if c["status"] == "warning")
    n_pass = sum(1 for c in checks if c["status"] == "pass")

    # Badges
    fb = f'<span class="badge badge-fail">{n_fail} FAIL</span>' if n_fail else ""
    wb = f'<span class="badge badge-warn">{n_warn} WARN</span>' if n_warn else ""
    pb = f'<span class="badge badge-pass">{n_pass} pass</span>'
    if not n_fail and not n_warn:
        fb = wb = ""
        pb = '<span class="badge badge-pass">All passed</span>'

    actionable = [g for g in grouped if g["status"] in ("fail", "warning")]
    n_pass_grouped = sum(1 for g in grouped if g["status"] == "pass")
    has_fail = 1 if n_fail > 0 else 0

    # Build check rows
    if not actionable:
        body_inner = f'<div class="all-pass">✔ All checks passed.</div>'
    else:
        rows = ""
        for ri, g in enumerate(actionable):
            status = g["status"]
            tag_cls = "tag-fail" if status == "fail" else "tag-warn"
            tag_lbl = "FAIL"    if status == "fail" else "WARN"
            row_cls = "row-fail" if status == "fail" else "row-warn"

            count = g["count"]
            name  = _esc(g["name"])
            count_span = f' <span class="check-count">({count}×)</span>' if count > 1 else ""
            detail = _esc(g["detail"])

            uid = f"{idx}-{ri}"
            pages_html = _build_pages_cell(g["pages"], count, uid)

            rows += f"""
<tr class="{row_cls}">
  <td class="status-cell"><span class="tag {tag_cls}">{tag_lbl}</span></td>
  <td class="check-name">{name}{count_span}</td>
  <td class="detail-cell">{detail}</td>
  <td class="pages-cell">{pages_html}</td>
</tr>"""

        # Collapsed pass row
        pass_row = ""
        if n_pass_grouped > 0:
            pass_row = f'<tr class="pass-row"><td colspan="4">✔ {n_pass} check(s) passed</td></tr>'

        body_inner = f"""
<table class="check-table">
  <thead>
    <tr><th style="width:60px">Status</th><th style="width:200px">Check</th><th>Detail</th><th style="width:220px">Pages</th></tr>
  </thead>
  <tbody>{rows}{pass_row}</tbody>
</table>"""

    return f"""
<div class="module">
  <div class="module-header" onclick="toggleModule('{idx}')">
    <span class="module-title">{_esc(title)}</span>
    <span class="module-badges">
      {fb}{wb}{pb}
      <span class="chevron" id="chev-{idx}">▼</span>
    </span>
  </div>
  <div class="module-body" id="body-{idx}" data-hasfail="{has_fail}">
    <div class="module-summary">{_esc(summary)}</div>
    {body_inner}
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_html_report(all_results: dict, score: dict, metadata: dict, output_path: str) -> str:
    """Generate a self-contained HTML report. Returns the saved file path."""

    header  = _build_header(metadata, score)
    summary = _build_summary(all_results)

    modules_html = ""
    for idx, (module_name, result) in enumerate(all_results.items(), 1):
        modules_html += _build_module(module_name, result, idx)

    url_esc = _esc(metadata.get("url", ""))
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SEO Audit — {url_esc}</title>
<style>{CSS}</style>
</head>
<body>

{header}

<div class="container">
  {summary}
  {modules_html}
</div>

<div class="footer">
  SEO Audit Report &nbsp;|&nbsp; {url_esc} &nbsp;|&nbsp; {_esc(metadata.get('date', ''))}
</div>

<script>{JS}</script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
