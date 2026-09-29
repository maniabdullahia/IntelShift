"""
analyzers/shopify/product.py
============================
Shopify Product Page Analyzer - v7

Improvements over v6:
  - Fixed price normalization (Shopify .js returns major units, not cents)
  - Currency detection from page (window.Shopify.currency, OG tags, DOM symbols)
  - Variant availability per-option + swatch/color mapping from DOM
  - Reviews & ratings: JSON-LD AggregateRating, Yotpo, Okendo, Judge.me,
    Stamped.io, Loox, native star DOM patterns
  - Tightened description sections: RTE bold-heading pattern, better bullet mapping
  - Badges: DOM badge elements + sale/soldout/new logic
  - Related/recommended products: Shopify Recommendations API + DOM fallback
  - Media: video URLs, 3D model URLs from product JSON media array,
    lazy-load data-src image resolution
  - Extended window.* JS data extraction (currency, product ID, metafields)
"""

_PRODUCT_ANALYZER_VERSION = "v7.4-2024-keune-inci-fix"

import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

from normalizers.product_normalizer import normalize_product
from normalizers.description_normalizer import clean_html_description
from normalizers.price_normalizer import normalize_number
from normalizers.text_normalizer import title_case_from_handle
from extractors.accordion_extractor import extract_accordions
from extractors.section_detector import detect_section_type, map_accordion_entries, build_description_sections


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

SECTION_KEYWORDS = {
    "ingredients": [
        "ingredients", "ingredient", "key ingredients", "active ingredients",
        "full ingredients", "composition", "formula", "inci", "what's inside",
        "formulated with", "contains",
    ],
    "usage": [
        "how to apply", "how to use", "directions", "application", "usage",
        "instructions", "direction for use", "application method",
        "for best results", "steps", "how it works",
    ],
    "benefits": [
        "benefits", "key benefits", "why you'll love it", "why you will love it",
        "advantages", "results", "why choose", "what it does",
        "skin benefits", "hair benefits",
    ],
    "features": [
        "features", "details", "product details", "highlights",
        "product highlights", "key features", "about this product",
        "product info", "overview", "what's included", "why this product",
    ],
    "specifications": [
        "specifications", "size", "volume", "weight", "net weight",
        "shade", "color", "colour", "dimensions", "capacity",
        "material", "sku", "in the box",
    ],
    "faqs": [
        "faq", "frequently asked", "questions", "q&a",
        "questions & answers", "people also ask",
    ],
}

SECTION_LABELS = {
    "description", "ingredients", "ingredient", "key ingredients",
    "active ingredients", "benefits", "key benefits", "how to apply",
    "how to use", "usage", "directions", "application", "instructions",
    "features", "details", "product details", "specifications",
    "size", "volume", "weight",
}

BENEFIT_WORDS = {
    "helps", "help", "beautiful", "beauty", "shape", "nourish", "nourishes",
    "strong", "lashes", "eyelashes", "eyebrows", "curl", "define", "fall out",
}

INGREDIENT_TERMS = [
    "water", "aqua", "glycerin", "alcohol", "panthenol", "sodium",
    "potassium", "caprylyl", "carbomer", "phenoxyethanol", "parfum",
    "fragrance", "oxide", "mica", "talc", "wax", "acid", "extract",
    "oil", "butter", "peptide", "biotin", "aloe", "vitamin",
]

SPEC_KEYWORDS = ["ml", "g", "gm", "kg", "shade", "size", "volume", "weight", "oz"]

# Word-boundary regex for spec keywords to avoid "lightweight" matching "weight"
_SPEC_KEYWORD_RE = re.compile(
    r"\b(?:ml|gm?|kg|oz|shade|size|volume|weight|net weight|dimensions?|capacity|material|sku|model)\b",
    re.IGNORECASE,
)

# Action verbs that indicate a usage instruction, not a specification
_INSTRUCTION_VERB_RE = re.compile(
    r"^(?:apply|use|wear|start|layer|allow|reapply|rinse|massage|leave|spread|"
    r"cleanse|wash|mix|combine|add|place|remove|avoid|store|keep|shake|squeeze|"
    r"insert|attach|ensure|follow|check|consult)\b",
    re.IGNORECASE,
)

# Currencies that have no sub-units (safe to round to integer)
NO_DECIMAL_CURRENCIES = {"JPY", "KRW", "VND", "IDR", "CLP", "PYG", "UGX", "RWF"}


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def get_product_handle(url):
    parts = urlparse(url).path.strip("/").split("/")
    if "products" in parts:
        i = parts.index("products")
        if len(parts) > i + 1:
            # Shopify handles always use dashes; some storefronts (e.g. SKIMS
            # localized URLs) use underscores — normalise to dashes so the
            # /products/{handle}.json API call succeeds.
            return parts[i + 1].replace("_", "-")
    return None


def get_collection_handle_from_url(url):
    parts = urlparse(url).path.strip("/").split("/")
    if "collections" in parts:
        i = parts.index("collections")
        if len(parts) > i + 1:
            return parts[i + 1]
    return None


def get_base_url(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


# ---------------------------------------------------------------------------
# Currency detection
# ---------------------------------------------------------------------------

def extract_currency_from_page(html, soup, og=None, url=None):
    """
    Try to detect store currency from multiple sources.
    Priority: window.Shopify.currency → OG meta → DOM symbols → TLD → fallback.
    """
    html = html or ""

    # 1. window.Shopify.currency.active  or  Shopify.currency = "USD"
    for pattern in [
        r'Shopify\.currency\.active\s*[=:]\s*["\']([A-Z]{3})["\']',
        r'Shopify\.currency\s*=\s*["\']([A-Z]{3})["\']',
        r'"currency"\s*:\s*"([A-Z]{3})"',
        r"'currency'\s*:\s*'([A-Z]{3})'",
        r'"currency_code"\s*:\s*"([A-Z]{3})"',
    ]:
        m = re.search(pattern, html)
        if m:
            return m.group(1)

    # 2. OG price:currency
    if og:
        currency = og.get("price:currency") or og.get("product:price:currency")
        if currency and len(currency) == 3:
            return currency.upper()

    # 3. Meta tag
    meta = soup.find("meta", attrs={"property": "product:price:currency"}) or \
           soup.find("meta", attrs={"name": "currency"})
    if meta and meta.get("content"):
        c = meta["content"].strip().upper()
        if len(c) == 3:
            return c

    # 4. DOM currency symbol heuristics (rough)
    body_text = (soup.find("body") or soup).get_text(" ", strip=True)[:3000]
    if "£" in body_text:
        return "GBP"
    if "€" in body_text:
        return "EUR"
    if "₹" in body_text:
        return "INR"
    if "₨" in body_text or "Rs." in body_text or "PKR" in body_text:
        return "PKR"
    if "¥" in body_text:
        return "JPY"
    if "A$" in body_text:
        return "AUD"
    if "C$" in body_text:
        return "CAD"
    if "AED" in body_text:
        return "AED"
    if "SAR" in body_text:
        return "SAR"

    # 5. TLD-based fallback when Jina strips JS variables
    from utils.currency import currency_from_url as _cfu
    _tld_cur = _cfu(url)
    if _tld_cur:
        return _tld_cur

    return "USD"


# ---------------------------------------------------------------------------
# Price normalization
# ---------------------------------------------------------------------------

def normalize_shopify_price(value):
    """
    Shopify product JSON endpoints (.js / .json) return prices as strings
    in the store's major currency unit (e.g. "29.99", "12500", "0.00").
    We parse as float and return int when whole, float otherwise.
    """
    if value is None:
        return None
    try:
        value_str = str(value).strip()
        if not value_str or value_str in ("", "null", "None"):
            return None
        number = float(value_str)
        if number == 0:
            return None  # Zero-price guard: treat $0.00 as unfetched
        return int(number) if number == int(number) else round(number, 2)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def clean_empty(value):
    if value in ("", "Default Title", "default title", None):
        return None
    return value


def clean_text(value):
    if not value:
        return None
    value = re.sub(r"\s+", " ", str(value)).strip()
    value = value.strip(":-–—|• ")
    return value if value else None


def clean_section_value(value, section_type=None):
    value = clean_text(value)
    if not value:
        return None
    value = re.sub(
        r"^(description|ingredients?|key ingredients|active ingredients|"
        r"benefits|key benefits|how to apply|how to use|usage|directions|"
        r"application|features|details|product details|specifications)"
        r"\s*[:\-–—]?\s*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"^include\s+", "", value, flags=re.IGNORECASE)
    value = clean_text(value)
    if not value:
        return None
    if value.lower().strip(":.-–— ") in SECTION_LABELS:
        return None
    if len(value) < 3:
        return None
    return value


def dedupe_list(items):
    seen = set()
    final = []
    for item in items or []:
        item = clean_section_value(item)
        if not item:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            final.append(item)
    return final


def split_text_items(value):
    parts = []
    for piece in re.split(r"[;•]", value or ""):
        piece = clean_section_value(piece)
        if piece:
            parts.append(piece)
    return parts


# ---------------------------------------------------------------------------
# Ingredient / benefit / usage / spec cleaners
# ---------------------------------------------------------------------------

def is_probable_ingredient_list(value):
    value = clean_section_value(value, "ingredients")
    if not value:
        return False
    lower = value.lower()
    if value.count(",") >= 5:
        return True
    if any(term in lower for term in INGREDIENT_TERMS) and value.count(",") >= 1:
        return True
    return False


def _split_inci_blob(value):
    """Split a comma-separated INCI ingredient blob into individual ingredient names.
    Each segment is trimmed; segments containing sentence-like text (verb phrases,
    long sentences) are dropped so marketing copy doesn't sneak in."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    result = []
    for part in parts:
        # Drop parts that look like sentences (contain a verb + long text)
        if len(part) > 60:
            continue
        if _INSTRUCTION_VERB_RE.match(part):
            continue
        result.append(part)
    return result


def _looks_like_inci_name(item):
    """True for short chemical/botanical names typical of INCI lists."""
    if len(item) > 60 or len(item) < 3:
        return False
    if _INSTRUCTION_VERB_RE.match(item):
        return False
    if any(word in item.lower() for word in BENEFIT_WORDS):
        return False
    # Reject sentences (contain period/exclamation/question mark)
    if re.search(r"[.!?]", item):
        return False
    # ≤5 words → likely a chemical or botanical name
    return len(item.split()) <= 5


def clean_ingredients(items):
    cleaned = []
    for item in items or []:
        item = clean_section_value(item, "ingredients")
        if not item:
            continue
        lower = item.lower()
        if is_probable_ingredient_list(item):
            # Comma-separated INCI blob → split into individual names
            # Threshold lowered from 5 to 1 so short lists ("A, B, C") are also split
            if item.count(",") >= 1:
                cleaned.extend(_split_inci_blob(item))
            else:
                cleaned.append(item)
            continue
        # Already-split INCI name or table-row ingredient
        if _looks_like_inci_name(item):
            cleaned.append(item)
            continue
        # Longer items: require a known ingredient term
        # but reject full marketing sentences (end with . or contain action phrases)
        if re.search(r"[.!?]\s*$", item):
            continue  # full sentence — not an ingredient name
        if re.match(r"(?:enriched|infused|formulated|free from|contains|with|"
                    r"made with|powered by)\b", item, re.IGNORECASE):
            continue  # marketing lead-in phrase
        if any(term in lower for term in INGREDIENT_TERMS) and not any(
            word in lower for word in BENEFIT_WORDS
        ):
            cleaned.append(item)
            continue
    return dedupe_list(cleaned)


# ---------------------------------------------------------------------------
# Body-HTML structural parser: arrow/bold sections (Keune-style)
# ---------------------------------------------------------------------------

# Section headings found in body_html arrow-structured content
# Used to skip heading text when it appears alongside feature/benefit items
_BODY_HTML_SECTION_HEADING_RE = re.compile(
    r"^(?:WHY IT PERFORMS|THE RESULT|HOW TO USE|HOW TO APPLY|HOW TO WEAR|"
    r"KEY BENEFITS?|KEY FEATURES?|PRODUCT FEATURES?|FEATURES?|"
    r"WHAT IT DOES|DIRECTIONS?|HOW IT WORKS|USAGE|INSTRUCTIONS?|"
    r"BENEFITS?|HIGHLIGHTS?|OVERVIEW|ABOUT THIS PRODUCT|"
    r"WHO IT (?:IS )?FOR|SUITABLE FOR|SKIN TYPE|HAIR TYPE)\s*[:\-→]?\s*$",
    re.IGNORECASE,
)

# Maps section heading text to the canonical section type
def _heading_section_type(heading_text):
    """Return 'features', 'benefits', 'usage', or None for a heading string."""
    h = heading_text.lower().rstrip(":→- ")
    if re.search(r"\bfeature|highlight|overview|about|suitable|skin type|hair type\b", h):
        return "features"
    if re.search(r"\bbenefit|result|why\b", h):
        return "benefits"
    if re.search(r"\buse|apply|wear|direction|instruction|usage|how to\b", h):
        return "usage"
    return None

# Matches → immediately followed by a <b> or <strong> tag (features pattern)
# e.g. → <b>Instantly Smooths &amp; Softens </b>
_ARROW_BOLD_RE = re.compile(
    r"→\s*<(b|strong)\b[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Heading bolds that introduce benefit/usage sections
_BENEFIT_HEADING_RE = re.compile(r"^THE\s+RESULT\s*$", re.IGNORECASE)
_USAGE_HEADING_RE = re.compile(
    r"^(?:HOW\s+TO\s+(?:USE|APPLY)|DIRECTIONS?|INSTRUCTIONS?|HOW\s+TO\s+WEAR)\s*$",
    re.IGNORECASE,
)


def _parse_body_html_arrow_sections(body_html):
    """
    Parse Shopify body_html for structured sections.

    Handles two layouts:
    A) Arrow+bold features:    → <b>Feature Name</b>
       THE RESULT benefits:    <b>THE RESULT</b> heading + → item<br/> lines
       HOW TO USE sections:    <b>HOW TO USE</b> heading + content

    B) Labelled bullet blocks (e.g. Sivanna):
       <p>Features:</p>
       <p>• Item one</p>
       <p>• Item two</p>

    Returns dict: {features, benefits, usage}  — each list[str].
    """
    if not body_html:
        return {}

    features = []
    benefits = []
    usage = []

    # ── Layout A: Arrow+bold features via regex on raw HTML ─────────────────
    for m in _ARROW_BOLD_RE.finditer(body_html):
        inner = re.sub(r"<[^>]+>", " ", m.group(2))
        inner = re.sub(r"&amp;", "&", inner)
        inner = re.sub(r"&[a-z#0-9]+;", " ", inner)
        inner = re.sub(r"\s+", " ", inner).strip().rstrip(".,")
        if inner and 4 <= len(inner) <= 80 and not _BODY_HTML_SECTION_HEADING_RE.match(inner):
            features.append(inner)

    # ── Layout A+B: Walk paragraphs for heading-based sections ──────────────
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(body_html, "html.parser")
    except Exception:
        return {"features": dedupe_list(features), "benefits": [], "usage": []}

    paras = soup.find_all(["p", "li"])

    def _para_is_bullet(para):
        """True if paragraph text starts with • (bullet character)."""
        t = para.get_text(" ", strip=True)
        return t.startswith("•") or t.startswith("·") or t.startswith("-")

    def _extract_arrow_lines(para_tag):
        """Return arrow/bullet-item strings from a paragraph, handling <br/> separators."""
        raw = str(para_tag)
        raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
        raw = re.sub(r"<[^>]+>", "", raw)
        raw = re.sub(r"&amp;", "&", raw)
        raw = re.sub(r"&[a-z#0-9]+;", " ", raw)
        items = []
        for line in raw.split("\n"):
            line = re.sub(r"\s+", " ", line).strip()
            if not line or _BODY_HTML_SECTION_HEADING_RE.match(line):
                continue
            # Arrow items
            if "→" in line:
                for part in line.split("→"):
                    part = re.sub(r"\s+", " ", part).strip().rstrip(".,")
                    if part and len(part) >= 3 and not _BODY_HTML_SECTION_HEADING_RE.match(part):
                        items.append(part)
            # Bullet items  (• prefix, possibly inline-concatenated)
            elif "•" in line or "·" in line:
                for part in re.split(r"[•·]", line):
                    part = re.sub(r"\s+", " ", part).strip().rstrip(".,")
                    if part and len(part) >= 3 and not _BODY_HTML_SECTION_HEADING_RE.match(part):
                        items.append(part)
            # Plain-text usage lines (no arrow/bullet)
            elif len(line) >= 10:
                items.append(line.rstrip(".,"))
        return items

    for idx, para in enumerate(paras):
        para_text = re.sub(r"\s+", " ", para.get_text(" ", strip=True)).strip()

        # ── Layout A: bold heading paragraphs (THE RESULT, HOW TO USE) ──────
        heading_type_a = None
        for bold in para.find_all(["b", "strong"]):
            bt = re.sub(r"\s+", " ", bold.get_text(" ", strip=True)).strip()
            if _BENEFIT_HEADING_RE.match(bt):
                heading_type_a = "benefits"
                break
            if _USAGE_HEADING_RE.match(bt):
                heading_type_a = "usage"
                break

        if heading_type_a:
            for target in [para] + ([paras[idx + 1]] if idx + 1 < len(paras) else []):
                items = _extract_arrow_lines(target)
                if heading_type_a == "benefits":
                    benefits.extend(items)
                else:
                    usage.extend(items)
            continue

        # ── Layout B: plain-text heading like "Features:" / "How to Use:" ───
        # Detect heading: short paragraph matching _BODY_HTML_SECTION_HEADING_RE
        # (no bold tag, no bullet prefix, stripped text matches heading pattern)
        clean_text_b = para_text.rstrip(":→- ").strip()
        if (_BODY_HTML_SECTION_HEADING_RE.match(para_text)
                and not para.find(["b", "strong"])
                and not _para_is_bullet(para)):
            section_type_b = _heading_section_type(clean_text_b) or "features"
            # Collect following bullet/arrow/plain paragraphs
            j = idx + 1
            while j < len(paras):
                next_para = paras[j]
                next_text = re.sub(r"\s+", " ", next_para.get_text(" ", strip=True)).strip()
                # Stop at next heading
                if (_BODY_HTML_SECTION_HEADING_RE.match(next_text)
                        and not _para_is_bullet(next_para)):
                    break
                if not next_text:
                    j += 1
                    continue
                items = _extract_arrow_lines(next_para)
                if items:
                    if section_type_b == "features":
                        features.extend(items)
                    elif section_type_b == "benefits":
                        benefits.extend(items)
                    elif section_type_b == "usage":
                        usage.extend(items)
                j += 1

    return {
        "features": dedupe_list([f for f in features if f]),
        "benefits": dedupe_list([b for b in benefits if b]),
        "usage": dedupe_list([u for u in usage if u]),
    }


# ---------------------------------------------------------------------------
# Active ingredients extractor
# ---------------------------------------------------------------------------

# Intro phrases that precede a list of active ingredients
_ACTIVE_ING_INTRO_RE = re.compile(
    r"(?:enriched\s+with|infused\s+with|powered\s+by|contains?|formulated\s+with|"
    r"with\s+the\s+power\s+of|key\s+ingredients?[:\s]+|active\s+ingredients?[:\s]+|"
    r"featuring|fortified\s+with|boosted\s+with)\s+",
    re.IGNORECASE,
)

# Capitalized proper-noun ingredient names (Hyaluronic Acid, Vitamin E, etc.)
_CAPITALIZED_INGREDIENT_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b"
)

# Known active ingredient keywords — partial/substring match against ingredient names.
# Also includes functional patterns: any ingredient containing "extract",
# "hydrolyzed", "oil" (non-mineral), "butter", "protein", etc. is treated as active.
_ACTIVE_INGREDIENT_KEYWORDS = {
    # Humectants & skin-identical
    "hyaluronic acid", "sodium hyaluronate", "glycerin", "glycerine",
    "panthenol", "niacinamide", "squalane", "ceramide", "peptide",
    "urea", "sorbitol", "betaine",
    # Vitamins
    "vitamin e", "vitamin c", "vitamin b5", "vitamin b", "vitamin a",
    "tocopherol", "ascorbic acid", "retinol", "retinyl",
    # Acids (exfoliating/active)
    "salicylic acid", "glycolic acid", "lactic acid", "azelaic acid",
    "mandelic acid", "malic acid", "tartaric acid", "citric acid",
    # Proteins & derivatives
    "hydrolyzed",        # matches "Hydrolyzed Vegetable Protein", "Hydrolyzed Keratin" etc.
    "amino acid",
    "collagen", "keratin",
    # Botanical extracts — "extract" alone is sufficient since it appears only in actives
    "extract",           # matches "Chamomile Extract", "Spathodea Campanulata Flower Extract"
    # Oils (active/functional)
    "argan oil", "jojoba oil", "rosehip oil", "coconut oil",
    "sunflower seed oil", "sunflower oil",
    "avocado oil", "marula oil", "sea buckthorn",
    "bakuchiol",
    # Butters
    "shea butter", "cocoa butter", "mango butter",
    # Plant actives
    "chamomile", "aloe vera", "green tea", "turmeric",
    "rosemary", "lavender", "peppermint",
    "caffeine", "biotin",
    # Minerals
    "zinc", "niacinamide",
}

# Regex for functional ingredient patterns in INCI names (complements keyword list)
_FUNCTIONAL_INCI_RE = re.compile(
    r"\b(?:hydrolyzed|extract|oil\b|butter\b|peptide|protein|acid\b|"
    r"ceramide|retinol|retinyl|tocopherol|ascorbyl|panthenol|niacinamide|"
    r"hyaluronate|squalane|caffeine|biotin|keratin|collagen)\b",
    re.IGNORECASE,
)

# Generic words that are NOT ingredients even when capitalised
_NOT_INGREDIENT_WORDS = {
    "The", "This", "That", "These", "With", "And", "For", "Our", "Your",
    "Its", "Has", "Can", "Will", "Not", "All", "New", "Get", "Add", "Use",
    "Best", "Good", "Made", "More", "Less", "Just", "From", "Into", "Over",
    "Hair", "Skin", "Scalp", "Dry", "Wet", "Each", "Every", "Also",
    "Feel", "Look", "Help", "Make", "Keep", "Give", "Leave", "Work",
    "Long", "Strong", "Soft", "Smooth", "Clean", "Free", "Safe", "Pure",
}


def extract_active_ingredients(description_text, description_html=None, ingredients_list=None):
    """
    Extract active/key ingredient names.

    Strategy 0 (highest quality): filter already-extracted INCI ingredients list
                  against known active-ingredient keywords.
    Strategy 1: intro-phrase extraction ("Enriched with X, Y, Z") from text.
    Strategy 2: known keyword list scan in description text.

    Intentionally does NOT use capitalized-word heuristics — those grab
    marketing copy fragments, not ingredient names.

    Returns a deduplicated list of ingredient names.
    """
    found = []
    seen_lower = set()

    def _add(name):
        name = re.sub(r"\s+", " ", name).strip().rstrip(".,;:()")
        if not name or len(name) < 3 or len(name) > 80:
            return
        lname = name.lower()
        if lname in seen_lower:
            return
        seen_lower.add(lname)
        found.append(name)

    # Strategy 0: filter INCI ingredients list to find known actives
    # Skips unsplit blobs (comma-separated strings — those are handled by Fix 4)
    # Uses keyword substring match and functional-pattern regex
    for ing in (ingredients_list or []):
        if "," in ing:          # skip unsplit INCI blobs
            continue
        ing_lower = ing.lower()
        if (any(kw in ing_lower for kw in _ACTIVE_INGREDIENT_KEYWORDS)
                or _FUNCTIONAL_INCI_RE.search(ing)):
            _add(ing)

    if not description_text:
        return dedupe_list(found)

    # Strategy 1: intro-phrase extraction ("Enriched with X and Y")
    for m in _ACTIVE_ING_INTRO_RE.finditer(description_text):
        after = description_text[m.end():m.end() + 120]
        after = re.split(r"[.!?]", after)[0]
        parts = re.split(r",\s*|\s+and\s+|\s*&\s*", after)
        for part in parts:
            part = part.strip().rstrip(".,;:)")
            # Reject obvious non-ingredient fragments (marketing phrases)
            if 3 <= len(part) <= 50 and not re.search(
                r"\b(?:your|our|it|this|that|with|for|to|in|its|the|a|an)\b",
                part, re.IGNORECASE
            ):
                _add(part)

    # Strategy 2: known keyword list scan in description text
    # Short single-word keywords use word-boundary matching to avoid "silky" → "silk"
    text_lower = description_text.lower()
    for kw in _ACTIVE_INGREDIENT_KEYWORDS:
        if " " in kw:
            # Multi-word keyword: substring match is fine
            if kw in text_lower:
                idx = text_lower.index(kw)
                actual = description_text[idx:idx + len(kw)]
                _add(actual)
        else:
            # Single-word keyword: require word boundaries
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                m = re.search(r"(?i)\b" + re.escape(kw) + r"\b", description_text)
                if m:
                    _add(m.group(0))

    return dedupe_list(found)


# Benefit verbs/adjectives that confirm an item is a real benefit, not a nav label
_BENEFIT_SIGNAL_RE = re.compile(
    r"\b(?:smooth|soft|shine|shiny|frizz|hydrat|moisturi|nourish|strengthen|repair|"
    r"protect|prevent|reduc|control|enhanc|boost|volumiz|thicken|lock|seal|"
    r"manageab|glossy|silky|lightweight|non.stick|long.last|plump|glow|vibrant|"
    r"anti|helps|makes|leaves|gives|adds|fights|locks|improves|reduces)",
    re.IGNORECASE,
)

# Title-case noun phrases that are clearly navigation/category labels, not benefits
_NAV_LABEL_RE = re.compile(
    r"^(Color Protection|Blonde And Silver|No Dandruff|Hair Growth|More Volume|"
    r"Confident Curls|Soothed Scalp|Damaged And Brittle|Long And Strong|"
    r"Keratin|Hydration|Volume|Repair|Moisture|Shine|Curls?|Waves?|"
    r"Scalp Care|Colour Protection)$",
    re.IGNORECASE,
)


# Verb-like words that signal a new benefit clause after a comma
_BENEFIT_CLAUSE_VERBS = re.compile(
    r",\s+(?:this|the|a|an|it|and)\s+\w+\s+(?:formula|product|conditioner|treatment|tint|gloss|serum|cream|oil)\b",
    re.IGNORECASE,
)

# Patterns that split a benefit list sentence into individual items:
# e.g. "hydrate, detangle, and tame frizz" → ["hydrate", "detangle", "tame frizz"]
_BENEFIT_LIST_SPLIT_RE = re.compile(
    r",\s+(?:and\s+)?(?=(?:hydrat|detangl|tame|reduc|seal|leav|soften|smooth|nourish|repair|protect|boost|enhanc|lock|strengthen|volumiz|thicken|plump|glow|sooth|calm|bright|clear|minimiz|firm|tighten|moisturi|condition|control|manag|improv|help))",
    re.IGNORECASE,
)


def _split_long_benefit(text):
    """Split a long benefit paragraph into individual bullet points."""
    if len(text) < 60:
        return [text]

    # 1. Split on ". " followed by capital letter (separate sentences)
    parts = re.split(r"\.\s+(?=[A-Z])", text)
    if len(parts) > 1:
        result = []
        for p in parts:
            p = p.strip().rstrip(".")
            if p and len(p) > 5:
                # Recurse on each sentence
                result.extend(_split_long_benefit(p))
        return result

    # 2. Split on ", " + action verbs (benefit list within a sentence)
    list_parts = _BENEFIT_LIST_SPLIT_RE.split(text)
    if len(list_parts) > 2:
        cleaned = []
        for p in list_parts:
            p = re.sub(r"^(?:designed to|helps to|to|and)\s+", "", p.strip(), flags=re.IGNORECASE)
            p = p.strip().rstrip(".,")
            if p and len(p) >= 6:
                cleaned.append(p)
        return cleaned if len(cleaned) > 1 else [text]

    # 3. Split on em-dash, arrow, or " — "
    parts = re.split(r"\s[–—→]\s", text)
    if len(parts) > 1:
        return [p.strip().rstrip(".,") for p in parts if p.strip() and len(p.strip()) > 5]

    return [text]


def clean_benefits(items):
    expanded = []
    for item in items or []:
        # First expand list items, then split long paragraphs
        for sub in split_text_items(item):
            expanded.extend(_split_long_benefit(sub))

    cleaned = []
    seen = []
    for item in expanded:
        item = clean_section_value(item, "benefits")
        if not item:
            continue

        # Reject known navigation/category labels
        if _NAV_LABEL_RE.match(item):
            continue

        # Short titlecase phrases with no benefit signal are likely nav items
        words = item.split()
        if len(words) <= 3 and not _BENEFIT_SIGNAL_RE.search(item):
            # Allow only if it explicitly contains known benefit terminology
            continue

        key = item.lower()
        duplicate = any(key in existing or existing in key for existing in seen)
        if not duplicate:
            seen.append(key)
            cleaned.append(item)
    return cleaned


# Section-header labels to strip from feature text
_FEATURE_SECTION_HEADER_RE = re.compile(
    r"^(?:WHY IT PERFORMS|THE RESULT|WHO IT(?:'S| IS) FOR|HOW IT WORKS|"
    r"KEY BENEFITS|KEY FEATURES|WHAT IT DOES|PRODUCT DETAILS|"
    r"ABOUT THIS PRODUCT|OVERVIEW|HIGHLIGHTS?)\s*[:\-→]?\s*",
    re.IGNORECASE,
)


def _split_feature_block(text):
    """Split a single feature block string into individual feature bullets."""
    # Strip leading section-header labels
    text = _FEATURE_SECTION_HEADER_RE.sub("", text).strip()
    if not text:
        return []

    # Split on → or • or | separators first
    if re.search(r"[→•|]", text):
        parts = re.split(r"\s*[→•|]\s*", text)
        parts = [p.strip().rstrip(".,") for p in parts if p.strip() and len(p.strip()) >= 8]
        if len(parts) > 1:
            return parts

    # Split on newlines
    lines = [l.strip() for l in re.split(r"[\n\r]+", text) if l.strip()]
    if len(lines) > 1:
        return [l.rstrip(".,") for l in lines if len(l) >= 8]

    # Split on ". " followed by capital letter
    parts = re.split(r"\.\s+(?=[A-Z])", text)
    if len(parts) > 1:
        return [p.strip().rstrip(".") for p in parts if p.strip() and len(p.strip()) >= 8]

    # Short enough to keep as-is
    if len(text) <= 160:
        return [text.rstrip(".")]

    # Last resort: split on comma-verb boundary like benefit splitter
    parts = _BENEFIT_LIST_SPLIT_RE.split(text)
    if len(parts) > 2:
        return [p.strip().rstrip(".,") for p in parts if p.strip() and len(p.strip()) >= 8]

    return [text.rstrip(".")]


def _split_and_clean_features(items):
    """Split long feature blocks into individual bullets and filter noise."""
    result = []
    for item in items or []:
        item = item.strip()
        if not item:
            continue
        for part in _split_feature_block(item):
            if part and 8 <= len(part) <= 220:
                result.append(part)
    return dedupe_list(result)



# Storage and safety instruction detection
_STORAGE_INSTRUCTION_RE = re.compile(
    r"\b(?:store|storage|keep\s+in|keep\s+away|refrigerat|freeze|frozen|"
    r"expiry|expir|best\s+before|use\s+by|shelf\s+life|"
    r"cool\s+dry|dry\s+cool|avoid\s+(?:sunlight|heat|moisture|direct)|"
    r"seal|reseal|close\s+tightly|airtight|"
    r"check\s+.*date|date.*check|"
    r"not\s+suitable\s+for|warning|caution|keep\s+out\s+of\s+reach|"
    r"for\s+external\s+use|do\s+not\s+ingest|do\s+not\s+swallow)\b",
    re.IGNORECASE,
)


def extract_storage_instructions(items):
    """
    Filter a list of text items and return those that are storage/safety instructions.
    Items that match are suitable for a 'storageInstructions' field.
    """
    storage = []
    for item in (items or []):
        if _STORAGE_INSTRUCTION_RE.search(item):
            storage.append(item.strip())
    return dedupe_list(storage)


# Action verbs that confirm a text item is actually a usage instruction
_USAGE_ACTION_VERB_RE = re.compile(
    r"\b(?:apply|use|massage|rinse|leave|brush|spray|mix|serve|feed|wash|add|"
    r"distribute|work|comb|style|section|shake|dispense|squeeze|dot|"
    r"blend|pat|tap|dab|smooth|spread|layer|clean|avoid|remove|take|"
    r"warm|heat|allow|let|towel|dry|wet|place|hold|press|roll|twist|"
    r"start|begin|first|then|next|finally|step|repeat|continue|"
    r"gently|evenly|thoroughly|generously|sparingly)\b",
    re.IGNORECASE,
)


def clean_usage(items):
    cleaned = []
    for item in items or []:
        item = clean_section_value(item, "usage")
        if not item:
            continue
        lower = item.lower()
        if "for best results" in lower:
            item = re.sub(r"^for best results[:,]?\s*", "", item, flags=re.IGNORECASE)
            item = clean_section_value(item, "usage")
        if not item:
            continue
        # Reject items that look like feature-bullet lists (contain • with no action verb)
        has_bullets = "•" in item or "·" in item
        has_verb = bool(_USAGE_ACTION_VERB_RE.search(item))
        if has_bullets and not has_verb:
            continue
        # Reject items that are clearly not instructions (no action verb, very short, or
        # look like product descriptors / feature lists)
        if not has_verb and len(item.split()) <= 6:
            continue
        cleaned.append(item)
    return dedupe_list(cleaned)


def clean_specifications(items):
    cleaned = []
    for item in items or []:
        item = clean_section_value(item, "specifications")
        if not item:
            continue
        # Reject instruction-style sentences (usage steps sneaking into specs)
        if _INSTRUCTION_VERB_RE.match(item):
            continue
        # Reject long marketing/description blobs (> 120 chars rarely a spec)
        if len(item) > 120:
            continue
        # Require at least one spec keyword using word-boundary match
        if _SPEC_KEYWORD_RE.search(item):
            cleaned.append(item)
    return dedupe_list(cleaned)


# ---------------------------------------------------------------------------
# DOM section helpers
# ---------------------------------------------------------------------------

def extract_heading_text(block):
    heading = block.find(["h1", "h2", "h3", "h4", "h5", "h6", "button", "summary"])
    if heading:
        text = clean_text(heading.get_text(" ", strip=True))
        if text:
            return text
    for attr in ("aria-label", "data-title", "data-tab-title"):
        val = block.get(attr)
        if val:
            return clean_text(val)
    return None


def remove_headings_from_block(block):
    cloned = BeautifulSoup(str(block), "lxml")
    for tag in cloned.select("h1,h2,h3,h4,h5,h6,button,summary,strong,b"):
        tag.extract()
    return cloned


def extract_list_or_text(block, section_type=None):
    items = []
    cloned = remove_headings_from_block(block)
    for li in cloned.select("li"):
        text = clean_section_value(li.get_text(" ", strip=True), section_type)
        if text:
            items.append(text)
    if items:
        return dedupe_list(items)
    text = clean_section_value(cloned.get_text(" ", strip=True), section_type)
    return [text] if text else []


# ---------------------------------------------------------------------------
# Window / JS data extraction (extended)
# ---------------------------------------------------------------------------

def extract_window_data(html):
    """
    Extract product & store data from window.* JS variables.
    Returns a dict with keys: product, currency, productId, variantId.
    """
    if not html:
        return {}

    result = {}

    # --- Product data ---
    for pattern in [
        r"window\.meta\s*=\s*(\{.+?\})\s*;",
        r"window\.ShopifyAnalytics\.meta\s*=\s*(\{.+?\})\s*;",
        r"window\.__st\s*=\s*(\{.+?\})\s*;",
        r"var\s+meta\s*=\s*(\{.+?\})\s*;",
        r"window\.productJSON\s*=\s*(\{.+?\})\s*;",
        r"window\.product\s*=\s*(\{.+?\})\s*;",
    ]:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    product_data = parsed.get("product") or parsed
                    if isinstance(product_data, dict) and product_data.get("id"):
                        result["product"] = product_data
                        result["productId"] = str(product_data.get("id", ""))
                        break
            except Exception:
                continue

    # --- Product ID from various sources ---
    if not result.get("productId"):
        for pattern in [
            r'"product_id"\s*:\s*(\d+)',
            r"'product_id'\s*:\s*(\d+)",
            r'data-product-id=["\'](\d+)["\']',
            r'"productId"\s*:\s*(\d+)',
        ]:
            m = re.search(pattern, html)
            if m:
                result["productId"] = m.group(1)
                break

    # --- Currency ---
    for pattern in [
        r'Shopify\.currency\.active\s*[=:]\s*["\']([A-Z]{3})["\']',
        r'Shopify\.currency\s*=\s*["\']([A-Z]{3})["\']',
        r'"currency"\s*:\s*"([A-Z]{3})"',
        r'"currency_code"\s*:\s*"([A-Z]{3})"',
    ]:
        m = re.search(pattern, html)
        if m:
            result["currency"] = m.group(1)
            break

    # --- Shop domain (for API calls) ---
    m = re.search(r'Shopify\.shop\s*=\s*["\']([^"\']+)["\']', html)
    if m:
        result["shopDomain"] = m.group(1)

    return result


# ---------------------------------------------------------------------------
# Shopify API fetchers
# ---------------------------------------------------------------------------

def fetch_shopify_product_json(url):
    """Fetch /products/{handle}.js — prices in major units as strings."""
    handle = get_product_handle(url)
    if not handle:
        return None
    parsed = urlparse(url)
    json_url = f"{parsed.scheme}://{parsed.netloc}/products/{handle}.js"
    try:
        resp = requests.get(json_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def fetch_shopify_product_json_extended(url):
    """
    Fetch /products/{handle}.json — returns {"product": {...}} with a
    `media` array containing images, videos, and 3D models.
    Falls back gracefully to None on failure.
    """
    handle = get_product_handle(url)
    if not handle:
        return None
    parsed = urlparse(url)
    json_url = f"{parsed.scheme}://{parsed.netloc}/products/{handle}.json"
    try:
        resp = requests.get(json_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data.get("product") if isinstance(data, dict) else None
    except Exception:
        return None


def fetch_related_products(base_url, product_id, limit=8):
    """
    Fetch Shopify product recommendations via the Recommendations API.
    Returns list of raw product dicts, or [] on failure.
    """
    if not product_id:
        return []
    api_url = (
        f"{base_url}/recommendations/products.json"
        f"?product_id={product_id}&limit={limit}&intent=related"
    )
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("products", [])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Media extraction
# ---------------------------------------------------------------------------

def extract_media_from_shopify(raw_product, url):
    """
    Extract all media (images, videos, 3D models) from the Shopify product JSON.
    The `media` array is only present in the .json endpoint response.
    Falls back to `images` array if `media` is absent.

    Returns:
        {
            "images": [...],        # all image URLs (deduped)
            "videos": [...],        # video source URLs or embed URLs
            "models": [...],        # 3D model source URLs
            "featuredImage": str,   # primary image URL
        }
    """
    images = []
    videos = []
    models = []

    media_array = raw_product.get("media") or []

    if media_array:
        for media in media_array:
            media_type = (media.get("media_type") or "").lower()

            if media_type == "image":
                src = (
                    media.get("src")
                    or (media.get("preview_image") or {}).get("src")
                )
                if src:
                    images.append(_clean_shopify_image_url(src))

            elif media_type in ("video", "external_video"):
                # Native Shopify video
                sources = media.get("sources") or []
                added = False
                for source in sources:
                    if source.get("url"):
                        videos.append({
                            "type": "native",
                            "url": source["url"],
                            "mimeType": source.get("mime_type"),
                            "width": source.get("width"),
                            "height": source.get("height"),
                        })
                        added = True
                        break
                # External video (YouTube / Vimeo)
                if not added:
                    embed_url = media.get("embed_url") or media.get("host_url")
                    if embed_url:
                        videos.append({
                            "type": media.get("host", "external"),
                            "url": embed_url,
                            "embeddedVideoId": media.get("video_id") or media.get("external_id"),
                        })

            elif media_type == "model":
                sources = media.get("sources") or []
                for source in sources:
                    if source.get("url"):
                        models.append({
                            "url": source["url"],
                            "format": source.get("format"),
                            "mimeType": source.get("mime_type"),
                        })

    else:
        # Fallback: use images array from .js response
        for image in raw_product.get("images") or []:
            if isinstance(image, str):
                images.append(_clean_shopify_image_url(image))
            elif isinstance(image, dict) and image.get("src"):
                images.append(_clean_shopify_image_url(image["src"]))

    # Dedupe images
    seen = set()
    deduped_images = []
    for img in images:
        if img and img not in seen:
            seen.add(img)
            deduped_images.append(img)

    featured = deduped_images[0] if deduped_images else None

    return {
        "images": deduped_images,
        "videos": videos,
        "models": models,
        "featuredImage": featured,
    }


def _clean_shopify_image_url(url):
    """Remove Shopify image size suffixes like _100x100 for full-res."""
    if not url:
        return url
    # Remove _WxH or _Wx suffixes before the extension
    url = re.sub(r"_\d+x\d*\.(jpg|jpeg|png|webp|gif)", r".\1", url, flags=re.IGNORECASE)
    # Remove query params added by Shopify CDN sizing
    url = url.split("?")[0]
    return url


def extract_lazy_images_from_dom(soup):
    """
    Collect image URLs from lazy-load attributes (data-src, data-lazy,
    data-srcset) that browsers load after JS runs.
    Returns a deduped list of URLs.
    """
    urls = []
    attrs = ["data-src", "data-lazy", "data-lazy-src", "data-original"]

    for img in soup.find_all("img"):
        for attr in attrs:
            val = img.get(attr)
            if val and val.startswith("http"):
                urls.append(_clean_shopify_image_url(val))
                break
        # data-srcset — take the last (largest) entry
        srcset = img.get("data-srcset") or img.get("srcset")
        if srcset:
            parts = [p.strip() for p in srcset.split(",") if p.strip()]
            for part in reversed(parts):
                src_candidate = part.split(" ")[0]
                if src_candidate.startswith("http"):
                    urls.append(_clean_shopify_image_url(src_candidate))
                    break

    seen = set()
    result = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            result.append(u)
    return result


# ---------------------------------------------------------------------------
# Reviews & Ratings
# ---------------------------------------------------------------------------

def extract_reviews(soup, html, json_ld_blocks=None):
    """
    Multi-source review extraction.

    Sources (in priority order):
      1. JSON-LD AggregateRating
      2. Yotpo
      3. Okendo
      4. Judge.me
      5. Stamped.io
      6. Loox
      7. Generic DOM star patterns

    Returns:
        {
            "averageRating": float | None,
            "reviewCount": int | None,
            "source": str | None,
            "snippets": [str, ...],   # up to 5 review text snippets
            "breakdown": {            # star breakdown if available
                "5": int, "4": int, ...
            }
        }
    """
    html = html or ""
    result = {
        "averageRating": None,
        "reviewCount": None,
        "source": None,
        "snippets": [],
        "breakdown": {},
    }

    # ------------------------------------------------------------------
    # 1. JSON-LD AggregateRating
    # ------------------------------------------------------------------
    for block in json_ld_blocks or []:
        agg = _find_aggregate_rating(block)
        if agg:
            result["averageRating"] = agg.get("averageRating")
            result["reviewCount"] = agg.get("reviewCount")
            result["source"] = "json_ld"
            break

    # Also scan raw script tags if json_ld_blocks not provided
    if not result["averageRating"]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                agg = _find_aggregate_rating(data)
                if agg:
                    result["averageRating"] = agg.get("averageRating")
                    result["reviewCount"] = agg.get("reviewCount")
                    result["source"] = "json_ld"
                    break
            except Exception:
                continue

    # ------------------------------------------------------------------
    # 2. Yotpo
    # ------------------------------------------------------------------
    if not result["averageRating"]:
        _extract_yotpo(soup, html, result)

    # ------------------------------------------------------------------
    # 3. Okendo
    # ------------------------------------------------------------------
    if not result["averageRating"]:
        _extract_okendo(soup, html, result)

    # ------------------------------------------------------------------
    # 4. Judge.me
    # ------------------------------------------------------------------
    if not result["averageRating"]:
        _extract_judgeme(soup, html, result)

    # ------------------------------------------------------------------
    # 5. Stamped.io
    # ------------------------------------------------------------------
    if not result["averageRating"]:
        _extract_stamped(soup, html, result)

    # ------------------------------------------------------------------
    # 6. Loox
    # ------------------------------------------------------------------
    if not result["averageRating"]:
        _extract_loox(soup, html, result)

    # ------------------------------------------------------------------
    # 7. Generic DOM star patterns
    # ------------------------------------------------------------------
    if not result["averageRating"]:
        _extract_generic_stars(soup, html, result)

    # ------------------------------------------------------------------
    # Review text snippets (any source)
    # ------------------------------------------------------------------
    result["snippets"] = _extract_review_snippets(soup)

    # Clamp rating to 0-5
    if result["averageRating"] is not None:
        try:
            r = float(result["averageRating"])
            result["averageRating"] = round(min(5.0, max(0.0, r)), 1)
        except Exception:
            result["averageRating"] = None

    if result["reviewCount"] is not None:
        try:
            result["reviewCount"] = int(str(result["reviewCount"]).replace(",", "").strip())
        except Exception:
            result["reviewCount"] = None

    return result


def _find_aggregate_rating(data):
    """Recursively find AggregateRating in a JSON-LD block."""
    if not isinstance(data, dict):
        return None

    # Direct
    if data.get("@type") == "AggregateRating":
        rating = _parse_rating_value(data.get("ratingValue"))
        count = _parse_review_count(
            data.get("reviewCount") or data.get("ratingCount")
        )
        if rating:
            return {"averageRating": rating, "reviewCount": count}

    # Nested aggregateRating key
    agg = data.get("aggregateRating")
    if isinstance(agg, dict):
        rating = _parse_rating_value(agg.get("ratingValue"))
        count = _parse_review_count(
            agg.get("reviewCount") or agg.get("ratingCount")
        )
        if rating:
            return {"averageRating": rating, "reviewCount": count}

    # @graph
    for item in data.get("@graph", []):
        found = _find_aggregate_rating(item)
        if found:
            return found

    return None


def _parse_rating_value(value):
    if value is None:
        return None
    try:
        r = float(str(value).replace(",", "."))
        return r if 0 < r <= 5 else None
    except Exception:
        return None


def _parse_review_count(value):
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except Exception:
        return None


def _extract_yotpo(soup, html, result):
    """Extract ratings from Yotpo widgets."""
    # data-score / data-average-score attributes
    for el in soup.select("[data-score], [data-average-score], [data-product-score]"):
        score = (
            el.get("data-score")
            or el.get("data-average-score")
            or el.get("data-product-score")
        )
        r = _parse_rating_value(score)
        if r:
            result["averageRating"] = r
            result["source"] = "yotpo"
            break

    # Review count
    if result["averageRating"]:
        for sel in [
            "[data-reviews-count]",
            "[data-number-of-reviews]",
            ".yotpo-sum-reviews .based-on",
            ".yotpo-reviews-header .yotpo-sum-reviews",
        ]:
            el = soup.select_one(sel)
            if el:
                count_text = (
                    el.get("data-reviews-count")
                    or el.get("data-number-of-reviews")
                    or el.get_text()
                )
                count = _parse_review_count(
                    re.sub(r"[^\d]", "", count_text or "")
                )
                if count is not None:
                    result["reviewCount"] = count
                    break
        return

    # JS var yotpo_reviews_count
    m = re.search(r"yotpo_reviews_count\s*[=:]\s*['\"]?(\d+)['\"]?", html)
    if m:
        result["reviewCount"] = int(m.group(1))

    m = re.search(r"yotpo_avg_score\s*[=:]\s*['\"]?([\d.]+)['\"]?", html)
    if m:
        r = _parse_rating_value(m.group(1))
        if r:
            result["averageRating"] = r
            result["source"] = "yotpo"


def _extract_okendo(soup, html, result):
    """Extract ratings from Okendo widgets."""
    # data-oke-reviews-average-rating
    for el in soup.select(
        "[data-oke-reviews-average-rating], "
        "[data-oke-star-rating], "
        ".oke-sr-count, "
        "[class*='oke-sr']"
    ):
        score = (
            el.get("data-oke-reviews-average-rating")
            or el.get("data-oke-star-rating")
        )
        r = _parse_rating_value(score)
        if r:
            result["averageRating"] = r
            result["source"] = "okendo"
            break

    if not result["averageRating"]:
        m = re.search(r'"averageRating"\s*:\s*([\d.]+)', html)
        if m and "oke" in html.lower():
            r = _parse_rating_value(m.group(1))
            if r:
                result["averageRating"] = r
                result["source"] = "okendo"

    if result["source"] == "okendo":
        for el in soup.select("[data-oke-reviews-count], .oke-sr-count"):
            count_text = el.get("data-oke-reviews-count") or el.get_text()
            count = _parse_review_count(re.sub(r"[^\d]", "", count_text or ""))
            if count is not None:
                result["reviewCount"] = count
                break


def _extract_judgeme(soup, html, result):
    """Extract ratings from Judge.me widgets."""
    # jdgm-prev-badge data attributes
    badge = soup.select_one(
        ".jdgm-prev-badge, [class*='jdgm'], #judgeme_product_widget"
    )
    if badge:
        score = badge.get("data-average-rating")
        count = badge.get("data-number-of-reviews")
        r = _parse_rating_value(score)
        if r:
            result["averageRating"] = r
            result["reviewCount"] = _parse_review_count(count)
            result["source"] = "judgeme"
            return

    # JS JSON
    m = re.search(r'"average_rating"\s*:\s*([\d.]+)', html)
    n = re.search(r'"number_of_reviews"\s*:\s*(\d+)', html)
    if m and ("judgeme" in html.lower() or "judge.me" in html.lower()):
        r = _parse_rating_value(m.group(1))
        if r:
            result["averageRating"] = r
            result["source"] = "judgeme"
            if n:
                result["reviewCount"] = int(n.group(1))


def _extract_stamped(soup, html, result):
    """Extract ratings from Stamped.io widgets."""
    badge = soup.select_one(
        ".stamped-badge, [data-widget-type='star-reviews'], "
        "#stamped-main-widget, [class*='stamped']"
    )
    if badge:
        score = (
            badge.get("data-rating")
            or badge.get("data-average-rating")
        )
        count = (
            badge.get("data-count")
            or badge.get("data-total")
        )
        r = _parse_rating_value(score)
        if r:
            result["averageRating"] = r
            result["reviewCount"] = _parse_review_count(count)
            result["source"] = "stamped"
            return

    m = re.search(r'stamped.*?"rating"\s*:\s*([\d.]+)', html, re.DOTALL)
    if m:
        r = _parse_rating_value(m.group(1))
        if r:
            result["averageRating"] = r
            result["source"] = "stamped"


def _extract_loox(soup, html, result):
    """Extract ratings from Loox widgets."""
    loox = soup.select_one(".loox-rating, [class*='loox']")
    if loox:
        score = loox.get("data-rating") or loox.get("data-score")
        count = loox.get("data-count") or loox.get("data-reviews-count")
        r = _parse_rating_value(score)
        if r:
            result["averageRating"] = r
            result["reviewCount"] = _parse_review_count(count)
            result["source"] = "loox"
            return

    m = re.search(r'"loox".*?"rating"\s*:\s*([\d.]+)', html, re.DOTALL)
    if m:
        r = _parse_rating_value(m.group(1))
        if r:
            result["averageRating"] = r
            result["source"] = "loox"


def _extract_generic_stars(soup, html, result):
    """
    Generic DOM patterns for star ratings when no known app is detected.
    Handles: aria-label="4.5 out of 5", data-rating, itemprop="ratingValue",
    and common class patterns.
    """
    # itemprop="ratingValue"
    el = soup.find(attrs={"itemprop": "ratingValue"})
    if el:
        r = _parse_rating_value(el.get("content") or el.get_text())
        if r:
            result["averageRating"] = r
            result["source"] = "microdata"
            count_el = soup.find(attrs={"itemprop": "reviewCount"}) or \
                       soup.find(attrs={"itemprop": "ratingCount"})
            if count_el:
                result["reviewCount"] = _parse_review_count(
                    count_el.get("content") or count_el.get_text()
                )
            return

    # aria-label patterns: "Rated 4.5 out of 5" / "4.5 stars"
    for el in soup.find_all(attrs={"aria-label": True}):
        label = el["aria-label"].lower()
        m = re.search(r"(\d(?:\.\d)?)\s*(?:out\s*of\s*5|stars?|\/5)", label)
        if m:
            r = _parse_rating_value(m.group(1))
            if r:
                result["averageRating"] = r
                result["source"] = "aria_label"
                break

    # data-rating / data-score
    if not result["averageRating"]:
        for sel in [
            "[data-rating]", "[data-score]", "[data-average]",
            "[class*='star-rating']", "[class*='product-rating']",
            "[class*='review-rating']",
        ]:
            el = soup.select_one(sel)
            if el:
                score = (
                    el.get("data-rating")
                    or el.get("data-score")
                    or el.get("data-average")
                )
                r = _parse_rating_value(score)
                if r:
                    result["averageRating"] = r
                    result["source"] = "dom_data_attr"
                    break

    # Visible text patterns: "4.8 / 5" or "(312 reviews)"
    if not result["averageRating"]:
        m = re.search(r"\b([\d]\.\d)\s*(?:\/\s*5|out of 5|stars?)", html, re.I)
        if m:
            r = _parse_rating_value(m.group(1))
            if r:
                result["averageRating"] = r
                result["source"] = "text_pattern"

    if not result["reviewCount"]:
        m = re.search(r"\(?([\d,]+)\s*(?:reviews?|ratings?|customers?)\)?", html, re.I)
        if m:
            result["reviewCount"] = _parse_review_count(m.group(1))


def _extract_review_snippets(soup, limit=5):
    """Extract short review text snippets from the page."""
    snippets = []
    seen = set()

    selectors = [
        ".yotpo-review-content",
        ".spr-review-content-body",
        ".review-content",
        ".review-text",
        ".review__text",
        "[class*='review-body']",
        "[class*='review-content']",
        ".jdgm-rev__body",
        ".oke-review-body",
        ".stamped-review-content-body",
    ]

    for sel in selectors:
        for el in soup.select(sel):
            text = clean_text(el.get_text(" ", strip=True))
            if text and len(text) >= 20 and len(text) <= 500:
                key = text.lower()[:80]
                if key not in seen:
                    seen.add(key)
                    snippets.append(text)
                    if len(snippets) >= limit:
                        return snippets

    return snippets


# ---------------------------------------------------------------------------
# Badges extraction
# ---------------------------------------------------------------------------

def extract_badges(soup, product_data=None):
    """
    Extract product badges and labels from DOM and product data.

    Returns a list of normalized badge strings, e.g.:
    ["Sale", "New", "Sold Out", "Best Seller", "Limited Edition"]
    """
    badges = set()
    product_data = product_data or {}

    # --- From product data ---
    availability = product_data.get("availability") or {}
    if availability.get("inStock") is False:
        badges.add("Sold Out")

    price = product_data.get("price") or {}
    if price.get("isOnSale") and price.get("compareAt"):
        badges.add("Sale")

    # --- From DOM badge elements ---
    badge_selectors = [
        ".badge",
        ".product-badge",
        ".product__badge",
        ".product-label",
        ".product__label",
        "[class*='badge']",
        "[class*='label--']",
        "[class*='product-label']",
        "[class*='product-tag']",
        ".sash",
        ".flag",
        ".ribbon",
    ]

    badge_text_map = {
        "sale": "Sale",
        "on sale": "Sale",
        "% off": "Sale",
        "discount": "Sale",
        "new": "New",
        "new arrival": "New Arrival",
        "sold out": "Sold Out",
        "out of stock": "Sold Out",
        "best seller": "Best Seller",
        "bestseller": "Best Seller",
        "popular": "Popular",
        "limited": "Limited Edition",
        "limited edition": "Limited Edition",
        "coming soon": "Coming Soon",
        "pre-order": "Pre-Order",
        "preorder": "Pre-Order",
        "low stock": "Low Stock",
        "almost gone": "Low Stock",
        "free shipping": "Free Shipping",
        "exclusive": "Exclusive",
        "featured": "Featured",
        "hot": "Hot",
        "trending": "Trending",
    }

    for sel in badge_selectors:
        for el in soup.select(sel):
            text = clean_text(el.get_text(" ", strip=True))
            if not text or len(text) > 60:
                continue
            text_l = text.lower()
            matched = False
            for pattern, label in badge_text_map.items():
                if pattern in text_l:
                    badges.add(label)
                    matched = True
                    break
            if not matched and 2 <= len(text) <= 30:
                # Add verbatim if it looks like a short label
                badges.add(text.title())

    # --- From product tags ---
    tags = product_data.get("tags") or []
    tag_badge_map = {
        "sale": "Sale",
        "new": "New",
        "best-seller": "Best Seller",
        "bestseller": "Best Seller",
        "featured": "Featured",
        "limited-edition": "Limited Edition",
        "coming-soon": "Coming Soon",
        "pre-order": "Pre-Order",
        "free-shipping": "Free Shipping",
    }
    for tag in tags:
        tag_l = (tag or "").lower().strip()
        if tag_l in tag_badge_map:
            badges.add(tag_badge_map[tag_l])

    return sorted(badges)


# ---------------------------------------------------------------------------
# Swatches / color options
# ---------------------------------------------------------------------------

def extract_swatches_from_dom(soup, options=None):
    """
    Extract color/swatch data from the product page DOM.
    Returns list of {"label": str, "value": str, "imageUrl": str|None, "colorHex": str|None}.
    """
    swatches = []
    seen_labels = set()
    options = options or []

    # Determine if there is a color option
    color_option_values = set()
    for opt in options:
        opt_name = (opt.get("name") or "").lower()
        if any(x in opt_name for x in ["color", "colour", "shade", "finish"]):
            for v in opt.get("values") or []:
                if v:
                    color_option_values.add(v.lower())

    # Swatch selectors
    swatch_selectors = [
        ".swatch__element",
        ".color-swatch",
        ".product__color-swatch",
        "[class*='color-swatch']",
        "[class*='colour-swatch']",
        "[data-swatch]",
        "[data-color]",
        ".variant-swatch",
        ".product-form__color-swatch",
        "label[data-value]",
        ".swatch",
        "[class*='swatch--']",
    ]

    for sel in swatch_selectors:
        for el in soup.select(sel):
            label = (
                el.get("data-swatch")
                or el.get("data-color")
                or el.get("data-value")
                or el.get("title")
                or el.get("aria-label")
                or clean_text(el.get_text(" ", strip=True))
            )
            label = clean_text(label)
            if not label or len(label) > 50:
                continue

            key = label.lower()
            if key in seen_labels:
                continue
            seen_labels.add(key)

            # Image URL from background-image style or data-image
            img_url = el.get("data-image") or el.get("data-src")
            style = el.get("style") or ""
            bg_match = re.search(r"background-image\s*:\s*url\(['\"]?([^'\")\s]+)['\"]?\)", style)
            if bg_match:
                img_url = bg_match.group(1)

            # Color hex from style
            color_hex = None
            hex_match = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6}|rgb[^;]+)", style)
            if hex_match:
                color_hex = hex_match.group(1)

            swatches.append({
                "label": label,
                "value": label,
                "imageUrl": img_url,
                "colorHex": color_hex,
            })

        if swatches:
            break  # Stop after first successful selector set

    return swatches[:30]


# ---------------------------------------------------------------------------
# Related products (DOM fallback)
# ---------------------------------------------------------------------------

def extract_related_products_from_dom(soup, url, currency="USD"):
    """
    DOM fallback for related/recommended products.
    Looks for common "You may also like", "Related products", etc. sections.
    Returns list of simplified product dicts.
    """
    products = []
    seen_urls = set()

    section_selectors = [
        "[data-section-type='product-recommendations']",
        ".product-recommendations",
        ".recently-viewed",
        "[class*='related-products']",
        "[class*='recommended-products']",
        "[class*='you-may-also-like']",
        "[class*='customers-also-bought']",
        "#recommendations",
        ".upsell",
        "[class*='upsell']",
    ]

    base = get_base_url(url)

    for sel in section_selectors:
        section = soup.select_one(sel)
        if not section:
            continue

        cards = section.select(
            ".product-card, .grid__item, .product-item, "
            "[class*='product-card'], [class*='product-item']"
        )

        for card in cards[:12]:
            link = card.select_one("a[href]")
            href = link["href"] if link else None
            if not href:
                continue
            product_url = urljoin(base, href)
            if product_url in seen_urls:
                continue
            if "/products/" not in product_url:
                continue
            seen_urls.add(product_url)

            title_el = card.select_one(
                ".product-card__title, .product__title, h2, h3, "
                "[class*='product-title'], [class*='card-title']"
            )
            title = clean_text(title_el.get_text()) if title_el else None

            img_el = card.select_one("img")
            img_url = None
            if img_el:
                img_url = (
                    img_el.get("src")
                    or img_el.get("data-src")
                    or img_el.get("data-lazy")
                )
                if img_url:
                    img_url = _clean_shopify_image_url(img_url)

            price_el = card.select_one(
                ".price, .product-price, [class*='price']"
            )
            price_text = clean_text(price_el.get_text()) if price_el else None
            price_value = None
            if price_text:
                price_match = re.search(r"[\d,]+(?:\.\d{1,2})?", price_text.replace(",", ""))
                if price_match:
                    try:
                        price_value = float(price_match.group())
                        if price_value == int(price_value):
                            price_value = int(price_value)
                    except Exception:
                        pass

            products.append({
                "title": title,
                "url": product_url,
                "imageUrl": img_url,
                "price": {
                    "currency": currency,
                    "current": price_value,
                    "priceTextRaw": price_text,
                },
            })

        if products:
            break

    return products[:12]


def _normalize_shopify_cents_price(value):
    """
    Normalize a price value from Shopify collection/recommendations JSON APIs,
    which return prices as integer cents (e.g. 56000 = PKR 560.00).
    Divides by 100 and returns int when whole, float otherwise.
    """
    if value is None:
        return None
    try:
        number = float(str(value).strip())
        if number == 0:
            return None  # Zero-price guard
        result = number / 100
        return int(result) if result == int(result) else round(result, 2)
    except Exception:
        return None


def normalize_related_products(raw_products, currency="USD"):
    """
    Normalize related products from Shopify Recommendations API response.
    NOTE: This API returns variant prices as integer cents (e.g. 56000 = 560 PKR),
    unlike the product .js/.json endpoints which use major units.
    """
    products = []
    for p in raw_products or []:
        handle = p.get("handle")
        variants = p.get("variants") or []
        prices = [
            _normalize_shopify_cents_price(v.get("price"))
            for v in variants
            if v.get("price") is not None
        ]
        compare_prices = [
            _normalize_shopify_cents_price(v.get("compare_at_price"))
            for v in variants
            if v.get("compare_at_price") is not None
        ]
        min_price = min(p for p in prices if p is not None) if prices else None
        compare_at = min(p for p in compare_prices if p is not None) if compare_prices else None

        # Availability: check available field, fallback to inventory_quantity
        available = False
        for v in variants:
            v_available = v.get("available")
            if v_available is True:
                available = True
                break
            if v_available is None:
                qty = v.get("inventory_quantity")
                policy = (v.get("inventory_policy") or "deny").lower()
                if qty is None or qty > 0 or policy == "continue":
                    available = True
                    break

        images = p.get("images") or []
        image_url = None
        if images:
            first = images[0]
            image_url = _clean_shopify_image_url(
                first.get("src") if isinstance(first, dict) else first
            )

        products.append({
            "title": p.get("title"),
            "handle": handle,
            "url": f"/products/{handle}" if handle else None,
            "imageUrl": image_url,
            "price": {
                "currency": currency,
                "current": min_price,
                "compareAt": compare_at,
                "isOnSale": bool(compare_at and min_price and compare_at > min_price),
            },
            "available": available,
        })

    return products[:12]


# ---------------------------------------------------------------------------
# Description sections
# ---------------------------------------------------------------------------

def extract_faqs_from_dom(soup):
    """
    Extract FAQ pairs. Sources: dl/dt/dd, accordion entries with '?',
    heading+paragraph patterns.
    """
    faqs = []
    seen_questions = set()

    def add_faq(q, a):
        q = clean_text(q)
        a = clean_text(a)
        if not q or not a or len(a) < 20:
            return
        key = q.lower()
        if key in seen_questions:
            return
        seen_questions.add(key)
        faqs.append({"question": q, "answer": a[:1500]})

    # dl > dt + dd
    for dl in soup.select("dl"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            add_faq(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))

    # Accordion entries with "?"
    for entry in extract_accordions(soup):
        title = entry.get("title", "")
        if "?" in title or detect_section_type(title) == "faqs":
            content = entry.get("content") or ""
            items = entry.get("items") or []
            answer = content or " ".join(items)
            add_faq(title, answer)

    # Headings with "?" followed by paragraphs
    for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
        q_text = clean_text(heading.get_text(" ", strip=True))
        if not q_text or "?" not in q_text:
            continue
        answer_parts = []
        sibling = heading.find_next_sibling()
        while sibling:
            tag = getattr(sibling, "name", None)
            if tag in ["h2", "h3", "h4"]:
                break
            text = clean_text(sibling.get_text(" ", strip=True))
            if text and len(text) >= 20:
                answer_parts.append(text)
            sibling = sibling.find_next_sibling()
        if answer_parts:
            add_faq(q_text, " ".join(answer_parts))

    return faqs[:20]


def _extract_table_sections(soup, sections):
    """
    Extract structured content from HTML tables inside product descriptions.

    Handles two patterns:
      Pattern A — Section-labeled table: a <table> preceded by a heading whose
                  text maps to a section type (e.g. "Ingredients & Nutrition").
                  First column values become items for that section.

      Pattern B — Two-column key/value table: <tr><td>Ingredient</td><td>Chicken</td></tr>
                  Header row is used to detect section type; first-column cell
                  values are collected as items.
    """
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        # Detect section type from: table caption, preceding heading, or header row
        section_type = None

        caption = table.find("caption")
        if caption:
            section_type = detect_section_type(caption.get_text(" ", strip=True))

        if not section_type:
            # Look at preceding sibling heading
            prev = table.find_previous_sibling(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "p"])
            if prev:
                section_type = detect_section_type(prev.get_text(" ", strip=True))

        if not section_type:
            # Look at the parent container heading
            parent = table.parent
            if parent:
                parent_heading = parent.find(["h1", "h2", "h3", "h4", "strong", "b"])
                if parent_heading:
                    section_type = detect_section_type(parent_heading.get_text(" ", strip=True))

        # Parse header row to detect column meanings
        header_row = rows[0]
        header_cells = [
            clean_text(th.get_text(" ", strip=True))
            for th in header_row.find_all(["th", "td"])
        ]

        if not section_type and header_cells:
            # Try to detect from header: "Ingredient" / "Nutritional Benefit" etc.
            for hdr in header_cells:
                section_type = detect_section_type(hdr or "")
                if section_type:
                    break

        if not section_type:
            continue

        # Determine which columns to extract (first non-header column)
        data_rows = rows[1:] if header_cells and any(
            th.name == "th" for th in header_row.find_all(["th", "td"])
        ) else rows

        for row in data_rows:
            cells = [clean_text(td.get_text(" ", strip=True)) for td in row.find_all(["td", "th"])]
            if not cells:
                continue

            # For ingredient tables: first column is the ingredient name
            first_cell = cells[0]
            if first_cell and first_cell not in (header_cells or []):
                val = clean_section_value(first_cell, section_type)
                if val and val not in sections[section_type]:
                    sections[section_type].append(val)

            # For spec tables: "key: value" style — combine first two cells
            if len(cells) >= 2 and section_type == "specifications":
                key = cells[0]
                value = cells[1]
                if key and value and key not in (header_cells or []):
                    combined = f"{key}: {value}"
                    val = clean_section_value(combined, section_type)
                    if val and val not in sections[section_type]:
                        sections[section_type].append(val)


def _make_product_soup(soup):
    """
    Return a BeautifulSoup object with navigation/chrome nodes removed so that
    section extraction only sees product content, not menus or footers.
    """
    from copy import copy as _copy
    product_soup = BeautifulSoup(str(soup), "lxml")
    noise_selectors = [
        "nav", "header", "footer",
        "[class*='nav']", "[class*='navigation']", "[class*='menu']",
        "[class*='drawer']", "[class*='mega']", "[class*='sidebar']",
        "[class*='breadcrumb']", "[class*='collection-list']",
        "[class*='site-nav']", "[class*='main-nav']",
        "[id*='nav']", "[id*='menu']", "[id*='drawer']", "[id*='sidebar']",
        "script", "style",
    ]
    for sel in noise_selectors:
        try:
            for el in product_soup.select(sel):
                el.decompose()
        except Exception:
            pass
    return product_soup


def extract_product_sections_from_dom(soup):
    """
    Multi-strategy extraction of product description sections.

    Strategy A: Shared accordion extractor (details/summary, Bootstrap,
                Shopify collapsibles, tab panels, Elementor, generic).
    Strategy B: RTE blocks with bold/strong headings (common in Shopify themes
                where sections are separated by <strong>Title:</strong> + <p>).
    Strategy C: Legacy direct DOM selector scan.

    Navigation, menus, headers, footers and sidebars are stripped first so
    that collection/category links are never mistaken for product benefits.
    """
    soup = _make_product_soup(soup)
    sections = {
        "ingredients": [],
        "usage": [],
        "benefits": [],
        "features": [],
        "specifications": [],
        "faqs": [],
    }

    # --- Strategy A: Accordion extractor ---
    accordion_entries = extract_accordions(soup)
    mapped = map_accordion_entries(accordion_entries)
    accordion_sections = build_description_sections(mapped)
    for key in sections:
        sections[key].extend(accordion_sections.get(key, []))

    # --- Strategy B: Table-based section extraction ---
    # Handles ingredient/spec tables like:
    # <table><tr><th>Ingredient</th><th>Benefit</th></tr>
    #        <tr><td>Chicken</td><td>High-quality protein...</td></tr></table>
    _extract_table_sections(soup, sections)

    # --- Strategy C: RTE bold-heading pattern ---
    # Matches: <strong>Benefits:</strong> followed by <ul> or <p> siblings
    rte_containers = soup.select(
        ".rte, .product__description, .product-description, "
        ".product-single__description, [class*='product-description']"
    )
    for container in rte_containers:
        _extract_rte_bold_sections(container, sections)

    # --- Strategy C: Legacy DOM selector scan ---
    selectors = [
        ".product__description",
        ".product-description",
        ".product-single__description",
        ".product-form__description",
        ".rte",
        "[class*='product-description']",
        "[class*='tab-content']",
    ]
    for block in soup.select(",".join(selectors)):
        heading = extract_heading_text(block)
        section_type = detect_section_type(heading) if heading else None
        if not section_type:
            block_text = clean_text(block.get_text(" ", strip=True))
            if block_text:
                section_type = detect_section_type(block_text[:120])
        if not section_type:
            continue
        for value in extract_list_or_text(block, section_type):
            value = clean_section_value(value, section_type)
            if value and value not in sections[section_type]:
                sections[section_type].append(value)

    # --- FAQs ---
    sections["faqs"] = extract_faqs_from_dom(soup)

    # --- Finalize ---
    sections["ingredients"] = clean_ingredients(sections["ingredients"])
    sections["benefits"] = clean_benefits(sections["benefits"])
    sections["usage"] = clean_usage(sections["usage"])
    sections["specifications"] = clean_specifications(sections["specifications"])
    sections["features"] = dedupe_list(sections["features"])

    return sections


def _extract_rte_bold_sections(container, sections):
    """
    Handle RTE blocks where section headings are <strong> or <b> tags
    followed immediately by content in the same or next element.

    Example:
        <p><strong>Benefits:</strong> Hydrates, nourishes, smooths.</p>
        <p><strong>How to Use:</strong></p>
        <ul><li>Apply to clean skin...</li></ul>
    """
    clone = BeautifulSoup(str(container), "lxml")
    current_section = None
    current_items = []

    def flush():
        nonlocal current_section, current_items
        if current_section and current_items:
            sections[current_section].extend(current_items)
        current_section = None
        current_items = []

    for el in clone.find_all(["p", "ul", "ol", "h2", "h3", "h4", "strong", "b"]):
        tag = el.name

        if tag in ("h2", "h3", "h4"):
            flush()
            heading_text = clean_text(el.get_text(" ", strip=True))
            current_section = detect_section_type(heading_text)
            continue

        if tag in ("strong", "b"):
            text = clean_text(el.get_text(" ", strip=True))
            if not text:
                continue
            section_type = detect_section_type(text)
            if section_type:
                flush()
                current_section = section_type
                # Check for inline content after the bold tag
                parent = el.parent
                if parent:
                    parent_text = clean_text(parent.get_text(" ", strip=True))
                    # Remove the heading from the parent text
                    content = parent_text.replace(text, "").strip(":–— ")
                    if content and len(content) > 3:
                        val = clean_section_value(content, current_section)
                        if val:
                            current_items.append(val)
            continue

        if tag == "p":
            text = clean_text(el.get_text(" ", strip=True))
            if not text:
                continue
            # Check if this paragraph starts with a bold heading
            bold = el.find(["strong", "b"])
            if bold:
                bold_text = clean_text(bold.get_text(" ", strip=True))
                section_type = detect_section_type(bold_text)
                if section_type:
                    flush()
                    current_section = section_type
                    # Inline content after bold
                    remaining = text.replace(bold_text, "").strip(":–— ")
                    if remaining and len(remaining) > 3:
                        val = clean_section_value(remaining, current_section)
                        if val:
                            current_items.append(val)
                    continue
            # Regular paragraph: add to active section
            if current_section:
                val = clean_section_value(text, current_section)
                if val:
                    current_items.append(val)

        elif tag in ("ul", "ol"):
            if current_section:
                for li in el.find_all("li"):
                    val = clean_section_value(
                        li.get_text(" ", strip=True), current_section
                    )
                    if val:
                        current_items.append(val)

    flush()


def infer_ingredients_from_description_text(text):
    text = clean_text(text)
    if not text:
        return []

    results = []
    bad_phrases = [
        "comfortable", "well-cared", "finish", "beautiful",
        "all day", "look", "shape", "strong option", "supporting", "before purchase",
    ]
    patterns = [
        r"active ingredients?\s+(?:such as|include|includes|including)\s+([^\.]+)",
        r"ingredients?\s+(?:such as|include|includes|including)\s+([^\.]+)",
        r"combines\s+(?:powerful\s+)?active ingredients?\s+(?:such as|including)?\s*([^\.]+)",
        r"contains\s+([^\.]*(?:vitamin|peptide|aloe|acid|oil|extract|butter|wax|glycerin|panthenol|biotin)[^\.]*)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            match = clean_section_value(match, "ingredients")
            if not match or len(match) > 220:
                continue
            match = re.sub(r",?\s*supporting.*$", "", match, flags=re.IGNORECASE)
            match = re.sub(r",?\s*helping.*$", "", match, flags=re.IGNORECASE)
            match = re.sub(
                r",?\s*to\s+(nourish|hydrate|moisturize|protect|strengthen|soften|make|support).*?$",
                "", match, flags=re.IGNORECASE,
            )
            for item in re.split(r",| and ", match):
                item = clean_section_value(item, "ingredients")
                if not item or len(item) > 60:
                    continue
                if any(x in item.lower() for x in bad_phrases):
                    continue
                results.append(item)

    return dedupe_list(results)


def infer_sections_from_description_text(description):
    sections = {
        "ingredients": [], "usage": [], "benefits": [],
        "features": [], "specifications": [], "faqs": [],
    }
    if not isinstance(description, dict):
        return sections

    text = clean_text(description.get("text"))
    bullets = description.get("bullets") or []
    headings = description.get("headings") or []

    if text:
        sections["ingredients"] = infer_ingredients_from_description_text(text)
        for pattern in [
            r"(?:for best results|how to apply|how to use|directions?)[:,]?\s*([^\.]{10,200})",
            r"(?:step \d+)\s*[:\-]\s*([^\.]{10,200})",
        ]:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                val = clean_section_value(match, "usage")
                if val:
                    sections["usage"].append(val)

        for pattern in [
            r"(?:key benefits include|benefits include|benefits are)\s*([^\.]+)",
            r"(?:helps to|helps)\s+([^\.]{10,120})",
        ]:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                for part in split_text_items(match):
                    sections["benefits"].append(part)

    active_section = None
    for item in (headings + bullets):
        item_clean = clean_text(item)
        if not item_clean:
            continue
        inferred = detect_section_type(item_clean)
        if inferred:
            active_section = inferred
            continue
        if active_section:
            val = clean_section_value(item_clean, active_section)
            if val:
                sections[active_section].append(val)

    sections["ingredients"] = dedupe_list(sections["ingredients"])
    sections["usage"] = clean_usage(sections["usage"])
    sections["benefits"] = clean_benefits(sections["benefits"])
    sections["features"] = dedupe_list(sections["features"])
    sections["specifications"] = clean_specifications(sections["specifications"])
    return sections


def merge_description_sections(description, extra_sections):
    description = description or {}
    for key in ["ingredients", "usage", "benefits", "features", "specifications", "faqs"]:
        existing = description.get(key, []) or []
        incoming = extra_sections.get(key, []) or []
        if not isinstance(existing, list):
            existing = [existing]
        combined = existing + incoming
        if key == "ingredients":
            description[key] = clean_ingredients(combined)
        elif key == "benefits":
            description[key] = clean_benefits(combined)
        elif key == "usage":
            description[key] = clean_usage(combined)
        elif key == "specifications":
            description[key] = clean_specifications(combined)
        elif key == "faqs":
            seen_q = set()
            clean_faqs = []
            for faq in combined:
                if not isinstance(faq, dict):
                    continue
                q = (faq.get("question") or "").lower().strip()
                if q and q not in seen_q:
                    seen_q.add(q)
                    clean_faqs.append(faq)
            description[key] = clean_faqs
        else:
            description[key] = dedupe_list(combined)
    return description


# ---------------------------------------------------------------------------
# Variant normalization
# ---------------------------------------------------------------------------

def get_available_variants(variants):
    return [v for v in variants or [] if v.get("available") is True]


def get_price_list(variants, key="price"):
    return [
        p for p in (normalize_shopify_price(v.get(key)) for v in variants or [])
        if p is not None
    ]


def normalize_variants_from_shopify(raw_variants):
    variants = []
    for variant in raw_variants or []:
        price = normalize_shopify_price(variant.get("price"))
        compare_at = normalize_shopify_price(variant.get("compare_at_price"))
        on_sale = bool(compare_at and price and compare_at > price)

        # The .js endpoint provides `available` directly (bool).
        # The .json endpoint does NOT — compute it from inventory fields instead.
        available = variant.get("available")
        if available is None:
            inv_qty = variant.get("inventory_quantity")
            inv_policy = (variant.get("inventory_policy") or "deny").lower()
            inv_mgmt = variant.get("inventory_management")
            if inv_mgmt is None:
                # No inventory tracking → always available
                available = True
            elif inv_qty is not None:
                available = inv_qty > 0 or inv_policy == "continue"
            else:
                # inventory_management set but quantity not publicly exposed
                # → can't determine stock, assume available
                available = True

        variants.append({
            "id": variant.get("id"),
            "title": clean_empty(variant.get("title")),
            "option1": clean_empty(variant.get("option1")),
            "option2": clean_empty(variant.get("option2")),
            "option3": clean_empty(variant.get("option3")),
            "sku": clean_empty(variant.get("sku")),
            "barcode": clean_empty(variant.get("barcode")),
            "available": available,
            "inventoryPolicy": variant.get("inventory_policy"),
            "inventoryQuantity": variant.get("inventory_quantity"),
            "price": price,
            "compareAtPrice": compare_at,
            "isOnSale": on_sale,
            "weight": variant.get("weight"),
            "weightUnit": variant.get("weight_unit"),
            "featuredImage": variant.get("featured_image"),
            "requiresShipping": variant.get("requires_shipping"),
            "taxable": variant.get("taxable"),
        })
    return variants


def normalize_options(raw_options):
    cleaned = []
    for option in raw_options or []:
        name = clean_empty(option.get("name"))
        values = [v for v in (option.get("values") or []) if clean_empty(v)]
        if not name:
            continue
        if name.lower() == "title" and (not values or values == ["Default Title"]):
            continue
        cleaned.append({
            "name": name,
            "position": option.get("position"),
            "values": values,
        })
    return cleaned


def build_variant_availability_map(variants, options):
    """
    Build a map of option-value → availability.
    Example: {"Color/Red": True, "Size/M": False}
    Useful for UI to show which combinations are in stock.
    """
    if not variants or not options:
        return {}

    option_names = [opt.get("name") for opt in options]
    availability_map = {}

    for variant in variants:
        available = variant.get("available", False)
        for i, opt_name in enumerate(option_names):
            opt_key = f"option{i + 1}"
            value = variant.get(opt_key)
            if value:
                key = f"{opt_name}/{value}"
                # Mark as available if ANY variant with this option is available
                if key not in availability_map:
                    availability_map[key] = available
                else:
                    availability_map[key] = availability_map[key] or available

    return availability_map


# ---------------------------------------------------------------------------
# Image normalization
# ---------------------------------------------------------------------------

def normalize_images_from_shopify(raw_product):
    images = raw_product.get("images") or []
    seen = set()
    final = []
    for image in images:
        src = image.get("src") if isinstance(image, dict) else image
        src = _clean_shopify_image_url(src)
        if src and src not in seen:
            seen.add(src)
            final.append(src)
    return final


# ---------------------------------------------------------------------------
# Category / vendor helpers
# ---------------------------------------------------------------------------

# (category, productType) inference rules — ordered from most to least specific
_CATEGORY_RULES = [
    # ── Footwear ─────────────────────────────────────────────────────────────
    (r"\bsneaker[s]?\b",                    "Footwear",   "Sneakers"),
    (r"\btrainer[s]?\b",                    "Footwear",   "Trainers"),
    (r"\brunner[s]?\b|\brunning\s*shoe",    "Footwear",   "Running Shoes"),
    (r"\bloafer[s]?\b",                     "Footwear",   "Loafers"),
    (r"\bboat\s*shoe",                      "Footwear",   "Boat Shoes"),
    (r"\boxing\s*shoe|\bcleats?\b",         "Footwear",   "Athletic Shoes"),
    (r"\bsandal[s]?\b",                     "Footwear",   "Sandals"),
    (r"\bslide[s]?\b|\bflip.?flop",        "Footwear",   "Slides"),
    (r"\bslipper[s]?\b",                    "Footwear",   "Slippers"),
    (r"\bboot[s]?\b|\bchukka\b",           "Footwear",   "Boots"),
    (r"\bflat[s]?\b|\bmoccasin",           "Footwear",   "Flats"),
    (r"\boxford[s]?\b|\bderby\b|\bbrogues?\b", "Footwear", "Dress Shoes"),
    (r"\bshoe[s]?\b|\bfootwear\b",         "Footwear",   "Shoes"),
    # ── Tops ─────────────────────────────────────────────────────────────────
    (r"\bt[\-\s]?shirt[s]?\b|\btee[s]?\b", "Clothing",   "T-Shirt"),
    (r"\btank\s*top[s]?\b",                "Clothing",   "Tank Top"),
    (r"\bhoodie[s]?\b",                    "Clothing",   "Hoodie"),
    (r"\bsweatshirt[s]?\b",               "Clothing",   "Sweatshirt"),
    (r"\bpullover[s]?\b",                  "Clothing",   "Pullover"),
    (r"\bjumper[s]?\b|\bknitwear\b",       "Clothing",   "Jumper"),
    (r"\bsweater[s]?\b|\bcardigan[s]?\b",  "Clothing",   "Sweater"),
    (r"\bhenley[s]?\b",                    "Clothing",   "Henley"),
    (r"\bpolo[s]?\b|\bpolo\s*shirt",       "Clothing",   "Polo Shirt"),
    (r"\bblouse[s]?\b",                    "Clothing",   "Blouse"),
    (r"\bcrop\s*top[s]?\b",               "Clothing",   "Crop Top"),
    # ── Bottoms ──────────────────────────────────────────────────────────────
    (r"\bsweatpant[s]?\b|\bjogger[s]?\b",  "Clothing",   "Sweatpants"),
    (r"\blegging[s]?\b|\btight[s]?\b",     "Clothing",   "Leggings"),
    (r"\bpant[s]?\b|\btrousse?r[s]?\b",   "Clothing",   "Pants"),
    (r"\bjean[s]?\b|\bdenim\b",            "Clothing",   "Jeans"),
    (r"\bshort[s]?\b",                     "Clothing",   "Shorts"),
    (r"\bskirt[s]?\b",                     "Clothing",   "Skirt"),
    # ── Dresses ──────────────────────────────────────────────────────────────
    (r"\bdress(?:es)?\b|\bjumpsuit[s]?\b|\boverall[s]?\b", "Clothing", "Dress"),
    (r"\bromper[s]?\b",                    "Clothing",   "Romper"),
    # ── Outerwear ────────────────────────────────────────────────────────────
    (r"\bwindrunner\b|\bwindbreaker\b",    "Clothing",   "Windbreaker"),
    (r"\bjacket[s]?\b",                    "Clothing",   "Jacket"),
    (r"\bvest[s]?\b|\bgilet\b",           "Clothing",   "Vest"),
    (r"\bcoat[s]?\b|\bparka[s]?\b|\banorak\b", "Clothing", "Coat"),
    # ── Underwear / Intimates ─────────────────────────────────────────────────
    (r"\bbox(?:er[s]?\b|\b)",              "Clothing",   "Boxers"),
    (r"\bbrief[s]?\b|\bunderwear\b",       "Clothing",   "Underwear"),
    (r"\bbra[s]?\b|\bsports\s*bra\b",     "Clothing",   "Bras"),
    # ── Socks ────────────────────────────────────────────────────────────────
    (r"\bsock[s]?\b",                      "Accessories","Socks"),
    # ── Bags & Accessories ───────────────────────────────────────────────────
    (r"\bbackpack[s]?\b",                  "Accessories","Backpack"),
    (r"\btote\s*bag[s]?\b",               "Accessories","Tote Bag"),
    (r"\bhandbag[s]?\b|\bpurse[s]?\b",    "Accessories","Handbag"),
    (r"\bwallet[s]?\b",                    "Accessories","Wallet"),
    (r"\bhat[s]?\b|\bcap[s]?\b|\bbeanie[s]?\b", "Accessories", "Headwear"),
    (r"\bglove[s]?\b|\bmitten[s]?\b",     "Accessories","Gloves"),
    (r"\bbelt[s]?\b",                      "Accessories","Belt"),
    (r"\bscarf\b|\bscarves\b",            "Accessories","Scarf"),
    # ── Lip ──────────────────────────────────────────────────────────────────
    (r"\blip\s*tint\b",           "Lip Makeup",    "Lip Tint"),
    (r"\blip\s*gloss\b",          "Lip Makeup",    "Lip Gloss"),
    (r"\blip\s*balm\b",           "Lip Makeup",    "Lip Balm"),
    (r"\blip\s*liner\b",          "Lip Makeup",    "Lip Liner"),
    (r"\blipstick\b",             "Lip Makeup",    "Lipstick"),
    (r"\blit\s*tint\b",           "Lip Makeup",    "Lip Tint"),
    # Eye
    (r"\bmascara\b",              "Eye Makeup",    "Mascara"),
    (r"\beyeshadow\b|eye\s*shadow","Eye Makeup",   "Eyeshadow"),
    (r"\beyeliner\b|eye\s*liner", "Eye Makeup",    "Eyeliner"),
    (r"\bkajal\b|\bkohl\b",       "Eye Makeup",    "Kajal"),
    (r"\beyebrow\b|brow\s*gel",   "Eye Makeup",    "Eyebrow"),
    # Face makeup
    (r"\bfoundation\b",           "Face Makeup",   "Foundation"),
    (r"\bconcealer\b",            "Face Makeup",   "Concealer"),
    (r"\bblush\b",                "Face Makeup",   "Blush"),
    (r"\bbronzer\b",              "Face Makeup",   "Bronzer"),
    (r"\bhighlighter\b",          "Face Makeup",   "Highlighter"),
    (r"\bbb\s*cream\b|\bcc\s*cream\b", "Face Makeup", "BB/CC Cream"),
    (r"\bsetting\s*powder\b|\bface\s*powder\b", "Face Makeup", "Face Powder"),
    # Hair
    (r"\bconditioner\b",          "Hair Care",     "Conditioner"),
    (r"\bshampoo\b",              "Hair Care",     "Shampoo"),
    (r"\bhair\s*mask\b",          "Hair Care",     "Hair Mask"),
    (r"\bhair\s*serum\b",         "Hair Care",     "Hair Serum"),
    (r"\bhair\s*oil\b",           "Hair Care",     "Hair Oil"),
    (r"\bhair\s*spray\b",         "Hair Care",     "Hair Spray"),
    (r"\bhair\s*color\b|\bhair\s*dye\b|\bhair\s*colour\b", "Hair Care", "Hair Color"),
    (r"\bhair\s*treatment\b|\bhair\s*therapy\b", "Hair Care", "Hair Treatment"),
    (r"\bleave.in\b",             "Hair Care",     "Leave-In Treatment"),
    # Skin
    (r"\bface\s*wash\b|\bfacial\s*cleanser\b|\bcleanser\b", "Skincare", "Cleanser"),
    (r"\bface\s*toner\b|\btoner\b","Skincare",     "Toner"),
    (r"\bface\s*serum\b|\bserum\b","Skincare",     "Serum"),
    (r"\bsunscreen\b|\bspf\b|\bsun\s*protection\b", "Skincare", "Sunscreen"),
    (r"\bface\s*cream\b|\bface\s*moisturizer\b|\bday\s*cream\b", "Skincare", "Moisturizer"),
    (r"\bnight\s*cream\b",        "Skincare",      "Night Cream"),
    (r"\beye\s*cream\b",          "Skincare",      "Eye Cream"),
    (r"\bface\s*mask\b|\bsheet\s*mask\b", "Skincare", "Face Mask"),
    # Body
    (r"\bbody\s*lotion\b|\bbody\s*cream\b|\bbody\s*butter\b", "Body Care", "Body Moisturizer"),
    (r"\bbody\s*wash\b|\bshower\s*gel\b", "Body Care", "Body Wash"),
    # Fragrance
    (r"\bperfume\b|\beau\s*de\b|\bfragrance\b", "Fragrance", "Fragrance"),
    # Nail
    (r"\bnail\s*polish\b|\bnail\s*color\b|\bnail\s*colour\b|\bnail\s*lacquer\b", "Nail Care", "Nail Polish"),
]


def _infer_category_and_type(name, tags, description_text=""):
    """Infer (category, productType) from product name, tags, and description."""
    search_text = " ".join(filter(None, [name, " ".join(tags or []), description_text[:200]])).lower()
    for pattern, category, product_type in _CATEGORY_RULES:
        if re.search(pattern, search_text, re.IGNORECASE):
            return category, product_type
    return None, None


def choose_category(raw_product, url):
    # 1. Use explicit product type from Shopify
    product_type = clean_empty(raw_product.get("type"))
    if product_type:
        return product_type
    # 2. Infer from name + tags
    name = raw_product.get("title") or ""
    tags = raw_product.get("tags") or []
    body = raw_product.get("body_html") or raw_product.get("description") or ""
    category, _ = _infer_category_and_type(name, tags, body)
    if category:
        return category
    # 3. Fallback to collection URL
    collection_handle = get_collection_handle_from_url(url)
    if collection_handle:
        return title_case_from_handle(collection_handle)
    return None


# ---------------------------------------------------------------------------
# Build product dict from Shopify JSON
# ---------------------------------------------------------------------------

def build_product_from_shopify_json(raw_product, url, currency="USD", media_data=None):
    raw_variants = raw_product.get("variants") or []
    variants = normalize_variants_from_shopify(raw_variants)
    available_variants = [v for v in variants if v.get("available") is True]

    # Use media_data if available (from .json endpoint), else fallback
    if media_data:
        images = media_data.get("images") or []
        videos = media_data.get("videos") or []
        models = media_data.get("models") or []
        featured_image = media_data.get("featuredImage")
    else:
        images = normalize_images_from_shopify(raw_product)
        videos = []
        models = []
        featured_image = images[0] if images else None

    prices = get_price_list(raw_variants, "price")
    compare_prices = get_price_list(raw_variants, "compare_at_price")

    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    compare_at = min(compare_prices) if compare_prices else None

    handle = raw_product.get("handle") or get_product_handle(url)
    product_url = urljoin(url, f"/products/{handle}") if handle else url

    category = choose_category(raw_product, url)
    product_type = clean_empty(raw_product.get("type"))
    # Infer category and productType from name/tags if not set
    if not category or not product_type:
        _inf_cat, _inf_type = _infer_category_and_type(
            raw_product.get("title") or "",
            raw_product.get("tags") or [],
            raw_product.get("body_html") or raw_product.get("description") or "",
        )
        if not category and _inf_cat:
            category = _inf_cat
        if not product_type and _inf_type:
            product_type = _inf_type
    options = normalize_options(raw_product.get("options") or [])

    on_sale = bool(compare_at and min_price and compare_at > min_price)
    initial_badges = []
    if not available_variants:
        initial_badges.append("Sold Out")
    if on_sale:
        initial_badges.append("Sale")

    product = {
        "rank": 1,
        "name": raw_product.get("title"),
        "handle": handle,
        "productId": str(raw_product.get("id")) if raw_product.get("id") else None,
        "productUrl": product_url,
        "imageUrl": featured_image,
        "additionalImageUrls": images[1:] if len(images) > 1 else [],
        "media": {
            "images": images,
            "videos": videos,
            "models": models,
        },
        "price": {
            "currency": currency,
            "current": min_price,
            "compareAt": compare_at,
            "isOnSale": on_sale,
            "priceTextRaw": None,
            "min": min_price,
            "max": max_price,
        },
        "availability": {
            "status": "in_stock" if available_variants else "out_of_stock",
            "inStock": bool(available_variants),
            "availableVariantCount": len(available_variants),
            "stockTextRaw": None,
        },
        "category": category,
        "vendor": clean_empty(raw_product.get("vendor")),
        "shortDescription": raw_product.get("body_html") or raw_product.get("description"),
        "description": clean_html_description(raw_product.get("body_html") or raw_product.get("description")),
        "productType": product_type,
        "tags": raw_product.get("tags") or [],
        "options": options,
        "swatches": [],
        "badges": initial_badges,
        "variants": variants,
        "discount": (
            {
                "percent": round(((compare_at - min_price) / compare_at) * 100),
                "savedAmount": round(compare_at - min_price, 2),
                "originalPrice": compare_at,
                "currentPrice": min_price,
            }
            if on_sale and compare_at and min_price and compare_at > min_price
            else None
        ),
        "variantAvailabilityMap": build_variant_availability_map(variants, options),
        "reviews": {},
        "relatedProducts": [],
        "metrics": {
            "variantCount": len(variants),
            "availableVariantCount": len(available_variants),
            "imageCount": len(images),
            "videoCount": len(videos),
            "modelCount": len(models),
            "hasMultiplePrices": min_price != max_price,
            "hasOptions": bool(options),
            "hasVideo": bool(videos),
            "has3DModel": bool(models),
        },
        "source": {
            "cardSelector": "shopify_product_js",
            "confidence": 0.95,
        },
    }

    return normalize_product(product, default_currency=currency)


def extract_product_from_open_graph(result, url, currency="USD"):
    og = result.get("openGraph") or {}
    title = og.get("title") or (result.get("seo") or {}).get("h1")
    image = og.get("image:secure_url") or og.get("image")
    price_raw = str(og.get("price:amount") or "").replace(",", "")
    price = normalize_number(price_raw)
    currency = og.get("price:currency") or currency
    collection_handle = get_collection_handle_from_url(url)

    product = {
        "rank": 1,
        "name": title,
        "handle": get_product_handle(url),
        "productId": None,
        "productUrl": url,
        "imageUrl": image,
        "additionalImageUrls": [],
        "media": {"images": [image] if image else [], "videos": [], "models": []},
        "price": {
            "currency": currency,
            "current": price,
            "compareAt": None,
            "isOnSale": False,
            "priceTextRaw": og.get("price:amount"),
            "min": price,
            "max": price,
        },
        "availability": {
            "status": "unknown",
            "inStock": None,
            "availableVariantCount": None,
            "stockTextRaw": None,
        },
        "category": title_case_from_handle(collection_handle) if collection_handle else None,
        "vendor": og.get("site_name"),
        "shortDescription": og.get("description") or (result.get("seo") or {}).get("metaDescription"),
        "description": clean_html_description(
            og.get("description") or (result.get("seo") or {}).get("metaDescription")
        ),
        "productType": None,
        "tags": [],
        "options": [],
        "swatches": [],
        "badges": [],
        "variants": [],
        "variantAvailabilityMap": {},
        "reviews": {},
        "relatedProducts": [],
        "metrics": {
            "variantCount": 0,
            "availableVariantCount": 0,
            "imageCount": 1 if image else 0,
            "videoCount": 0,
            "modelCount": 0,
            "hasMultiplePrices": False,
            "hasOptions": False,
            "hasVideo": False,
            "has3DModel": False,
        },
        "source": {
            "cardSelector": "open_graph_product",
            "confidence": 0.55,
        },
    }

    return normalize_product(product, default_currency=currency)


# ---------------------------------------------------------------------------
# Description enrichment
# ---------------------------------------------------------------------------

def enrich_product_description(product, soup):
    description = product.get("description") or {}

    dom_sections = extract_product_sections_from_dom(soup)
    inferred_sections = infer_sections_from_description_text(description)

    merged = {
        "ingredients": clean_ingredients(
            dom_sections.get("ingredients", []) + inferred_sections.get("ingredients", [])
        ),
        "usage": clean_usage(
            dom_sections.get("usage", []) + inferred_sections.get("usage", [])
        ),
        "benefits": clean_benefits(
            dom_sections.get("benefits", []) + inferred_sections.get("benefits", [])
        ),
        "features": _split_and_clean_features(dom_sections.get("features", [])),
        "specifications": clean_specifications(dom_sections.get("specifications", [])),
        "faqs": dom_sections.get("faqs", []),
    }

    product["description"] = merge_description_sections(description, merged)

    # --- Description fallback: if still null, pull from DOM / meta ---
    desc = product.get("description") or {}
    if not desc.get("text"):
        # Try product description containers in DOM
        for sel in [
            ".product__description", ".product-description",
            ".product-single__description", ".product-form__description",
            ".rte", "[class*='product-description']",
        ]:
            el = soup.select_one(sel)
            if el:
                raw_text = clean_text(el.get_text(" ", strip=True))
                if raw_text and len(raw_text) > 20:
                    desc["text"] = raw_text
                    desc["html"] = str(el)
                    break

    product["description"] = desc
    product["shortDescription"] = (
        desc.get("text") or product.get("shortDescription")
    )
    return product


# ---------------------------------------------------------------------------
# CTA extraction
# ---------------------------------------------------------------------------

_CTA_BUTTON_RE = re.compile(
    r"\b(add to cart|add to bag|buy now|sold out|checkout|view cart|"
    r"add to basket|order now|get it now|shop now|pre.?order)\b",
    re.IGNORECASE,
)


def extract_ctas_from_dom(soup):
    """
    Extract CTA button texts from the product form area.
    Searches product form buttons, submit inputs, and Shopify payment buttons.
    """
    ctas = []
    seen = set()

    # Prioritise product form context
    form = soup.find("form", attrs={"action": re.compile(r"/cart/add", re.I)})
    search_root = form if form else soup

    selectors = [
        "button[type='submit']", "button[name='add']",
        "input[type='submit']", "input[name='add']",
        ".product-form__submit", ".btn-add-to-cart",
        "[class*='add-to-cart']", "[class*='add_to_cart']",
        "[data-testid*='add-to-cart']", "[data-action*='add-to-cart']",
        ".shopify-payment-button button", ".product-form button",
    ]

    for sel in selectors:
        for el in search_root.select(sel):
            text = clean_text(
                el.get_text(" ", strip=True)
                or el.get("value", "")
                or el.get("aria-label", "")
            )
            if text and 3 <= len(text) <= 60:
                key = text.lower()
                if key not in seen:
                    seen.add(key)
                    ctas.append({"text": text, "url": None})

    # Regex scan the page for common CTA phrases not caught above
    body_text = (soup.find("body") or soup).get_text(" ", strip=True)
    for m in _CTA_BUTTON_RE.finditer(body_text):
        text = m.group(0).strip()
        key = text.lower()
        if key not in seen:
            seen.add(key)
            ctas.append({"text": text, "url": None})

    return ctas[:10]


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def analyze_product(*args, **kwargs):
    """
    Entry point called by ShopifyAnalyzer.analyze().
    Accepts both call signatures:
      new: (self, url, html, headers, page_type, level1)
      old: (url, soup, result, extractor, confidence)
    """
    from bs4 import BeautifulSoup

    # Detect call style by inspecting first argument
    if args and hasattr(args[0], "base_result"):
        # New-style: (self, url, html, headers, page_type, level1)
        self_obj, url, html = args[0], args[1], args[2]
        headers  = args[3] if len(args) > 3 else kwargs.get("headers", {})
        page_type = args[4] if len(args) > 4 else kwargs.get("page_type", "product")
        level1   = args[5] if len(args) > 5 else kwargs.get("level1", {})
        result = self_obj.base_result(url, html, headers, page_type, level1)
        soup = BeautifulSoup(html or "", "lxml")
        raw_product = fetch_shopify_product_json_extended(url)
        result["_raw_product"] = raw_product or {}
        result["_html"] = html or ""
        extractor  = "shopify_json" if raw_product else "dom"
        confidence = 0.95 if raw_product else 0.7
        return _analyze_product_internal(url, soup, result, extractor, confidence)
    else:
        # Old-style: (url, soup, result, extractor, confidence)
        url    = args[0] if len(args) > 0 else kwargs.get("url", "")
        soup   = args[1] if len(args) > 1 else kwargs.get("soup")
        result = args[2] if len(args) > 2 else kwargs.get("result", {})
        extractor  = args[3] if len(args) > 3 else kwargs.get("extractor", "dom")
        confidence = args[4] if len(args) > 4 else kwargs.get("confidence", 0.7)
        if soup is None:
            soup = BeautifulSoup("", "lxml")
        return _analyze_product_internal(url, soup, result, extractor, confidence)


def _analyze_product_internal(url, soup, result, extractor="shopify_json", confidence=0.95):
    """Core extraction logic."""
    raw_product = result.get("_raw_product") or {}

    # --- Currency detection: variant > OG > page ---
    currency = None
    for v in (raw_product.get("variants") or []):
        vc = v.get("price_currency") or v.get("currency")
        if vc and len(str(vc)) == 3:
            currency = str(vc).upper()
            break
    if not currency:
        og = result.get("openGraph") or {}
        vc = og.get("price:currency") or og.get("product:price:currency")
        if vc and len(str(vc)) == 3:
            currency = str(vc).upper()
    if not currency:
        html_str = result.get("_html") or ""
        og = result.get("openGraph") or {}
        currency = extract_currency_from_page(html_str, soup, og, url=url)

    product = build_product_from_shopify_json(raw_product, url, currency=currency or "USD")
    product_soup = _make_product_soup(soup)
    dom_sections = extract_product_sections_from_dom(product_soup)

    # ── Parse body_html HTML structure for arrow/bold sections ──────────────
    # Highest-priority: correctly extracts Keune-style
    # → <b>Feature</b> / THE RESULT / HOW TO USE sections
    raw_body_html = raw_product.get("body_html") or ""
    html_sections = _parse_body_html_arrow_sections(raw_body_html)

    # ── Features ─────────────────────────────────────────────────────────────
    # Priority: body_html arrow structure > DOM section > description text
    desc = product.get("description") or {}
    if html_sections.get("features"):
        best_features = html_sections["features"]
    else:
        dom_features = _split_and_clean_features(dom_sections.get("features", []))
        split_desc_features = _split_and_clean_features(desc.get("features") or [])
        best_features = dom_features or split_desc_features

    # ── Benefits ─────────────────────────────────────────────────────────────
    # Priority: body_html THE RESULT section > DOM section > description text
    if html_sections.get("benefits"):
        best_benefits = clean_benefits(html_sections["benefits"])
    else:
        dom_benefits_raw = [b for x in (dom_sections.get("benefits") or [])
                            for b in _split_long_benefit(x)]
        dom_benefits = clean_benefits(dom_benefits_raw)
        split_desc_benefits = clean_benefits(
            [b for x in (desc.get("benefits") or []) for b in _split_long_benefit(x)]
        )
        best_benefits = dom_benefits or split_desc_benefits

    # ── Usage ─────────────────────────────────────────────────────────────────
    # Priority: body_html HOW TO USE > DOM accordion > description text
    if html_sections.get("usage"):
        best_usage = clean_usage(html_sections["usage"])
    else:
        dom_usage = clean_usage(dom_sections.get("usage") or [])
        desc_usage = clean_usage(desc.get("usage") or [])
        best_usage = dom_usage or desc_usage

    if not product.get("features"):
        product["features"] = best_features
    if not product.get("benefits"):
        product["benefits"] = best_benefits

    # Sync back into description dict
    desc["features"] = best_features or desc.get("features", [])
    desc["benefits"] = best_benefits or desc.get("benefits", [])
    desc["usage"] = best_usage or desc.get("usage", [])
    product["description"] = desc

    if not product.get("ingredients"):
        dom_ing = clean_ingredients(dom_sections.get("ingredients", []))
        product["ingredients"] = dom_ing
        if dom_ing and not desc.get("ingredients"):
            desc["ingredients"] = dom_ing
            product["description"] = desc

    # ── Active ingredients ──────────────────────────────────────────────────
    if not product.get("activeIngredients"):
        desc_text = desc.get("text") or ""
        active = extract_active_ingredients(desc_text, description_html=raw_body_html, ingredients_list=product.get("ingredients") or [])
        if active:
            product["activeIngredients"] = active

    # ── Storage / safety instructions ───────────────────────────────────────
    # Pull storage sentences out of features so they don't pollute product bullets
    if not product.get("storageInstructions"):
        all_feature_candidates = list(best_features or []) + list(desc.get("features") or [])
        storage = extract_storage_instructions(all_feature_candidates)
        if storage:
            product["storageInstructions"] = storage
            # Remove storage items from features
            storage_set = {s.lower() for s in storage}
            product["features"] = [f for f in (product.get("features") or [])
                                    if f.lower() not in storage_set]
            desc["features"] = [f for f in (desc.get("features") or [])
                                 if f.lower() not in storage_set]
            product["description"] = desc

    if not product.get("reviews"):
        html_str = result.get("_html") or ""
        product["reviews"] = extract_reviews(product_soup, html_str)
    if not product.get("badges"):
        product["badges"] = extract_badges(product_soup, product)
    if not product.get("swatches"):
        product["swatches"] = extract_swatches_from_dom(product_soup)
    if not product.get("relatedProducts"):
        product["relatedProducts"] = extract_related_products_from_dom(product_soup, url)

    lazy_imgs = extract_lazy_images_from_dom(soup)
    if lazy_imgs and not product.get("images"):
        product["images"] = lazy_imgs

    ctas = extract_ctas_from_dom(soup)

    metrics = product.get("metrics") or {}
    metrics["hasReviews"] = bool((product.get("reviews") or {}).get("averageRating"))
    metrics["reviewCount"] = (product.get("reviews") or {}).get("reviewCount")
    metrics["hasBadges"] = bool(product.get("badges"))
    metrics["hasSwatches"] = bool(product.get("swatches"))
    metrics["hasRelatedProducts"] = bool(product.get("relatedProducts"))
    metrics["hasCtas"] = bool(ctas)
    product["metrics"] = metrics

    # ── Headless-Shopify fallback: OG tags + JSON-LD + H1 ────────────────────
    # When the Shopify product JSON API is unavailable (headless stores like
    # SKIMS or Gymshark that disable the public storefront), raw_product is
    # empty and all Shopify-specific extractions fail.  Fill critical nulls
    # from universal signals that any properly rendered page will have.
    # Triggers on missing name OR missing price: Gymshark extracts the name
    # from the DOM but renders the price client-side, so a name-only gate
    # left the price permanently null.
    if not product.get("name") or not (product.get("price") or {}).get("current"):
        og = result.get("openGraph") or {}

        # 1. JSON-LD Product schema — highest-fidelity source.
        # Handles both @type=Product and @type=ProductGroup (nike/gymshark
        # style), where the sellable Products with offers live in hasVariant.
        jl_name = jl_price = jl_currency = jl_image = jl_description = None
        for _script in soup.find_all("script", type="application/ld+json"):
            try:
                _data = json.loads(_script.string or "")
                if isinstance(_data, list):
                    _data = _data[0] if _data else {}
                if not isinstance(_data, dict):
                    continue
                _type = _data.get("@type", "")
                _types = _type if isinstance(_type, list) else [_type]
                if "Product" in _types or "ProductGroup" in _types:
                    _node = _data
                    if "ProductGroup" in _types and not _data.get("offers"):
                        _variants = _data.get("hasVariant") or []
                        if isinstance(_variants, list) and _variants and isinstance(_variants[0], dict):
                            _node = _variants[0]
                    # Name comes from the GROUP (canonical product name);
                    # variants carry per-colour/size names ("... - Size XS").
                    jl_name = _data.get("name") or _node.get("name")
                    _offers = _node.get("offers") or {}
                    if isinstance(_offers, list):
                        _offers = _offers[0] if _offers else {}
                    jl_price = _offers.get("price")
                    jl_currency = _offers.get("priceCurrency")
                    _img = _node.get("image") or _data.get("image")
                    if isinstance(_img, list):
                        _img = _img[0]
                    jl_image = _img.get("url") if isinstance(_img, dict) else _img
                    jl_description = _node.get("description") or _data.get("description")
                    break
            except Exception:
                pass

        # 2. H1 for name
        _h1 = soup.find("h1")
        _h1_text = _h1.get_text(strip=True) if _h1 else None

        # OG title often contains "Product Name | Variant | Brand" — take
        # only the first segment so we get a clean product name.
        _og_title_raw = og.get("title") or ""
        _og_title = _og_title_raw.split("|")[0].strip() if "|" in _og_title_raw else _og_title_raw.strip() or None
        # Never overwrite a name the DOM extraction already found — this block
        # can now run for price-only recovery. When both exist, prefer the OG
        # title if it CONTAINS the JSON-LD name: og carries the richer form
        # ("Gymshark Everyday Seamless Shorts - Black" vs ld's
        # "everyday seamless shorts").
        if not product.get("name"):
            _best_name = jl_name or _og_title or _h1_text
            if (
                jl_name and _og_title
                and jl_name.strip().lower() in _og_title.strip().lower()
                and len(_og_title) > len(jl_name)
            ):
                _best_name = _og_title
            product["name"] = _best_name

        # Image — OG extractor may store it as "image", "image:url", or "image:secure_url"
        if not product.get("imageUrl"):
            _og_img = (
                og.get("image:secure_url")
                or og.get("image:url")
                or og.get("image")
            )
            if isinstance(_og_img, list):
                _og_img = _og_img[0]
            _fb_img = jl_image or _og_img
            if _fb_img:
                product["imageUrl"] = _fb_img
                product.setdefault("additionalImageUrls", [])
                _media = product.setdefault("media", {})
                if not _media.get("images"):
                    _media["images"] = [_fb_img]

        # Price
        _p = product.get("price") or {}
        if not _p.get("current"):
            _og_price_str = og.get("price:amount") or og.get("product:price:amount")
            try:
                _og_price_val = float(_og_price_str) if _og_price_str else None
            except (ValueError, TypeError):
                _og_price_val = None
            try:
                _jl_price_val = float(jl_price) if jl_price else None
            except (ValueError, TypeError):
                _jl_price_val = None
            _price_val = _jl_price_val or _og_price_val
            if _price_val:
                _og_cur = og.get("price:currency") or og.get("product:price:currency")
                _p["current"] = _price_val
                _p["currency"] = jl_currency or _og_cur or _p.get("currency") or "USD"
                _p["isOnSale"] = False
                product["price"] = _p

        # Description
        if not (product.get("description") or {}).get("text"):
            _desc_text = jl_description or og.get("description")
            if _desc_text:
                product["description"] = {
                    "html": None,
                    "text": _desc_text,
                    "bullets": [],
                    "headings": [],
                    "features": [],
                    "benefits": [],
                    "usage": [],
                    "specifications": [],
                }

        # Re-infer category + productType from the recovered name
        if product.get("name") and not product.get("category"):
            _inf_cat, _inf_type = _infer_category_and_type(
                product["name"], product.get("tags") or [], ""
            )
            if _inf_cat:
                product["category"] = _inf_cat
            if not product.get("productType") and _inf_type:
                product["productType"] = _inf_type
    # ─────────────────────────────────────────────────────────────────────────

    result["content"]["productName"] = product.get("name")
    result["content"]["productDescription"] = product.get("description") or {}
    result["content"]["productType"] = product.get("productType")
    result["content"]["category"] = product.get("category")
    result["content"]["tags"] = product.get("tags") or []
    result["content"]["ctas"] = ctas

    result["ecommerce"]["product"] = product
    result["ecommerce"]["price"] = product.get("price")
    result["ecommerce"]["availability"] = product.get("availability")
    result["ecommerce"]["variants"] = product.get("variants") or []
    result["ecommerce"]["options"] = product.get("options") or []
    result["ecommerce"]["metrics"] = product.get("metrics") or {}

    result["products"] = [product]
    result["source"]["extractor"] = extractor
    result["source"]["confidence"] = confidence

    return result
