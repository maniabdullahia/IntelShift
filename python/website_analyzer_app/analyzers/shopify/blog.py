from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import json


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


# ── Blog content analysis helpers ─────────────────────────────────────────────

# Patterns that disqualify a string from being a product name
_NON_PRODUCT_RE = re.compile(
    r'^\s*('
    r'step\s+\d+|tip\s+\d+|method\s+\d+|part\s+\d+|chapter\s+\d+|phase\s+\d+|'
    r'\d+[\.\)]\s+'           # "1. " or "1) "
    r'|how\s+to\s'
    r'|why\s'
    r'|what\s+is\s'
    r'|when\s'
    r'|where\s'
    r'|choosing\s'
    r'|finding\s'
    r'|using\s'
    r'|making\s'
    r'|getting\s'
    r')',
    re.I
)

_GENERIC_BOLD = {
    "note", "important", "tip", "warning", "caution", "pro tip", "key takeaway",
    "conclusion", "summary", "result", "final thoughts", "bonus", "important note",
    "note:", "tip:", "warning:", "caution:", "remember", "faq",
}

# Product category words — used to anchor product-name extraction from plain text
_PRODUCT_CATEGORY_RE = re.compile(
    r'\b(shampoo|conditioner|cleanser|serum|cream|lotion|gel|toner|'
    r'moisturi[sz]er|sunscreen|sun\s*screen|'
    r'face\s+wash|body\s+wash|hand\s+wash|face\s+scrub|body\s+scrub|'
    r'pomade|hair\s*wax|hair\s+oil|hair\s+mask|hair\s+serum|hair\s+gel|'
    r'balm|fragrance|perfume|spray|mist|essence|emulsion|treatment|'
    r'foundation|lipstick|lip\s+gloss|blush|eyeshadow|eye\s+liner|mascara|'
    r'highlighter|contour|primer|powder|concentrate|'
    r'micellar\s+water|makeup\s+remover|'
    r'foam|cleansing\s+milk|body\s+butter|scrub|mask|wash)\b',
    re.I
)

# Words that are too generic to be the *start* of a product name extracted from prose
_PROSE_SKIP_START = re.compile(
    r'^(the|a|an|our|your|my|this|that|these|those|'
    r'best|good|great|perfect|ideal|right|proper|gentle|natural|organic|'
    r'new|old|any|some|every|all|use|using|try|apply|find|get|choose|'
    r'for|in|at|by|of|with|to|into|from)\s+',
    re.I
)

# Comprehensive brand skip-list
_BRAND_SKIP = {
    # Articles / prepositions / conjunctions
    "the","a","an","and","or","but","of","in","at","by","for","from","with",
    "to","into","onto","upon","over","under","about","around",
    # Pronouns
    "it","its","this","that","these","those","they","their","them",
    "you","your","we","our","my","he","she","his","her","who","which",
    # Common verbs / gerunds
    "is","are","was","were","be","been","being","have","has","had","do","does","did",
    "will","would","can","could","should","may","might","shall","must",
    "using","choosing","finding","making","getting","keeping","starting",
    "following","applying","washing","rinsing","drying","mixing","adding",
    "combining","step","start","use","try","apply","find","get","choose",
    "see","look","read","learn","discover","explore","shop","buy","visit",
    "ensure","avoid","keep","leave","let","wait","repeat","rinse","note",
    # Common adjectives / adverbs
    "best","good","great","perfect","ideal","right","proper","new","old",
    "big","small","long","short","high","low","hot","cold","dry","wet",
    "oily","natural","organic","gentle","strong","mild","deep","light",
    "dark","bright","clean","clear","smooth","soft","hard","fast","slow",
    "easy","simple","complex","special","different","various","certain",
    # Common nouns (not brands)
    "hair","skin","face","body","hand","eye","lip","nail","scalp",
    "care","type","use","way","step","tip","trick","method","result",
    "product","item","thing","kind","form","style","look","feel","effect",
    "benefit","ingredient","formula","texture","scent","color","colour",
    "wash","rinse","cleanse","hydrate","nourish","protect","repair",
    "routine","guide","tips","review","benefits","reasons","ways","steps",
    "understanding","exploring","discovering","introducing",
    # Product category words (not brand names)
    "shampoo","conditioner","cleanser","serum","cream","lotion","gel",
    "toner","moisturizer","sunscreen","mask","scrub","pomade","wax","oil",
    "balm","spray","mist","essence","emulsion","treatment","formula",
    "mousse","foundation","lipstick","blush","mascara","liner","highlighter",
    "primer","foam","milk","butter","soap","water","micellar",
    # Sequence / time
    "first","second","third","last","next","then","also","finally","once",
    "before","after","during","while","when","always","never","just","even",
    # Question words
    "how","why","what","where","which","when",
    # Months (May, etc.)
    "january","february","march","april","may","june","july",
    "august","september","october","november","december",
}


def _is_valid_product_name(name):
    """True if text could be a real product name (not a step/instruction heading)."""
    if not name or len(name) > 90:
        return False
    if _NON_PRODUCT_RE.match(name):
        return False
    return True


def _looks_like_product_name(text):
    """True if bold/strong text looks like a product name (not a heading or generic phrase)."""
    t = text.strip()
    if t.lower().rstrip(":") in _GENERIC_BOLD:
        return False
    if t.endswith(":"):
        return False
    words = t.split()
    if not (2 <= len(words) <= 8):
        return False
    if not words[0][0].isupper():
        return False
    return True


def _slug_to_name(href):
    """Convert a /products/slug-here URL to a title-cased product name."""
    m = re.search(r'/products/([^/?#]+)', href)
    if not m:
        return None
    slug = m.group(1)
    # Title-case words; preserve numbers and hyphens like "8-in-1"
    words = slug.split('-')
    return " ".join(w.capitalize() if re.match(r'^[a-z]', w) else w for w in words)


def _classify_cta_type(text, href):
    """Classify CTA as product, lead_gen, or store_locator."""
    url_lower = href.lower()
    text_lower = text.lower()

    if "/products/" in url_lower or "/collections/" in url_lower:
        return "product"

    store_words = [
        "find a salon", "find a store", "store locator", "find near",
        "locate", "find stockist", "where to buy", "find dealer",
    ]
    if any(w in text_lower for w in store_words):
        return "store_locator"

    lead_gen_words = [
        "subscribe", "sign up", "newsletter", "contact", "get in touch",
        "book", "appointment", "register", "join",
    ]
    if any(w in text_lower for w in lead_gen_words):
        return "lead_gen"

    if any(w in text_lower for w in ["shop", "buy", "order", "purchase", "explore", "discover"]):
        return "product"

    return "lead_gen"


# Product suffix words — every valid product name MUST contain at least one
_PRODUCT_SUFFIXES = {
    "shampoo", "conditioner", "mask", "serum", "oil", "treatment", "pomade",
    "cream", "cleanser", "fragrance", "spray", "gel", "wax", "mousse",
    "powder", "toner", "moisturizer", "lotion", "balm", "mist", "essence",
    "scrub", "wash", "primer", "foundation", "lipstick", "blush", "mascara",
    "liner", "highlighter", "emulsion", "foam", "butter", "milk", "paste",
    "fluid", "elixir", "complex", "formula", "concentrate", "booster",
}

# Words/prefixes that disqualify a string from being a product name (in addition to _NON_PRODUCT_RE)
_HARD_REJECT_RE = re.compile(
    r'^(what|why|how|when|where|can|should|help|article|follow|read|step|tip|faq|'
    r'too\s|washing\s|scrubbing\s|spraying\s|applying\s|avoid|don\'t|do\s+not|'
    r'never\s|not\s|don\'t|always\s|making\s|getting\s)',
    re.I
)

# Context words that signal sentence setup (trim from before product name).
# Includes imperative verbs ("Finish with X", "Pair with X") and prepositions
# that introduce the product after a verb phrase.
_SENTENCE_CONTEXT = {
    # Auxiliary / linking verbs
    "will", "would", "can", "could", "should", "must", "may", "might",
    "is", "are", "was", "were", "be", "been", "do", "did", "does",
    "have", "has", "had",
    # Action verbs commonly seen before product names
    "try", "use", "using", "find", "get", "choose", "prefer", "recommend",
    "need", "want", "like", "love", "make", "makes", "give", "gives",
    "help", "helps", "let", "lets", "keep", "keeps", "see", "saw",
    "feel", "felt", "apply", "start", "begin", "finish", "complete",
    "pair", "top", "seal", "layer", "combine", "follow", "replace",
    "swap", "add", "include", "spritz", "spray", "style", "wash",
    # Prepositions that introduce the product after an action verb
    # ("Finish with X", "Seal with X", "Style with X")
    "with",
}

# Trailing words marking the end of a product name in running prose.
# NOTE: do NOT include descriptive adjectives (perfect, great, good) here —
# they appear legitimately inside product names like "Perfect Clarity Shampoo".
_TRAILING_STOP_RE = re.compile(
    r'\s+(?:is|are|was|were|will|would|can|could|should|for|in|at|by|of|on|to|'
    r'from|with|that|which|who|and|but|or|removes|soothes|helps|makes|keeps|'
    r'gives|provides|works|suits|leaves|feels|smells|looks|contains|has|have|'
    r'comes|adds|boosts|reduces|fights|prevents|protects|especially|also)\b.*$',
    re.I
)

# Generic anchor words that trigger URL-slug fallback instead of anchor text
_GENERIC_ANCHORS = {
    "this", "here", "it", "link", "click", "these", "more", "read", "view",
    "page", "site", "one", "them", "product", "now", "get", "buy", "shop",
}


def _has_product_suffix(name):
    """True if name contains at least one recognised product suffix word."""
    words = set(re.findall(r'\b\w+\b', name.lower()))
    return bool(words & _PRODUCT_SUFFIXES)


def _is_valid_product_mention(name):
    """
    Single gate for all product name candidates.
    Returns True only if the text is plausibly a real product name.
    """
    if not name:
        return False
    # Hard length / punctuation rules
    if len(name) > 80 or "?" in name:
        return False
    # Must start with uppercase or digit (not mid-sentence fragment)
    if name[0].islower():
        return False
    # Must contain a product suffix word
    if not _has_product_suffix(name):
        return False
    # Reject known non-product starts
    if _HARD_REJECT_RE.match(name):
        return False
    # Use the existing heading-pattern guard
    if not _is_valid_product_name(name):
        return False
    return True


def _extract_site_brand(url):
    """Derive a brand name from the site's domain (e.g. keune.com → Keune)."""
    try:
        domain = url.split("/")[2].replace("www.", "")
        raw = domain.split(".")[0]          # "keune", "argandeluxe"
        # Title-case, split on common separators
        cleaned = re.sub(r'[-_]', ' ', raw).title()
        return cleaned
    except Exception:
        return None


def _slug_to_name(href):
    """Convert /products/slug-here to a title-cased name."""
    m = re.search(r'/products/([^/?#]+)', href)
    if not m:
        return None
    words = m.group(1).split('-')
    return " ".join(w.capitalize() if re.match(r'^[a-z]', w) else w for w in words)


def _extract_products_pipeline(content_node, url, json_ld_items):
    """
    Product extraction pipeline – priority order:
      Tier 1: internal /products/ links whose link text contains a product suffix
      Tier 2: JSON-LD Product schema
      Tier 3: <strong>/<b> text containing a product suffix
      Tier 4: paragraph/list text anchored by a product category word
    Every candidate is validated through _is_valid_product_mention().
    """
    site_brand = _extract_site_brand(url)
    mentioned  = []
    seen_names = set()
    seen_urls  = set()

    # ── Tier 1: /products/ links ───────────────────────────────────────────
    for a in content_node.select("a[href*='/products/']"):
        href     = a.get("href", "")
        full_url = urljoin(url, href)
        if full_url in seen_urls:
            continue

        anchor = clean_text(a.get_text(" "))
        use_anchor = (
            anchor
            and len(anchor) > 4
            and anchor.lower() not in _GENERIC_ANCHORS
            and _is_valid_product_mention(anchor)
        )
        name = anchor if use_anchor else _slug_to_name(href)
        if not name or not _is_valid_product_mention(name):
            continue

        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        seen_urls.add(full_url)
        mentioned.append({
            "name":  name,
            "url":   full_url,
            "brand": site_brand,
            "type":  "recommended_product",
        })

    # ── Tier 2: JSON-LD Product schema ────────────────────────────────────
    for item in (json_ld_items or []):
        itype = item.get("@type", "")
        if not ("Product" in itype if isinstance(itype, list) else itype == "Product"):
            continue
        name     = item.get("name", "")
        item_url = item.get("url") or item.get("@id") or ""
        if not _is_valid_product_mention(name):
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        if item_url:
            seen_urls.add(item_url)
        mentioned.append({
            "name":  name,
            "url":   item_url or None,
            "brand": site_brand,
            "type":  "recommended_product",
        })

    # ── Tier 3: bold / strong text containing a product suffix ────────────
    for tag in content_node.find_all(["strong", "b"]):
        name = clean_text(tag.get_text(" "))
        if not _is_valid_product_mention(name):
            continue
        if not _looks_like_product_name(name):
            continue
        key = name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        mentioned.append({
            "name":  name,
            "url":   None,
            "brand": site_brand,
            "type":  "recommended_product",
        })

    # ── Tier 4: paragraph / list text anchored by product category words ──
    for node in content_node.find_all(["p", "li"]):
        text = clean_text(node.get_text(" "))
        if not text or len(text) < 10:
            continue

        for m in _PRODUCT_CATEGORY_RE.finditer(text):
            before       = text[:m.start()].strip()
            words_before = before.split()[-5:] if before else []

            # Split at inline punctuation boundaries (comma/semicolon/colon) first —
            # anything before "washes," or "skin:" is a new clause, not part of the name
            boundary_idx = -1
            for i, w in enumerate(words_before):
                if re.search(r'[,;:]$', w):
                    boundary_idx = i
            if boundary_idx >= 0:
                words_before = words_before[boundary_idx + 1:]

            # Trim leading sentence-context / article words
            trim_idx = -1
            for i, w in enumerate(words_before):
                wl = w.lower().rstrip(",")
                if wl in _SENTENCE_CONTEXT:
                    trim_idx = i
                elif wl in {"the", "a", "an", "our", "their"} and i < len(words_before) - 1:
                    trim_idx = i
            words_before = words_before[trim_idx + 1:] if trim_idx >= 0 else words_before

            if not words_before:
                continue

            candidate = " ".join(words_before + [m.group(0)]).strip()

            # Absorb comma/ampersand-led title-case trailers only
            after = text[m.end():m.end() + 50]
            extra = re.match(
                r'^((?:[,\s]*&\s*[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,2})'
                r'|(?:,\s*[A-Z][A-Za-z]*(?:\s+[A-Z&][A-Za-z]*){0,2}))',
                after
            )
            if extra:
                candidate += extra.group(1).rstrip(" ,")

            candidate = _PROSE_SKIP_START.sub("", candidate).strip(" ,–—")
            candidate = _TRAILING_STOP_RE.sub("", candidate).strip()
            candidate = re.sub(r'\s+by\s+\w+\s*$', "", candidate, flags=re.I).strip()

            if not _is_valid_product_mention(candidate):
                continue

            # Require at least one proper-noun word before the suffix token
            cat_tok   = len(m.group(0).split())
            all_words = candidate.split()
            nm_words  = all_words[:-cat_tok] if cat_tok < len(all_words) else all_words
            has_proper = any(
                len(w) >= 2 and (w[0].isupper() or re.match(r'\d', w))
                and w.lower() not in _BRAND_SKIP
                for w in nm_words
            )
            if not has_proper:
                continue

            key = candidate.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            mentioned.append({
                "name":  candidate,
                "url":   None,
                "brand": site_brand,
                "type":  "recommended_product",
            })

    return mentioned[:50]



def _extract_mentioned_brands(text, site_brand=None):
    """
    Extract brand names from article text.
    Strategy:
      1. If site_brand appears in the text, include it.
      2. Find single-word proper nouns appearing 3+ times that are not
         product suffixes, skip words, or product-line modifiers.
    Intentionally avoids multi-word extraction to prevent product-line
    names ("Derma Regulate", "Scalp Sensitive") from being classified
    as brands.
    """
    from collections import Counter

    # Product-line modifier words — commonly mis-identified as brand components
    _LINE_MODIFIERS = {
        "regulate", "sensitive", "hydrating", "repair", "restore", "balance",
        "pure", "clear", "calm", "soothe", "renew", "revive", "boost", "nourish",
        "protect", "active", "intense", "ultra", "super", "advanced", "original",
        "classic", "natural", "organic", "gentle", "smooth", "fresh", "clean",
        "derma", "scalp", "curl", "straight", "volume", "moisture", "color",
        "colour", "silver", "gold", "black", "white", "pink", "blue",
    }

    brands = []
    seen   = set()

    # 1. Site brand — highest confidence
    if site_brand and site_brand.lower() not in _BRAND_SKIP:
        # Check it actually appears in the text
        if re.search(r'\b' + re.escape(site_brand) + r'\b', text or "", re.I):
            brands.append(site_brand)
            seen.add(site_brand.lower())

    # 2. Single-word proper nouns: 3+ occurrences, not a suffix or modifier
    single = re.findall(r'(?<![.\n])\b([A-Z][a-z]{2,})\b', text or "")
    counts = Counter(single)
    for word, count in counts.most_common(30):
        if count < 3:
            break
        wl = word.lower()
        if wl in _BRAND_SKIP or wl in _PRODUCT_SUFFIXES or wl in _LINE_MODIFIERS:
            continue
        if word in seen or wl in seen:
            continue
        # Skip if already captured as part of site brand
        if site_brand and word.lower() in site_brand.lower():
            continue
        seen.add(wl)
        brands.append(word)
        if len(brands) >= 8:
            break

    return brands[:8]


def _detect_search_intent(title, headings, paragraphs):
    """Detect search intent: informational, commercial, transactional."""
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


def _detect_funnel_stage(title, headings, products):
    """Detect funnel stage using standardised labels."""
    combined = " ".join(
        [title or ""]
        + [h.get("text", "") for h in (headings or [])[:5]]
    ).lower()

    if any(w in combined for w in ["best ", "top ", " vs ", "review", "compare", "choosing", "should i"]):
        return "bottom_of_funnel" if products else "middle_of_funnel"
    if any(w in combined for w in ["how to", "guide", "tips", "benefits", "what is", "why "]):
        return "top_of_funnel"
    return "top_of_funnel"


def _extract_target_keyword(title, headings):
    """Extract primary target keyword from article title."""
    source = title or (headings[0].get("text") if headings else None)
    if not source:
        return None
    cleaned = re.sub(r'\s*[\|–—\-]\s*\S+.*$', '', source).strip()
    return (cleaned or source).lower()


def _extract_secondary_keywords(headings):
    """Extract secondary keywords from H2/H3 headings."""
    return [
        h.get("text", "").lower()
        for h in (headings or [])
        if h.get("tag") in ("h2", "h3") and h.get("text")
        and not _NON_PRODUCT_RE.match(h.get("text", ""))
    ][:10]


def _cluster_blog_topics(titles):
    """Group blog titles into thematic clusters."""
    clusters = {
        "how_to":       (["how to", "guide", "tutorial", "tips", "steps", "ways"], []),
        "product":      (["best", "review", "top", "vs", "compare", "recommend"], []),
        "education":    (["what is", "benefits", "why", "about", "understand", "learn"], []),
        "lifestyle":    (["routine", "daily", "weekly", "morning", "night", "seasonal"], []),
    }
    general = []

    for title in titles:
        t = title.lower()
        matched = False
        for cluster, (keywords, bucket) in clusters.items():
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


def _extract_product_themes_from_titles(blog_posts):
    """
    Extract product type themes from blog listing post titles.
    e.g. "How to Use Hair Pomade" -> "Hair Pomade"
    Returns a deduplicated list of theme strings.
    """
    themes = []
    seen   = set()
    for post in (blog_posts or []):
        title = post.get("title", "")
        for m in _PRODUCT_CATEGORY_RE.finditer(title):
            # Take up to 3 preceding words as qualifier
            before = title[:m.start()].strip().split()
            # Strip common sentence-start words
            while before and before[0].lower() in {
                "how", "what", "why", "best", "top", "a", "an", "the",
                "to", "for", "in", "is", "are", "do", "does", "can", "using",
                "choosing", "finding", "guide", "tips", "about",
            }:
                before = before[1:]
            qualifier = " ".join(before[-3:]) if before else ""
            suffix    = m.group(0)
            phrase    = (qualifier + " " + suffix).strip().title()
            # Must look like a product phrase (has a proper word before suffix)
            if phrase and phrase.lower() not in seen and len(phrase) > len(suffix):
                seen.add(phrase.lower())
                themes.append(phrase)
    return themes[:15]


def _build_listing_content_analysis(blog_posts, headings):
    """Generate topic clustering for blog listing pages."""
    from collections import Counter
    skip = {
        "a","an","the","for","in","on","at","to","of","and","or","is","are",
        "how","why","what","when","where","with","that","this","from",
        "your","our","you","we","it","be","was","were","by","do","get",
    }
    titles = [p.get("title", "") for p in (blog_posts or [])]
    words = []
    for t in titles:
        for w in re.findall(r'\b[a-z]{3,}\b', t.lower()):
            if w not in skip:
                words.append(w)

    dominant = [w for w, _ in Counter(words).most_common(8)]

    return {
        "searchIntent": "informational",
        "funnelStage": "top_of_funnel",
        "dominantTopics": dominant,
        "postCount": len(blog_posts),
        "topicClusters": _cluster_blog_topics(titles),
        "productThemes": _extract_product_themes_from_titles(blog_posts),
    }


def analyze_blog(self, url, html, headers, page_type, level1):
    result = self.base_result(url, html, headers, page_type, level1)
    soup = BeautifulSoup(html or "", "lxml")

    result["source"]["extractor"] = "Shopify Blog Extractor"

    path = url.lower()
    is_article = "/blogs/" in path and len(path.rstrip("/").split("/")) >= 6
    is_blog_listing = "/blogs/" in path and not is_article

    json_ld_items = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text()
            if not raw:
                continue

            parsed = json.loads(raw)

            if isinstance(parsed, list):
                json_ld_items.extend(parsed)
            else:
                json_ld_items.append(parsed)

        except Exception:
            continue

    soup_for_content = BeautifulSoup(html or "", "lxml")

    for selector in [
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "header",
        "footer",
        "nav",
        "aside",
        "form",

        ".header",
        ".footer",
        ".site-header",
        ".site-footer",
        ".announcement-bar",
        ".top-bar",
        ".promo-bar",
        ".newsletter",
        ".popup",
        ".modal",
        ".drawer",
        ".cart-drawer",
        ".menu-drawer",
        ".predictive-search",
        ".search-modal",
        ".breadcrumb",
        ".breadcrumbs",
        ".share-buttons",
        ".social-share",
        ".pagination",
        ".shopify-section-group-footer-group",
        ".shopify-section-group-header-group",

        "[class*='newsletter']",
        "[class*='popup']",
        "[class*='announcement']",
        "[class*='breadcrumb']",
        "[class*='social']",
        "[class*='share']",
        "[id*='newsletter']",
        "[id*='popup']"
    ]:
        for node in soup_for_content.select(selector):
            node.decompose()

    possible_containers = []

    priority_selectors = [
        "article",
        "[itemprop='articleBody']",
        ".article-template",
        ".article-content",
        ".rte",
        ".blog-post",
        ".article",
        ".template-article",
        "main article",
        "#MainContent"
    ]

    for selector in priority_selectors:
        for node in soup_for_content.select(selector):
            text = clean_text(node.get_text(" "))

            if len(text) < 200:
                continue

            score = len(text)
            class_text = " ".join(node.get("class", []))

            if "article" in class_text:
                score += 3000

            if "content" in class_text:
                score += 2000

            possible_containers.append((node, score))

    if possible_containers:
        content_node = sorted(
            possible_containers,
            key=lambda x: x[1],
            reverse=True
        )[0][0]
    else:
        content_node = soup_for_content.body or soup_for_content

    headings = []

    for h in content_node.find_all(["h1", "h2", "h3", "h4"]):
        text = clean_text(h.get_text(" "))
        if text:
            headings.append({
                "tag": h.name,
                "text": text
            })

    paragraphs = []

    for p in content_node.find_all("p"):
        text = clean_text(p.get_text(" "))
        if len(text) >= 35:
            paragraphs.append(text)

    paragraphs = list(dict.fromkeys(paragraphs))

    images = []

    for img in content_node.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-original")
            or img.get("data-lazy-src")
        )

        if not src:
            continue

        src_lower = src.lower()

        bad_patterns = [
            "icon",
            "logo",
            "placeholder",
            "avatar",
            "emoji",
            "whatsapp",
            "facebook",
            "instagram",
            "twitter",
            "pinterest",
            "linkedin",
            "svg"
        ]

        if any(pattern in src_lower for pattern in bad_patterns):
            continue

        if src.startswith("//"):
            src = "https:" + src

        elif src.startswith("/"):
            src = urljoin(url, src)

        images.append({
            "url": src,
            "alt": clean_text(img.get("alt", ""))
        })

    images = unique_items(images, "url")

    internal_links = []
    external_links = []

    base_domain = url.split("/")[2].replace("www.", "")

    bad_link_patterns = [
        "facebook.com/sharer",
        "twitter.com/intent",
        "pinterest.com/pin",
        "linkedin.com/share",
        "whatsapp",
        ".atom"
    ]

    for a in content_node.find_all("a", href=True):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not href:
            continue

        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue

        full_url = urljoin(url, href)

        if any(pattern in full_url.lower() for pattern in bad_link_patterns):
            continue

        link_obj = {
            "text": text,
            "url": full_url
        }

        if base_domain in full_url:
            internal_links.append(link_obj)
        else:
            external_links.append(link_obj)

    internal_links = unique_items(internal_links, "url")
    external_links = unique_items(external_links, "url")

    blog_posts = []

    for a in soup.select("a[href*='/blogs/']"):
        href = a.get("href")
        text = clean_text(a.get_text(" "))

        if not href or not text:
            continue

        full_url = urljoin(url, href)

        if full_url.rstrip("/") == url.rstrip("/"):
            continue

        if len(text) < 15:
            continue

        bad_blog_texts = [
            "read more",
            "continue reading",
            "previous",
            "next",
            "share"
        ]

        if text.lower().strip() in bad_blog_texts:
            continue

        blog_posts.append({
            "title": text,
            "url": full_url
        })

    blog_posts = unique_items(blog_posts, "url")

    products = []

    for a in content_node.select("a[href*='/products/']"):
        href = a.get("href")

        if not href:
            continue

        full_url = urljoin(url, href)

        parent = a.find_parent([
            "product-card",
            "li",
            "div",
            "article",
            "section"
        ])

        if not parent:
            continue

        parent_text = clean_text(parent.get_text(" "))

        bad_phrases = [
            "quick add",
            "add to cart",
            "sale",
            "sold out",
            "choose options",
            "wishlist",
            "compare"
        ]

        if any(p in parent_text.lower() for p in bad_phrases):
            continue

        name = None

        for selector in [
            "h1",
            "h2",
            "h3",
            "h4",
            ".card__heading",
            ".product-title",
            ".product-card__title",
            "[class*=\'product-title\']",
            "[class*=\'card__heading\']"
        ]:
            found = parent.select_one(selector)

            if found:
                candidate = clean_text(found.get_text(" "))

                if len(candidate) > 3:
                    name = candidate
                    break

        if not name:
            anchor_text = clean_text(a.get_text(" "))
            if len(anchor_text) > 3:
                name = anchor_text

        if not name:
            continue

        if not _is_valid_product_name(name):
            continue

        price = None

        price_match = re.search(
            r"(Rs\.?|PKR|\u20a8|\$|\xa3|AED|USD)\s?[\d,]+(?:\.\d{2})?",
            parent_text,
            re.I
        )

        if price_match:
            price = price_match.group(0)

        image = None
        img = parent.find("img")

        if img:
            image = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy-src")
            )

            if image:
                if image.startswith("//"):
                    image = "https:" + image

                elif image.startswith("/"):
                    image = urljoin(url, image)

        products.append({
            "name": name,
            "url": full_url,
            "price": price,
            "image": image
        })

    products = unique_items(products, "url")

    # Build mentioned products via full pipeline (links, schema, bold, text)
    mentioned_products = _extract_products_pipeline(content_node, url, json_ld_items)

    cta_keywords = [
        "shop now",
        "buy now",
        "add to cart",
        "view product",
        "explore",
        "learn more",
        "read more",
        "continue reading",
        "shop",
        "discover"
    ]

    ctas = []

    for a in content_node.find_all("a", href=True):
        text = clean_text(a.get_text(" "))
        href = a.get("href")

        if not text or not href:
            continue

        full_url = urljoin(url, href)

        if any(pattern in full_url.lower() for pattern in bad_link_patterns):
            continue

        if any(keyword in text.lower() for keyword in cta_keywords):
            ctas.append({
                "text": text,
                "url": full_url,
                "type": _classify_cta_type(text, full_url)
            })

    ctas = unique_items(ctas, "url")

    faqs = []

    if is_article:
        faq_nodes = content_node.find_all(["h2", "h3", "h4"])

        for node in faq_nodes:
            question = clean_text(node.get_text(" "))

            if "?" not in question:
                continue

            answer = ""
            current = node.find_next_sibling()

            while current:
                if current.name in ["h2", "h3", "h4"]:
                    break

                text = clean_text(current.get_text(" "))

                if len(text) > 40:
                    answer += " " + text

                current = current.find_next_sibling()

            answer = clean_text(answer)

            if len(answer) < 40:
                continue

            faqs.append({
                "question": question,
                "answer": answer[:1000]
            })

    publish_date = None
    date_modified = None
    author = None

    time_tag = soup.find("time")
    if time_tag:
        publish_date = time_tag.get("datetime") or clean_text(time_tag.get_text(" "))

    meta_date = soup.find("meta", attrs={"property": "article:published_time"})
    if meta_date:
        publish_date = meta_date.get("content")

    meta_modified = soup.find("meta", attrs={"property": "article:modified_time"})
    if meta_modified:
        date_modified = meta_modified.get("content")

    author_tag = soup.find("meta", attrs={"name": "author"})
    if author_tag:
        author = author_tag.get("content")

    if not author:
        author_node = soup.select_one("[class*=\'author\'], [rel=\'author\']")
        if author_node:
            author = clean_text(author_node.get_text(" "))

    # Try JSON-LD for author and dates
    if not author or not publish_date:
        for item in json_ld_items:
            if item.get("@type") in ("Article", "BlogPosting", "NewsArticle"):
                author_data = item.get("author")
                if not author and author_data:
                    if isinstance(author_data, dict):
                        author = author_data.get("name")
                    elif isinstance(author_data, list) and author_data:
                        first = author_data[0]
                        author = first.get("name") if isinstance(first, dict) else str(first)
                    elif isinstance(author_data, str):
                        author = author_data
                if not publish_date and item.get("datePublished"):
                    publish_date = item.get("datePublished")
                if not date_modified and item.get("dateModified"):
                    date_modified = item.get("dateModified")
                if author and publish_date:
                    break

    main_text = clean_text(content_node.get_text(" "))
    word_count = len(re.findall(r"\w+", main_text))
    reading_time = max(1, round(word_count / 200))

    # Category from JSON-LD, meta, or URL
    category = None
    for a in soup.select("a[rel='category tag'], a[rel='category']"):
        text = clean_text(a.get_text(" "))
        if text and len(text) < 60:
            category = text
            break
    if not category:
        for sel in [".cat-links a", ".posted-in a", ".breadcrumb a"]:
            node = soup.select_one(sel)
            if node:
                text = clean_text(node.get_text(" "))
                if text and len(text) < 60:
                    category = text
                    break

    # Article sections (heading-keyed content blocks)
    article_sections = []
    if is_article:
        current_heading = None
        current_paras = []
        for tag in content_node.find_all(["h2", "h3", "p"]):
            if tag.name in ("h2", "h3"):
                if current_heading is not None or current_paras:
                    article_sections.append({
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
            article_sections.append({
                "heading": current_heading,
                "text": " ".join(current_paras)[:1500],
            })
        article_sections = [s for s in article_sections if s.get("heading") or s.get("text")][:25]

    # Excerpt from meta or first paragraph
    excerpt = None
    if is_article:
        for sel in ["meta[property='og:description']", "meta[name='description']"]:
            meta = soup.select_one(sel)
            if meta and meta.get("content"):
                text = clean_text(meta.get("content"))
                if text and len(text) > 30:
                    excerpt = text[:300]
                    break
        if not excerpt:
            for p in content_node.select("p"):
                text = clean_text(p.get_text(" "))
                if text and len(text) >= 80:
                    excerpt = text[:300]
                    break

    article_title = (
        result.get("openGraph", {}).get("title")
        or result.get("seo", {}).get("h1")
        or result.get("seo", {}).get("title")
    )

    # Build contentAnalysis — article pages get full analysis; listing pages get topic clustering
    content_analysis = None
    if is_article:
        content_analysis = {
            "searchIntent": _detect_search_intent(article_title, headings, paragraphs),
            "funnelStage": _detect_funnel_stage(article_title, headings, mentioned_products),
            "targetKeyword": _extract_target_keyword(article_title, headings),
            "secondaryKeywords": _extract_secondary_keywords(headings),
            "mentionedBrands": _extract_mentioned_brands(main_text, site_brand=_extract_site_brand(url)),
            "mentionedProducts": mentioned_products[:30],
        }
    elif is_blog_listing:
        content_analysis = _build_listing_content_analysis(blog_posts, headings)

    result["content"] = {
        "isArticle": is_article,
        "isBlogListing": is_blog_listing,
        "title": article_title,
        "publishDate": publish_date,
        "dateModified": date_modified,
        "author": author,
        "category": category,
        "excerpt": excerpt,
        "wordCount": word_count if is_article else None,
        "estimatedReadingTime": reading_time if is_article else None,
        "sections": article_sections if is_article else [],
        "featuredImage": (
            result.get("openGraph", {}).get("image:secure_url")
            or result.get("openGraph", {}).get("image")
            or (images[0]["url"] if images else None)
        ),
        "headings": headings,
        "paragraphs": paragraphs[:100],
        "mainText": main_text[:15000],
        "images": images[:40],
        "internalLinks": internal_links[:100],
        "externalLinks": external_links[:50],
        "ctas": ctas[:30],
        "faqs": faqs[:20],
        "blogPosts": blog_posts[:100],
        "contentAnalysis": content_analysis
    }

    result["products"] = products[:100]

    result["ecommerce"] = {
        "mentionedProductsCount": len(mentioned_products),
        "mentionedProducts": mentioned_products[:100],
        "collectionLinks": [
            link for link in internal_links
            if "/collections/" in link.get("url", "")
        ][:100],
        "productLinks": [
            link for link in internal_links
            if "/products/" in link.get("url", "")
        ][:100]
    }

    result["structuredData"] = {
        "jsonLdCount": len(json_ld_items),
        "items": json_ld_items[:20]
    }

    confidence = 0.45

    if result["content"]["mainText"]:
        confidence += 0.15

    if len(paragraphs) >= 2:
        confidence += 0.15

    if len(headings) >= 1:
        confidence += 0.05

    if is_article and result["content"]["featuredImage"]:
        confidence += 0.05

    if is_blog_listing and len(blog_posts) >= 1:
        confidence += 0.15

    if products:
        confidence += 0.05

    result["source"]["confidence"] = round(min(confidence, 0.95), 2)

    return result
