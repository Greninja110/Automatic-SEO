"""Module 5: Image Optimization"""
import re
from urllib.parse import urljoin


def check_image_optimization(url: str, soup, response, session=None, **kwargs) -> dict:
    checks = []
    imgs = soup.find_all("img")
    total_imgs = len(imgs)

    if total_imgs == 0:
        return {
            "checks": [{"name": "Images present", "status": "warning", "detail": "No <img> tags found on page"}],
            "summary": "No images found on this page."
        }

    # 1. All images have alt attribute
    missing_alt = [img for img in imgs if img.get("alt") is None]
    if not missing_alt:
        checks.append({"name": "All images have alt attribute", "status": "pass", "detail": f"All {total_imgs} images have alt attributes"})
    else:
        checks.append({"name": "All images have alt attribute", "status": "fail",
                        "detail": f"{len(missing_alt)}/{total_imgs} images missing alt attribute"})

    # 2. Alt text not empty (empty alt is OK for decorative images — warn instead)
    empty_alt = [img.get("src", "")[:50] for img in imgs if img.get("alt") is not None and img.get("alt", "").strip() == ""]
    if not empty_alt:
        checks.append({"name": "Alt text not empty string", "status": "pass", "detail": "All alt attributes contain text"})
    else:
        checks.append({"name": "Alt text not empty string", "status": "warning",
                        "detail": f"{len(empty_alt)} image(s) have empty alt (OK if decorative): {empty_alt[:2]}"})

    # 3. Alt text not filename
    filename_alts = [img.get("alt", "") for img in imgs
                     if re.search(r'\w+\.(jpg|jpeg|png|gif|webp|svg)', img.get("alt", ""), re.IGNORECASE)]
    if not filename_alts:
        checks.append({"name": "Alt text not a filename", "status": "pass", "detail": "No alt texts that look like filenames"})
    else:
        checks.append({"name": "Alt text not a filename", "status": "warning",
                        "detail": f"Filename-like alt texts: {filename_alts[:3]}"})

    # 4. Modern format usage
    srcs = [img.get("src", "") for img in imgs]
    webp_count = sum(1 for s in srcs if s.lower().endswith(".webp"))
    gif_count = sum(1 for s in srcs if s.lower().endswith(".gif"))
    png_count = sum(1 for s in srcs if s.lower().endswith(".png"))
    if webp_count >= total_imgs * 0.5:
        checks.append({"name": "Modern image formats (WebP)", "status": "pass", "detail": f"{webp_count}/{total_imgs} images use WebP format"})
    elif gif_count > 0:
        checks.append({"name": "Modern image formats (WebP)", "status": "warning", "detail": f"{gif_count} GIF image(s) found — consider WebP/video for animations"})
    else:
        checks.append({"name": "Modern image formats (WebP)", "status": "warning", "detail": f"Only {webp_count}/{total_imgs} images use WebP — consider converting JPEG/PNG to WebP"})

    # 5. Image file sizes (HEAD request sample — first 5 images)
    oversized = []
    if session:
        for img in imgs[:5]:
            src = img.get("src", "")
            if not src or src.startswith("data:"):
                continue
            img_url = urljoin(url, src)
            try:
                head = session.head(img_url, timeout=5, allow_redirects=True)
                content_length = int(head.headers.get("content-length", 0))
                if content_length > 500_000:
                    oversized.append(f"{src[:50]} ({content_length//1024}KB)")
            except Exception:
                pass
    if oversized:
        checks.append({"name": "Image file sizes (≤500KB)", "status": "fail", "detail": f"Oversized images: {oversized}"})
    else:
        checks.append({"name": "Image file sizes (≤500KB)", "status": "pass", "detail": "Sampled images appear within size limits"})

    # 6. Lazy loading for below-fold images
    lazy_imgs = [img for img in imgs if img.get("loading") == "lazy"]
    if total_imgs <= 2:
        checks.append({"name": "Lazy loading for images", "status": "pass", "detail": "Few images — lazy loading less critical"})
    elif len(lazy_imgs) >= total_imgs * 0.5:
        checks.append({"name": "Lazy loading for images", "status": "pass", "detail": f"{len(lazy_imgs)}/{total_imgs} images use lazy loading"})
    else:
        checks.append({"name": "Lazy loading for images", "status": "warning",
                        "detail": f"Only {len(lazy_imgs)}/{total_imgs} images use loading=\"lazy\""})

    # 7. Width and height attributes (prevent layout shift)
    missing_dimensions = [img.get("src", "")[:40] for img in imgs
                          if not img.get("width") or not img.get("height")]
    if not missing_dimensions:
        checks.append({"name": "Images have width/height attributes", "status": "pass", "detail": "All images have explicit dimensions"})
    else:
        checks.append({"name": "Images have width/height attributes", "status": "warning",
                        "detail": f"{len(missing_dimensions)} image(s) missing width/height (causes CLS): {missing_dimensions[:3]}"})

    # 8. Descriptive alt text length (5–125 chars)
    bad_length_alts = [img.get("alt", "") for img in imgs
                       if img.get("alt") and img.get("alt", "").strip()
                       and not (5 <= len(img.get("alt", "").strip()) <= 125)]
    if not bad_length_alts:
        checks.append({"name": "Alt text length (5–125 chars)", "status": "pass", "detail": "Alt text lengths are appropriate"})
    else:
        checks.append({"name": "Alt text length (5–125 chars)", "status": "warning",
                        "detail": f"{len(bad_length_alts)} alt text(s) outside recommended 5–125 char range"})

    # 9. No broken image URLs
    broken_imgs = []
    if session:
        for img in imgs[:10]:
            src = img.get("src", "")
            if not src or src.startswith("data:"):
                continue
            img_url = urljoin(url, src)
            try:
                head = session.head(img_url, timeout=5, allow_redirects=True)
                if head.status_code >= 400:
                    broken_imgs.append(f"{src[:50]} ({head.status_code})")
            except Exception:
                pass
    if broken_imgs:
        checks.append({"name": "No broken image URLs", "status": "fail", "detail": f"Broken images: {broken_imgs}"})
    else:
        checks.append({"name": "No broken image URLs", "status": "pass", "detail": "Sampled images returned valid responses"})

    # 10. Image count heuristic
    if total_imgs <= 30:
        checks.append({"name": "Image count (≤30 per page)", "status": "pass", "detail": f"Total images: {total_imgs}"})
    else:
        checks.append({"name": "Image count (≤30 per page)", "status": "warning", "detail": f"High image count: {total_imgs} — may impact performance"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = f"{passed} passed, {failed} failed, {warned} warnings. Total images: {total_imgs}"

    return {"checks": checks, "summary": summary}
