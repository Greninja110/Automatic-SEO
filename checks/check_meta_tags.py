"""Module 2: Meta Tags"""


def check_meta_tags(url: str, soup, response, seen_titles: set = None, seen_descs: set = None, **kwargs) -> dict:
    checks = []
    if seen_titles is None:
        seen_titles = set()
    if seen_descs is None:
        seen_descs = set()

    # 1. Title exists
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    if title_text:
        checks.append({"name": "Title tag exists", "status": "pass", "detail": f"Title: \"{title_text[:80]}\""})
    else:
        checks.append({"name": "Title tag exists", "status": "fail", "detail": "No <title> tag found on page"})

    # 2. Title length
    title_len = len(title_text)
    if 1 <= title_len <= 60:
        checks.append({"name": "Title length (≤60 chars)", "status": "pass", "detail": f"Title length: {title_len} characters"})
    elif title_len <= 70:
        checks.append({"name": "Title length (≤60 chars)", "status": "warning", "detail": f"Title slightly long: {title_len} chars (ideal ≤60)"})
    elif title_len == 0:
        checks.append({"name": "Title length (≤60 chars)", "status": "fail", "detail": "Title is empty"})
    else:
        checks.append({"name": "Title length (≤60 chars)", "status": "fail", "detail": f"Title too long: {title_len} chars (max 60)"})

    # 3. Title uniqueness
    if title_text:
        if title_text.lower() in seen_titles:
            checks.append({"name": "Title uniqueness", "status": "fail", "detail": f"Duplicate title found: \"{title_text[:60]}\""})
        else:
            seen_titles.add(title_text.lower())
            checks.append({"name": "Title uniqueness", "status": "pass", "detail": "Title is unique across crawled pages"})

    # 4. Meta description exists
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc_text = desc_tag.get("content", "").strip() if desc_tag else ""
    if desc_text:
        checks.append({"name": "Meta description exists", "status": "pass", "detail": f"Description: \"{desc_text[:100]}...\""})
    else:
        checks.append({"name": "Meta description exists", "status": "fail", "detail": "No meta description found"})

    # 5. Meta description length
    desc_len = len(desc_text)
    if 1 <= desc_len <= 160:
        checks.append({"name": "Meta description length (≤160 chars)", "status": "pass", "detail": f"Description length: {desc_len} characters"})
    elif desc_len <= 200:
        checks.append({"name": "Meta description length (≤160 chars)", "status": "warning", "detail": f"Description slightly long: {desc_len} chars (ideal ≤160)"})
    elif desc_len == 0:
        checks.append({"name": "Meta description length (≤160 chars)", "status": "fail", "detail": "Description is empty"})
    else:
        checks.append({"name": "Meta description length (≤160 chars)", "status": "fail", "detail": f"Description too long: {desc_len} chars"})

    # 6. Meta robots
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    if robots_tag:
        content = robots_tag.get("content", "").lower()
        if "noindex" in content:
            checks.append({"name": "Meta robots (indexable)", "status": "warning", "detail": f"Page is set to noindex: content=\"{content}\""})
        elif "nofollow" in content:
            checks.append({"name": "Meta robots (indexable)", "status": "warning", "detail": f"Page links are nofollowed: content=\"{content}\""})
        else:
            checks.append({"name": "Meta robots (indexable)", "status": "pass", "detail": f"Robots meta: \"{content}\""})
    else:
        checks.append({"name": "Meta robots (indexable)", "status": "pass", "detail": "No robots meta tag — defaults to index, follow"})

    # 7. Meta charset
    charset = soup.find("meta", charset=True) or soup.find("meta", attrs={"http-equiv": "Content-Type"})
    if charset:
        checks.append({"name": "Meta charset declared", "status": "pass", "detail": f"Charset declared: {str(charset)[:80]}"})
    else:
        checks.append({"name": "Meta charset declared", "status": "warning", "detail": "No charset meta tag found"})

    # 8. Viewport meta tag
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport:
        checks.append({"name": "Viewport meta tag", "status": "pass", "detail": f"Viewport: {viewport.get('content', '')[:80]}"})
    else:
        checks.append({"name": "Viewport meta tag", "status": "fail", "detail": "No viewport meta tag — critical for mobile SEO"})

    # 9. No duplicate meta description tags
    all_desc = soup.find_all("meta", attrs={"name": "description"})
    if len(all_desc) > 1:
        checks.append({"name": "No duplicate meta description", "status": "fail", "detail": f"Found {len(all_desc)} meta description tags; should be exactly 1"})
    else:
        checks.append({"name": "No duplicate meta description", "status": "pass", "detail": "Single meta description tag found"})

    # 10. Meta keywords (obsolete but informational)
    keywords_tag = soup.find("meta", attrs={"name": "keywords"})
    if keywords_tag:
        checks.append({"name": "Meta keywords (obsolete)", "status": "warning", "detail": "Meta keywords tag present — ignored by Google, remove to declutter"})
    else:
        checks.append({"name": "Meta keywords (obsolete)", "status": "pass", "detail": "No obsolete meta keywords tag"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Title: \"{title_text[:50]}\""

    return {"checks": checks, "summary": summary}
