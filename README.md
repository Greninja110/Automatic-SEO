# SEO Audit Tool

An asynchronous, comprehensive Technical and On-Page SEO Audit Tool that crawls websites, runs 23 different SEO checks, and generates detailed reports in HTML and DOCX formats. Supports both a **Web GUI** (`app.py`) and a **CLI** (`main.py`).

---

## Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Web GUI** | `python app.py` | Opens a browser-based dashboard with real-time progress, live log streaming, and download buttons |
| **CLI** | `python main.py --url <url>` | Classic terminal mode — same engine, outputs to `reports/` |

---

## Features

- **Web GUI** (`app.py`) — Full browser-based interface:
  - Single URL or batch (multi-line) URL input
  - All crawl settings controllable via sliders (depth, max pages, delay, concurrency)
  - Target keyword and PageSpeed API key fields
  - Per-module selection: pick any of the 23 checks individually, or filter by site-wide / per-page scope
  - Report format selection: DOCX, HTML, or both
  - Real-time log stream — every print from the crawl and all check modules appears live
  - Live progress bar showing X/Y modules completed with % indicator
  - "Currently Running" indicator showing the active module name, scope, and result badge
  - Score ring animation with pass/fail/warn breakdown
  - Module result grid — click any card to see detailed findings
  - One-click download buttons for generated reports
  - Previous reports history panel

- **Asynchronous Crawling:** BFS crawler using `aiohttp`/`asyncio` with configurable concurrency, delay, and depth.
- **23 Comprehensive SEO Checks:** Site-wide and per-page modules covering all major SEO dimensions.
- **Dual Reporting:** Generates `.docx` (A4 landscape, colour-coded tables) and `.html` (self-contained, interactive) reports.
- **PageSpeed Integration:** Real Core Web Vitals via Google PageSpeed Insights API (falls back to heuristics).
- **Batch Auditing:** Audit multiple URLs at once via the GUI or via `targets.txt` in CLI mode.

---

## The 23 SEO Checks

### 1. Technical & Architecture
1. **HTTPS Security** — TLS validation, mixed-content detection
2. **XML Sitemap** — existence, structure, URL count
3. **Robots.txt** — syntax, crawl directives, disallow rules
4. **URL Structure** — length, casing, underscores, trailing slashes
5. **Pagination & Canonicals** — `rel="canonical"` validity, duplicate prevention
6. **Technical SEO** — viewport, base tags, iframe dimensions

### 2. Performance & Vitals
7. **Page Speed** — PageSpeed Insights API, render-blocking resources, caching headers
8. **Core Web Vitals** — LCP, FID, CLS estimates
9. **Mobile Friendliness** — viewport meta, tap-target sizes

### 3. Content & On-Page
10. **Headings** — H1–H6 hierarchy, duplicate H1 detection
11. **Meta Tags** — title/description length, keyword relevance
12. **Content Quality** — word count, text-to-HTML ratio, keyword density, readability
13. **Content Accessibility** — ARIA roles, lang attribute, semantic tags
14. **Image Optimization** — alt text, lazy loading, format hints

### 4. Linking & Navigation
15. **Internal Linking** — click depth, anchor diversity, orphan pages
16. **External Links** — reachability, nofollow usage
17. **Backlinks & Authority** — external reference surface indicators

### 5. Crawler Integrity
18. **Crawl Errors** — 4xx/5xx status codes, noindex directives
19. **Error Pages** — 404 correctness, soft-404 detection
20. **Redirects** — redirect chains, loops, 301 vs 302 usage

### 6. Metadata & Tracking
21. **Structured Data** — JSON-LD / Microdata presence and format
22. **Social OpenGraph** — `og:` tags, Twitter Cards, share preview data
23. **Analytics Tracking** — Google Analytics, GTM embed detection

---

## Prerequisites

- Python 3.10+
- Dependencies in `requirements.txt`:
  - `requests`, `aiohttp`, `beautifulsoup4`, `lxml`
  - `python-docx`, `python-dotenv`, `certifi`
  - `flask` *(for Web GUI only)*

---

## Installation

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure PageSpeed API key (optional)
echo "PAGESPEED_API_KEY=your_key_here" > .env
```

---

## Usage

### Web GUI (recommended)

```bash
python app.py
# → Opens http://localhost:5000 in your browser automatically
```

- Enter a URL (or switch to multi-URL mode for batch audits)
- Adjust crawl depth, max pages, delay, and concurrency via sliders
- Optionally enter a target keyword and PageSpeed API key
- Select which of the 23 modules to run (defaults to all)
- Choose DOCX and/or HTML report format
- Click **Run Audit** — watch the live log and progress bar
- When complete, click **Download** to save the report

### CLI

```bash
# Single URL
python main.py --url https://example.com

# Deep crawl with keyword
python main.py --url https://example.com --depth 3 --max-pages 100 --keyword "seo tool"

# Batch from targets.txt (one URL per line, # to skip)
python main.py

# Full options
python main.py --url URL --depth N --max-pages N --delay 0.3 --concurrency 10 --keyword "kw" --output filename
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--url` | — | Single URL (overrides `targets.txt`) |
| `--depth` | 1 | Crawl depth from start URL |
| `--max-pages` | 0 | Max pages per site (0 = unlimited) |
| `--delay` | 0.3 | Seconds between requests |
| `--concurrency` | 10 | Async connections |
| `--keyword` | — | Target keyword for density checks |
| `--output` | auto | Output filename prefix |

---

## Project Structure

```
SEO/
├── app.py                  # Flask Web GUI (run this for the browser interface)
├── main.py                 # CLI entry point
├── report_generator.py     # DOCX report builder
├── report_generator_html.py# HTML report builder
├── requirements.txt
├── .env                    # PAGESPEED_API_KEY=...
├── targets.txt             # Batch URLs for CLI mode (one per line)
├── reports/                # Generated reports saved here
├── checks/
│   ├── __init__.py         # ALL_CHECKS registry, MODULE_TITLES, SITE_WIDE_CHECKS
│   └── check_*.py          # 23 individual check modules
├── templates/
│   └── index.html          # Web GUI HTML template
└── static/
    ├── css/style.css       # Dark theme stylesheet
    └── js/app.js           # Frontend logic (SSE, progress, results rendering)
```

---

## How It Works

1. **Target Loading** — GUI collects form inputs; CLI resolves `--url`, `targets.txt`, or `main.py` variable.
2. **Async BFS Crawl** — `aiohttp` fetches pages concurrently up to the configured depth and page limit.
3. **Check Modules** — Each module receives `(url, soup, response, **shared_state)` and returns a list of `{name, status, detail, page}` check results.
4. **Scoring** — `pass / total * 100` gives the SEO score out of 100.
5. **Report Generation** — Results are written to `.docx` (colour-coded tables) and/or `.html` (interactive, self-contained) in the `reports/` folder.
6. **Web GUI Live Streaming** — Audit runs in a background thread; all `print()` output is intercepted by a thread-aware stdout wrapper and streamed to the browser via SSE (Server-Sent Events).
