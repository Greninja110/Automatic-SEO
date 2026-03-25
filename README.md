# SEO Audit Tool

An asynchronous, comprehensive Technical and On-Page SEO Audit Tool that crawls websites, runs 23 different SEO checks, and generates detailed reports in HTML and DOCX formats.

## Features

- **Asynchronous Crawling:** Fast and efficient BFS crawling using `aiohttp` and `asyncio`, with configurable concurrency, delay, and depth.
- **23 Comprehensive SEO Checks:** Includes a wide variety of site-wide and page-level tests:
  - Technical SEO, Core Web Vitals, and Page Speed
  - Content Quality, Accessibility, and Structure (Headings, Meta Tags)
  - Image Optimization
  - Analytics Tracking, Social OpenGraph (OG), and Structured Data (JSON-LD)
  - Redirects, Internal/External linking, XML Sitemap, Robots.txt, HTTPS security, and more.
- **Dual Reporting:** Generates detailed audit reports in both HTML and DOCX formats.
- **Configurable Targets:** Audit single URLs from the CLI, set a default inside `main.py`, or batch audit multiple websites sequentially via a `targets.txt` file.
- **PageSpeed Integration:** Computes core metrics via the Google PageSpeed Insights API (when `.env` is configured), falling back to heuristics when unavailable.

## The 23 SEO Checks in Detail

The tool runs a comprehensive suite of 23 diagnostic modules located under the `checks/` directory.

### 1. Technical & Architecture
1. **HTTPS Security (`check_https_security.py`)**: Ensures all pages are served over a secure TLS connection and flags mixed content.
2. **XML Sitemap (`check_xml_sitemap.py`)**: Validates the existence, structure, and readability of `sitemap.xml`.
3. **Robots.txt (`check_robots_txt.py`)**: Checks the health and syntax of `robots.txt` instructions and crawl directives.
4. **URL Structure (`check_url_structure.py`)**: Analyzes URLs for best formatting practices: length, trailing slashes, absence of underscores, and lowercase characters.
5. **Pagination & Canonicals (`check_pagination_canonicals.py`)**: Validates `rel="canonical"` tags to prevent duplicate content, and checks pagination links.
6. **Technical SEO (`check_technical_seo.py`)**: Catches missing base tags, viewport configurations, and missing iframe dimensions.

### 2. Performance & Vitals
7. **Page Speed (`check_page_speed.py`)**: Utilizes PageSpeed Insights API (when configured) to audit page load times and evaluate render-blocking resources.
8. **Core Web Vitals (`check_core_web_vitals.py`)**: Measures and estimates critical metrics like Largest Contentful Paint (LCP), First Input Delay (FID), and Cumulative Layout Shift (CLS).
9. **Mobile Friendliness (`check_mobile_friendliness.py`)**: Evaluates viewport meta tags and tap-target sizing for optimal mobile indexing and experience.

### 3. Content & On-Page
10. **Headings (`check_headings.py`)**: Ensures a proper multi-level hierarchy (H1, H2, H3) and identifies missing or duplicate H1 tags.
11. **Meta Tags (`check_meta_tags.py`)**: Scrutinizes `<title>` and `<meta name="description">` tags for optimal lengths and keyword relevance.
12. **Content Quality (`check_content_quality.py`)**: Estimates word counts, text-to-HTML ratios, primary keyword density, and overall content depth.
13. **Content Accessibility (`check_content_accessibility.py`)**: Examines semantic tags and basic WCAG criteria such as ARIA roles and language tagging.
14. **Image Optimization (`check_image_optimization.py`)**: Verifies the implementation of descriptive `alt` text on all `<img>` elements and optimized file formats.

### 4. Linking & Navigation
15. **Internal Linking (`check_internal_linking.py`)**: Evaluates click-depth, anchor text, and overall internal distribution of PageRank.
16. **External Links (`check_external_links.py`)**: Validates outbound links are reachable and checks for `rel="nofollow"` spam protections.
17. **Backlinks Authority (`check_backlinks_authority.py`)**: Provides surface-level external reference counts to estimate domain authority strength.

### 5. Crawler Integrity & Stability
18. **Crawl Errors (`check_crawl_errors.py`)**: Records 4xx/5xx HTTP status codes actively and evaluates page indexability directives (`noindex`).
19. **Error Pages (`check_error_pages.py`)**: Validates that random/incorrect URLs correctly generate a 404 response rather than soft-404s.
20. **Redirects (`check_redirects.py`)**: Audits redirect loops, redirect chains, and overuse of 302 vs 301 redirects.

### 6. Optimization & Metadata
21. **Structured Data (`check_structured_data.py`)**: Validates the presence and format of rich-snippet `JSON-LD` or `Microdata` markup.
22. **Social OpenGraph (`check_social_opengraph.py`)**: Ensures social media share previews populate images, titles, and descriptions correctly using OpenGraph (`og:`) and Twitter-card properties.
23. **Analytics Tracking (`check_analytics_tracking.py`)**: Confirms that common web analytics tracking snippets (Google Analytics, GTM, etc.) are correctly embedded.

## Prerequisites

- Python 3.8+
- Dependencies listed in `requirements.txt`:
  - `requests`
  - `aiohttp`
  - `beautifulsoup4`
  - `lxml`
  - `python-docx`
  - `python-dotenv`
  - `certifi`

## Installation

1. Clone or download this project.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up the environment variables:
   - Create a `.env` file in the root directory (or use the existing one).
   - Add your Google PageSpeed API key:
     ```env
     PAGESPEED_API_KEY=your_pagespeed_api_key_here
     ```

## Usage

### 1. Quick Ad-hoc Audit
You can audit a single URL directly from the terminal by passing the `--url` argument:
```bash
python main.py --url https://example.com/
```

### 2. Auditing Multiple Sites
Add URLs to `targets.txt` (one per line). To skip a site, prepend `#` to its line.
Then run the script without any target arguments:
```bash
python main.py
```

### 3. CLI Options
The tool supports several CLI arguments to customize the crawler properties:

- `--url`: Single URL override (ignores `targets.txt`)
- `--depth`: Crawl depth (default: 1)
- `--max-pages`: Max pages to crawl per site (0 = unlimited, default: 0)
- `--delay`: Delay between requests in seconds (default: 0.3)
- `--concurrency`: Max concurrent async fetch connections (default: 10)
- `--keyword`: Primary SEO keyword for density check.
- `--output`: Custom output filename prefix.

**Example of a deep scan:**
```bash
python main.py --url https://example.com/ --depth 3 --max-pages 100 --concurrency 20 --keyword "seo services"
```

## How It Works

1. **Target Loading:** Resolves targets using CLI args, `targets.txt`, or fallback variables in `main.py`.
2. **Crawling:** Uses an async BFS crawler stringing a session pool to explore pages dynamically up to the specified `--depth` and `--max-pages`.
3. **Check Modules:** The parsed HTML (`BeautifulSoup`) and Network Response definitions are handed over to 23 localized scripts located in the `./checks/` directory.
4. **Scoring & Reporting:** The results of the tests accumulate to compute a final qualitative score out of 100 before compiling user-friendly `.docx` and `.html` reports under the `./reports/` directory.
