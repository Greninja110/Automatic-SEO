"""Module 4: Content Quality"""
import re
import hashlib
from collections import Counter


def _get_visible_text(soup) -> str:
    for tag in soup(["script", "style", "noscript", "head", "meta", "link"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def check_content_quality(url: str, soup, response, keyword: str = None,
                           content_hashes: dict = None, **kwargs) -> dict:
    checks = []
    if content_hashes is None:
        content_hashes = {}

    # Work on a copy to avoid mutating the original soup
    from bs4 import BeautifulSoup
    soup_copy = BeautifulSoup(str(soup), "lxml")
    visible_text = _get_visible_text(soup_copy)
    words = re.findall(r'\b\w+\b', visible_text)
    word_count = len(words)
    html_len = len(response.text)
    text_len = len(visible_text)

    # 1. Minimum word count
    if word_count >= 300:
        checks.append({"name": "Minimum word count (≥300)", "status": "pass", "detail": f"Word count: {word_count}"})
    elif word_count >= 100:
        checks.append({"name": "Minimum word count (≥300)", "status": "warning", "detail": f"Low word count: {word_count} (recommended ≥300)"})
    else:
        checks.append({"name": "Minimum word count (≥300)", "status": "fail", "detail": f"Very low word count: {word_count}"})

    # 2. Text-to-HTML ratio
    ratio = (text_len / html_len * 100) if html_len > 0 else 0
    if ratio >= 20:
        checks.append({"name": "Text-to-HTML ratio (≥20%)", "status": "pass", "detail": f"Ratio: {ratio:.1f}%"})
    elif ratio >= 10:
        checks.append({"name": "Text-to-HTML ratio (≥20%)", "status": "warning", "detail": f"Low ratio: {ratio:.1f}% (recommended ≥20%)"})
    else:
        checks.append({"name": "Text-to-HTML ratio (≥20%)", "status": "fail", "detail": f"Very low ratio: {ratio:.1f}% — page may be bloated with markup"})

    # 3. Duplicate content detection (MD5 hash)
    normalized = re.sub(r'\s+', ' ', visible_text.lower()).strip()
    content_hash = hashlib.md5(normalized[:5000].encode()).hexdigest()
    if content_hash in content_hashes and content_hashes[content_hash] != url:
        checks.append({"name": "No duplicate content", "status": "fail",
                        "detail": f"Duplicate content detected — same hash as: {content_hashes[content_hash]}"})
    else:
        content_hashes[content_hash] = url
        checks.append({"name": "No duplicate content", "status": "pass", "detail": "Content appears unique across crawled pages"})

    # 4. Keyword density
    if keyword:
        kw_lower = keyword.lower()
        kw_count = sum(1 for w in words if w.lower() == kw_lower)
        density = (kw_count / word_count * 100) if word_count > 0 else 0
        if 1 <= density <= 3:
            checks.append({"name": "Keyword density (1–3%)", "status": "pass", "detail": f"Keyword \"{keyword}\" density: {density:.1f}%"})
        elif density == 0:
            checks.append({"name": "Keyword density (1–3%)", "status": "fail", "detail": f"Keyword \"{keyword}\" not found on page"})
        elif density > 5:
            checks.append({"name": "Keyword density (1–3%)", "status": "warning", "detail": f"Keyword \"{keyword}\" density: {density:.1f}% (over-optimised)"})
        else:
            checks.append({"name": "Keyword density (1–3%)", "status": "warning", "detail": f"Keyword \"{keyword}\" density: {density:.1f}%"})
    else:
        checks.append({"name": "Keyword density (1–3%)", "status": "warning", "detail": "No target keyword provided — pass --keyword flag for density check"})

    # 5. No lorem ipsum / placeholder text
    if re.search(r'lorem\s+ipsum', visible_text, re.IGNORECASE):
        checks.append({"name": "No placeholder text", "status": "fail", "detail": "Lorem ipsum placeholder text found on page"})
    else:
        checks.append({"name": "No placeholder text", "status": "pass", "detail": "No placeholder text detected"})

    # 6. Paragraph structure (≥3 non-empty <p> tags)
    paragraphs = [p for p in soup.find_all("p") if p.get_text(strip=True)]
    if len(paragraphs) >= 3:
        checks.append({"name": "Paragraph structure (≥3 paragraphs)", "status": "pass", "detail": f"Found {len(paragraphs)} non-empty <p> tags"})
    elif len(paragraphs) >= 1:
        checks.append({"name": "Paragraph structure (≥3 paragraphs)", "status": "warning", "detail": f"Only {len(paragraphs)} paragraph(s) found"})
    else:
        checks.append({"name": "Paragraph structure (≥3 paragraphs)", "status": "fail", "detail": "No <p> tags found — content not structured in paragraphs"})

    # 7. Readability heuristic (avg sentence length)
    sentences = re.split(r'[.!?]+', visible_text)
    sentences = [s.strip() for s in sentences if len(s.split()) > 3]
    if sentences:
        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        if avg_words <= 25:
            checks.append({"name": "Readable sentence length (≤25 words avg)", "status": "pass", "detail": f"Average sentence length: {avg_words:.0f} words"})
        else:
            checks.append({"name": "Readable sentence length (≤25 words avg)", "status": "warning", "detail": f"Long average sentence: {avg_words:.0f} words (recommended ≤25)"})
    else:
        checks.append({"name": "Readable sentence length (≤25 words avg)", "status": "warning", "detail": "Could not determine sentence length"})

    # 8. Internal link anchor diversity
    internal_anchors = [a.get_text(strip=True).lower() for a in soup.find_all("a", href=True) if a.get_text(strip=True)]
    if internal_anchors:
        most_common = Counter(internal_anchors).most_common(1)[0]
        ratio_common = most_common[1] / len(internal_anchors)
        if ratio_common <= 0.3:
            checks.append({"name": "Anchor text diversity", "status": "pass", "detail": f"Most frequent anchor: \"{most_common[0]}\" ({most_common[1]}x)"})
        else:
            checks.append({"name": "Anchor text diversity", "status": "warning", "detail": f"Over-used anchor text: \"{most_common[0]}\" ({most_common[1]}/{len(internal_anchors)} links)"})
    else:
        checks.append({"name": "Anchor text diversity", "status": "warning", "detail": "No anchor text found on page"})

    # 9. Structured content (lists or tables)
    lists_tables = soup.find("ul") or soup.find("ol") or soup.find("table")
    if lists_tables:
        checks.append({"name": "Structured content (lists/tables)", "status": "pass", "detail": "Page contains lists or tables for structured presentation"})
    else:
        checks.append({"name": "Structured content (lists/tables)", "status": "warning", "detail": "No lists or tables found — consider adding structured content"})

    # 10. Alt text on all images (cross-reference)
    imgs_missing_alt = [img.get("src", "")[:60] for img in soup.find_all("img") if not img.get("alt")]
    if not imgs_missing_alt:
        checks.append({"name": "All images have alt text", "status": "pass", "detail": "All <img> tags have alt attributes"})
    else:
        checks.append({"name": "All images have alt text", "status": "fail",
                        "detail": f"{len(imgs_missing_alt)} image(s) missing alt: {imgs_missing_alt[:3]}"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Word count: {word_count}, text ratio: {ratio:.1f}%"

    return {"checks": checks, "summary": summary}
