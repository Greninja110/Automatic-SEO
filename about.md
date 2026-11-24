# About — Automatic SEO: from side project to a paid AI-agent skill

**Date:** 24 November 2026
**Live listing:** https://agensi.io/skills/automatic-seo-audit ($1, version 1.0, security review: approved)
**Source code:** https://github.com/Greninja110/Automatic-SEO

This file records what was done in one working session: a 7–8-month-old SEO audit project was
cleaned up, debugged, sped up, extended from 23 to 25 checks, given a new interface, packaged as a
skill for AI agents (Claude Code, Codex, Cursor, Gemini CLI) and published for sale on the Agensi
marketplace.

---

## 1. How it started

The day began with an email from **Agensi.io**, a marketplace where developers sell *skills*
(packaged instructions, optionally with scripts) for AI agents. They had found Automatic-SEO on
GitHub and suggested listing it. The main points of their offer:

- Listing is free; the creator sets the price (from $1) or lists for free.
- The creator keeps **70%** of each sale. Agensi takes 30% and handles payments, tax and refunds.
- Skills can call **4,500+ tools on Agensi's API keys**, including DataForSEO, Google results and
  backlink data. Buyers approve the price of each call, so they need no API accounts of their own.
- They report about 150,000 visitors a month and 20,000+ users.

Before committing, we read their creator documentation: the SKILL.md format, the security scan,
payouts and review process. These points stood out:

- Every listing passes an automated 8-point security scan, an AI review and a human review
  (usually 24–48 h).
- Scripts are allowed but must be readable, must not install packages globally, and must not
  download code at runtime.
- Refunds under the money-back guarantee have no time limit and are taken from future payouts.
- Agensi takes a *licence to distribute* the skill; the creator keeps ownership.

## 2. Housekeeping

- Moved the non-code documents (college chapter notes, diagram notes, colour notes,
  `rules.docx`, `report.docx`, extracted text) into **`assets/`** and added `assets/` to
  `.gitignore`.
- Found that the Agensi connector, already connected to claude.ai, syncs into Claude Code
  automatically. No separate MCP install was needed, only a restart for its tools to load.

## 3. Code review: bugs found and fixed

Every check module was read and a baseline audit was run before changing anything. Each fix
below was confirmed with a before/after run.

| Area | Bug | Effect before the fix |
|---|---|---|
| Crawler | Response object had no redirect `history` | **Redirects module (13) crashed on every audit** and showed a single "Module error" |
| Crawler | Response time hard-coded to `0` | TTFB check **always passed with "0.00s"** |
| Crawler | Headers stored in a plain, case-sensitive dict | Sites sending lowercase headers (Cloudflare, Vercel) were wrongly reported as missing HSTS, caching and similar headers |
| PageSpeed | API called twice per audit (modules 9 and 19), URL not encoded, errors hidden | Doubled quota use; an **invalid API key** was reported only as "no score found" |
| Content | Keyword density compared single words | Multi-word keywords like "humic acid" were **never found** |
| Content | `alt=""` (valid for decorative images) counted as a failure | Contradicted the Image module |
| Structured data | `@graph` ignored; a list-valued `@type` crashed the module | Most WordPress (Yoast, Rank Math) sites were misread |
| robots.txt | Consecutive `User-agent:` lines not grouped | Rules were applied to the wrong bots |
| Canonicals | Relative canonical URLs compared as raw text | False "canonical points elsewhere" warnings |
| HTTPS | Only 301/302 accepted as HTTP→HTTPS redirects | 307/308 redirects were reported as failures |
| Crawl errors | Orphan check used only the homepage's links, plus dead code | False orphan warnings |
| Meta tags | Length checked before the empty case | Empty descriptions shown as "slightly long: 0 chars" |
| Sitemap | `Sitemap:` line in robots.txt ignored; sitemap indexes not expanded | Missed sitemaps that live at non-default paths |
| Crawl order | Links collected into a `set` | `--max-pages` picked a different, random set of pages on every run |
| Web GUI | Listened on `0.0.0.0` | Crawler and PageSpeed key exposed to everyone on the local network; now `127.0.0.1` by default (`SEO_GUI_HOST` to change) |
| Web GUI | Finished jobs never removed from memory | Memory grew with every audit; jobs now expire after an hour |
| Packaging | `requirements.txt` saved as UTF-16 | Could fail to install with pip |

## 4. Speed: 77 s → 16 s for the same 12-page audit (about 5×)

- **`checks/_http.py`** (new) adds a per-audit **cached HTTP session**. Navigation links, images,
  robots.txt, sitemaps and PageSpeed are fetched once per audit instead of once per module and page.
- Link, image and status checks now run **in parallel** (`parallel_map`) instead of one at a time.
- Crawl-error and error-page modules **reuse the status codes the crawler already recorded**
  instead of requesting every page again.
- Faster text extraction in the Content module (no longer re-parses the whole page).
- The crawler pauses once per crawl level, not after every page.
- The web GUI and the CLI now share **one check runner**; previously the GUI kept its own copy,
  which had drifted.

Outside the intended bug fixes, results matched the original code module by module.

## 5. Two new checks: 23 → 25

**24. AI Search / GEO readiness**, about being found and quoted by ChatGPT, Perplexity, Claude and
Google AI Overviews:

- `llms.txt` present and well-formed
- robots.txt access for AI *search* crawlers (OAI-SearchBot, ChatGPT-User, PerplexityBot,
  Claude-SearchBot/User), which fails if blocked
- AI *training* crawlers (GPTBot, ClaudeBot, Google-Extended, CCBot), reported for information only
- Content readable without JavaScript
- FAQ / Q&A structure
- Organization/Person schema with `sameAs` links
- Author and date (freshness) signals
- `nosnippet` / `max-snippet:0` directives

**25. Backlinks (Live Data)** scores real inbound-link data supplied with `--backlinks-json`. In the
skill, the agent fetches it with Agensi's `agensi:web.backlinks.summary` tool for about
$0.02–0.03. Checks: referring domains, total backlinks, links per domain, authority, spam score,
nofollow share, IP diversity and broken backlinks. It accepts the field names of several
providers. Without data the module is marked "not supplied" and the other 24 still run.

## 6. New CLI options

| Flag | Purpose |
|---|---|
| `--format docx,html,json` | Choose report formats |
| `--json` | Shorthand to add the machine-readable JSON report |
| `--output-dir DIR` | Where reports are written |
| `--backlinks-json FILE` | Live backlink data for check 25 |

The JSON report (`score`, `metadata`, `modules[].checks[]`) is what an AI agent reads to write its
summary.

## 7. New web GUI: the inspection board

Redesigned with the *frontend-design* skill, around the idea of a site **inspection sheet**:

- A **5×5 board, one square per check**. Each square lights up while its check runs and fills in
  green, ochre or red as results arrive. Afterwards you can click it to see the findings.
- Calm survey-paper palette (paper `#EEF2EC`, navy ink `#16263A`, survey green, ochre, red
  pencil) and the *Archivo* typeface, using its width axis for the big numbers.
- Score shown as a large figure with a highlighter mark and a pass/warn/fail bar.
- JSON added as a report format; the layout works on phones; keyboard focus and reduced motion
  are supported.
- Verified with headless-browser screenshots of a real audit.

## 8. Packaging the Agensi skill

**Package:** `skills/automatic-seo-audit/`, uploaded as `skills/automatic-seo-audit.zip` (33 files,
about 281 KB).

```
automatic-seo-audit/
├── SKILL.md              ← instructions the buyer's agent follows
├── references/checks.md  ← what each of the 25 modules measures
└── scripts/              ← the full audit engine (no web GUI)
    ├── main.py, report_generator.py, report_generator_html.py, requirements.txt
    └── checks/  (25 modules + _http.py)
```

What `SKILL.md` tells the agent to do:

1. Ask for the URL and optional keyword, crawl size and formats.
2. Copy the scripts into `.seo-audit-tmp/` and install the dependencies into a local virtual
   environment, never globally.
3. Optionally fetch live backlink data through Agensi, with the buyer approving the price.
4. Run the audit and read the JSON report.
5. Report the score, the **top 10 fixes** (blockers first, with affected pages and exact remedies),
   AI-search readiness and backlinks.
6. Delete the temporary folder and keep `seo-reports/`.

Checks before upload:

- A simulated buyer run from a clean folder with no `.env`.
- The hard-coded `target_website` cleared in the packaged `main.py`.
- **Secret scan of the ZIP:** no `.env`, no API keys or tokens (the real PageSpeed key was searched
  for explicitly), no personal details or local paths.

## 9. The listing

- **Name:** Automatic SEO Audit (25 checks), category *Marketing & SEO*
- **Price:** **$1**, the marketplace minimum ($0.10 was not allowed). The creator receives about
  $0.70 per sale.
- **Payouts:** connected through **Zoneless** (USDC on Solana), because Stripe Connect does not
  support India. Income is reported personally; crypto income in India falls under the VDA rules
  (30% tax plus 1% TDS), which should be confirmed with a CA.
- **Listing text:** description, use cases, sample input and output, 8-question FAQ, known
  limitations, requirements and declared permissions (terminal, files, network, env vars). Kept in
  `skills/LISTING.md`.
- **Logo:** `skills/logo/logo-512.png`, the inspection board enlarged to 16×16 with **SEO** spelled
  in green squares and one warning and one failure in the corner.
- **Screenshots:** `skills/screenshots/` contains 5 views from a real audit of abhijeetsahoo.in:
  finished board, live progress, score and results, check details, and the HTML report.
- **Review:** passed the security scan and review, and is **live**.

### Why $1 is fair here

Most SEO skills on Agensi ship only a `SKILL.md`: instructions that ask the agent to look at a page
and give an opinion. This skill ships the **complete working engine**, about 280 KB of tested
Python: an async crawler, 25 check modules, three report generators and live backlink data. The
agent runs real measurements and reports numbers instead of guessing. The code is also open source
on GitHub, so the $1 pays for the convenience of a ready-made, maintained agent workflow, not for
access to secrets.

## 10. Update 1.1 (same day)

- Removed every hard-coded website from the engine: the old default target (`openai.com`), a
  made-up project URL in the crawler's User-Agent (now just `SEOAuditBot/2.0`), an Ahrefs link in
  check 23's advice (it now points to check 25), and leftover client keyword examples.
- Fixed a crash on Windows when an AI agent runs the engine and captures its output: the console's
  cp1252 encoding could not print `→` or `✓`. Output is now forced to UTF-8.
- Rebuilt and re-tested the package as a buyer would, then shipped it as version 1.1.

## 11. Where things are

| Path | What |
|---|---|
| `main.py`, `app.py`, `checks/` | The audit engine and web GUI (fixed, faster, 25 checks) |
| `checks/_http.py` | Cached session, parallel helpers, shared PageSpeed call |
| `checks/check_ai_search_readiness.py` | Check 24 |
| `checks/check_backlinks_live.py` | Check 25 |
| `templates/`, `static/` | Redesigned GUI |
| `skills/automatic-seo-audit/` | Skill source (SKILL.md and reference) |
| `skills/LISTING.md` | All listing text |
| `skills/logo/`, `skills/screenshots/` | Marketplace images |
| `assets/` | Project documents (git-ignored) |

## 12. Follow-ups

- [ ] Create a new **Google PageSpeed API key**. The one in `.env` is rejected by Google, so real
      Core Web Vitals have never been used. Delete the old key in Google Cloud.
- [ ] When the engine changes, rebuild the ZIP and ship it with Agensi's `update_skill`. The live
      version keeps serving buyers while the update is reviewed.
- [ ] Watch uses, ratings and feedback (`my_skills`) and answer buyer questions through the
      GitHub issues.
