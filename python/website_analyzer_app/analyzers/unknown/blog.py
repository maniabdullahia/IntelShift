from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import json
from collections import Counter


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_url(raw_url, base_url=None):
    if not raw_url:
        return None
    s = str(raw_url).lower()
    if s.startswith("javascript:") or s.startswith("mailto:") or s.startswith("tel:"):
        return None
    full_url = urljoin(base_url or "", raw_url)
    parsed = urlparse(full_url)
    cleaned = parsed._replace(query="", fragment="")
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


def clean_dom_for_blog(html):
    """Remove nav/header/footer/social noise before extraction."""
    soup = BeautifulSoup(html or "", "lxml")
    remove_selectors = [
        "script", "style", "noscript", "iframe", "svg", "form", "template",
        "header", "footer", "nav",
        ".menu", ".navbar", ".site-header", ".site-footer",
        ".sidebar", ".widget", ".comments", "#comments",
        ".comment-respond", ".related-posts", ".newsletter",
        ".popup", ".modal", ".drawer", ".cookie",
        ".announcement-bar", ".top-bar", ".promo-bar",
        ".breadcrumb", ".breadcrumbs", ".share-buttons", ".social-share",
        ".pagination", ".search-modal", ".predictive-search",
        "[class*='cookie']", "[class*='popup']", "[class*='modal']",
        "[class*='share']", "[class*='social']", "[class*='newsletter']",
        "[class*='breadcrumb']", "[class*='announcement']",
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


def flatten_json_ld(item):
    output = []
    if isinstance(item, list):
        for child in item:
            output.extend(flatten_json_ld(child))
    elif isinstance(item, dict):
        output.append(item)
        for child in (item.get("@graph") or []):
            output.extend(flatten_json_ld(child))
    return output


# ---------------------------------------------------------------------------
# PAGE-TYPE DETECTION
# ---------------------------------------------------------------------------

def detect_blog_page_type(url, soup):
    """Return 'article', 'blogListing', or 'unknownBlog'."""
    url_path = urlparse(url or "").path.lower()
    body_classes = " ".join(soup.body.get("class", [])).lower() if soup.body else ""

    json_ld_items = extract_json_ld_items(soup)
    article_schema = False
    for item in json_ld_items:
        for flat in flatten_json_ld(item):
            t = flat.get("@type", "")
            types = [x.lower() for x in (t if isinstance(t, list) else [t])]
            if any(x in types for x in ["article", "blogposting", "newsarticle"]):
                article_schema = True

    single_post_signals = [
        "single-post" in body_classes,
        "post-template" in body_classes,
        "article" in body_classes,
        article_schema,
        bool(soup.select_one("article")),
        bool(soup.select_one(".post-content, .entry-content, .wp-block-post-content")),
    ]
    listing_signals = [
        "blog" in body_classes,
        "archive" in body_classes,
        "category" in body_classes,
        "/blog" in url_path,
        "/blogs" in url_path,
        "/news" in url_path,
        "/articles" in url_path,
        bool(soup.select(".post, article, .blog-post, .post-card")),
    ]

    # /blog/some-post-title -> article; /blog/ -> listing
    path_parts = [p for p in url_path.split("/") if p]
    blog_keywords = ("blog", "blogs", "news", "articles")
    blog_idx = next((i for i, p in enumerate(path_parts) if p in blog_keywords), None)
    if blog_idx is not None and blog_idx < len(path_parts) - 1:
        single_post_signals.append(True)

    if any(single_post_signals):
        return "article"
    if any(listing_signals):
        return "blogListing"
    return "unknownBlog"


# ---------------------------------------------------------------------------
# ARTICLE EXTRACTION
# ---------------------------------------------------------------------------

def extract_author(soup):
    """Extract author from DOM selectors, meta, or JSON-LD."""
    for selector in [".author", ".byline", ".post-author", "[rel='author']", ".entry-author"]:
        node = soup.select_one(selector)
        if node:
            text = re.sub(r"^(by|author|written by)\s+", "", clean_text(node.get_text(" ")), flags=re.I)
            text = clean_text(text)
            if text and len(text) <= 80:
                return text

    meta_author = soup.select_one("meta[name='author']")
    if meta_author:
        return clean_text(meta_author.get("content"))

    for item in extract_json_ld_items(soup):
        for flat in flatten_json_ld(item):
            t = flat.get("@type", "")
            types = [x.lower() for x in (t if isinstance(t, list) else [t])]
            if any(x in types for x in ["article", "blogposting", "newsarticle"]):
                author_data = flat.get("author")
                if isinstance(author_data, dict):
                    return clean_text(author_data.get("name"))
                elif isinstance(author_data, list) and author_data:
                    first = author_data[0]
                    return clean_text(first.get("name") if isinstance(first, dict) else str(first))
                elif isinstance(author_data, str):
                    return clean_text(author_data)
    return None


def extract_dates(soup):
    """Return {published, modified} from meta tags and DOM."""
    published = None
    modified = None

    for selector in [
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "time[datetime]",
        ".published", ".posted-on", ".entry-date",
    ]:
        node = soup.select_one(selector)
        if node:
            v = node.get("content") or node.get("datetime") or node.get_text(" ")
            v = clean_text(v)
            if v:
                published = v
                break

    for selector in [
        "meta[property='article:modified_time']",
        "meta[name='article:modified_time']",
        ".updated", ".modified",
    ]:
        node = soup.select_one(selector)
        if node:
            v = node.get("content") or node.get("datetime") or node.get_text(" ")
            v = clean_text(v)
            if v:
                modified = v
                break

    return {"published": published, "modified": modified}


def extract_featured_image(soup, base_url):
    """Return {url, alt, source} for the article featured image."""
    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        return {
            "url": normalize_url(og_image.get("content"), base_url),
            "alt": None,
            "source": "og:image",
        }

    for selector in [
        ".post-thumbnail img", ".featured-image img",
        ".entry-content img", "article img",
        ".article-template img", "#MainContent img",
    ]:
        img = soup.select_one(selector)
        if not img:
            continue
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
        if src and not src.startswith("data:image"):
            return {
                "url": normalize_url(src, base_url),
                "alt": clean_text(img.get("alt")),
                "source": selector,
            }
    return None


def extract_article_content(soup):
    """Extract headings, paragraphs, links, images and word count."""
    content_node = (
        soup.select_one("article .entry-content")
        or soup.select_one(".entry-content")
        or soup.select_one(".post-content")
        or soup.select_one(".wp-block-post-content")
        or soup.select_one(".article-template")
        or soup.select_one(".rte")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.body
        or soup
    )

    headings = []
    for h in content_node.select("h2, h3, h4"):
        text = clean_text(h.get_text(" "))
        if text and len(text) <= 160:
            headings.append({"tag": h.name, "text": text})

    paragraphs = []
    for p in content_node.select("p"):
        text = clean_text(p.get_text(" "))
        if len(text) >= 40:
            paragraphs.append(text)
    paragraphs = list(dict.fromkeys(paragraphs))

    links = []
    for a in content_node.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href")
        if text and href:
            links.append({"text": text[:120], "url": href})

    images = []
    for img in content_node.select("img"):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
        if not src or src.startswith("data:image"):
            continue
        src_lower = src.lower()
        if any(p in src_lower for p in ["icon", "logo", "placeholder", "avatar", "emoji", "svg"]):
            continue
        images.append({"url": src, "alt": clean_text(img.get("alt", ""))})

    full_text = clean_text(content_node.get_text(" "))
    word_count = len(re.findall(r"\w+", full_text))

    return {
        "headings": headings[:30],
        "paragraphs": paragraphs[:80],
        "mainText": full_text[:20000],
        "wordCount": word_count,
        "links": links[:80],
        "images": unique_items(images, "url")[:40],
    }


def extract_article_sections(soup):
    """Split article into {heading, text} sections keyed by H2/H3."""
    content_node = (
        soup.select_one("article .entry-content")
        or soup.select_one(".entry-content")
        or soup.select_one(".post-content")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.body
        or soup
    )
    sections = []
    current_heading = None
    current_paras = []

    for tag in content_node.find_all(["h2", "h3", "p"]):
        if tag.name in ("h2", "h3"):
            if current_heading is not None or current_paras:
                sections.append({
                    "heading": current_heading,
                    "text": " ".join(current_paras)[:1500],
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
            "text": " ".join(current_paras)[:1500],
        })

    return [s for s in sections if s.get("heading") or s.get("text")][:25]


def extract_category(soup, url):
    """Extract post category from DOM or URL slug."""
    for a in soup.select("a[rel='category tag'], a[rel='category']"):
        text = clean_text(a.get_text(" "))
        if text and len(text) < 60:
            return text

    for sel in [
        ".cat-links a", ".posted-in a", ".categories a",
        ".entry-meta a[href*='/category/']", ".breadcrumb a", ".breadcrumbs a",
    ]:
        node = soup.select_one(sel)
        if node:
            text = clean_text(node.get_text(" "))
            if text and len(text) < 60:
                return text

    m = re.search(r'/category/([^/]+)/', url or "")
    if m:
        return m.group(1).replace("-", " ").title()
    return None


def extract_excerpt(soup, max_chars=300):
    """Extract article excerpt from meta or first paragraph."""
    for sel in ["meta[property='og:description']", "meta[name='description']"]:
        meta = soup.select_one(sel)
        if meta and meta.get("content"):
            text = clean_text(meta.get("content"))
            if text and len(text) > 30:
                return text[:max_chars]

    for p in soup.select(".entry-content p, .post-content p, .rte p, article p"):
        text = clean_text(p.get_text(" "))
        if text and len(text) >= 80:
            return text[:max_chars]
    return None


def extract_faqs(soup):
    """Extract FAQ pairs from headings that contain a question mark."""
    faqs = []
    for node in soup.find_all(["h2", "h3", "h4"]):
        question = clean_text(node.get_text(" "))
        if "?" not in question:
            continue
        answer_parts = []
        current = node.find_next_sibling()
        while current:
            if current.name in ("h2", "h3", "h4"):
                break
            text = clean_text(current.get_text(" "))
            if len(text) > 40:
                answer_parts.append(text)
            current = current.find_next_sibling()
        answer = clean_text(" ".join(answer_parts))
        if len(answer) >= 40:
            faqs.append({"question": question, "answer": answer[:1000]})
    return faqs[:20]


def extract_article_schema(json_ld_items):
    """Pull headline, dates, author from JSON-LD article types."""
    for item in json_ld_items:
        for flat in flatten_json_ld(item):
            t = flat.get("@type", "")
            types = [x.lower() for x in (t if isinstance(t, list) else [t])]
            if any(x in types for x in ["article", "blogposting", "newsarticle"]):
                author_data = flat.get("author")
                if isinstance(author_data, dict):
                    author_name = author_data.get("name")
                elif isinstance(author_data, list) and author_data:
                    first = author_data[0]
                    author_name = first.get("name") if isinstance(first, dict) else str(first)
                else:
                    author_name = author_data
                return {
                    "type": flat.get("@type"),
                    "headline": clean_text(flat.get("headline")),
                    "description": clean_text(flat.get("description")),
                    "datePublished": flat.get("datePublished"),
                    "dateModified": flat.get("dateModified"),
                    "author": clean_text(author_name),
                    "publisher": flat.get("publisher"),
                }
    return {}


# ---------------------------------------------------------------------------
# LISTING EXTRACTION
# ---------------------------------------------------------------------------

def extract_post_cards(soup, base_url):
    """Extract blog post cards from a listing page."""
    posts = []
    card_selectors = [
        "article", ".post", ".blog-post", ".post-card",
        ".elementor-post", ".wp-block-post", ".type-post", ".entry",
        ".blog-item", ".news-item",
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
            href = a.get("href", "")
            link_text = clean_text(a.get_text(" "))
            if any(x in href.lower() for x in ["#", "comment", "reply", "author"]):
                continue
            if len(link_text) >= 5:
                link = a
                break
        if not link:
            continue

        title = None
        for sel in ["h2", "h3", ".entry-title", ".post-title", ".elementor-post__title", ".card__heading"]:
            h = node.select_one(sel)
            if h:
                title = clean_text(h.get_text(" "))
                if title:
                    break
        if not title:
            title = clean_text(link.get_text(" "))
        if not title or len(title) > 180:
            continue

        excerpt = None
        for sel in [".excerpt", ".entry-summary", ".post-excerpt", ".elementor-post__excerpt", "p"]:
            p = node.select_one(sel)
            if p:
                ex = clean_text(p.get_text(" "))
                if ex and len(ex) >= 30:
                    excerpt = ex
                    break

        img_url = None
        img = node.select_one("img")
        if img:
            src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
            if src and not src.startswith("data:image"):
                img_url = normalize_url(src, base_url)

        date = None
        time_node = node.select_one("time[datetime], .date, .posted-on, .entry-date")
        if time_node:
            date = clean_text(time_node.get("datetime") or time_node.get_text(" "))

        posts.append({
            "title": title,
            "url": normalize_url(link.get("href"), base_url),
            "excerpt": excerpt,
            "date": date,
            "image": img_url,
        })

    return unique_items(posts, "url")[:50]


_DATE_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)

_JINA_SKIP_HEADINGS = frozenset({
    "menu", "navigation", "footer", "sidebar",
    "contact us", "subscribe", "newsletter", "follow us", "social media",
    "recent posts", "categories", "tags", "search", "about",
    "stay connected", "blogs & media", "blogs and media",
    "as seen on", "in the media", "press coverage",
})


def _extract_url_from_p_text(p_text):
    """Extract URL from [](url) markdown literal text."""
    m = re.search(r"\[\]\(([^)\"]+)", p_text)
    if not m:
        return None
    raw = re.sub(r'\s+"[^"]*$', "", m.group(1)).strip()
    if not raw.startswith("http") or raw.endswith("#"):
        return None
    return raw


def _classify_post_source_type(url, base_domain):
    if not url:
        return "internal_post"
    try:
        domain = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        domain = ""
    if any(v in domain for v in ("youtube.com", "youtu.be", "vimeo.com")):
        return "video"
    if base_domain and (domain == base_domain or domain.endswith("." + base_domain)):
        return "internal_post"
    return "external_media"


def extract_jina_section_posts(soup, base_url):
    """Fallback: parse Jina-converted HTML sections for blog post listings."""
    posts = []
    seen_urls = set()
    base_domain = urlparse(base_url or "").netloc.lower().lstrip("www.")

    for sec in soup.find_all("section"):
        heading_node = sec.find(["h2", "h3", "h4"])
        if not heading_node:
            continue
        title = clean_text(heading_node.get_text(" "))
        if not title or len(title.split()) < 2 or len(title) > 200:
            continue
        if title.lower() in _JINA_SKIP_HEADINGS:
            continue

        sec_raw = sec.get_text(" ")
        date_m = _DATE_RE.search(sec_raw)
        date = date_m.group(0) if date_m else None

        link_url = None
        for a in sec.find_all("a", href=True):
            href = a.get("href", "")
            if href.startswith("http") and "#" not in href:
                link_url = href
                break
        if not link_url:
            for p in sec.find_all("p"):
                candidate = _extract_url_from_p_text(p.get_text(""))
                if candidate:
                    link_url = candidate
                    break
        if not link_url:
            continue

        link_lower = link_url.lower()
        if any(s in link_lower for s in ("/instagram", "/facebook", "/twitter", "/linkedin", "mailto:", "tel:")):
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

    # Flat text fallback: "Title  Month DD, YYYY  [](url)"
    _MONTH = (r"(?:January|February|March|April|May|June|July|August|"
               r"September|October|November|December)")
    _FLAT_RE = re.compile(
        r"([A-Z][^\[\n]{10,180}?)\s+(" + _MONTH + r"\s+\d{1,2},\s+\d{4})\s+\[\]\(([^)\"]+)",
        re.IGNORECASE,
    )
    flat_text = (soup.find("body") or soup).get_text(" ")
    for m in _FLAT_RE.finditer(flat_text):
        title = clean_text(m.group(1))
        date = clean_text(m.group(2))
        raw_url = re.sub(r'\s+"[^"]*$', "", m.group(3)).strip()
        if not raw_url.startswith("http") or raw_url.endswith("#"):
            continue
        norm = normalize_url(raw_url, base_url)
        if not norm or norm in seen_urls or len(title.split()) < 2 or len(title) > 200:
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


def extract_blog_categories(soup, base_url):
    """Extract blog category links."""
    categories = []
    patterns = ["/category/", "/tag/", "/blog/category/", "/blogs/", "/articles/", "/news/"]
    for a in soup.select("a[href]"):
        text = clean_text(a.get_text(" "))
        href = a.get("href", "")
        if not text or not href:
            continue
        if not any(p in href.lower() for p in patterns):
            continue
        if len(text) > 80:
            continue
        categories.append({"text": text, "url": normalize_url(href, base_url)})
    return unique_items(categories, "url")[:40]


def detect_pagination(soup, base_url):
    """Detect next/prev page links for listing pages."""
    page_links = []
    for selector in [
        ".pagination a[href]", ".nav-links a[href]", ".page-numbers[href]",
        "a.next[href]", "a.prev[href]", "[rel='next']", "[rel='prev']",
    ]:
        for a in soup.select(selector):
            href = a.get("href")
            if href:
                page_links.append({"text": clean_text(a.get_text(" ")), "url": normalize_url(href, base_url)})
    return {"detected": bool(page_links), "pageLinks": unique_items(page_links, "url")[:20]}


# ---------------------------------------------------------------------------
# CONTENT ANALYSIS (search intent, funnel, topic clustering)
# ---------------------------------------------------------------------------

def _detect_search_intent(title, headings, paragraphs):
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
    cleaned = re.sub(r"\s*[|–—-]\s*\S+.*$", "", source).strip()
    return (cleaned or source).lower()


def _extract_secondary_keywords(headings):
    _NOISE = re.compile(
        r"^\s*(step\s+\d+|tip\s+\d+|method\s+\d+|\d+[.)]\s+|how\s+to\s|why\s|what\s+is\s)",
        re.I,
    )
    return [
        h.get("text", "").lower()
        for h in (headings or [])
        if h.get("tag") in ("h2", "h3") and h.get("text")
        and not _NOISE.match(h.get("text", ""))
    ][:10]


def _cluster_blog_topics(titles):
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
    skip = {
        "a", "an", "the", "for", "in", "on", "at", "to", "of", "and", "or", "is", "are",
        "how", "why", "what", "when", "where", "with", "that", "this", "from",
        "your", "our", "you", "we", "it", "be", "was", "were", "by", "do", "get",
    }
    titles = [p.get("title", "") for p in (posts or [])]
    words = []
    for t in titles:
        for w in re.findall(r"\b[a-z]{3,}\b", t.lower()):
            if w not in skip:
                words.append(w)
    dominant = [w for w, _ in Counter(words).most_common(8)]
    return {
        "searchIntent": "informational",
        "funnelStage": "top_of_funnel",
        "dominantTopics": dominant,
        "postCount": len(posts),
        "topicClusters": _cluster_blog_topics(titles),
    }


# ---------------------------------------------------------------------------
# MAIN ANALYZERS
# ---------------------------------------------------------------------------

def _analyze_article(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    result["source"]["extractor"] = "Unknown Blog Article Extractor"
    result["page"]["pageType"] = "blogPost"

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_dom_for_blog(html)

    seo_title = None
    title_tag = raw_soup.find("title")
    if title_tag:
        seo_title = clean_text(title_tag.get_text(" "))
    h1_tag = raw_soup.find("h1")
    seo_h1 = clean_text(h1_tag.get_text(" ")) if h1_tag else None
    meta_desc = raw_soup.select_one("meta[name='description']")
    seo_meta = clean_text(meta_desc.get("content")) if meta_desc else None
    canonical_tag = raw_soup.select_one("link[rel='canonical']")
    seo_canonical = normalize_url(canonical_tag.get("href"), url) if canonical_tag else None

    og = {}
    for meta in raw_soup.select("meta[property^='og:']"):
        prop = meta.get("property", "").replace("og:", "")
        content = meta.get("content")
        if prop and content:
            og[prop] = clean_text(content)

    json_ld_items = extract_json_ld_items(raw_soup)
    schema_article = extract_article_schema(json_ld_items)

    article_content = extract_article_content(content_soup)
    sections = extract_article_sections(content_soup)
    dates = extract_dates(raw_soup)
    faqs = extract_faqs(content_soup)

    word_count = article_content.get("wordCount", 0)
    reading_time = max(1, round(word_count / 200))

    date_published = dates.get("published") or schema_article.get("datePublished")
    date_modified = dates.get("modified") or schema_article.get("dateModified")
    author = extract_author(raw_soup) or schema_article.get("author")

    post_title = (
        seo_h1
        or schema_article.get("headline")
        or og.get("title")
        or seo_title
    )

    headings = article_content.get("headings", [])
    paragraphs = article_content.get("paragraphs", [])

    content_analysis = {
        "searchIntent": _detect_search_intent(post_title, headings, paragraphs),
        "funnelStage": _detect_funnel_stage(post_title, headings, False),
        "targetKeyword": _extract_target_keyword(post_title, headings),
        "secondaryKeywords": _extract_secondary_keywords(headings),
    }

    result["seo"] = {
        "title": seo_title,
        "metaDescription": seo_meta,
        "canonical": seo_canonical,
        "h1": seo_h1,
    }
    result["openGraph"] = og

    result["blogPost"] = {
        "title": post_title,
        "datePublished": date_published,
        "dateModified": date_modified,
        "author": author,
        "category": extract_category(raw_soup, url),
        "excerpt": extract_excerpt(raw_soup),
        "featuredImage": extract_featured_image(raw_soup, url),
        "content": article_content.get("mainText", ""),
        "headings": headings,
        "sections": sections,
        "paragraphs": paragraphs[:20],
        "links": article_content.get("links", []),
        "images": article_content.get("images", []),
        "faqs": faqs,
        "wordCount": word_count,
        "estimatedReadingTime": reading_time,
        "schema": schema_article,
        "contentAnalysis": content_analysis,
    }

    result["content"] = {
        "pageTitle": post_title,
        "mainText": article_content.get("mainText", ""),
        "headings": headings,
        "links": article_content.get("links", []),
        "images": article_content.get("images", []),
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20],
        "articleSchema": schema_article,
    }

    result["products"] = []

    confidence = 0.45
    if post_title:
        confidence += 0.15
    if word_count >= 300:
        confidence += 0.20
    if headings:
        confidence += 0.05
    if date_published:
        confidence += 0.05
    if schema_article:
        confidence += 0.10

    result["source"]["confidence"] = round(min(max(confidence, 0.35), 0.95), 2)
    return result


def _analyze_listing(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    result["source"]["extractor"] = "Unknown Blog Listing Extractor"

    raw_soup = BeautifulSoup(html or "", "lxml")
    content_soup = clean_dom_for_blog(html)

    seo_title = None
    title_tag = raw_soup.find("title")
    if title_tag:
        seo_title = clean_text(title_tag.get_text(" "))
    h1_tag = raw_soup.find("h1")
    seo_h1 = clean_text(h1_tag.get_text(" ")) if h1_tag else None
    meta_desc = raw_soup.select_one("meta[name='description']")
    seo_meta = clean_text(meta_desc.get("content")) if meta_desc else None
    canonical_tag = raw_soup.select_one("link[rel='canonical']")
    seo_canonical = normalize_url(canonical_tag.get("href"), url) if canonical_tag else None

    og = {}
    for meta in raw_soup.select("meta[property^='og:']"):
        prop = meta.get("property", "").replace("og:", "")
        content = meta.get("content")
        if prop and content:
            og[prop] = clean_text(content)

    json_ld_items = extract_json_ld_items(raw_soup)

    posts = extract_post_cards(content_soup, url)
    if not posts:
        posts = extract_jina_section_posts(content_soup, url)

    categories = extract_blog_categories(raw_soup, url)
    pagination = detect_pagination(raw_soup, url)
    content_analysis = _build_listing_content_analysis(posts, [])

    listing_title = seo_h1 or og.get("title") or seo_title

    result["seo"] = {
        "title": seo_title,
        "metaDescription": seo_meta,
        "canonical": seo_canonical,
        "h1": seo_h1,
    }
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


def analyze_blog(self, url, html, headers, page_type, level1):
    soup = BeautifulSoup(html or "", "lxml")
    detected_type = detect_blog_page_type(url, soup)

    if detected_type == "article":
        return _analyze_article(self, url, html, headers, "blogPost", level1)

    if detected_type == "blogListing":
        return _analyze_listing(self, url, html, headers, "blogListing", level1)

    # Fallback: long content is probably an article
    content_soup = clean_dom_for_blog(html)
    text = clean_text(content_soup.get_text(" "))
    if len(re.findall(r"\w+", text)) >= 400:
        return _analyze_article(self, url, html, headers, "blogPost", level1)

    return _analyze_listing(self, url, html, headers, "blogListing", level1)
