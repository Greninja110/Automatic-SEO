# The 25 check modules

Each module returns about 10 checks. **Scope** is either *site-wide* (run once on the start URL)
or *per-page* (run on every crawled page; modules marked † sample the first 10 pages).
"Heuristic" means the result is inferred from HTML/headers, not measured in a browser.

| # | Module id | Scope | What it checks |
|---|---|---|---|
| 1 | `url_structure` | per-page | Query strings, length ≤115, lowercase, hyphens vs underscores, special characters, canonical present/self-referencing, duplicate URLs, depth ≤4, session IDs |
| 2 | `meta_tags` | per-page | Title present, ≤60 chars, unique; meta description present, ≤160 chars, single; meta robots; charset; viewport; obsolete meta keywords |
| 3 | `headings` | per-page | Exactly one H1, H1 length, H1/title overlap, skipped levels, order, heading count, duplicate H1s across pages, empty headings, H1 terms in H2s |
| 4 | `content_quality` | per-page | Word count ≥300, text-to-HTML ratio, duplicate content (hash), keyword/phrase density 1–3%, lorem ipsum, paragraphs, sentence length, anchor diversity, lists/tables, alt attributes |
| 5 | `image_optimization` † | per-page | Alt present/meaningful/length, WebP usage, file size ≤500 KB (HEAD), lazy loading, width/height, broken images, image count |
| 6 | `internal_linking` † | per-page | Internal link count, broken internal links (404 / other), generic or empty anchors, internal nofollow, links to key pages, self-links, protocol consistency |
| 7 | `external_links` † | per-page | Broken external links (bot-protection 403/429 ignored), nofollow on untrusted links, spam TLDs, rel=sponsored/ugc, noopener on target=_blank, count, HTTP links, anchor quality, redirect chains |
| 8 | `mobile_friendliness` | per-page | Viewport (present, device-width, initial-scale), fixed wide widths, horizontal overflow, font size ≥12px, tap targets ≥44px, Flash/plugins, responsive images, touch icons (heuristic) |
| 9 | `page_speed` | site-wide | Server response time (TTFB proxy), page weight, render-blocking JS/CSS, caching and compression headers, lazy loading, minification, third-party scripts, **PageSpeed Insights score** (needs `PAGESPEED_API_KEY`) |
| 10 | `structured_data` | per-page | JSON-LD present and valid (incl. `@graph`), schema.org context, @type, known types, microdata, OG/schema consistency, BreadcrumbList on deep URLs, duplicates, Article required fields |
| 11 | `xml_sitemap` | site-wide | Sitemap found (robots.txt location, /sitemap.xml, /sitemap_index.xml), referenced in robots.txt, valid XML, root element, domain, lastmod presence/freshness, size limits, child sitemaps reachable |
| 12 | `robots_txt` | site-wide | Exists, text/plain, not blocking everything or CSS/JS, Googlebot allowed, Sitemap directive, syntax, crawl-delay, admin paths |
| 13 | `redirects` | site-wide | HTTP→HTTPS, www consistency, 301/308 vs temporary redirects, chains, loops, trailing slash vs canonical, meta refresh, final 200, latency |
| 14 | `https_security` | site-wide | HTTPS, certificate valid and expiry, HSTS and max-age, HTTP→HTTPS redirect, mixed content, Secure cookies, X-Content-Type-Options, X-Frame-Options/CSP |
| 15 | `pagination_canonicals` | per-page | Pagination detection, page-1 canonical, canonicals on paginated/parameter URLs, trailing slash, duplicate canonicals |
| 16 | `analytics_tracking` | per-page | GA4 / GTM / legacy Universal Analytics detected, duplicate tags or containers, tag placement in <head>, official CDN, debug mode, consent mode, other trackers (informational) |
| 17 | `social_opengraph` | per-page | og:title/description/image/url/type, og:image reachable and ≥1200×630, Twitter card tags |
| 18 | `error_pages` | site-wide | Real 404 status for missing pages, soft 404s, custom/branded 404 with navigation and search, 410/5xx pages in the crawl |
| 19 | `core_web_vitals` | site-wide | LCP image size proxy, above-fold lazy loading, CLS proxies (image dimensions, ad slots), render-blocking JS; **real LCP/CLS/INP/FCP** with PageSpeed key |
| 20 | `technical_seo` | per-page | Canonical, hreflang and x-default, AMP, X-Robots-Tag noindex, lang attribute, UTF-8, Content-Type, breadcrumbs |
| 21 | `content_accessibility` | per-page | ARIA landmarks, alt attributes, button names, colour-contrast heuristic, descriptive link text, form labels, lang, positive tabindex, semantic elements, skip link (heuristic) |
| 22 | `crawl_errors` | site-wide | 4xx/5xx across crawled pages, soft 404 on the start page, response-time p95, sitemap URLs returning errors, orphan candidates (in sitemap but not linked) |
| 23 | `backlinks_authority` | per-page | On-page link signals: outbound dofollow/nofollow, internal nofollow, spam anchors, sponsored/ugc tagging (does **not** measure inbound links — see 25) |
| 24 | `ai_search_readiness` | site-wide | **GEO**: llms.txt present and well-formed; robots.txt access for AI search crawlers (OAI-SearchBot, ChatGPT-User, PerplexityBot, Claude-SearchBot/User) and training crawlers (informational); content visible without JavaScript; FAQ/Q&A structure; Organization/Person schema with sameAs; author and date signals; nosnippet / max-snippet:0 |
| 25 | `backlinks_live` | site-wide | **Real inbound-link data** from Agensi `agensi:web.backlinks.summary` (passed via `--backlinks-json`): referring domains, total backlinks, links per domain, authority/rank, spam score, nofollow share, IP diversity, broken backlinks. Only metrics the provider returns are scored. |

## Scoring

`score_pct = passed / total × 100` over every individual check result (per-page modules
contribute one result per page). Warnings count as not passed, so a site with many advisory
warnings scores lower without having hard failures — always read the fail list first.
