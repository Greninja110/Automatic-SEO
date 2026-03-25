"""Module 17: Social & Open Graph"""
from urllib.parse import urljoin


def check_social_opengraph(url: str, soup, response, session=None, **kwargs) -> dict:
    checks = []

    def get_og(prop):
        tag = soup.find("meta", property=prop)
        return tag.get("content", "").strip() if tag else ""

    def get_twitter(name):
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content", "").strip() if tag else ""

    # 1. og:title
    og_title = get_og("og:title")
    if og_title:
        checks.append({"name": "og:title present", "status": "pass", "detail": f"og:title: \"{og_title[:80]}\""})
    else:
        checks.append({"name": "og:title present", "status": "fail", "detail": "og:title meta tag missing"})

    # 2. og:description
    og_desc = get_og("og:description")
    if og_desc:
        checks.append({"name": "og:description present", "status": "pass",
                        "detail": f"og:description: \"{og_desc[:80]}...\""})
    else:
        checks.append({"name": "og:description present", "status": "fail", "detail": "og:description meta tag missing"})

    # 3. og:image
    og_image = get_og("og:image")
    if og_image:
        checks.append({"name": "og:image present", "status": "pass", "detail": f"og:image: {og_image[:80]}"})
    else:
        checks.append({"name": "og:image present", "status": "fail", "detail": "og:image meta tag missing"})

    # 4. og:url
    og_url = get_og("og:url")
    if og_url:
        checks.append({"name": "og:url present", "status": "pass", "detail": f"og:url: {og_url[:80]}"})
    else:
        checks.append({"name": "og:url present", "status": "warning", "detail": "og:url meta tag missing"})

    # 5. og:type
    og_type = get_og("og:type")
    if og_type:
        checks.append({"name": "og:type present", "status": "pass", "detail": f"og:type: {og_type}"})
    else:
        checks.append({"name": "og:type present", "status": "warning", "detail": "og:type meta tag missing"})

    # 6. og:image reachable
    if og_image and session:
        try:
            img_url = urljoin(url, og_image)
            r = session.head(img_url, timeout=8, allow_redirects=True)
            if r.status_code < 400:
                checks.append({"name": "og:image reachable", "status": "pass",
                                "detail": f"og:image returns HTTP {r.status_code}"})
            else:
                checks.append({"name": "og:image reachable", "status": "fail",
                                "detail": f"og:image unreachable (HTTP {r.status_code}): {og_image[:60]}"})
        except Exception as e:
            checks.append({"name": "og:image reachable", "status": "warning",
                            "detail": f"Could not check og:image: {str(e)[:60]}"})
    elif og_image:
        checks.append({"name": "og:image reachable", "status": "warning",
                        "detail": "og:image found but no session to verify reachability"})
    else:
        checks.append({"name": "og:image reachable", "status": "fail",
                        "detail": "og:image missing — cannot check"})

    # 7. og:image dimensions
    og_width = get_og("og:image:width")
    og_height = get_og("og:image:height")
    if og_width and og_height:
        try:
            w, h = int(og_width), int(og_height)
            if w >= 1200 and h >= 630:
                checks.append({"name": "og:image dimensions (≥1200×630)", "status": "pass",
                                "detail": f"og:image: {w}×{h}px (recommended ≥1200×630)"})
            else:
                checks.append({"name": "og:image dimensions (≥1200×630)", "status": "warning",
                                "detail": f"og:image: {w}×{h}px — recommended minimum 1200×630"})
        except ValueError:
            checks.append({"name": "og:image dimensions (≥1200×630)", "status": "warning",
                            "detail": "og:image dimensions present but not numeric"})
    else:
        checks.append({"name": "og:image dimensions (≥1200×630)", "status": "warning",
                        "detail": "og:image:width/height tags missing — add for better social preview control"})

    # 8. Twitter card present
    twitter_card = get_twitter("twitter:card")
    if twitter_card:
        valid_cards = {"summary", "summary_large_image", "app", "player"}
        status = "pass" if twitter_card in valid_cards else "warning"
        checks.append({"name": "twitter:card present", "status": status,
                        "detail": f"twitter:card: {twitter_card}"})
    else:
        checks.append({"name": "twitter:card present", "status": "warning",
                        "detail": "twitter:card missing — falls back to og: tags on Twitter"})

    # 9. twitter:title and twitter:description
    tw_title = get_twitter("twitter:title")
    tw_desc = get_twitter("twitter:description")
    if tw_title and tw_desc:
        checks.append({"name": "twitter:title and twitter:description", "status": "pass",
                        "detail": f"title: \"{tw_title[:50]}\", desc present"})
    elif tw_title or tw_desc:
        checks.append({"name": "twitter:title and twitter:description", "status": "warning",
                        "detail": "Only one of twitter:title/description present"})
    else:
        checks.append({"name": "twitter:title and twitter:description", "status": "warning",
                        "detail": "twitter:title and twitter:description missing (falls back to og:tags)"})

    # 10. twitter:image
    tw_image = get_twitter("twitter:image")
    if tw_image:
        checks.append({"name": "twitter:image present", "status": "pass",
                        "detail": f"twitter:image: {tw_image[:80]}"})
    else:
        checks.append({"name": "twitter:image present", "status": "warning",
                        "detail": "twitter:image missing (falls back to og:image)"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. og:title: \"{og_title[:40]}\""

    return {"checks": checks, "summary": summary}
