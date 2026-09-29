import re
from urllib.parse import urlparse


SCHEMA_VERSION = "competitive-analysis-v1"


PROMO_TERMS = [
    "sale", "discount", "free shipping", "bundle", "limited time",
    "clearance", "deal", "offer", "save", "coupon", "promo", "new arrival",
    "bestseller", "best seller", "free trial", "annual", "annually"
]

# Pattern for real percentage-off (e.g. "20% off", "50% off") — standalone "off" is excluded
_PROMO_PCT_OFF_RE = re.compile(r'\b\d+\s*%\s*off\b', re.I)

TRUST_TERMS = [
    "reviews", "guarantee", "warranty", "secure", "certified",
    "trusted", "award", "return", "refund", "money back", "free returns",
    "customer support", "verified", "security", "privacy", "compliance",
    # Policy-page trust signals
    "return policy", "refund policy", "shipping policy",
    "exchange policy", "delivery tracking",
]

CTA_TERMS = [
    "shop now", "buy now", "add to cart", "add to bag", "get quote",
    "contact us", "book now", "start now", "start free", "subscribe",
    "learn more", "view product", "request demo", "request a demo",
    "talk to sales", "contact sales", "get started", "try for free", "start free trial",
    "download", "get pro"
]

POSITIONING_TERMS = [
    "premium", "affordable", "sustainable", "natural", "organic",
    "luxury", "easy", "trusted", "professional",
    "handmade", "clean", "clinical", "science-backed",
    "performance", "comfortable", "durable", "automation", "security",
    "enterprise", "seo", "analytics", "collaboration",
    # Beauty/haircare/cosmetics terms
    "anti-frizz", "frizz-free", "non-sticky", "long-lasting", "salon-quality",
    "sulfate-free", "paraben-free", "cruelty-free", "vegan", "dermatologist-tested",
    "hyaluronic acid", "vitamin e", "vitamin c", "collagen", "keratin",
    "deep conditioning", "moisture-lock", "color-safe", "heat-protection",
    "lightweight formula", "fast-absorbing", "non-greasy",
    # Nail / colour cosmetics
    "nail polish", "nail care", "nail color", "gel laque", "nail lacquer",
    "vibrant shades", "nourishing formula", "nourishing formulas",
    "long-wearing", "chip-resistant", "quick-dry",
]

# Phrases/words that are too generic to be useful as positioning signals
_POSITIONING_BLOCKLIST = {
    "product", "formula", "solution", "system", "complex", "blend",
    "treatment", "care", "therapy", "boost", "technology", "item",
    "hair", "skin", "scalp", "body", "face", "it", "this",
    # Generic time/manner phrases that bleed through descriptor regex
    "long time", "long way", "long run", "long term",
    "deep breath", "deep dive",
    # Single generic tokens that should never stand alone
    "ai", "fast", "quickly", "easily", "simply",
    # Removed from POSITIONING_TERMS — too noisy on general/legal pages
    "custom", "eco", "sso", "rating",
}


def safe_get(data, path, default=None):
    current = data

    for key in path:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, (int, float)):
        return str(value)

    if not isinstance(value, str):
        return ""

    value = re.sub(r"\s+", " ", value)
    return value.strip()


def text_from_any(value, max_chars=5000):
    parts = []

    def walk(v):
        if v is None:
            return

        if isinstance(v, str):
            text = clean_text(v)
            if text:
                parts.append(text)
            return

        if isinstance(v, (int, float)):
            parts.append(str(v))
            return

        if isinstance(v, list):
            for item in v[:30]:
                walk(item)
            return

        if isinstance(v, dict):
            for item in v.values():
                walk(item)
            return

    walk(value)

    text = clean_text(" ".join(parts))
    return text[:max_chars]


def unique_list(items, limit=20):
    seen = set()
    output = []

    for item in items:
        item = clean_text(item)
        if not item:
            continue

        key = item.lower()
        if key in seen:
            continue

        seen.add(key)
        output.append(item)

        if len(output) >= limit:
            break

    return output


def extract_domain(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return None


def normalize_cta_text(text):
    text = clean_text(text)
    if not text:
        return ""

    # Remove UI arrow clutter, but keep the CTA meaning.
    text = text.replace("↗", "").replace("⤓", "")
    text = re.sub(r"\s+", " ", text).strip()

    # Avoid long navigation/hero blobs being treated as CTA labels.
    if len(text) > 90:
        return ""

    # Normalize common casing only; keep brand/product names intact otherwise.
    common = {
        "sign up": "Sign Up",
        "get started": "Get Started",
        "talk to sales": "Talk to Sales",
        "contact sales": "Contact Sales",
        "contact us": "Contact Us",
        "request demo": "Request Demo",
        "request a demo": "Request a Demo",
        "try for free": "Try for Free",
        "start free trial": "Start Free Trial",
        "subscribe": "Subscribe",
        "download": "Download",
        "learn more": "Learn More",
        "get pro": "Get Pro",
    }

    return common.get(text.lower(), text)


def extract_ctas(result):
    candidates = []

    possible_sources = [
        result.get("ctas"),
        safe_get(result, ["homepage", "ctas"]),
        safe_get(result, ["homepage", "hero", "primaryCtas"]),
        safe_get(result, ["content", "ctas"]),
        safe_get(result, ["product", "ctas"]),
        safe_get(result, ["collection", "ctas"]),
    ]

    for source in possible_sources:
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict):
                    text = normalize_cta_text(item.get("text") or item.get("label"))
                    url = item.get("url")
                    if text:
                        candidates.append({
                            "text": text,
                            "url": url
                        })
                elif isinstance(item, str):
                    text = normalize_cta_text(item)
                    if text:
                        candidates.append({
                            "text": text,
                            "url": None
                        })

    text_blob = text_from_any(result, max_chars=8000).lower()

    for term in CTA_TERMS:
        if term in text_blob:
            candidates.append({
                "text": normalize_cta_text(term.title()),
                "url": None
            })

    deduped = []
    seen = set()

    for cta in candidates:
        text = normalize_cta_text(cta.get("text"))
        url = cta.get("url")

        if not text:
            continue

        # Dedupe primarily by CTA text so repeated pricing-card buttons do not flood output.
        key = text.lower()
        if key in seen:
            continue

        seen.add(key)
        deduped.append({"text": text, "url": url})

    return deduped[:20]


def normalize_product_object(product, result=None):
    if not isinstance(product, dict):
        return None

    name = clean_text(
        product.get("name")
        or product.get("title")
        or safe_get(product, ["product", "title"])
    )

    price = (
        product.get("price")
        or product.get("currentPrice")
        or safe_get(product, ["price", "current"])
        or safe_get(product, ["pricing", "currentPrice"])
    )

    url = (
        product.get("url")
        or product.get("productUrl")
        or safe_get(result or {}, ["page", "url"])
    )

    if not name:
        return None

    return {
        "name": name,
        "price": price,
        "url": url,
        "availability": product.get("availability") or product.get("stockText"),
        "category": product.get("category"),
        "badges": product.get("badges", [])
    }


def extract_products(result):
    products = result.get("products")

    if not isinstance(products, list):
        products = []

    normalized = []

    single_product = result.get("product") or safe_get(result, ["ecommerce", "product"])

    if isinstance(single_product, dict):
        normalized_single = normalize_product_object(single_product, result)
        if normalized_single:
            normalized.append(normalized_single)

    for product in products[:30]:
        normalized_product = normalize_product_object(product, result)
        if normalized_product:
            normalized.append(normalized_product)

    featured_products = safe_get(result, ["ecommerce", "featuredProducts"], [])
    if isinstance(featured_products, list):
        for product in featured_products[:30]:
            normalized_product = normalize_product_object(product, result)
            if normalized_product:
                normalized.append(normalized_product)

    # Also scan products embedded in homepage product sections.
    # The homepage extractor stores per-section product arrays in content.sections[].products;
    # these are richer (prices, images) but not surfaced to ecommerce.featuredProducts
    # when extract_product_links() returns empty (JS-rendered grids, quickview themes).
    content_sections = safe_get(result, ["content", "sections"]) or []
    for section in content_sections:
        if section.get("type") == "product_section":
            for product in (section.get("products") or [])[:12]:
                normalized_product = normalize_product_object(product, result)
                if normalized_product:
                    normalized.append(normalized_product)

    deduped = []
    seen = set()

    for product in normalized:
        _raw_url = clean_text(product.get("url") or "").strip()
        try:
            _p = urlparse(_raw_url)
            # Drop query (?ref=…) and fragment (#section) — keep scheme+host+path
            _purl = (
                f"{_p.scheme}://{_p.netloc}{_p.path}".lower().rstrip("/")
                if _p.netloc else _raw_url.lower().rstrip("/")
            )
        except Exception:
            _purl = _raw_url.lower().rstrip("/")
        key = (
            clean_text(product.get("name") or "").lower(),
            _purl,
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(product)

    return deduped[:30]


def extract_prices(result):
    """Return pricing objects/values from the richest available source.

    New Unknown General extractor writes structured pricing to result["pricing"].
    That should be the source of truth for analysisReady.
    """
    structured_prices = safe_get(result, ["pricing", "prices"], [])
    if isinstance(structured_prices, list) and structured_prices:
        return structured_prices[:20]

    sample_prices = safe_get(result, ["collection", "samplePrices"], [])
    if isinstance(sample_prices, list) and sample_prices:
        return sample_prices[:20]

    prices = []
    products = extract_products(result)

    for product in products:
        price = product.get("price")
        if price not in [None, "", {}]:
            prices.append(price)

    ecommerce = result.get("ecommerce", {})

    possible_prices = [
        ecommerce.get("samplePrices"),
        # productStats.priceRange is an aggregate {min,max} dict, NOT a sample price —
        # skip it to avoid polluting samplePrices with non-scalar values
        safe_get(result, ["openGraph", "price:amount"]),
        safe_get(result, ["product", "price"]),
        safe_get(result, ["ecommerce", "product", "price"]),
    ]

    for item in possible_prices:
        if item:
            if isinstance(item, list):
                prices.extend(item)
            else:
                prices.append(item)

    return prices[:20]


def build_pricing_signals(result):
    pricing = result.get("pricing") if isinstance(result.get("pricing"), dict) else {}
    prices = extract_prices(result)

    prices_detected = pricing.get("pricesDetected")
    if prices_detected is None:
        prices_detected = len(prices)

    output = {
        "pricesDetected": prices_detected,
        "samplePrices": prices[:10]
    }

    if pricing.get("summary"):
        output["summary"] = pricing.get("summary")

    if pricing.get("plans"):
        output["plans"] = pricing.get("plans")[:10]
        output["planMappingConfidence"] = pricing.get("planMappingConfidence")

    return output


def detect_terms(text, terms, limit=15):
    text_l = text.lower()
    found = []

    for term in terms:
        if term in text_l:
            found.append(term)

    return unique_list(found, limit=limit)


# Regex to extract product-descriptor phrases from product name/title
# e.g. "Velvet Smooth Anti-Frizz Conditioner" → "Smooth Anti-Frizz"
# NOTE: broad \w+\s+(product_type) pattern removed to avoid "Frizz Conditioner", "a Gloss"
# [\w\-]+ captures hyphenated words whole (e.g. "Anti-Frizz")
_PRODUCT_DESCRIPTOR_RE = re.compile(
    r"\b("
    r"anti[\-\s][\w\-]+(?:\s+[\w\-]+)?|"                             # anti-frizz, anti-aging
    r"glossy\s+\w+(?:\s+\w+)?|"                                          # glossy lip tint
    r"(?:long|deep|ultra|super|extra)\s*[\-]?\s*[\w\-]+(?:\s+[\w\-]+)?|"  # long-lasting
    r"(?:salon|professional|clinical)\s*[\-]?\s*[\w\-]+(?:\s+[\w\-]+)?|"  # salon-quality
    r"(?:smooth|soft|shine|hydrat|moisturi|nourish|volumiz|strengthen)\w*\s+[\w\-]+"  # smooth hair
    r")",
    re.IGNORECASE,
)

# Stopwords that must not appear at leading/trailing edge of a positioning phrase.
# Trailing list includes fragment-prefix words ("anti", "pro") that appear alone.
_PHRASE_EDGE_STOPWORDS_RE = re.compile(
    r"^(?:a|an|the|and|or|of|in|on|at|by|for|with|to|its|this|that|every|each|"
    r"also|just|our|your|their|these|those|all|any|more|less|very|quite|so|as)\b"
    r"|"
    r"\b(?:and|or|every|each|a|an|the|of|in|with|for|to|by|on|at|into|"
    r"also|just|so|as|but|not|that|this|anti|pro|free|based|rich)\s*$",
    re.IGNORECASE,
)

# First words that should never start a positioning phrase
_PHRASE_NOISE_FIRST_WORDS = {
    "frizz", "sticky", "waxy", "greasy", "oily", "flat", "dull",
    "rough", "dry", "wet", "thick", "thin",
    "hair", "skin", "scalp", "body", "product", "formula",
    "it", "this", "that", "there", "strand", "cuticle",
}


def _build_product_text(result):
    """Combine name, description and tags into a single text blob for matching."""
    product = (
        result.get("product")
        or safe_get(result, ["ecommerce", "product"])
        or {}
    )
    products = result.get("products") or []
    p = product or (products[0] if products else {})
    seo = result.get("seo") or {}
    parts = [
        p.get("name") or "",
        seo.get("title") or "",
        seo.get("metaDescription") or "",
        clean_text(text_from_any(p.get("description"), max_chars=600)),
        " ".join(p.get("tags") or []),
    ]
    return " ".join(filter(None, parts))


def _extract_descriptor_phrases(text, max_phrases=6):
    """Extract short positioning descriptor phrases from product name / description."""
    phrases = []
    seen = set()
    for m in _PRODUCT_DESCRIPTOR_RE.finditer(text):
        phrase = m.group(0).strip()
        phrase_lower = phrase.lower()
        if len(phrase_lower) < 5 or len(phrase_lower) > 50:
            continue
        if phrase_lower in _POSITIONING_BLOCKLIST:
            continue
        # Reject phrases with stopwords at leading or trailing edge
        if _PHRASE_EDGE_STOPWORDS_RE.search(phrase_lower):
            continue
        # Reject if first word is a noise noun (e.g. "frizz conditioner")
        first_word = phrase_lower.split()[0]
        if first_word in _PHRASE_NOISE_FIRST_WORDS:
            continue
        if phrase_lower not in seen:
            seen.add(phrase_lower)
            phrases.append(phrase)
        if len(phrases) >= max_phrases:
            break
    return phrases


# ---------------------------------------------------------------------------
# Collection-specific positioning
# ---------------------------------------------------------------------------

# Category terms that map collection handle / name tokens → clean positioning
_CATEGORY_POSITIONING_MAP = {
    "nail": ["nail care", "nail polish", "nail color"],
    "nails": ["nail care", "nail polish", "nail color"],
    "lip": ["lip color", "lip care"],
    "lips": ["lip color", "lip care"],
    "lipstick": ["lipstick"],
    "foundation": ["foundation", "base makeup"],
    "concealer": ["concealer"],
    "eyeshadow": ["eye makeup", "eyeshadow"],
    "blush": ["blush", "cheek color"],
    "mascara": ["mascara", "eye makeup"],
    "skincare": ["skincare"],
    "moisturizer": ["moisturizer", "skincare"],
    "serum": ["serum", "skincare"],
    "haircare": ["hair care"],
    "shampoo": ["shampoo", "hair care"],
    "conditioner": ["conditioner", "hair care"],
    "hair-oil": ["hair oil", "hair care"],
    "hair-mask": ["hair mask", "hair care"],
    "perfume": ["fragrance", "perfume"],
    "fragrance": ["fragrance"],
    "sunscreen": ["sun protection", "sunscreen"],
    "toner": ["toner", "skincare"],
}


def _extract_collection_category_terms(collection_name, collection_handle):
    """Map collection name/handle tokens to canonical category positioning terms."""
    terms = []
    text = " ".join(filter(None, [collection_name, collection_handle])).lower()
    for token, mappings in _CATEGORY_POSITIONING_MAP.items():
        if token in text:
            terms.extend(mappings)
    return terms


def _extract_repeated_product_terms(products, min_count=2, max_terms=6):
    """Find words/phrases that appear in >= min_count product names."""
    from collections import Counter
    word_counter = Counter()
    for p in (products or []):
        name = (p.get("name") or "").lower()
        # Extract 1-2 word sequences (skip very short words)
        words = re.findall(r"[a-z]{4,}", name)
        for w in words:
            word_counter[w] += 1
        # Bigrams
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            word_counter[bigram] += 1

    # Return terms seen in multiple products (likely the collection category)
    repeated = [
        term for term, cnt in word_counter.most_common(20)
        if cnt >= min_count and term not in _POSITIONING_BLOCKLIST
    ]
    return repeated[:max_terms]


def extract_collection_positioning(result):
    """Build positioning signals specifically for collection pages.

    Sources (in priority order):
    1. Category terms derived from collection handle / name
    2. POSITIONING_TERMS matching against meta description + OG description
    3. Descriptor phrases extracted from meta/OG text
    4. Repeated terms across product names (category signal)
    """
    seo = result.get("seo") or {}
    og = result.get("openGraph") or {}
    content = result.get("content") or {}
    products = result.get("products") or []
    collection_summary = result.get("collectionSummary") or {}

    collection_name = content.get("collectionName") or collection_summary.get("name") or ""
    collection_handle = collection_summary.get("category") or ""

    signals = []

    # 1. Category terms from handle/name
    signals.extend(_extract_collection_category_terms(collection_name, collection_handle))

    # 2. POSITIONING_TERMS matching on meta desc + OG desc (richer than full text)
    focused_text = " ".join(filter(None, [
        seo.get("metaDescription") or "",
        og.get("description") or "",
        collection_name,
    ]))
    signals.extend(detect_terms(focused_text, POSITIONING_TERMS, limit=8))

    # 3. Descriptor phrases from meta/OG text
    signals.extend(_extract_descriptor_phrases(focused_text, max_phrases=5))

    # 4. Repeated product name terms (weak category signal)
    signals.extend(_extract_repeated_product_terms(products, min_count=2, max_terms=4))

    # Filter known garbage tokens
    cleaned = []
    for s in signals:
        sl = s.lower().strip()
        if sl in _POSITIONING_BLOCKLIST:
            continue
        if sl in {"ai", "fast", "quickly", "easily", "long time", "long term"}:
            continue
        cleaned.append(s)

    return unique_list(cleaned, limit=12)


def extract_positioning(result, full_text):
    # Route collection pages to dedicated collection positioning
    page_type = safe_get(result, ["page", "pageType"])
    if page_type == "collection":
        return extract_collection_positioning(result)

    # Homepage: pull from homepage.positioning (already filtered by extractor)
    if page_type == "homepage":
        hp_pos = safe_get(result, ["homepage", "positioning"])
        if isinstance(hp_pos, list) and hp_pos:
            cleaned = [s for s in hp_pos if s and s.lower() not in _POSITIONING_BLOCKLIST]
            if cleaned:
                return unique_list(cleaned, limit=12)

    existing = result.get("positioningSignals")
    if isinstance(existing, list) and existing:
        cleaned = [s for s in existing if s.lower() not in _POSITIONING_BLOCKLIST]
        return unique_list(cleaned, limit=20)

    product_text = _build_product_text(result)

    # 1. Term-list matching (multi-word phrases from POSITIONING_TERMS)
    signals = detect_terms(product_text, POSITIONING_TERMS, limit=10)

    # 2. Extract product-descriptor phrases from name / h1 / meta
    product = (
        result.get("product")
        or safe_get(result, ["ecommerce", "product"])
        or {}
    )
    products = result.get("products") or []
    p = product or (products[0] if products else {})
    seo = result.get("seo") or {}

    name_text = " ".join(filter(None, [
        p.get("name"),
        seo.get("h1"),
        seo.get("metaDescription"),
    ]))
    signals.extend(_extract_descriptor_phrases(name_text))

    # 3. Descriptor phrases from description text
    desc_text = clean_text(text_from_any(p.get("description"), max_chars=400))
    signals.extend(_extract_descriptor_phrases(desc_text, max_phrases=4))

    return unique_list(signals, limit=15)


def extract_headings(result):
    headings = []

    possible_sources = [
        safe_get(result, ["content", "headings"]),
        safe_get(result, ["homepage", "headings"]),
        safe_get(result, ["article", "headings"]),
    ]

    for source in possible_sources:
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict):
                    text = clean_text(item.get("text"))
                else:
                    text = clean_text(item)

                if text:
                    headings.append(text)

    h1 = safe_get(result, ["seo", "h1"])
    if h1:
        headings.insert(0, h1)

    return unique_list(headings, limit=25)


def build_page_summary(result):
    page = result.get("page", {})
    seo = result.get("seo", {})
    open_graph = result.get("openGraph", {})

    page_type = page.get("pageType")
    url = page.get("url") or safe_get(result, ["technical", "finalUrl"])

    title = (
        seo.get("title")
        or open_graph.get("title")
        or safe_get(result, ["content", "title"])
        or safe_get(result, ["product", "title"])
        or safe_get(result, ["product", "name"])
        or safe_get(result, ["ecommerce", "product", "name"])
        or safe_get(result, ["article", "title"])
    )

    description = (
        seo.get("metaDescription")
        or open_graph.get("description")
        or safe_get(result, ["content", "summaryText"])
        or safe_get(result, ["product", "description"])
        or safe_get(result, ["ecommerce", "product", "description"])
        or safe_get(result, ["article", "excerpt"])
    )

    # If seo.h1 is just the brand/site name, replace it with the most meaningful
    # heading available so pageSummary.h1 reflects the actual page subject.
    raw_h1 = clean_text(seo.get("h1"))
    if raw_h1:
        site_name_og = (open_graph.get("site_name") or "").strip().lower()
        raw_h1_lower = raw_h1.lower()
        _brand_suffix_tokens = {
            "pakistan", "store", "official", "online", "shop", "pk",
            "brand", "co", "ltd", "inc",
        }
        _is_brand_only = (
            (site_name_og and raw_h1_lower == site_name_og)
            or (site_name_og and raw_h1_lower.endswith(site_name_og))
            or (
                len(raw_h1.split()) <= 3
                and raw_h1.split()[-1].lower() in _brand_suffix_tokens
            )
        )
        if _is_brand_only:
            if page_type == "collection":
                # Use resolved collection name
                replacement = (
                    safe_get(result, ["content", "collectionName"])
                    or safe_get(result, ["collectionSummary", "name"])
                )
            else:
                # Product / general page: use OG title (stripped) or product name
                og_t = clean_text(open_graph.get("title") or "")
                if og_t and site_name_og:
                    import re as _re
                    og_t = _re.sub(
                        r"\s*[\|–\-]\s*" + _re.escape(open_graph.get("site_name") or "") + r"\s*$",
                        "", og_t, flags=_re.IGNORECASE,
                    ).strip()
                replacement = og_t or clean_text(
                    safe_get(result, ["product", "name"])
                    or safe_get(result, ["ecommerce", "product", "name"])
                )
            if replacement:
                raw_h1 = clean_text(replacement)

    summary = {
        "url": url,
        "domain": extract_domain(url),
        "pageType": page_type,
        "platform": result.get("platform"),
        "title": clean_text(title),
        "description": clean_text(description)[:700],
        "h1": raw_h1,
        "canonical": seo.get("canonical")
    }

    if page.get("generalSubtype"):
        summary["generalSubtype"] = page.get("generalSubtype")

    return summary


def has_real_ecommerce_evidence(result, products, prices):
    page_type = safe_get(result, ["page", "pageType"])
    general_subtype = safe_get(result, ["page", "generalSubtype"])

    # SaaS/general pricing pages have prices but should not become ecommerce evidence.
    if page_type == "general" and general_subtype == "pricing":
        return False

    return bool(
        len(products) > 0
        or len(prices) > 0
        or safe_get(result, ["ecommerce", "hasProductGrid"], False)
        or safe_get(result, ["ecommerce", "hasProductCards"], False)
        or safe_get(result, ["ecommerce", "hasCartOrCheckout"], False)
        or page_type in ["product", "collection"]
    )


def build_competitive_signals(result):
    full_text = text_from_any({
        "seo": result.get("seo"),
        "openGraph": result.get("openGraph"),
        "content": result.get("content"),
        "homepage": result.get("homepage"),
        "product": result.get("product"),
        "collection": result.get("collection"),
        "article": result.get("article"),
        "products": result.get("products"),
        "ecommerce": result.get("ecommerce"),
        "pricing": result.get("pricing"),
        "positioningSignals": result.get("positioningSignals")
    }, max_chars=12000)

    products = extract_products(result)
    prices = extract_prices(result)
    ctas = extract_ctas(result)
    headings = extract_headings(result)
    pricing_signals = build_pricing_signals(result)

    trust_signals = []

    existing_trust = (
        result.get("trustSignals")
        or safe_get(result, ["homepage", "trustSignals"])
        or safe_get(result, ["content", "trustSignals"])
    )

    if isinstance(existing_trust, list):
        for item in existing_trust:
            if isinstance(item, dict):
                trust_signals.append(clean_text(item.get("text") or item.get("label")))
            else:
                trust_signals.append(clean_text(item))

    business_trust = safe_get(result, ["business", "trustSignals", "signals"])
    if isinstance(business_trust, dict):
        for values in business_trust.values():
            if isinstance(values, list):
                trust_signals.extend(values)

    trust_signals += detect_terms(full_text, TRUST_TERMS)

    # Section-based ecommerce evidence (handles JS-rendered Shopify pages)
    sections = safe_get(result, ["content", "sections"]) or []
    section_text_blob = " ".join(
        (s.get("textPreview") or "") for s in sections
    ).lower()
    has_product_sections = any(s.get("type") == "product_section" for s in sections)
    has_cart_text_in_sections = any(
        k in section_text_blob
        for k in ("add to cart", "quick add", "add to bag", "choose options")
    )
    has_prices_in_sections = bool(
        any(k in section_text_blob for k in ("rs.", "pkr", "£", "€", "$"))
        or any(
            (s.get("source") or {}).get("priceCount", 0) > 0
            for s in sections
        )
    )
    # Detected features may also carry the signal
    detected_features = safe_get(result, ["content", "detectedFeatures"]) or {}
    has_products_signal = (
        len(products) > 0
        or has_product_sections
        or detected_features.get("hasProducts", False)
    )
    has_prices_signal = (
        len(prices) > 0
        or has_prices_in_sections
        or detected_features.get("hasPrices", False)
    )
    has_cart_signal = (
        has_cart_text_in_sections
        or safe_get(result, ["ecommerce", "hasCartOrCheckout"], False)
        or detected_features.get("hasFeaturedProducts", False)
    )

    real_ecommerce = has_real_ecommerce_evidence(result, products, prices) or has_product_sections

    # Filter product-action CTAs (add to cart, quick add etc.) — these are not page-level CTAs
    _CART_CTA_TEXTS = frozenset({
        "add to cart", "quick add", "quickadd", "add to bag",
        "choose options", "quick view", "quickview",
    })
    page_level_ctas = [
        c for c in ctas
        if (c.get("text") or "").lower().strip() not in _CART_CTA_TEXTS
        or c.get("url")  # keep if it has a real URL
    ]

    # Promotional signals: keyword match + regex percentage-off
    promo_signals = detect_terms(full_text, PROMO_TERMS)
    if _PROMO_PCT_OFF_RE.search(full_text):
        if "% off" not in promo_signals:
            promo_signals.append("% off")

    # Suppress promo terms that appear in legal/policy context rather than
    # actual promotional intent (e.g. "sale items are non-returnable").
    _legal_page_intents = {
        "shipping_policy", "return_policy", "privacy_policy",
        "terms_policy", "legal",
    }
    _page_intent  = safe_get(result, ["content", "pageIntent"]) or ""
    _general_sub  = safe_get(result, ["page", "generalSubtype"]) or ""
    _is_legal     = _page_intent in _legal_page_intents or _general_sub == "legal"
    if _is_legal:
        # These terms appear legitimately in policy copy without being promotions
        _legal_promo_false = {"sale", "clearance", "offer", "discount"}
        promo_signals = [s for s in promo_signals if s not in _legal_promo_false]

    return {
        "positioning": extract_positioning(result, full_text),
        "promotionalSignals": promo_signals,
        "pricingSignals": pricing_signals,
        "productFocus": unique_list(
            [p.get("name") for p in products if p.get("name")],
            limit=20
        ),
        "trustSignals": unique_list(trust_signals, limit=20),
        "ctaStrategy": {
            "primaryCtas": page_level_ctas[:10],
            "ctaCount": len(page_level_ctas)
        },
        "contentAngles": headings[:15],
        "ecommerceSignals": {
            "hasProducts": has_products_signal,
            "productCountExtracted": len(products),
            "hasPrices": has_prices_signal,
            "hasCartOrCheckout": bool(has_cart_signal),
            "hasRealEcommerceEvidence": real_ecommerce
        }
    }


def build_extraction_quality(result):
    warnings = []
    missing = []

    success = result.get("success", True)
    crawl = result.get("crawl", {})
    page = result.get("page", {})

    score = 1.0

    if success is False:
        score -= 0.55
        warnings.append("Extraction failed.")

    if crawl.get("blocked") or crawl.get("crawlBlocked"):
        # Fallback methods that successfully extracted content: smaller penalty
        _fallback_methods = ("jina_fallback", "microlink_fallback", "firecrawl_fallback", "openai_browse_fallback")
        if result.get("extractionMethod") in _fallback_methods and success is not False:
            score -= 0.15
            warnings.append("Page was blocked; extracted via fallback method.")
        else:
            score -= 0.45
            warnings.append("Page was blocked or no usable HTML was returned.")

    status_code = (
        crawl.get("statusCode")
        or safe_get(result, ["technical", "responseHeaders", "status_code"])
    )

    if isinstance(status_code, int) and status_code >= 400:
        score -= 0.35
        warnings.append(f"HTTP status code indicates a failed or error page: {status_code}.")

    page_title = safe_get(result, ["seo", "title"], "")
    page_h1 = safe_get(result, ["seo", "h1"], "")
    error_text = f"{page_title} {page_h1}".lower()

    if any(x in error_text for x in [
        "invalid ssl certificate",
        "error code 526",
        "access denied",
        "just a moment",
        "attention required",
        "page not found",
        "404"
    ]):
        score -= 0.45
        warnings.append("Fetched page appears to be an error, blocked, or security page.")

    if page.get("pageType") in [None, "", "unknown"]:
        score -= 0.2
        missing.append("pageType")

    if not safe_get(result, ["seo", "title"]):
        score -= 0.08
        missing.append("seo.title")

    if not safe_get(result, ["seo", "metaDescription"]):
        score -= 0.05
        missing.append("seo.metaDescription")

    if (
        not result.get("content")
        and not result.get("homepage")
        and not result.get("product")
        and not result.get("collection")
        and not result.get("article")
        and not safe_get(result, ["ecommerce", "product"])
    ):
        score -= 0.15
        missing.append("mainContent")

    products = extract_products(result)
    page_type = page.get("pageType")
    single_product = result.get("product") or safe_get(result, ["ecommerce", "product"])

    has_any_product_data = bool(products) or isinstance(single_product, dict)

    if page_type in ["product", "collection"] and not has_any_product_data:
        score -= 0.12
        warnings.append("Ecommerce page detected but products were not extracted.")

    # ── Collection-specific quality scoring ──────────────────────────────────
    if page_type == "collection":
        collection_summary = result.get("collectionSummary") or {}
        content = result.get("content") or {}
        ecommerce = result.get("ecommerce") or {}
        prod_stats = ecommerce.get("productStats") or {}

        # collectionName
        if not content.get("collectionName"):
            score -= 0.08
            missing.append("collection.collectionName")

        # products extracted
        if not products:
            score -= 0.15
            missing.append("collection.products")
            warnings.append("No products extracted from collection page.")
        else:
            # product URLs — use raw result products (normalized objects use "url" not "productUrl")
            raw_products = result.get("products") or []
            missing_urls = [p for p in raw_products if not p.get("productUrl") and not p.get("url")]
            if raw_products and len(missing_urls) > len(raw_products) * 0.5:
                score -= 0.07
                missing.append("collection.productUrls")

            # product images — use raw result products (normalized objects strip imageUrl)
            raw_products = result.get("products") or []
            missing_imgs = [
                p for p in raw_products
                if not p.get("imageUrl") and not (p.get("additionalImageUrls") or [])
            ]
            if raw_products and len(missing_imgs) > len(raw_products) * 0.5:
                score -= 0.05
                missing.append("collection.productImages")
                warnings.append("images_missing")

            # prices
            missing_prices = [
                p for p in products
                if not (
                    p.get("price").get("current")
                    if isinstance(p.get("price"), dict)
                    else p.get("price")
                )
            ]
            if len(missing_prices) > len(products) * 0.5:
                score -= 0.05
                missing.append("collection.prices")

            # availability
            unknown_avail = [
                p for p in products
                if (
                    (p.get("availability") or {}).get("status", "unknown")
                    if isinstance(p.get("availability"), dict)
                    else (p.get("availability") or "unknown")
                ) == "unknown"
            ]
            if len(unknown_avail) > len(products) * 0.8:
                score -= 0.04
                missing.append("collection.availability")

        # productStats
        if not prod_stats.get("productCount"):
            score -= 0.04
            missing.append("collection.productStats")

        # priceRange
        pr = prod_stats.get("priceRange") or {}
        if pr.get("min") is None and pr.get("max") is None:
            score -= 0.04
            missing.append("collection.priceRange")

        # collectionSummary
        if not collection_summary:
            score -= 0.03
            missing.append("collection.collectionSummary")

    elif page_type == "homepage":
        # ── Homepage quality checks ──────────────────────────────────────────
        # Do NOT apply product-page or collection-page scoring here.
        content = result.get("content") or {}
        ecommerce = result.get("ecommerce") or {}
        hp_summary = result.get("homepageSummary") or {}
        nav_links = safe_get(result, ["navigation", "links"]) or []
        sections = content.get("sections") or []
        featured_products = ecommerce.get("featuredProducts") or []
        featured_collections = ecommerce.get("featuredCollections") or []
        primary_ctas = content.get("primaryCtas") or []
        hero_media = content.get("heroMedia") or []

        # siteName
        if not (content.get("siteName") or hp_summary.get("siteName")):
            score -= 0.05
            missing.append("homepage.siteName")

        # hero or major banner
        # Also accept WordPress-style hero from homepageStrategy.hero
        _wp_strategy = result.get("homepageStrategy") or {}
        _wp_hero = _wp_strategy.get("hero") or {}
        _has_wp_hero = bool(
            _wp_hero.get("headline")
            or _wp_hero.get("subheadline")
            or _wp_hero.get("image")
        )
        # Also accept unknown-homepage-analyzer hero fields
        _unknown_hero = safe_get(result, ["homepage", "hero"]) or {}
        _has_unknown_hero = bool(
            _unknown_hero.get("headline")
            or _unknown_hero.get("campaignHero")
            or _unknown_hero.get("supportingText")
            or _unknown_hero.get("subheadline")
        )
        if not hero_media and not _has_wp_hero and not _has_unknown_hero:
            score -= 0.07
            missing.append("homepage.heroMedia")
            warnings.append("hero_missing")
        else:
            # hero text warning (text baked into image/video)
            content_warnings = content.get("warnings") or []
            if "hero_text_not_detected_possible_embedded_media_text" in content_warnings:
                warnings.append("hero_text_not_detected_possible_embedded_media_text")

        # navigation
        # Read business model early so we can waive nav penalty for service businesses
        _hp_biz_primary_early = (
            safe_get(result, ["homepage", "businessModel", "primaryModel"])
            or safe_get(result, ["business", "businessModel", "primary"])
            or ""
        )
        _SERVICE_BIZ_MODELS_EARLY = {
            "service_business", "security_services", "lead_generation",
            "agency", "local_business", "web_hosting_provider",
        }
        if not nav_links:
            # Service businesses that have services + CTAs don't need nav links
            # to demonstrate they have a usable, structured homepage.
            _hp_svc_early = safe_get(result, ["homepage", "services"]) or []
            _hp_ctas_early = (
                safe_get(result, ["homepage", "ctas"])
                or safe_get(result, ["homepage", "hero", "primaryCtas"])
                or primary_ctas
            )
            _service_has_equiv_nav = (
                _hp_biz_primary_early in _SERVICE_BIZ_MODELS_EARLY
                and bool(_hp_svc_early)
                and bool(_hp_ctas_early)
            )
            if not _service_has_equiv_nav:
                score -= 0.06
                warnings.append("navigation_missing")
            missing.append("homepage.navigation")

        # sections
        if not sections:
            score -= 0.08
            missing.append("homepage.sections")
            warnings.append("sections_missing")
        elif len(sections) < 2:
            score -= 0.03
            missing.append("homepage.sections_too_few")

        # featured products or collections — also check section-level products
        # so we never fire this warning when product grids are present in sections
        sections_with_products = any(
            (s.get("products") or [])
            for s in sections
            if s.get("type") == "product_section"
        )
        has_cart_in_sections = any(
            k in (s.get("textPreview") or "").lower()
            for s in sections
            for k in ("add to cart", "quick add", "choose options")
        )
        has_product_data = bool(
            featured_products
            or featured_collections
            or sections_with_products
            or has_cart_in_sections
        )
        # Do NOT penalise non-ecommerce homepages for missing product content.
        # SaaS, plugin, service, security, restaurant, and local-business
        # homepages are not expected to have product grids or collections.
        _hp_biz_primary = (
            safe_get(result, ["homepage", "businessModel", "primaryModel"])
            or safe_get(result, ["business", "businessModel", "primary"])
            or ""
        )
        _NON_ECOMMERCE_MODELS = {
            "saas", "plugin_software", "service_business", "security_services",
            "lead_generation", "agency", "restaurant", "local_business",
            "hybrid_local_ecommerce", "web_hosting_provider",
        }
        _is_non_ecommerce_homepage = _hp_biz_primary in _NON_ECOMMERCE_MODELS
        if not has_product_data and not _is_non_ecommerce_homepage:
            score -= 0.07
            missing.append("homepage.featuredProductsOrCollections")
            warnings.append("no_ecommerce_content_on_homepage")
        elif not has_product_data and _hp_biz_primary not in (
            "security_services", "web_hosting_provider", "restaurant",
            "service_business", "local_business", "lead_generation",
            "agency", "saas", "plugin_software",
        ):
            # Non-ecommerce models without product focus: don't clutter missingFields
            missing.append("homepage.featuredProductsOrCollections")

        # CTAs — check hero.primaryCtas, content.ctas, and homepage.ctas (unknown analyzer)
        hero_primary_ctas = safe_get(result, ["homepage", "hero", "primaryCtas"]) or []
        homepage_ctas = safe_get(result, ["homepage", "ctas"]) or []
        if (not primary_ctas and not (content.get("ctas") or [])
                and not hero_primary_ctas and not homepage_ctas):
            score -= 0.05
            missing.append("homepage.primaryCtas")
            warnings.append("no_ctas_detected")

        # ecommerce evidence — only penalise ecommerce models for missing signals
        announcement_bar = content.get("announcementBar") or {}
        features_detected = content.get("detectedFeatures") or {}
        has_ecommerce_signals = bool(
            featured_products
            or featured_collections
            or features_detected.get("hasCollectionBanners")
            or announcement_bar.get("detected")
        )
        if not _is_non_ecommerce_homepage and not has_ecommerce_signals:
            score -= 0.04
            missing.append("homepage.ecommerceSignals")

        # ── Service-business-specific quality checks ─────────────────────────
        _SERVICE_BIZ_MODELS = {
            "service_business", "security_services", "lead_generation",
            "agency", "local_business",
        }
        if _hp_biz_primary in _SERVICE_BIZ_MODELS:
            _hp_services = safe_get(result, ["homepage", "services"]) or []
            _hp_trust = safe_get(result, ["homepage", "trustSignals"]) or []
            _hp_service_area = safe_get(result, ["homepage", "serviceArea"]) or []
            _hp_contact = safe_get(result, ["homepage", "contact"]) or {}
            _has_contact = bool(
                _hp_contact.get("phone") or _hp_contact.get("email")
            )

            if not _hp_services:
                score -= 0.06
                missing.append("homepage.services")
                warnings.append("services_missing")
            elif len(_hp_services) < 2:
                score -= 0.03
                missing.append("homepage.services_too_few")

            if not _hp_trust:
                score -= 0.04
                missing.append("homepage.trustSignals")

            if not _hp_service_area:
                score -= 0.03
                missing.append("homepage.serviceArea")

            if not _has_contact:
                # Waive contact penalty for service businesses that have serviceArea + trust signals
                # (e.g. ARFM Security has London/Birmingham serviceArea + SIA-licensed trust signals
                # but doesn't show a phone number on their Jina-rendered homepage)
                _can_waive_contact = bool(_hp_service_area and _hp_trust)
                if not _can_waive_contact:
                    score -= 0.04
                    warnings.append("contact_missing")
                    missing.append("homepage.contactInfo")
                # If waived: omit from missingFields (serviceArea + trustSignals compensate)

        # Restaurant-specific quality checks
        elif _hp_biz_primary == "restaurant":
            _hp_menu_items = safe_get(result, ["homepage", "menuItems"]) or []
            _hp_menu_cats = safe_get(result, ["homepage", "menuCategories"]) or []
            _hp_hero_supporting = safe_get(
                result, ["homepage", "hero", "supportingText"]
            )
            _hp_contact = safe_get(result, ["homepage", "contact"]) or {}
            _has_contact = bool(
                _hp_contact.get("phone") or _hp_contact.get("email")
            )

            if not _hp_menu_items:
                score -= 0.10
                missing.append("homepage.menuItems")
                warnings.append("menu_items_missing")
            elif len(_hp_menu_items) < 5:
                score -= 0.06
                missing.append("homepage.menuItems_too_few")

            if not _hp_menu_cats:
                score -= 0.07
                missing.append("homepage.menuCategories")

            if not _hp_hero_supporting:
                score -= 0.06
                missing.append("homepage.hero.supportingText")

            if not _has_contact:
                score -= 0.05
                missing.append("homepage.contactInfo")
                warnings.append("contact_missing")

        # Web hosting provider quality checks
        elif _hp_biz_primary == "web_hosting_provider":
            _hp_services = safe_get(result, ["homepage", "services"]) or []
            _hp_pricing_plans = safe_get(result, ["homepage", "pricingPlans"]) or []
            _hp_trust = safe_get(result, ["homepage", "trustSignals"]) or []
            _hp_contact = safe_get(result, ["homepage", "contact"]) or {}
            _has_contact = bool(
                _hp_contact.get("phone") or _hp_contact.get("email")
            )
            if not _hp_services:
                score -= 0.04
                missing.append("homepage.services")
            if not _hp_pricing_plans:
                missing.append("homepage.pricingPlans")
            if not _hp_trust:
                score -= 0.02
                missing.append("homepage.trustSignals")
            if not _has_contact:
                missing.append("homepage.contactInfo")

    else:
        # Product-level quality checks (non-collection, non-homepage pages).
        # Use raw result["products"] — normalize_product_object() strips description/
        # features/benefits for the competitive schema, so the normalized `products`
        # list is unsuitable here.  Fall back to the normalized list only if the raw
        # list is absent, then to single_product (also raw ecommerce.product).
        _raw_products = list(result.get("products") or [])
        all_products = _raw_products if _raw_products else list(products or [])
        if not all_products and single_product:
            all_products = [single_product]

        for p in all_products[:1]:  # check the primary product
            if not isinstance(p, dict):
                continue

            # description is a dict ({text, html}) on Shopify but a plain
            # string on WordPress/Woo product extractions — support both.
            desc = p.get("description") or {}
            if isinstance(desc, str):
                desc = {"text": desc}
            elif not isinstance(desc, dict):
                desc = {}
            has_desc = bool(desc.get("text") or desc.get("html") or p.get("shortDescription"))
            if not has_desc:
                score -= 0.05
                missing.append("product.description")
                warnings.append("description_missing")

            desc_benefits = desc.get("benefits") or []
            desc_features = desc.get("features") or []
            if not p.get("benefits") and not p.get("features") and not desc_benefits and not desc_features:
                score -= 0.06
                missing.append("product.benefits_or_features")
                warnings.append("benefits_features_missing")

            has_images = bool(
                p.get("imageUrl")
                or (p.get("media") or {}).get("images")
                or p.get("additionalImageUrls")
            )
            if not has_images:
                score -= 0.05
                missing.append("product.images")
                warnings.append("images_missing")

            if not p.get("variants"):
                score -= 0.03
                missing.append("product.variants")
                warnings.append("variants_missing")

            if not p.get("category"):
                score -= 0.04
                missing.append("product.category")
                warnings.append("category_missing")

    score = max(0, min(1, round(score, 2)))

    # Collect fields explicitly marked as "unfetched" across the result tree.
    # These are knowable but weren't retrieved in this pass — AI can re-fetch them.
    _UNFETCHED = "unfetched"
    unfetched_fields = []
    _sp = result.get("product") or safe_get(result, ["ecommerce", "product"]) or {}
    if isinstance(_sp, dict):
        for _field in ("variants", "options", "discount", "shortDescription"):
            if _sp.get(_field) == _UNFETCHED:
                unfetched_fields.append(f"product.{_field}")
    _raw_col_products = result.get("products") or []
    if _raw_col_products and isinstance(_raw_col_products[0], dict):
        _uf_counts = {}
        for _cp in _raw_col_products[:50]:
            if not isinstance(_cp, dict):
                continue
            for _field in ("price", "shortDescription", "variantCount", "discount"):
                if _cp.get(_field) == _UNFETCHED:
                    _uf_counts[f"collectionProduct.{_field}"] = _uf_counts.get(f"collectionProduct.{_field}", 0) + 1
        for _k, _v in _uf_counts.items():
            if _v > len(_raw_col_products) * 0.5:
                unfetched_fields.append(_k)

    # ── Data consistency checks ──────────────────────────────────────────────
    # These are purely additive — they flag potential extraction errors without
    # changing the score. Operators can use these signals to filter or review results.
    data_consistency = _build_data_consistency(result, products, single_product)

    return {
        "score": score,
        "warnings": unique_list(warnings, limit=20),
        "missingFields": unique_list(missing, limit=20),
        "unfetchedFields": unfetched_fields,
        "dataConsistency": data_consistency,
    }


def _build_data_consistency(result, products, single_product):
    """
    Cross-check extracted fields for internal consistency.
    Returns a dict of flags — none of these affect the quality score.

    Flags:
      structuredDataFound       bool  — JSON-LD/schema.org was present in the page
      structuredDataProductFound bool  — A Product schema type was found
      priceConsistent           bool | None — JSON-LD price ≈ text-extracted price
      currencyPlausible         bool | None — Extracted currency matches TLD expectation
      suspiciousName            bool  — Product name looks wrong (equals site name / very long)
      flags                     list[str]  — Human-readable warnings for reviewers
    """
    from utils.currency import currency_from_url

    flags = []
    page_url = safe_get(result, ["page", "url"]) or ""

    # 1. Structured data presence
    structured_items = safe_get(result, ["structuredData", "items"]) or []
    sd_found = bool(structured_items)
    sd_product_found = any(
        (item.get("@type") or "").lower() in ("product", "productgroup")
        for item in structured_items
        if isinstance(item, dict)
    )

    # 2. Price cross-check: JSON-LD price vs text-extracted price
    price_consistent = None
    _sd_price = None
    for item in structured_items:
        if not isinstance(item, dict):
            continue
        if (item.get("@type") or "").lower() in ("product", "productgroup"):
            _offers = item.get("offers") or {}
            if isinstance(_offers, list):
                _offers = _offers[0] if _offers else {}
            _sd_price_raw = _offers.get("price") or item.get("price")
            if _sd_price_raw is not None:
                try:
                    _sd_price = float(str(_sd_price_raw).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            break

    _extracted_price = None
    _p = single_product or (products[0] if products else None)
    if isinstance(_p, dict):
        _pn = _p.get("priceNormalized") or {}
        if isinstance(_pn, dict):
            _extracted_price = _pn.get("amount")
        if _extracted_price is None:
            # Try normalized price in the result root
            _extracted_price = safe_get(result, ["ecommerce", "product", "priceNormalized", "amount"])

    if _sd_price is not None and _extracted_price is not None:
        _diff_pct = abs(_sd_price - _extracted_price) / max(_sd_price, 0.01)
        price_consistent = _diff_pct <= 0.05   # within 5%
        if not price_consistent:
            flags.append(
                f"price_mismatch: structured_data={_sd_price} vs extracted={_extracted_price}"
            )

    # 3. Currency plausibility: does extracted currency match TLD?
    currency_plausible = None
    _extracted_currency = None
    if isinstance(_p, dict):
        _pn2 = _p.get("priceNormalized") or {}
        if isinstance(_pn2, dict):
            _extracted_currency = _pn2.get("currency")
    if _extracted_currency is None:
        _extracted_currency = safe_get(result, ["ecommerce", "product", "priceNormalized", "currency"])

    _tld_currency = currency_from_url(page_url)
    if _extracted_currency and _tld_currency:
        currency_plausible = (_extracted_currency == _tld_currency)
        if not currency_plausible:
            # USD on a non-US TLD is the most common wrong-currency case
            if _extracted_currency == "USD" and _tld_currency != "USD":
                flags.append(
                    f"currency_likely_wrong: got USD but TLD suggests {_tld_currency} ({page_url})"
                )
            # else: different currencies can be legitimate (international store priced in USD)
    elif _extracted_currency == "USD" and _tld_currency:
        currency_plausible = None  # can't be certain without TLD confirmation

    # 4. Suspicious product name
    suspicious_name = False
    _prod_name = None
    if isinstance(_p, dict):
        _prod_name = _p.get("name") or _p.get("title")
    if _prod_name:
        _site_name = (safe_get(result, ["seo", "siteName"]) or "").strip().lower()
        _og_site   = (safe_get(result, ["openGraph", "site_name"]) or "").strip().lower()
        _name_l    = _prod_name.strip().lower()
        if len(_prod_name) > 120:
            suspicious_name = True
            flags.append("product_name_too_long")
        elif _site_name and _name_l == _site_name:
            suspicious_name = True
            flags.append("product_name_equals_site_name")
        elif _og_site and _name_l == _og_site:
            suspicious_name = True
            flags.append("product_name_equals_og_site_name")

    # 5. Zero / negative price in structured data
    if _sd_price is not None and _sd_price <= 0:
        flags.append(f"structured_data_zero_or_negative_price: {_sd_price}")

    return {
        "structuredDataFound":        sd_found,
        "structuredDataProductFound": sd_product_found,
        "priceConsistent":            price_consistent,
        "currencyPlausible":          currency_plausible,
        "suspiciousName":             suspicious_name,
        "flags":                      flags,
    }


_COLLECTION_TITLE_PRICE_RE = re.compile(
    r'\s+(?:Sale\s+Price\s+)?\$\s*\d.*$',
    re.I,
)


def _enrich_collection_result(result):
    """
    Derive missing collection fields before quality scoring.
    Runs for every fetch path (Firecrawl, Jina, Microlink, OpenAI browse).

    - Strips trailing price text from product titles (e.g. "Name $ 88" → "Name")
    - Sets content.collectionName from collection.title / seo.h1 / content.heading
    - Computes ecommerce.productStats (productCount, priceRange) from product list
    - Sets top-level collectionSummary (read by quality scorer)
    """
    page_type = safe_get(result, ["page", "pageType"]) or ""
    if page_type != "collection":
        return result

    # ── Strip trailing price text from product titles ─────────────────────────
    for _plist in (result.get("products") or [], (result.get("collection") or {}).get("products") or []):
        for _p in _plist:
            if not isinstance(_p, dict):
                continue
            _t = _p.get("title") or ""
            if _t:
                _t2 = _COLLECTION_TITLE_PRICE_RE.sub("", _t).strip()
                if _t2:
                    _p["title"] = _t2

    # ── Set content.collectionName (brand-aware) ──────────────────────────────
    collection = result.get("collection") or {}
    content    = result.get("content") or {}
    seo        = result.get("seo") or {}
    og         = result.get("openGraph") or {}

    _site_name = (og.get("site_name") or "").strip().lower()

    def _brand_only(name):
        """True when `name` is just the site/brand name, not a collection name."""
        n = (name or "").strip().lower()
        if not n:
            return True
        return bool(_site_name) and n == _site_name

    def _strip_brand(title):
        if not title:
            return ""
        cleaned = re.sub(r"\s*[\|–—-]\s*" + re.escape(og.get("site_name") or "") + r"\s*$",
                         "", title).strip() if og.get("site_name") else title
        return cleaned or title

    _handle = ""
    _url_for_handle = safe_get(result, ["page", "url"]) or ""
    _hm = re.search(r"/collections/([^/?#]+)", _url_for_handle)
    if _hm:
        _handle = _hm.group(1)
    else:
        # Non-Shopify collection URLs: use the last meaningful path segment
        _segs = [x for x in _url_for_handle.split("?")[0].split("#")[0].split("/") if x][2:]
        if _segs:
            _handle = _segs[-1]
    _handle_title = re.sub(r"\d{4,}.*$", "", _handle).replace("-", " ").replace("_", " ").strip().title()

    def _strip_domainish(title):
        # "Mens Clothing. Nike.com" -> "Mens Clothing"
        return re.sub(r"[\s\|\-–—.]+[A-Za-z0-9-]+\.[A-Za-z]{2,}\s*$", "", title or "").strip() or (title or "")

    _slug_tokens = set(re.sub(r"[^a-z0-9]+", " ", _handle_title.lower()).split())

    def _slug_overlap(name):
        if not _slug_tokens:
            return 0
        tokens = set(re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).split())
        return len(tokens & _slug_tokens)

    # The analyzer-resolved name always wins when it is valid.
    _existing = content.get("collectionName")
    if _existing and not _brand_only(_existing) and len(_existing) <= 80:
        col_name = _existing
    else:
        _candidates = [
            collection.get("title"),
            collection.get("collectionName"),
            seo.get("h1"),
            _strip_domainish(_strip_brand(og.get("title"))),
            _strip_domainish(_strip_brand(seo.get("title"))),
            content.get("heading"),
            _handle_title,                       # URL slug as last resort
        ]
        _valid = [c for c in _candidates if c and not _brand_only(c) and len(c) <= 80]
        # Prefer the shortest candidate overlapping the URL slug (an h1 like
        # "Select your Location" has no overlap with "mens-clothing" and loses).
        _overlapping = sorted([c for c in _valid if _slug_overlap(c) > 0], key=len)
        col_name = (_overlapping[0] if _overlapping else (_valid[0] if _valid else "")) or ""
    if col_name:
        result.setdefault("content", {})["collectionName"] = col_name

    # ── Compute ecommerce.productStats ────────────────────────────────────────
    products = result.get("products") or []
    if products:
        _prices_num = []
        _detected_currency = None
        for _p in products:
            _raw = _p.get("price") or ((_p.get("allPrices") or [None])[0])
            if _raw:
                try:
                    if isinstance(_raw, dict):
                        # Extract numeric value and currency from price dict
                        # (avoid str(dict) which concatenates all digit chars)
                        _val = _raw.get("current") or _raw.get("amount")
                        _cur = _raw.get("currency")
                        if _val is not None:
                            _prices_num.append(float(_val))
                            if _cur:
                                _detected_currency = _cur
                    elif isinstance(_raw, (int, float)):
                        _prices_num.append(float(_raw))
                    else:
                        _prices_num.append(float(re.sub(r"[^\d.]", "", str(_raw))))
                except (ValueError, TypeError):
                    pass
        _price_range = (
            {
                "min": round(min(_prices_num), 2),
                "max": round(max(_prices_num), 2),
                **({"currency": _detected_currency} if _detected_currency else {}),
            }
            if _prices_num else None
        )
        ecommerce = result.setdefault("ecommerce", {})
        if not ecommerce.get("productStats"):
            ecommerce["productStats"] = {
                "productCount": len(products),
                **({"priceRange": _price_range} if _price_range else {}),
            }
        elif _price_range and not (ecommerce["productStats"].get("priceRange") or {}).get("min"):
            # Fill in priceRange if the analyzer left it empty
            ecommerce["productStats"]["priceRange"] = _price_range
    else:
        _price_range = None

    # ── Set collectionSummary with totalProductsOnSite ────────────────────────
    # Parse total from pagination text (e.g. "430 products" → 430) so downstream
    # consumers see the true catalog size, not just what was extracted.
    _total_on_site = None
    _pag = (result.get("collection") or {}).get("pagination") or {}
    _pag_text = _pag.get("totalProductsText") or ""
    _total_match = re.search(r"(\d[\d,]+)\s+(?:products|items|results)", _pag_text, re.I)
    if _total_match:
        try:
            _total_on_site = int(_total_match.group(1).replace(",", ""))
        except ValueError:
            pass

    existing_cs = result.get("collectionSummary") or {}
    _prod_count = len(products) if products else (existing_cs.get("productCount") or 0)
    _pr = (
        (result.get("ecommerce") or {}).get("productStats", {}).get("priceRange")
        or _price_range
        or existing_cs.get("priceRange")
    )
    # MERGE: preserve everything the analyzer computed (category,
    # dominantProductTypes, topBrands, stock counts, availabilityRatio, ...).
    new_cs = dict(existing_cs)
    _existing_name = existing_cs.get("name") or ""
    if col_name and (not _existing_name or _brand_only(_existing_name)):
        new_cs["name"] = col_name
    elif not _existing_name:
        new_cs["name"] = col_name or ""
    new_cs["productCount"] = _prod_count
    if _pr:
        new_cs["priceRange"] = _pr
    new_cs.setdefault("source", result.get("extractionMethod") or "unknown")
    if _total_on_site and _total_on_site > _prod_count:
        new_cs["totalProductsOnSite"] = _total_on_site

    # ── Coerce string prices into canonical dicts ────────────────────────────
    # Some DOM extractions emit price as a bare string ("38") for part of the
    # cards; normalize so every product has the same price shape.
    for _p in products:
        _pr = _p.get("price")
        if isinstance(_pr, str) and _pr.strip():
            _m = re.search(r"\d[\d,]*(?:\.\d+)?", _pr)
            if _m:
                try:
                    _num = float(_m.group(0).replace(",", ""))
                except ValueError:
                    continue
                _cur2 = None
                _prl = _pr.lower()
                if "$" in _pr or "usd" in _prl:
                    _cur2 = "USD"
                elif "rs" in _prl or "pkr" in _prl or "₨" in _pr:
                    _cur2 = "PKR"
                elif "£" in _pr:
                    _cur2 = "GBP"
                elif "€" in _pr:
                    _cur2 = "EUR"
                _p["price"] = {
                    "currency": _cur2,
                    "current": int(_num) if _num.is_integer() else _num,
                    "compareAt": None,
                    "isOnSale": False,
                    "priceTextRaw": _pr,
                }
                # NOTE: string prices were already counted into _prices_num by
                # the productStats block above - do not double-count here.

    # ── Data-consistency flags for the quality gate ───────────────────────────
    _flags = []
    if products:
        _priced_n = len(_prices_num) if products else 0
        if _priced_n == 0:
            # Products found but no prices at all: usually JS-rendered prices
            # (headless stores) - the quality gate should trigger a retry.
            _flags.append("collection_prices_missing")
        elif _priced_n / max(1, len(products)) < 0.5:
            # Under half the products have prices: partial JS render.
            _flags.append("collection_prices_partial")
        _with_prod_url = sum(
            1 for _p in products
            if (_p.get("productUrl") or _p.get("url") or "")
            and (_p.get("productUrl") or _p.get("url")) != safe_get(result, ["page", "url"])
        )
        if _priced_n == 0 and _with_prod_url == 0:
            _flags.append("products_look_like_services")
        elif _priced_n == 0 and not (result.get("ecommerce") or {}).get("hasProducts"):
            _flags.append("products_may_be_service_links")
    if _flags:
        new_cs["consistencyFlags"] = _flags
        _eqc = (result.setdefault("analysisReady", {})
                     .setdefault("extractionQuality", {})
                     .setdefault("dataConsistency", {}))
        _eqc["flags"] = list(dict.fromkeys((_eqc.get("flags") or []) + _flags))

    result["collectionSummary"] = new_cs

    return result


def _flag_pricing_without_plans(result):
    """hasPricing=True with zero plans is a weak signal; flag it so downstream
    consumers (comparison, accuracy scorecard) can treat it with caution."""
    pricing = result.get("pricing") or {}
    if pricing.get("hasPricing") and not (pricing.get("plans") or []):
        eq = (result.setdefault("analysisReady", {})
                    .setdefault("extractionQuality", {})
                    .setdefault("dataConsistency", {}))
        flags = eq.get("flags") or []
        if "pricing_detected_but_no_plans" not in flags:
            flags.append("pricing_detected_but_no_plans")
        eq["flags"] = flags
    return result


def _ensure_quality_bucket(result):
    """qualityBucket was only set on some code paths; derive it from the final
    score whenever it is missing so every result is bucketable."""
    eq = ((result.get("analysisReady") or {}).get("extractionQuality") or {})
    score = eq.get("score")
    if isinstance(score, (int, float)) and not eq.get("qualityBucket"):
        eq["qualityBucket"] = (
            "excellent" if score >= 0.90 else
            "good"      if score >= 0.80 else
            "partial"   if score >= 0.65 else
            "low"       if score >= 0.35 else
            "poor"
        )
    return result


def normalize_for_competitive_analysis(result):
    if not isinstance(result, dict):
        return result

    # Promote the detected platform: the Unknown analyzer stamps "Unknown"
    # even when level1 detection identified the platform (e.g. HubSpot CMS).
    _l1 = result.get("level1") or {}
    if (
        result.get("platform") in (None, "", "Unknown")
        and _l1.get("platform") not in (None, "", "Unknown")
        and (_l1.get("platformConfidence") or 0) >= 0.65
    ):
        result["platform"] = _l1.get("platform")

    # Enrich collection fields before quality scoring
    result = _enrich_collection_result(result)

    # Backfill ecommerce.products from normalized product extraction if not set.
    # The product analyzer writes result["ecommerce"]["product"] (singular) but not
    # the plural list; collection analyzers may also not set it. extract_products()
    # handles both singular product dicts and collection product arrays.
    _extracted = extract_products(result)
    _ecomm = result.get("ecommerce")
    if isinstance(_ecomm, dict) and _extracted and not _ecomm.get("products"):
        _ecomm["products"] = _extracted

    page_summary        = build_page_summary(result)
    competitive_signals = build_competitive_signals(result)
    extraction_quality  = build_extraction_quality(result)

    result["analysisReady"] = {
        "schemaVersion":      "competitive-analysis-v1",
        "pageSummary":        page_summary,
        "competitiveSignals": competitive_signals,
        "extractionQuality":  extraction_quality,
    }

    # Re-attach consistency flags computed by _enrich_collection_result
    # (analysisReady was just rebuilt, which would otherwise drop them).
    _cs_flags = (result.get("collectionSummary") or {}).get("consistencyFlags") or []
    if _cs_flags:
        _dc = extraction_quality.setdefault("dataConsistency", {})
        _dc["flags"] = list(dict.fromkeys((_dc.get("flags") or []) + _cs_flags))

    result = _flag_pricing_without_plans(result)
    result = _ensure_quality_bucket(result)

    return result

