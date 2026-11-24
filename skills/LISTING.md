# Agensi listing — Automatic SEO Audit (25 checks)

Upload: `skills/automatic-seo-audit.zip` at https://agensi.io/dashboard/submit
(one top-level folder `automatic-seo-audit/` with SKILL.md at its root).

## Basics
- **Name:** Automatic SEO Audit (25 checks)
- **Summary (one line):** Crawls a live site and runs 25 technical, on-page, AI-search (GEO) and live-backlink SEO checks, then hands you a prioritised fix list with HTML, DOCX and JSON reports.
- **Pricing:** Paid — **$0.10**. If the form rejects it (minimum price), choose **Free**.
- **Category / tags:** `marketing-seo` (also: `research-analysis`, `workflow-automation`)
- **Version:** 1.0
- **Keywords:** seo audit, technical seo, site audit, on-page seo, core web vitals, pagespeed, geo, ai search, llms.txt, backlinks, schema markup, robots.txt, sitemap, seo report, crawler

## Description
Automatic SEO Audit runs a real crawl of any website and scores it on **25 check modules (~250 individual checks)**, then has your agent turn the results into a short, prioritised action plan instead of a wall of warnings.

**What it checks**
- **Technical:** HTTPS and certificate expiry, security headers, redirects (chains, loops, 301 vs 302), robots.txt, XML sitemaps (incl. sitemap indexes), canonicals, hreflang, pagination, crawl errors (4xx/5xx, soft 404s, orphan candidates), custom 404 pages.
- **On-page and content:** titles, meta descriptions, headings, word count, keyword or phrase density, duplicate content, readability, images (alt, size, WebP, lazy loading), internal and external links.
- **Performance:** server response time, page weight, render-blocking resources, caching and compression. Add a free Google PageSpeed key to get real Core Web Vitals (LCP, CLS, INP, FCP).
- **Structured data and social:** JSON-LD validation (including `@graph`), Open Graph and Twitter cards.
- **NEW: AI search / GEO readiness:** llms.txt, whether robots.txt blocks ChatGPT/Perplexity/Claude search crawlers, content visible without JavaScript, FAQ structure, entity schema with sameAs, author and freshness signals, nosnippet directives.
- **NEW: live backlink data:** referring domains, total backlinks, authority, spam score, link diversity and broken backlinks, fetched with Agensi's backlink tool (about $0.02–0.03 per audit, approved by you). No API account needed.

**Output:** a 0–100 score, the top fixes with affected pages and exact remedies, and reports in `seo-reports/`: an interactive HTML report, a client-ready DOCX (A4, colour-coded) and machine-readable JSON.

Runs locally in your agent with Python. The engine installs into a temporary virtual environment inside your project, which is removed afterwards. Open source: https://github.com/Greninja110/Automatic-SEO

## Use cases
- Audit your own site before a launch or redesign
- Produce a client-ready SEO report (DOCX) for an agency or freelance client
- Find out why pages aren't indexed or ranking (noindex, robots blocks, broken canonicals, 4xx/5xx)
- Check whether AI search engines (ChatGPT, Perplexity, Claude, Google AI Overviews) can read and cite your site
- Track SEO health over time from the JSON output
- Get real backlink numbers without paying for an Ahrefs or Semrush subscription

## Sample input
> Audit https://example-bakery.com for SEO, target keyword "sourdough bread delivery", and give me the top fixes.

## Sample output
> **SEO score: 64/100.** Solid technical base, but content and AI-search signals are holding it back (12 pages crawled).
>
> **Top fixes**
> 1. **Duplicate titles on 7 of 12 pages:** every product page uses "Example Bakery". Give each one a unique title of 60 characters or fewer, e.g. "Sourdough Bread Delivery in Leeds | Example Bakery".
> 2. **No meta descriptions on 9 pages:** add 140–160 character descriptions that include "sourdough bread delivery".
> 3. **robots.txt blocks OAI-SearchBot and PerplexityBot:** the site can't be cited in ChatGPT or Perplexity answers. Remove those `Disallow: /` lines.
> 4. **Homepage hero image is 1.8 MB (LCP risk):** convert it to WebP at 1600px or less (≈200 KB) and add width and height attributes.
> 5. **No sitemap.xml:** generate one and add `Sitemap: https://example-bakery.com/sitemap.xml` to robots.txt.
> 6. …
>
> **AI search:** no llms.txt, and no FAQ or Organization schema. **Backlinks:** 23 referring domains, authority 18/100, spam score 4.
> Reports: `seo-reports/example-bakery.com-audit.html`, `.docx`, `.json`.

## Usage example
"Run an SEO audit on https://mysite.com" — or with options: "Audit mysite.com, crawl 100 pages, keyword 'vegan protein powder', and include a Word report for my client."

## FAQ
1. **Do I need any API keys?**
   No. Everything runs without keys. A free Google PageSpeed Insights key (set `PAGESPEED_API_KEY`) adds real Core Web Vitals. The backlink check uses Agensi's own data tool, which you approve per call (about $0.02–0.03).
2. **What do I need installed?**
   Python 3.10 or newer. The skill creates a temporary virtual environment in your project and removes it when done.
3. **Does it render JavaScript?**
   No. It reads the HTML your server sends, which is also what most AI crawlers see. Pages that only exist after client-side rendering are flagged in the AI-readiness check.
4. **How long does an audit take?**
   About 15–60 seconds for 25 pages. Full-site crawls (depth 2, 100+ pages) take a few minutes.
5. **Which sites can I audit?**
   Only sites you own or are authorised to test. The crawler is polite by default (10 connections, a delay between crawl levels) and identifies itself as SEOAuditBot.
6. **Can I get a report for a client?**
   Yes. Ask for DOCX and you get an A4 landscape Word report with colour-coded tables, ready to brand and send.
7. **Is the backlink check required?**
   No. If you skip it, check 25 is marked "not supplied" and the other 24 modules run as normal.
8. **Which agents does it work with?**
   Any agent that can run terminal commands and Python: Claude Code, Codex, Cursor, Gemini CLI.

## Known limitations
No JavaScript rendering. URLs with query strings are not crawled. Large sites are sampled with `--max-pages`, and link-heavy modules sample the first 10 pages. Core Web Vitals are estimates unless a PageSpeed key is set. Mobile, accessibility and contrast checks are HTML heuristics, not a full browser or WCAG audit.

## Requirements
- Python 3.10+
- Terminal access
- Internet access

**Optional:** Google PageSpeed API key; Agensi backlink tool

**Requirement note:** On Windows, use `venv\Scripts\python` instead of `venv/bin/python`. The skill explains this.

## Permissions to declare
- **Tools:** terminal, file_read, file_write, network, env_vars
- **Hosts:** the website being audited (any domain the user gives); `www.googleapis.com` (PageSpeed Insights, only with a key)
- **File scopes:** `.seo-audit-tmp/` (temporary: engine and virtual environment, deleted at the end), `seo-reports/` (output reports)
- **Notes:** Reads the optional `PAGESPEED_API_KEY` environment variable. Installs requests, aiohttp, beautifulsoup4, lxml, python-docx, python-dotenv and certifi into a local virtual environment only (never globally). Fetches no code at runtime.

## Agensi tools to enable
`agensi:web.backlinks.summary`

## Compatibility note
Claude Code, Codex, Cursor and Gemini CLI, or any agent with terminal access and Python 3.10+.

## Support / docs
- **Docs:** https://github.com/Greninja110/Automatic-SEO
- **Support:** GitHub issues at https://github.com/Greninja110/Automatic-SEO/issues
