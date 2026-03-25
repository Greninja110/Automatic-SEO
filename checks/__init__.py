"""SEO Check Registry — imports all 23 modules and exposes ALL_CHECKS."""

from checks.check_url_structure         import check_url_structure
from checks.check_meta_tags             import check_meta_tags
from checks.check_headings              import check_headings
from checks.check_content_quality       import check_content_quality
from checks.check_image_optimization    import check_image_optimization
from checks.check_internal_linking      import check_internal_linking
from checks.check_external_links        import check_external_links
from checks.check_mobile_friendliness   import check_mobile_friendliness
from checks.check_page_speed            import check_page_speed
from checks.check_structured_data       import check_structured_data
from checks.check_xml_sitemap           import check_xml_sitemap
from checks.check_robots_txt            import check_robots_txt
from checks.check_redirects             import check_redirects
from checks.check_https_security        import check_https_security
from checks.check_pagination_canonicals import check_pagination_canonicals
from checks.check_analytics_tracking    import check_analytics_tracking
from checks.check_social_opengraph      import check_social_opengraph
from checks.check_error_pages           import check_error_pages
from checks.check_core_web_vitals       import check_core_web_vitals
from checks.check_technical_seo         import check_technical_seo
from checks.check_content_accessibility import check_content_accessibility
from checks.check_crawl_errors          import check_crawl_errors
from checks.check_backlinks_authority   import check_backlinks_authority

# Modules that run once per site on the homepage only (not per crawled page).
# Add heavy API-based or site-level checks here to avoid 50x API calls.
SITE_WIDE_CHECKS = {
    "xml_sitemap",
    "robots_txt",
    "redirects",
    "https_security",
    "crawl_errors",
    "error_pages",
    "page_speed",        # PageSpeed API — run once on homepage only
    "core_web_vitals",   # PageSpeed API — run once on homepage only
}

ALL_CHECKS = [
    ("url_structure",           check_url_structure),
    ("meta_tags",               check_meta_tags),
    ("headings",                check_headings),
    ("content_quality",         check_content_quality),
    ("image_optimization",      check_image_optimization),
    ("internal_linking",        check_internal_linking),
    ("external_links",          check_external_links),
    ("mobile_friendliness",     check_mobile_friendliness),
    ("page_speed",              check_page_speed),
    ("structured_data",         check_structured_data),
    ("xml_sitemap",             check_xml_sitemap),
    ("robots_txt",              check_robots_txt),
    ("redirects",               check_redirects),
    ("https_security",          check_https_security),
    ("pagination_canonicals",   check_pagination_canonicals),
    ("analytics_tracking",      check_analytics_tracking),
    ("social_opengraph",        check_social_opengraph),
    ("error_pages",             check_error_pages),
    ("core_web_vitals",         check_core_web_vitals),
    ("technical_seo",           check_technical_seo),
    ("content_accessibility",   check_content_accessibility),
    ("crawl_errors",            check_crawl_errors),
    ("backlinks_authority",     check_backlinks_authority),
]

MODULE_TITLES = {
    "url_structure":           "1. URL Structure",
    "meta_tags":               "2. Meta Tags",
    "headings":                "3. Headings (H1–H6)",
    "content_quality":         "4. Content Quality",
    "image_optimization":      "5. Image Optimization",
    "internal_linking":        "6. Internal Linking",
    "external_links":          "7. External Links",
    "mobile_friendliness":     "8. Mobile Friendliness",
    "page_speed":              "9. Page Speed & Performance",
    "structured_data":         "10. Structured Data / Schema",
    "xml_sitemap":             "11. XML Sitemap",
    "robots_txt":              "12. Robots.txt",
    "redirects":               "13. Redirects",
    "https_security":          "14. HTTPS & Security",
    "pagination_canonicals":   "15. Pagination & Canonicals",
    "analytics_tracking":      "16. Analytics & Tracking",
    "social_opengraph":        "17. Social & Open Graph",
    "error_pages":             "18. Error Pages",
    "core_web_vitals":         "19. Core Web Vitals",
    "technical_seo":           "20. Technical SEO",
    "content_accessibility":   "21. Content Accessibility",
    "crawl_errors":            "22. Crawl Errors",
    "backlinks_authority":     "23. Backlinks & Authority",
}
