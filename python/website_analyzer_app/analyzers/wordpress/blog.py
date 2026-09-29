from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json


# -----------------------------
# BASIC HELPERS
# -----------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(raw_url, base_url=None):
    if not raw_url:
        return None

    if str(raw_url).lower().startswith(("javascript:", "mailto:", "tel:")):
        return None

    full_url = urljoin(base_url or "", raw_url)
    parsed = urlparse(full_url)

    cleaned = parsed._replace(
        query="",
        fragment=""
    )

    return urlunparse(cleaned)


def unique_items(items, key):
    seen = set()
    output = []

    for item in items:
        value = item.get(key)

        if not value or value in seen:
            continue

        seen.add(value)
        output.append(item)

    return output


def clean_dom_for_article(html):
    soup = BeautifulSoup(html or "", "lxml")

    remove_selectors = [
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "form",
        "template",
        "header",
        "footer",
        "nav",
        ".menu",
        ".navbar",
        ".site-header",
        ".site-footer",
        ".sidebar",
        ".widget",
        ".comments",
        "#comments",
        ".comment-respond",
        ".related-posts",
        ".newsletter",
        ".popup",
        ".modal",
        ".drawer",
        ".cookie",
        "[class*='cookie']",
        "[class*='popup']",
        "[class*='modal']",
        "[class*='share']",
        "[class*='social']"
    ]

    for selector in remove_selectors:
        for node in soup.select(selector):
            node.decompose()

    return soup


def extract_json_ld_items(soup):
    items = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()

            if not raw:
                continue

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                items.extend(parsed)
            else:
                items.append(parsed)

        except Exception:
            continue

    return items


def flatten_json_ld_items(item):
    output = []

    if isinstance(item, list):
        for child in item:
            output.extend(flatten_json_ld_items(child))

    elif isinstance(item, dict):
        output.append(item)

        graph = item.get("@graph")

        if isinstance(graph, list):
            for child in graph:
                output.extend(flatten_json_ld_items(child))

    return output


# -----------------------------
# SEO / META
# -----------------------------

def extract_basic_seo(soup, url):
    title = soup.title.get_text(" ") if soup.title else None

    meta_description = None
    desc = soup.select_one("meta[name='description']")

    if desc:
        meta_description = desc.get("content")

    canonical = None
    canonical_tag = soup.select_one("link[rel='canonical']")

    if canonical_tag:
        canonical = canonical_tag.get("href")

    h1 = soup.select_one("h1")

    return {
        "title": clean_text(title),
        "metaDescription": clean_text(meta_description),
        "canonical": normalize_url(canonical, url) if canonical else None,
        "h1": clean_text(h1.get_text(" ")) if h1 else None
    }


def extract_open_graph(soup):
    og = {}

    for meta in soup.select("meta[property^='og:']"):
        prop = meta.get("property", "").replace("og:", "")
        content = meta.get("content")

        if prop and content:
            og[prop] = clean_text(content)

    return og


# -----------------------------
# PAGE TYPE DETECTION
# -----------------------------

def detect_blog_page_type(url, soup):
    url_path = urlparse(url).path.lower()
    body_classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    body_classes = body_classes.lower()

    article_schema_found = False
    blog_schema_found = False

    json_ld_items = extract_json_ld_items(soup)

    for item in json_ld_items:
        for flat in flatten_json_ld_items(item):
            item_type = flat.get("@type")

            if isinstance(item_type, list):
                types = [str(t).lower() for t in item_type]
            elif item_type:
                types = [str(item_type).lower()]
            else:
                types = []

            if any(t in types for t in ["article", "blogposting", "newsarticle"]):
                article_schema_found = True

            if "blog" in types:
                blog_schema_found = True

    single_post_signals = [
        "single-post" in body_classes,
        "post-template" in body_classes,
        "article" in body_classes,
        article_schema_found,
        bool(soup.select_one("article")),
        bool(soup.select_one(".post-content, .entry-content, .wp-block-post-content"))
    ]

    listing_signals = [
        "blog" in body_classes,
        "archive" in body_classes,
        "category" in body_classes,
        "author" in body_classes,
        "/blog" in url_path,
        "/blogs" in url_path,
        "/news" in url_path,
        "/articles" in url_path,
        bool(soup.select(".post, article, .blog-post, .post-card, .elementor-post"))
    ]

    if any(single_post_signals):
        return "article"

    if any(listing_signals) or blog_schema_found:
        return "blogListing"

    return "unknownBlog"


# -----------------------------
# ARTICLE EXTRACTOR
# -----------------------------

def extract_author(soup):
    selectors = [
        ".author",
        ".byline",
        ".post-author",
        "[rel='author']",
        ".entry-author"
    ]

    for selector in selectors:
        node = soup.select_one(selector)

        if node:
            text = clean_text(node.get_text(" "))

            text = re.sub(r"^(by|author|written by)\s+", "", text, flags=re.I)
            text = clean_text(text)

            if text and len(text) <= 80:
                return text

    meta_author = soup.select_one("meta[name='author']")

    if meta_author:
        return clean_text(meta_author.get("content"))

    return None


def extract_dates(soup):
    published = None
    modified = None

    published_selectors = [
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "time[datetime]",
        ".published",
        ".posted-on",
        ".entry-date"
    ]

    modified_selectors = [
        "meta[property='article:modified_time']",
        "meta[name='article:modified_time']",
        ".updated",
        ".modified"
    ]

    for selector in published_selectors:
        node = soup.select_one(selector)

        if not node:
            continue

        published = node.get("content") or node.get("datetime") or node.get_text(" ")
        published = clean_text(published)

        if published:
            break

    for selector in modified_selectors:
        node = soup.select_one(selector)

        if not node:
            continue

        modified = node.get("content") or node.get("datetime") or node.get_text(" ")
        modified = clean_text(modified)

        if modified:
            break

    return {
        "published": published,
        "modified": modified
    }


def extract_featured_image(soup, base_url):
    og_image = soup.select_one("meta[property='og:image']")

    if og_image and og_image.get("content"):
        return {
            "url": normalize_url(og_image.get("content"), base_url),
            "alt": None,
            "source": "og:image"
        }

    image_selectors = [
        ".post-thumbnail img",
        ".featured-image img",
        ".entry-content img",
        "article img"
    ]

    for selector in image_selectors:
        img = soup.select_one(selector)

        if not img:
            continue

        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("src")
        )

        if src and not src.startswith("data:image"):
            return {
                "url": normalize_url(src, base_url),
                "alt": clean_text(img.get("alt")),
                "source": selector
            }

    return None


def extract_article_content(soup):
    content_node = (
        soup.select_one("article .entry-content")
        or soup.select_one(".entry-content")
        or soup.select_one(".post-content")
        or soup.select_one(".wp-block-post-content")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.body
        or soup
    )

    headings = []

    for h in content_node.select("h2, h3"):
        text = clean_text(h.get_text(" "))

        if text and len(text) <= 160:
            headings.append({
                "level": h.name,
                "text": text
            })

    paragraphs = []

    for p in content_node.select("p"):
        text = clean_text(p.get_text(" "))

        if len(text) >= 40:
            paragraphs.append(text)

    links = []

    for a in content_node.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        links.append({
            "text": text[:120],
            "url": href
        })

    images = []

    for img in content_node.select("img"):
        src = (
            img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("src")
        )

        if not src or src.startswith("data:image"):
            continue

        images.append({
            "url": src,
            "alt": clean_text(img.get("alt"))
        })

    full_text = clean_text(content_node.get_text(" "))

    word_count = len(re.findall(r"\w+", full_text))

    return {
        "headings": headings[:30],
        "paragraphs": paragraphs[:80],
        "mainText": full_text[:20000],
        "wordCount": word_count,
        "links": links[:80],
        "images": images[:40]
    }


def extract_category(soup, url):
    """Extract post category from DOM or URL."""
    for a in soup.select("a[rel='category tag'], a[rel='category']"):
        text = clean_text(a.get_text(" "))
        if text and len(text) < 60:
            return text

    for sel in [".cat-links a", ".posted-in a", ".categories a",
                ".entry-meta a[href*='/category/']", ".breadcrumb a", ".breadcrumbs a"]:
        node = soup.select_one(sel)
        if node:
            text = clean_text(node.get_text(" "))
            if text and len(text) < 60:
                return text

    m = re.search(r'/category/([^/]+)/', url or "")
    if m:
        return m.group(1).replace("-", " ").title()

    return None


def extract_excerpt(soup, schema_article, max_chars=300):
    """Extract post excerpt from schema, meta, or first paragraph."""
    desc = (schema_article or {}).get("description")
    if desc and len(desc) > 30:
        return clean_text(desc)[:max_chars]

    for sel in ["meta[property='og:description']", "meta[name='description']"]:
        meta = soup.select_one(sel)
        if meta and meta.get("content"):
            text = clean_text(meta.get("content"))
            if text and len(text) > 30:
                return text[:max_chars]

    for p in soup.select(".entry-content p, .post-content p, article p"):
        text = clean_text(p.get_text(" "))
        if text and len(text) >= 80:
            return text[:max_chars]

    return None


def extract_article_sections(content_node):
    """Split article into heading-keyed sections."""
    sections = []
    current_heading = None
    current_paras = []

    for tag in content_node.find_all(["h2", "h3", "p"]):
        if tag.name in ("h2", "h3"):
            if current_heading is not None or current_paras:
                sections.append({
                    "heading": current_heading,
                    "text": " ".join(current_paras)[:1500]
                })
            current_heading = clean_text(tag.get_text(" "))
            current_paras = []
        else:
            text = clean_text(tag.get_text(" "))
            if text and len(text) >= 20:
                current_paras.append(text)

    if current_heading is not None or current_paras:
        sections.append({
            "heading": current_heading,
            "text": " ".join(current_paras)[:1500]
        })

    return [s for s in sections if s.get("heading") or s.get("text")][:25]


def _classify_post_source_type(url, base_domain):
    """Return sourceType for a blog post URL: internal_post / external_media / video."""
    if not url:
        return "internal_post"
    try:
        from urllib.parse import urlparse as _up
        domain = _up(url).netloc.lower().lstrip("www.")
    except Exception:
        domain = ""
    if any(v in domain for v in ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")):
        return "video"
    # havengreens.ca == havengreens.ca ✓; also handles www.havengreens.ca
    if base_domain and (domain == base_domain or domain.endswith("." + base_domain)):
        return "internal_post"
    return "external_media"


def _extract_url_from_p_text(p_text):
    """Extract URL from a [](url) or [](url "title") markdown link literal in text."""
    # Matches [](url) or [](url "optional title")
    m = re.search(r'\[\]\(([^)"]+)', p_text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Strip markdown title attribute: url "title text"
    raw = re.sub(r'\s+"[^"]*$', '', raw).strip()
    # Must look like an HTTP(S) URL
    if not raw.startswith("http"):
        return None
    # Reject fragment-only or anchor links
    if "/#" in raw or raw.endswith("#"):
        return None
    return raw


def extract_jina_section_posts(soup, base_url):
    """Fallback post extractor for Jina-generated HTML.

    _jina_markdown_to_html() converts each ## / ### heading into a <section>
    block.  Blog post cards in Jina markdown use empty-text links [](url)
    which the markdown converter intentionally skips (it requires non-empty
    bracket text), so those links survive as literal '[](url)' text inside
    <p> elements rather than real <a> tags.

    Strategy (in order):
    1. Section-based  — iterate <section> blocks; find URL from <a href> or
                        from [](url) literal text in <p>.
    2. mainText-based — if no <section> elements exist, parse the flat text
                        content using the repeating pattern:
                        Title  Month DD, YYYY  [](url)
    """
    from urllib.parse import urlparse as _up

    posts = []
    seen_urls = set()

    _DATE_RE = re.compile(
        r'\b(?:January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+\d{1,2},\s+\d{4}\b',
        re.IGNORECASE
    )

    _SKIP_HEADINGS = frozenset({
        "menu", "navigation", "footer", "sidebar",
        "contact us", "subscribe", "newsletter",
        "follow us", "social media", "recent posts",
        "categories", "tags", "search", "about",
        "stay connected", "media inquiries", "as seen on",
        "in the media", "press coverage", "featured in",
        "blogs & media", "blogs and media",
    })

    base_domain = _up(base_url or "").netloc.lower().lstrip("www.")

    # ------------------------------------------------------------------ #
    # PASS 1 — <section> blocks produced by _jina_markdown_to_html()      #
    # ------------------------------------------------------------------ #
    sections = soup.find_all("section")
    for sec in sections:
        heading_node = sec.find(["h2", "h3", "h4"])
        if not heading_node:
            continue

        title = clean_text(heading_node.get_text(" "))
        if not title or len(title.split()) < 2 or len(title) > 200:
            continue

        if title.lower() in _SKIP_HEADINGS:
            continue

        # Date — search section text
        sec_raw = sec.get_text(" ")
        date_m = _DATE_RE.search(sec_raw)
        date = date_m.group(0) if date_m else None

        # URL — prefer a real <a href>, else parse [](url) literal text
        link_url = None

        for a in sec.find_all("a", href=True):
            href = a.get("href", "")
            if href.startswith("http") and "#" not in href:
                link_url = href
                break

        if not link_url:
            for p in sec.find_all("p"):
                p_raw = p.get_text("")  # no separator to keep []()
                candidate = _extract_url_from_p_text(p_raw)
                if candidate:
                    link_url = candidate
                    break

        if not link_url:
            continue

        # Skip navigation/social/footer links by URL pattern
        link_lower = link_url.lower()
        if any(s in link_lower for s in ("/instagram", "/facebook", "/twitter",
                                          "/linkedin", "/tiktok", "/pinterest",
                                          "mailto:", "tel:")):
            continue

        norm = normalize_url(link_url, base_url)
        if not norm or norm in seen_urls:
            continue
        seen_urls.add(norm)

        posts.append({
            "title": title,
            "url": norm,
            "date": date,
            "image": None,
            "sourceType": _classify_post_source_type(norm, base_domain),
        })

    if posts:
        return posts[:50]

    # ------------------------------------------------------------------ #
    # PASS 2 — flat mainText fallback when no <section> blocks exist      #
    # Pattern: Title  Month DD, YYYY  [](url)                             #
    # ------------------------------------------------------------------ #
    main_text_node = soup.find("body") or soup
    flat_text = main_text_node.get_text(" ")

    _MONTH = (r'(?:January|February|March|April|May|June|July|August|'
              r'September|October|November|December)')
    _FLAT_RE = re.compile(
        r'([A-Z][^\[\n]{10,180}?)\s+'          # title (starts uppercase)
        r'(' + _MONTH + r'\s+\d{1,2},\s+\d{4})\s+'  # Month DD, YYYY
        r'\[\]\(([^)"]+)',                      # [](url  (up to " or ))
        re.IGNORECASE
    )

    for m in _FLAT_RE.finditer(flat_text):
        title = clean_text(m.group(1))
        date = clean_text(m.group(2))
        raw_url = m.group(3).strip()
        raw_url = re.sub(r'\s+"[^"]*$', '', raw_url).strip()

        if not raw_url.startswith("http"):
            continue
        if "/#" in raw_url or raw_url.endswith("#"):
            continue

        norm = normalize_url(raw_url, base_url)
        if not norm or norm in seen_urls:
            continue
        if len(title.split()) < 2 or len(title) > 200:
            continue

        seen_urls.add(norm)
        posts.append({
            "title": title,
            "url": norm,
            "date": date,
            "image": None,
            "sourceType": _classify_post_source_type(norm, base_domain),
        })

    return posts[:50]


def extract_article_schema_summary(json_ld_items):
    flattened = []

    for item in json_ld_items:
        flattened.extend(flatten_json_ld_items(item))

    article = {}

    for item in flattened:
        item_type = item.get("@type")

        if isinstance(item_type, list):
            types = [str(t).lower() for t in item_type]
        elif item_type:
            types = [str(item_type).lower()]
        else:
            types = []

        if any(t in types for t in ["article", "blogposting", "newsarticle"]):
            author = item.get("author")

            if isinstance(author, dict):
                author_name = author.get("name")
            else:
                author_name = author

            article = {
                "type": item.get("@type"),
                "headline": clean_text(item.get("headline")),
                "description": clean_text(item.get("description")),
                "datePublished": item.get("datePublished"),
                "dateModified": item.get("dateModified"),
                "author": clean_text(author_name),
                "publisher": item.get("publisher")
            }

            break

    return article


# -----------------------------
# CONTENT ANALYSIS HELPERS
# -----------------------------

def _detect_search_intent(title, headings, paragraphs):
    """Return 'transactional', 'commercial', or 'informational'."""
    combined = " ".join(
        [title or ""]
        + [h.get("text", "") for h in (headings or [])[:5]]
        + (paragraphs or [])[:3]
    ).lower()
    if any(w in combined for w in ["buy", "order", "purchase", "add to cart", "checkout"]):
        return "transactional"
    if any(w in combined for w in ["best ", "top ", "review", " vs ", "compare", "recommend", "alternative"]):
        return "commercial"
    return "informational"


def _detect_funnel_stage(title, headings, has_products):
    """Return 'bottom_of_funnel', 'middle_of_funnel', or 'top_of_funnel'."""
    combined = " ".join([title or ""] + [h.get("text", "") for h in (headings or [])[:5]]).lower()
    if any(w in combined for w in ["best ", "top ", " vs ", "review", "compare", "choosing", "should i"]):
        return "bottom_of_funnel" if has_products else "middle_of_funnel"
    if any(w in combined for w in ["how to", "guide", "tips", "benefits", "what is", "why "]):
        return "top_of_funnel"
    return "top_of_funnel"


def _extract_target_keyword(title, headings):
    source = title or (headings[0].get("text") if headings else None)
    if not source:
        return None
    cleaned = re.sub(r'\s*[\|–—\-]\s*\S+.*$', '', source).strip()
    return (cleaned or source).lower()


def _extract_secondary_keywords(headings):
    _NOISE = re.compile(
        r'^\s*(step\s+\d+|tip\s+\d+|method\s+\d+|\d+[\.\)]\s+|how\s+to\s|why\s|what\s+is\s)',
        re.I,
    )
    return [
        h.get("text", "").lower()
        for h in (headings or [])
        if h.get("level") in ("h2", "h3") and h.get("text")
        and not _NOISE.match(h.get("text", ""))
    ][:10]


def _cluster_blog_topics(titles):
    from collections import Counter as _Counter
    clusters = {
        "how_to":    (["how to", "guide", "tutorial", "tips", "steps", "ways"], []),
        "product":   (["best", "review", "top", "vs", "compare", "recommend"], []),
        "education": (["what is", "benefits", "why", "about", "understand", "learn"], []),
        "lifestyle": (["routine", "daily", "weekly", "morning", "night", "seasonal"], []),
    }
    general = []
    for title in titles:
        t = title.lower()
        matched = False
        for _, (keywords, bucket) in clusters.items():
            if any(kw in t for kw in keywords):
                bucket.append(title)
                matched = True
                break
        if not matched:
            general.append(title)
    result = {}
    for cluster, (_, bucket) in clusters.items():
        if bucket:
            result[cluster] = bucket[:10]
    if general:
        result["general"] = general[:10]
    return result


def _build_listing_content_analysis(posts, headings):
    from collections import Counter as _Counter
    skip = {
        "a", "an", "the", "for", "in", "on", "at", "to", "of", "and", "or", "is", "are",
        "how", "why", "what", "when", "where", "with", "that", "this", "from",
        "your", "our", "you", "we", "it", "be", "was", "were", "by", "do", "get",
    }
    titles = [p.get("title", "") for p in (posts or [])]
    words = []
    for t in titles:
        for w in re.findall(r'\b[a-z]{3,}\b', t.lower()):
            if w not in skip:
                words.append(w)
    dominant = [w for w, _ in _Counter(words).most_common(8)]
    return {
        "searchIntent": "informational",
        "funnelStage": "top_of_funnel",
        "dominantTopics": dominant,
        "postCount": len(posts),
        "topicClusters": _cluster_blog_topics(titles),
    }


def analyze_wordpress_article(self, url, html, headers, page_type, level1):
    result = self.base_result(
        url,
        html,
        headers,
        page_type,
        level1
    )

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_dom_for_article(html)

    result["source"]["extractor"] = "WordPress Article Extractor"
    # Override pageType so single posts are "blogPost", not "article" or "blog"
    result["page"]["pageType"] = "blogPost"

    seo = extract_basic_seo(raw_soup, url)
    open_graph = extract_open_graph(raw_soup)
    json_ld_items = extract_json_ld_items(raw_soup)
    schema_article = extract_article_schema_summary(json_ld_items)

    article_content = extract_article_content(content_soup)
    dates = extract_dates(raw_soup)

    word_count = article_content.get("wordCount", 0)
    reading_time = max(1, round(word_count / 200))

    date_published = dates.get("published") or schema_article.get("datePublished")
    date_modified = dates.get("modified") or schema_article.get("dateModified")

    post_title = (
        seo.get("h1")
        or schema_article.get("headline")
        or open_graph.get("title")
        or seo.get("title")
    )

    result["seo"] = seo
    result["openGraph"] = open_graph

    result["blogPost"] = {
        "title": post_title,
        "datePublished": date_published,
        "dateModified": date_modified,
        "author": extract_author(raw_soup) or schema_article.get("author"),
        "category": extract_category(raw_soup, url),
        "featuredImage": extract_featured_image(raw_soup, url),
        "excerpt": extract_excerpt(raw_soup, schema_article),
        "content": article_content.get("mainText", ""),
        "headings": article_content.get("headings", []),
        "sections": extract_article_sections(content_soup),
        "links": article_content.get("links", []),
        "images": article_content.get("images", []),
        "wordCount": word_count,
        "estimatedReadingTime": reading_time,
        "schema": schema_article,
        "contentAnalysis": {
            "searchIntent": _detect_search_intent(
                post_title,
                article_content.get("headings", []),
                article_content.get("paragraphs", []),
            ),
            "funnelStage": _detect_funnel_stage(
                post_title,
                article_content.get("headings", []),
                False,
            ),
            "targetKeyword": _extract_target_keyword(
                post_title,
                article_content.get("headings", []),
            ),
            "secondaryKeywords": _extract_secondary_keywords(
                article_content.get("headings", [])
            ),
        },
    }

    result["content"] = {
        "pageTitle": post_title,
        "mainText": article_content.get("mainText", ""),
        "headings": article_content.get("headings", []),
        "links": article_content.get("links", []),
        "images": article_content.get("images", [])
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20],
        "articleSchema": schema_article
    }

    result["products"] = []

    confidence = 0.45

    if post_title:
        confidence += 0.15

    if word_count >= 300:
        confidence += 0.20

    if article_content.get("headings"):
        confidence += 0.05

    if date_published:
        confidence += 0.05

    if schema_article:
        confidence += 0.10

    result["source"]["confidence"] = round(
        min(max(confidence, 0.35), 0.95),
        2
    )

    return result


# -----------------------------
# BLOG LISTING EXTRACTOR
# -----------------------------

def extract_post_cards(soup, base_url):
    posts = []

    card_selectors = [
        "article",
        ".post",
        ".blog-post",
        ".post-card",
        ".elementor-post",
        ".wp-block-post",
        ".type-post",
        ".entry"
    ]

    nodes = []

    for selector in card_selectors:
        found = soup.select(selector)

        if found:
            nodes.extend(found)

    for node in nodes:
        text = clean_text(node.get_text(" "))

        if len(text) < 40:
            continue

        link = None

        for a in node.select("a[href]"):
            href = a.get("href")
            link_text = clean_text(a.get_text(" "))

            if not href:
                continue

            href_lower = href.lower()

            if any(x in href_lower for x in ["#", "comment", "reply", "author"]):
                continue

            if len(link_text) >= 5:
                link = a
                break

        if not link:
            continue

        title = None

        for selector in ["h2", "h3", ".entry-title", ".post-title", ".elementor-post__title"]:
            h = node.select_one(selector)

            if h:
                title = clean_text(h.get_text(" "))

                if title:
                    break

        if not title:
            title = clean_text(link.get_text(" "))

        if not title or len(title) > 180:
            continue

        excerpt = None

        for selector in [".excerpt", ".entry-summary", ".post-excerpt", ".elementor-post__excerpt", "p"]:
            p = node.select_one(selector)

            if p:
                excerpt = clean_text(p.get_text(" "))

                if excerpt and len(excerpt) >= 30:
                    break

        img_url = None
        img = node.select_one("img")

        if img:
            src = (
                img.get("data-src")
                or img.get("data-lazy-src")
                or img.get("src")
            )

            if src and not src.startswith("data:image"):
                img_url = normalize_url(src, base_url)

        date = None
        time_node = node.select_one("time[datetime], .date, .posted-on, .entry-date")

        if time_node:
            date = (
                time_node.get("datetime")
                or time_node.get_text(" ")
            )
            date = clean_text(date)

        posts.append({
            "title": title,
            "url": normalize_url(link.get("href"), base_url),
            "excerpt": excerpt,
            "date": date,
            "image": img_url
        })

    return unique_items(posts, "url")[:50]


def extract_blog_categories(soup, base_url):
    categories = []

    category_patterns = [
        "/category/",
        "/tag/",
        "/blog/category/",
        "/blogs/",
        "/articles/",
        "/news/"
    ]

    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        href_lower = href.lower()

        if not any(pattern in href_lower for pattern in category_patterns):
            continue

        if len(text) > 80:
            continue

        categories.append({
            "text": text,
            "url": normalize_url(href, base_url)
        })

    return unique_items(categories, "url")[:40]


def detect_pagination(soup, base_url):
    page_links = []
    for selector in [
        ".pagination a[href]",
        ".nav-links a[href]",
        ".page-numbers[href]",
        "a.next[href]",
        "a.prev[href]",
        "[rel='next']",
        "[rel='prev']",
    ]:
        for a in soup.select(selector):
            href = a.get("href")
            if href:
                page_links.append({
                    "text": clean_text(a.get_text(" ")),
                    "url": normalize_url(href, base_url)
                })
    return {
        "detected": bool(page_links),
        "pageLinks": unique_items(page_links, "url")[:20]
    }


def analyze_wordpress_blog_listing(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    result["source"]["extractor"] = "WordPress Blog Listing Extractor"

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = BeautifulSoup(html or "", "lxml")

    seo = extract_basic_seo(raw_soup, url)
    og = extract_open_graph(raw_soup)
    json_ld_items = extract_json_ld_items(raw_soup)

    posts = extract_post_cards(content_soup, url)
    if not posts:
        posts = extract_jina_section_posts(content_soup, url)

    categories = extract_blog_categories(raw_soup, url)
    pagination = detect_pagination(raw_soup, url)
    content_analysis = _build_listing_content_analysis(posts, [])

    listing_title = seo.get("h1") or og.get("title") or seo.get("title")

    result["seo"] = seo
    result["openGraph"] = og

    result["blog"] = {
        "listingTitle": listing_title,
        "postsCount": len(posts),
        "posts": posts,
        "categories": categories,
        "pagination": pagination,
        "contentAnalysis": content_analysis,
    }

    result["content"] = {
        "pageTitle": listing_title,
        "mainText": clean_text(content_soup.get_text(" "))[:12000],
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20],
    }

    result["products"] = []

    confidence = 0.45
    if posts:
        confidence += 0.25
    if len(posts) >= 3:
        confidence += 0.10
    if categories:
        confidence += 0.05
    if pagination.get("detected"):
        confidence += 0.05

    result["source"]["confidence"] = round(min(max(confidence, 0.35), 0.95), 2)
    return result


def analyze_wordpress_blog(self, url, html, headers, page_type, level1):
    soup = BeautifulSoup(html or "", "lxml")
    detected_type = detect_blog_page_type(url, soup)

    if detected_type == "article":
        return analyze_wordpress_article(self, url, html, headers, "blogPost", level1)

    if detected_type == "blogListing":
        return analyze_wordpress_blog_listing(self, url, html, headers, "blogListing", level1)

    # Fallback: long content is probably an article
    text = clean_text(soup.get_text(" "))
    if len(re.findall(r"\w+", text)) >= 400:
        return analyze_wordpress_article(self, url, html, headers, "blogPost", level1)

    return analyze_wordpress_blog_listing(self, url, html, headers, "blogListing", level1)


# -----------------------------
# PUBLIC ENTRYPOINT
# -----------------------------

def analyze_blog(self, url, html, headers, page_type, level1):
    return analyze_wordpress_blog(
        self,
        url,
        html,
        headers,
        page_type,
        level1
    )