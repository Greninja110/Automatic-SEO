---
name: automatic-seo-audit
description: Crawls a live website and runs 25 technical, on-page, AI-search (GEO) and backlink SEO checks, then turns the results into a prioritised fix list with a 0-100 score and HTML/DOCX/JSON reports. Use when the user asks to audit, check or score a website's SEO, find why a site isn't ranking, or prepare an SEO report for a client.
---

# Automatic SEO Audit (25 checks)

You run a real crawl-based SEO audit with the bundled Python engine, then explain the
results as a prioritised action plan. The engine does the measuring; your job is to run it
correctly and turn ~1,000+ raw check results into the handful of fixes that matter.

## 1. Collect inputs

Ask only for what is missing:

| Input | Default | Notes |
|---|---|---|
| Website URL | — (required) | Only audit sites the user owns or is authorised to test. |
| Target keyword | none | A word or phrase, e.g. `humic acid fertilizer`. Enables density checks. |
| Crawl size | depth 1, 25 pages | Raise to depth 2 / 100 pages for a full-site audit (slower). |
| Report formats | `json,html` | Add `docx` when the user wants a client-ready Word report. |

## 2. Set up the engine (once per run)

Requires Python 3.10+. Work in a temporary folder inside the user's current project and keep
everything there — never install packages globally.

1. Write every file under this skill's `scripts/` folder, unchanged and with the same relative
   paths, into `.seo-audit-tmp/` (e.g. `scripts/checks/check_meta_tags.py` →
   `.seo-audit-tmp/checks/check_meta_tags.py`).
2. Create a virtual environment and install the pinned dependencies into it:

```bash
python3 -m venv .seo-audit-tmp/venv
.seo-audit-tmp/venv/bin/pip install -q -r .seo-audit-tmp/requirements.txt
```

On Windows use `python -m venv .seo-audit-tmp\venv` and `.seo-audit-tmp\venv\Scripts\pip` /
`...\Scripts\python` in the commands below.

## 3. Live backlink data (check 25) — optional, uses an Agensi tool

Check 25 scores the domain's real backlink profile. If the Agensi tools are available in this
session, fetch the data before running the audit:

1. Call `skill_tools` for this skill, then `quote_tool` with tool
   `agensi:web.backlinks.summary` and request `{"body": {"target": "<bare domain, e.g. example.com>"}}`.
2. Follow the quote's instructions (run it, or tell the user the price — about $0.02–0.03 —
   and wait for approval).
3. Save the tool's JSON answer exactly as returned to `.seo-audit-tmp/backlinks.json`.

If the tools are unavailable or the user declines, skip this step — check 25 is then reported
as "not supplied" and everything else still runs.

## 4. Run the audit

```bash
.seo-audit-tmp/venv/bin/python .seo-audit-tmp/main.py \
  --url https://example.com \
  --depth 1 --max-pages 25 \
  --format json,html \
  --output-dir seo-reports \
  --output example.com-audit
  # optional: --keyword "target phrase"
  # optional: --backlinks-json .seo-audit-tmp/backlinks.json
```

A 25-page audit typically takes 15–60 seconds. Progress lines start with `[CHECK n/25]`.
If the PageSpeed Insights key is set in the environment as `PAGESPEED_API_KEY`, real Core Web
Vitals are included; otherwise the speed checks use HTML heuristics (say so in your summary).

## 5. Analyse `seo-reports/<name>.json`

Structure:

```
{ "score": {"score_pct", "passed", "failed", "warnings", "total"},
  "metadata": {"url", "pages_crawled", "pages_list", "keyword", ...},
  "modules": { "<module>": { "title", "scope", "summary", "pass", "fail", "warning",
                             "checks": [ {"name", "status", "detail", "page"} ] } } }
```

`status` is `pass`, `fail` or `warning`. Per-page modules repeat the same check for each page —
group identical check names and count the affected pages instead of listing each one.

Prioritise in this order:

1. **Blockers** — anything that stops indexing or crawling: robots.txt blocking, noindex,
   5xx/4xx pages, broken canonicals, HTTPS/certificate failures, client-rendered pages with no
   server HTML, AI search crawlers blocked.
2. **High impact** — missing/duplicate titles, H1s and meta descriptions, thin content,
   broken internal links, missing sitemap, slow server response, Core Web Vitals fails,
   very few referring domains.
3. **Quick wins** — alt text, Open Graph tags, llms.txt, schema (Organization, FAQ,
   Breadcrumb), author/date signals, security headers.
4. **Informational** — leave out unless the user asks.

See `references/checks.md` for what each of the 25 modules measures and which are heuristics.

## 6. Report back

Reply with:

- The score (`score_pct`/100) and one sentence on overall health.
- **Top fixes**: up to 10, most important first. For each: the problem, how many pages it
  affects (with 1–2 example URLs), and the concrete fix (exact tag, header or setting).
- **AI search (GEO) readiness** and **backlinks** in two short lines each.
- Paths of the generated reports in `seo-reports/`.

Be precise: quote the measured values from `detail`. Don't call a heuristic a measurement
(e.g. "LCP proxy" is an estimate unless PageSpeed data is present).

## 7. Clean up

Delete `.seo-audit-tmp/` (scripts, virtual environment, backlink file). Keep `seo-reports/`.

## Limits

- No JavaScript rendering: content injected only by client-side JS is not seen (the audit flags
  this in check 24).
- Query-string URLs are not crawled; large sites are sampled by `--max-pages`.
- Some link checks sample the first 10 pages / 10 links per page to keep runs fast.
- Be polite: keep the default `--concurrency 10` and `--delay 0.3`; lower them for small or
  fragile sites.
