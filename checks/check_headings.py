"""Module 3: Headings (H1–H6)"""
import re


def check_headings(url: str, soup, response, seen_h1s: set = None, **kwargs) -> dict:
    checks = []
    if seen_h1s is None:
        seen_h1s = set()

    all_headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    h1_tags = soup.find_all("h1")
    h1_text = h1_tags[0].get_text(strip=True) if h1_tags else ""

    # 1. Exactly one H1
    h1_count = len(h1_tags)
    if h1_count == 1:
        checks.append({"name": "Exactly one H1", "status": "pass", "detail": f"H1: \"{h1_text[:80]}\""})
    elif h1_count == 0:
        checks.append({"name": "Exactly one H1", "status": "fail", "detail": "No H1 tag found on page"})
    else:
        checks.append({"name": "Exactly one H1", "status": "warning", "detail": f"Found {h1_count} H1 tags; only one is recommended"})

    # 2. H1 not empty
    if h1_text:
        checks.append({"name": "H1 not empty", "status": "pass", "detail": f"H1 has text: \"{h1_text[:80]}\""})
    else:
        checks.append({"name": "H1 not empty", "status": "fail", "detail": "H1 tag is empty or missing"})

    # 3. H1 length
    h1_len = len(h1_text)
    if 10 <= h1_len <= 70:
        checks.append({"name": "H1 length (10–70 chars)", "status": "pass", "detail": f"H1 length: {h1_len} characters"})
    elif h1_len > 0:
        checks.append({"name": "H1 length (10–70 chars)", "status": "warning", "detail": f"H1 length: {h1_len} chars (recommended 10–70)"})
    else:
        checks.append({"name": "H1 length (10–70 chars)", "status": "fail", "detail": "H1 is empty"})

    # 4. H1 contains words from title (keyword overlap heuristic)
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    if h1_text and title_text:
        h1_words = set(re.sub(r'[^\w\s]', '', h1_text.lower()).split())
        title_words = set(re.sub(r'[^\w\s]', '', title_text.lower()).split())
        stopwords = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "is", "are", "was", "be"}
        h1_words -= stopwords
        title_words -= stopwords
        if title_words and len(h1_words & title_words) / len(title_words) >= 0.3:
            checks.append({"name": "H1 overlaps with title (keyword signal)", "status": "pass", "detail": "H1 shares key terms with page title"})
        else:
            checks.append({"name": "H1 overlaps with title (keyword signal)", "status": "warning", "detail": "H1 and title share few common words; ensure topical alignment"})
    else:
        checks.append({"name": "H1 overlaps with title (keyword signal)", "status": "warning", "detail": "Cannot compare — H1 or title is missing"})

    # 5. No skipped heading levels
    level_sequence = [int(h.name[1]) for h in all_headings]
    skips = []
    for i in range(1, len(level_sequence)):
        if level_sequence[i] - level_sequence[i - 1] > 1:
            skips.append(f"H{level_sequence[i-1]}→H{level_sequence[i]}")
    if not skips:
        checks.append({"name": "No skipped heading levels", "status": "pass", "detail": "Heading hierarchy is sequential"})
    else:
        checks.append({"name": "No skipped heading levels", "status": "warning", "detail": f"Skipped levels detected: {', '.join(skips[:5])}"})

    # 6. H2s appear after H1
    first_h1_idx = next((i for i, h in enumerate(all_headings) if h.name == "h1"), None)
    first_h2_idx = next((i for i, h in enumerate(all_headings) if h.name == "h2"), None)
    if first_h1_idx is not None and first_h2_idx is not None:
        if first_h2_idx > first_h1_idx:
            checks.append({"name": "H2s appear after H1", "status": "pass", "detail": "Heading hierarchy order is correct"})
        else:
            checks.append({"name": "H2s appear after H1", "status": "warning", "detail": "H2 appears before H1 in the document"})
    else:
        checks.append({"name": "H2s appear after H1", "status": "warning", "detail": "Not enough heading levels to verify order"})

    # 7. Total heading count (keyword stuffing guard)
    total = len(all_headings)
    if total <= 20:
        checks.append({"name": "Reasonable heading count (≤20)", "status": "pass", "detail": f"Total headings: {total}"})
    else:
        checks.append({"name": "Reasonable heading count (≤20)", "status": "warning", "detail": f"High heading count: {total} (possible keyword stuffing)"})

    # 8. No duplicate H1 across pages
    if h1_text:
        if h1_text.lower() in seen_h1s:
            checks.append({"name": "H1 unique across pages", "status": "fail", "detail": f"Duplicate H1 found on multiple pages: \"{h1_text[:60]}\""})
        else:
            seen_h1s.add(h1_text.lower())
            checks.append({"name": "H1 unique across pages", "status": "pass", "detail": "H1 is unique across crawled pages"})
    else:
        checks.append({"name": "H1 unique across pages", "status": "warning", "detail": "No H1 to check uniqueness"})

    # 9. No empty headings
    empty_headings = [h.name.upper() for h in all_headings if not h.get_text(strip=True)]
    if not empty_headings:
        checks.append({"name": "No empty headings", "status": "pass", "detail": "All headings contain text"})
    else:
        checks.append({"name": "No empty headings", "status": "fail", "detail": f"Empty headings found: {empty_headings[:5]}"})

    # 10. Keyword appears in at least one H2
    h2_tags = soup.find_all("h2")
    h2_text_all = " ".join(h.get_text(strip=True).lower() for h in h2_tags)
    if h1_text and h2_text_all:
        h1_words = set(re.sub(r'[^\w\s]', '', h1_text.lower()).split())
        stopwords = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of"}
        h1_words -= stopwords
        h2_words = set(re.sub(r'[^\w\s]', '', h2_text_all).split())
        if h1_words & h2_words:
            checks.append({"name": "H1 keywords appear in H2s", "status": "pass", "detail": "H2 headings share keywords with H1"})
        else:
            checks.append({"name": "H1 keywords appear in H2s", "status": "warning", "detail": "H2 headings share no keywords with H1 — check topical flow"})
    else:
        checks.append({"name": "H1 keywords appear in H2s", "status": "warning", "detail": "No H2 tags found to cross-check"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. H1: \"{h1_text[:50]}\""

    return {"checks": checks, "summary": summary}
