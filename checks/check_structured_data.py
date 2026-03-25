"""Module 10: Structured Data / Schema"""
import json
from urllib.parse import urlparse


KNOWN_TYPES = {
    "Organization", "WebSite", "Article", "NewsArticle", "BlogPosting",
    "Product", "BreadcrumbList", "LocalBusiness", "Event", "FAQPage",
    "HowTo", "Recipe", "Review", "Person", "WebPage", "ItemList",
    "VideoObject", "ImageObject", "SoftwareApplication", "Service"
}


def check_structured_data(url: str, soup, response, **kwargs) -> dict:
    checks = []
    ld_scripts = soup.find_all("script", type="application/ld+json")

    # 1. JSON-LD present
    if ld_scripts:
        checks.append({"name": "JSON-LD structured data present", "status": "pass",
                        "detail": f"Found {len(ld_scripts)} JSON-LD script block(s)"})
    else:
        checks.append({"name": "JSON-LD structured data present", "status": "warning",
                        "detail": "No JSON-LD found — consider adding schema markup for rich results"})

    # 2. JSON-LD parses without error
    parsed_schemas = []
    parse_errors = []
    for i, script in enumerate(ld_scripts):
        try:
            text = script.string or script.get_text()
            data = json.loads(text)
            if isinstance(data, list):
                parsed_schemas.extend(data)
            else:
                parsed_schemas.append(data)
        except json.JSONDecodeError as e:
            parse_errors.append(f"Block {i+1}: {str(e)[:60]}")

    if ld_scripts:
        if not parse_errors:
            checks.append({"name": "JSON-LD valid JSON", "status": "pass", "detail": "All JSON-LD blocks parse successfully"})
        else:
            checks.append({"name": "JSON-LD valid JSON", "status": "fail", "detail": f"Parse errors: {parse_errors[:3]}"})

    # 3. @context is schema.org
    if parsed_schemas:
        wrong_context = [s.get("@context", "") for s in parsed_schemas
                         if s.get("@context") and "schema.org" not in str(s.get("@context", ""))]
        if not wrong_context:
            checks.append({"name": "@context is schema.org", "status": "pass", "detail": "All schemas use https://schema.org context"})
        else:
            checks.append({"name": "@context is schema.org", "status": "warning", "detail": f"Non-standard @context: {wrong_context[:2]}"})

    # 4. @type present
    if parsed_schemas:
        missing_type = [i for i, s in enumerate(parsed_schemas) if not s.get("@type")]
        if not missing_type:
            types = [s.get("@type") for s in parsed_schemas]
            checks.append({"name": "@type present in all schemas", "status": "pass", "detail": f"Types found: {types[:5]}"})
        else:
            checks.append({"name": "@type present in all schemas", "status": "fail",
                            "detail": f"{len(missing_type)} schema block(s) missing @type"})

    # 5. Valid known @type
    if parsed_schemas:
        types_found = [s.get("@type") for s in parsed_schemas if s.get("@type")]
        unknown = [t for t in types_found if t not in KNOWN_TYPES]
        if not unknown:
            checks.append({"name": "Valid schema @type used", "status": "pass", "detail": f"Recognized types: {types_found[:5]}"})
        else:
            checks.append({"name": "Valid schema @type used", "status": "warning", "detail": f"Unrecognized @type(s): {unknown[:3]}"})

    if not parsed_schemas:
        for name in ["@context is schema.org", "@type present in all schemas", "Valid schema @type used"]:
            checks.append({"name": name, "status": "warning", "detail": "No JSON-LD schemas to validate"})

    # 6. Microdata present (informational fallback)
    microdata = soup.find_all(itemscope=True)
    if microdata:
        checks.append({"name": "Microdata present (fallback)", "status": "pass",
                        "detail": f"{len(microdata)} microdata item(s) found (informational)"})
    else:
        checks.append({"name": "Microdata present (fallback)", "status": "pass",
                        "detail": "No microdata (JSON-LD is preferred)"})

    # 7. OG tags consistent with LD schema
    og_title = soup.find("meta", property="og:title")
    og_title_text = og_title.get("content", "") if og_title else ""
    if parsed_schemas and og_title_text:
        ld_names = [s.get("name") or s.get("headline") or "" for s in parsed_schemas]
        consistent = any(og_title_text[:30].lower() in n.lower() or n[:30].lower() in og_title_text.lower()
                         for n in ld_names if n)
        if consistent:
            checks.append({"name": "OG title consistent with schema", "status": "pass", "detail": "og:title aligns with schema name/headline"})
        else:
            checks.append({"name": "OG title consistent with schema", "status": "warning",
                            "detail": "og:title may not match schema name — verify consistency"})
    else:
        checks.append({"name": "OG title consistent with schema", "status": "warning",
                        "detail": "No schema or OG title to compare"})

    # 8. BreadcrumbList for multi-level URLs
    path = urlparse(url).path
    depth = len([s for s in path.strip("/").split("/") if s])
    has_breadcrumb = any(s.get("@type") == "BreadcrumbList" for s in parsed_schemas)
    if depth > 1:
        if has_breadcrumb:
            checks.append({"name": "BreadcrumbList schema (multi-level URLs)", "status": "pass",
                            "detail": "BreadcrumbList schema found for deep URL"})
        else:
            checks.append({"name": "BreadcrumbList schema (multi-level URLs)", "status": "warning",
                            "detail": f"Deep URL (depth {depth}) lacks BreadcrumbList schema"})
    else:
        checks.append({"name": "BreadcrumbList schema (multi-level URLs)", "status": "pass",
                        "detail": "Top-level URL — BreadcrumbList not required"})

    # 9. No duplicate @type declarations
    if parsed_schemas:
        from collections import Counter
        type_counts = Counter(s.get("@type") for s in parsed_schemas if s.get("@type"))
        dups = {t: c for t, c in type_counts.items() if c > 1}
        if not dups:
            checks.append({"name": "No duplicate @type declarations", "status": "pass", "detail": "Each @type appears once"})
        else:
            checks.append({"name": "No duplicate @type declarations", "status": "warning",
                            "detail": f"Duplicate types: {dups}"})
    else:
        checks.append({"name": "No duplicate @type declarations", "status": "warning", "detail": "No schemas to check"})

    # 10. Article schema has required fields
    article_schemas = [s for s in parsed_schemas if s.get("@type") in ("Article", "NewsArticle", "BlogPosting")]
    if article_schemas:
        missing_fields = []
        for s in article_schemas:
            for field in ["headline", "author", "datePublished"]:
                if not s.get(field):
                    missing_fields.append(field)
        if not missing_fields:
            checks.append({"name": "Article schema required fields", "status": "pass",
                            "detail": "Article schema has headline, author, datePublished"})
        else:
            checks.append({"name": "Article schema required fields", "status": "fail",
                            "detail": f"Article schema missing: {list(set(missing_fields))}"})
    else:
        checks.append({"name": "Article schema required fields", "status": "pass",
                        "detail": "No Article schema — check not applicable"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    types_str = str([s.get("@type") for s in parsed_schemas[:3]]) if parsed_schemas else "none"
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Schema types: {types_str}"

    return {"checks": checks, "summary": summary}
