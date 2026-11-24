"""Module 24: AI Search / GEO Readiness

How well the site can be found, read and quoted by AI search engines
(ChatGPT search, Perplexity, Claude, Google AI Overviews / Gemini).
"""
import json
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

# Crawlers that fetch pages to answer user questions / show citations.
# Blocking these removes the site from that engine's answers.
AI_SEARCH_BOTS = ["OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Claude-SearchBot", "Claude-User"]

# Crawlers that collect training data. Blocking them is a legitimate choice,
# so this is reported for information, not as a failure.
AI_TRAINING_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Applebot-Extended"]


def _visible_word_count(soup) -> int:
    skip = {"script", "style", "noscript", "template", "head", "svg"}
    words = 0
    for s in soup.find_all(string=True):
        if s.parent is not None and s.parent.name in skip:
            continue
        words += len(s.split())
    return words


def _iter_schema_nodes(soup):
    """Yield every JSON-LD object, flattening lists and @graph."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                if "@graph" in node:
                    stack.append(node["@graph"])


def _types(node) -> set:
    t = node.get("@type", [])
    return set(t) if isinstance(t, list) else {t}


def _robots_parser(session, base_url: str, robots_txt_content: str):
    text = robots_txt_content or ""
    if not text and session:
        try:
            r = session.get(f"{base_url}/robots.txt", timeout=10)
            text = r.text if r.status_code == 200 else ""
        except Exception:
            text = ""
    if not text:
        return None
    rp = RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def check_ai_search_readiness(url: str, soup, response, session=None,
                              robots_txt_content: str = None, **kwargs) -> dict:
    checks = []
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # 1 & 2. llms.txt
    llms_text = ""
    if session:
        try:
            r = session.get(f"{base_url}/llms.txt", timeout=10)
            ctype = r.headers.get("Content-Type", "")
            if r.status_code == 200 and "html" not in ctype.lower():
                llms_text = r.text
        except Exception:
            pass
    if llms_text.strip():
        checks.append({"name": "llms.txt present", "status": "pass",
                       "detail": f"{base_url}/llms.txt found ({len(llms_text)} bytes)"})
        has_h1 = bool(re.search(r"^#\s+\S", llms_text, re.MULTILINE))
        n_links = len(re.findall(r"\[[^\]]+\]\([^)]+\)", llms_text))
        if has_h1 and n_links:
            checks.append({"name": "llms.txt well-formed", "status": "pass",
                           "detail": f"Has a '# Title' heading and {n_links} markdown link(s)"})
        else:
            missing = [m for m, ok in (("a '# Site name' heading", has_h1), ("markdown links to key pages", n_links)) if not ok]
            checks.append({"name": "llms.txt well-formed", "status": "warning",
                           "detail": f"llms.txt is missing {' and '.join(missing)} (see llmstxt.org)"})
    else:
        checks.append({"name": "llms.txt present", "status": "warning",
                       "detail": f"No {base_url}/llms.txt — add one to give AI assistants a curated map of your key pages (llmstxt.org)"})
        checks.append({"name": "llms.txt well-formed", "status": "warning",
                       "detail": "No llms.txt to validate"})

    # 3 & 4. AI crawler access in robots.txt
    rp = _robots_parser(session, base_url, robots_txt_content)
    if rp is None:
        checks.append({"name": "AI search crawlers allowed", "status": "pass",
                       "detail": "No robots.txt — AI search crawlers are not blocked"})
        checks.append({"name": "AI training crawlers policy (informational)", "status": "pass",
                       "detail": "No robots.txt — training crawlers are not blocked"})
    else:
        blocked_search = [b for b in AI_SEARCH_BOTS if not rp.can_fetch(b, url)]
        if not blocked_search:
            checks.append({"name": "AI search crawlers allowed", "status": "pass",
                           "detail": f"robots.txt allows {', '.join(AI_SEARCH_BOTS)}"})
        else:
            checks.append({"name": "AI search crawlers allowed", "status": "fail",
                           "detail": f"robots.txt blocks {', '.join(blocked_search)} — the site cannot be "
                                     f"cited in those AI answers. Allow them unless that is intended."})
        blocked_train = [b for b in AI_TRAINING_BOTS if not rp.can_fetch(b, url)]
        allowed_train = [b for b in AI_TRAINING_BOTS if b not in blocked_train]
        checks.append({"name": "AI training crawlers policy (informational)", "status": "pass",
                       "detail": (f"Blocked: {', '.join(blocked_train) or 'none'}; "
                                  f"allowed: {', '.join(allowed_train) or 'none'}. "
                                  "Blocking training crawlers is a business choice, not an SEO error.")})

    # 5. Content available without JavaScript (most AI crawlers do not render JS)
    words = _visible_word_count(soup)
    n_scripts = len(soup.find_all("script"))
    if words >= 150:
        checks.append({"name": "Content readable without JavaScript", "status": "pass",
                       "detail": f"{words} words of text in the server HTML"})
    elif words >= 50:
        checks.append({"name": "Content readable without JavaScript", "status": "warning",
                       "detail": f"Only {words} words in the server HTML ({n_scripts} scripts) — AI crawlers that "
                                 "don't run JavaScript may see little content. Consider SSR/SSG."})
    else:
        checks.append({"name": "Content readable without JavaScript", "status": "fail",
                       "detail": f"{words} words in the server HTML ({n_scripts} scripts) — page looks client-rendered; "
                                 "AI crawlers will see an almost empty page. Use server-side rendering or prerendering."})

    # 6. Question / answer structure
    nodes = list(_iter_schema_nodes(soup))
    all_types = set().union(*(_types(n) for n in nodes)) if nodes else set()
    question_headings = [h.get_text(strip=True) for h in soup.find_all(["h2", "h3", "h4"])
                         if h.get_text(strip=True).endswith("?")]
    if all_types & {"FAQPage", "QAPage", "HowTo"}:
        checks.append({"name": "Q&A / FAQ structure", "status": "pass",
                       "detail": f"Schema: {', '.join(sorted(all_types & {'FAQPage', 'QAPage', 'HowTo'}))}"})
    elif question_headings:
        checks.append({"name": "Q&A / FAQ structure", "status": "pass",
                       "detail": f"{len(question_headings)} question-style heading(s), e.g. \"{question_headings[0][:60]}\""})
    else:
        checks.append({"name": "Q&A / FAQ structure", "status": "warning",
                       "detail": "No FAQ schema or question-style headings — AI engines favour content that "
                                 "answers explicit questions"})

    # 7. Entity identity (Organization/Person with sameAs)
    entities = [n for n in nodes if _types(n) & {"Organization", "Person", "LocalBusiness", "Corporation"}]
    with_same_as = [n for n in entities if n.get("sameAs")]
    if with_same_as:
        checks.append({"name": "Entity schema with sameAs links", "status": "pass",
                       "detail": f"{len(with_same_as)} Organization/Person entity(ies) link to external profiles"})
    elif entities:
        checks.append({"name": "Entity schema with sameAs links", "status": "warning",
                       "detail": "Organization/Person schema found but no sameAs links (LinkedIn, Wikipedia, socials) "
                                 "— these help AI engines identify who you are"})
    else:
        checks.append({"name": "Entity schema with sameAs links", "status": "warning",
                       "detail": "No Organization or Person schema — add one with name, url, logo and sameAs"})

    # 8. Authorship signal
    author_meta = soup.find("meta", attrs={"name": "author"})
    schema_author = any(n.get("author") for n in nodes)
    rel_author = soup.find(["a", "link"], rel="author")
    if (author_meta and author_meta.get("content")) or schema_author or rel_author:
        checks.append({"name": "Author / publisher signal", "status": "pass",
                       "detail": "Authorship declared (meta author, rel=author or schema author)"})
    else:
        checks.append({"name": "Author / publisher signal", "status": "warning",
                       "detail": "No author information — named authors improve trust (E-E-A-T) for AI and search"})

    # 9. Freshness signal
    date_meta = soup.find("meta", attrs={"property": re.compile(r"article:(modified|published)_time")})
    schema_date = any(n.get("dateModified") or n.get("datePublished") for n in nodes)
    time_tag = soup.find("time", attrs={"datetime": True})
    last_modified = response.headers.get("Last-Modified", "") if response is not None else ""
    if date_meta or schema_date or time_tag:
        checks.append({"name": "Content date / freshness signal", "status": "pass",
                       "detail": "Publish/modified date found in markup"})
    elif last_modified:
        checks.append({"name": "Content date / freshness signal", "status": "warning",
                       "detail": f"Only an HTTP Last-Modified header ({last_modified}); add a visible date or "
                                 "dateModified schema"})
    else:
        checks.append({"name": "Content date / freshness signal", "status": "warning",
                       "detail": "No publish or update date — AI engines prefer content they can see is current"})

    # 10. Snippet controls don't block AI answers
    robots_meta = " ".join(m.get("content", "") for m in soup.find_all("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)}))
    x_robots = response.headers.get("X-Robots-Tag", "") if response is not None else ""
    directives = f"{robots_meta} {x_robots}".lower()
    if "nosnippet" in directives or re.search(r"max-snippet\s*:\s*0\b", directives):
        checks.append({"name": "Snippets allowed for AI answers", "status": "fail",
                       "detail": "nosnippet / max-snippet:0 set — Google AI Overviews and other engines cannot quote this page"})
    else:
        checks.append({"name": "Snippets allowed for AI answers", "status": "pass",
                       "detail": "No nosnippet or max-snippet:0 directive"})

    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warned = sum(1 for c in checks if c["status"] == "warning")
    summary = (f"{passed} passed, {failed} failed, {warned} warnings. "
               f"llms.txt: {'yes' if llms_text.strip() else 'no'}, server-HTML words: {words}")
    return {"checks": checks, "summary": summary}
