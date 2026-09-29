"""Vertical-agnostic product/collection matching for competitor comparison.

Design goals:
- Work for ANY ecommerce vertical (cosmetics, appliances, sports, clothing,
  electronics, home, toys, ...) via a broad category taxonomy.
- Ignore marketing adjectives ("matte", "professional", "premium") when
  matching product names, so a blusher never matches a powder just because
  both say "Matte Professional Long Lasting".
- Detect each site's own brand tokens dynamically and exclude them, instead of
  hardcoding brand names.
- Compare prices relatively (log-ratio, same currency), never with absolute
  currency-specific thresholds.
- Use globally-greedy assignment so the best pairs win first.
"""

from __future__ import annotations

import math
import os
import re
from difflib import SequenceMatcher
from statistics import mean, median
from typing import Any, Dict, List, Optional, Set, Tuple

from .utils import clean_text, pct

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

STOPWORDS = {
    "the", "and", "or", "for", "with", "without", "of", "in", "on", "to", "a", "an",
    "shop", "collection", "collections", "store", "official", "online", "buy",
    "pk", "com", "www", "https", "product", "products", "item", "items", "page",
}

# Marketing/descriptor words that appear across unrelated products.
# They must not drive name matching (they may still support description overlap).
MARKETING_TOKENS = {
    "new", "best", "top", "premium", "luxury", "professional", "pro", "original",
    "authentic", "quality", "high", "long", "lasting", "longlasting", "durable",
    "waterproof", "water", "proof", "resistant", "smudge", "matte", "glossy",
    "shiny", "glow", "radiant", "natural", "organic", "vegan", "free", "super",
    "ultra", "extra", "intense", "light", "lightweight", "heavy", "duty",
    "portable", "mini", "maxi", "large", "small", "big", "full", "double",
    "single", "multi", "smart", "digital", "electric", "automatic", "manual",
    "classic", "modern", "style", "stylish", "fashion", "trendy", "hot", "sale",
    "offer", "discount", "special", "edition", "limited", "exclusive", "perfect",
    "ideal", "easy", "quick", "fast", "instant", "advanced", "deluxe", "custom",
    "color", "colour", "colors", "colours", "shade", "shades", "soft", "smooth",
}

# Broad ecommerce taxonomy. label -> alias tokens/phrases.
# Single-word aliases match as tokens; multi-word aliases match as substrings.
CATEGORY_ALIASES: Dict[str, Set[str]] = {
    # Beauty & personal care
    "foundation": {"foundation", "foundations", "bb cream", "cc cream", "mousse foundation", "base makeup"},
    "concealer": {"concealer", "corrector", "camouflage"},
    "face_powder": {"powder", "compact", "loose powder", "setting powder"},
    "blush": {"blush", "blusher", "cheek tint", "cheeks"},
    "highlighter": {"highlighter", "illuminator", "shimmer", "bronzer", "contour"},
    "primer_fixer": {"primer", "makeup fixer", "setting spray", "fixer"},
    "eyeshadow": {"eyeshadow", "eye shadow", "palette", "palettes"},
    "eyeliner": {"eyeliner", "eye liner", "kajal", "kohl"},
    "eyebrow": {"eyebrow", "brow", "brows"},
    "mascara": {"mascara", "lash", "lashes"},
    "lip_color": {"lipstick", "lipsticks", "lip gloss", "lipgloss", "lip liner", "lip tint", "lip color", "lip crayon", "lips", "lip"},
    "nails": {"nail", "nails", "manicure", "pedicure", "cuticle"},
    "skincare": {"skincare", "skin care", "serum", "moisturizer", "moisturiser", "cleanser", "face wash", "facewash", "toner", "face mask", "sheet mask", "exfoliator", "scrub", "anti aging", "acne"},
    "suncare": {"sunscreen", "sunblock", "spf", "after sun"},
    "fragrance": {"perfume", "fragrance", "eau de", "cologne", "body spray", "attar", "scent", "mist"},
    "haircare": {"shampoo", "conditioner", "hair oil", "hair mask", "hair serum", "hair spray", "hair color", "hair dye", "hair"},
    "bath_body": {"body wash", "body lotion", "soap", "shower gel", "deodorant", "body butter", "hand cream", "body scrub"},
    "mens_grooming": {"beard", "shaving", "razor", "aftershave", "grooming"},

    # Fashion
    "tops": {"shirt", "shirts", "t shirt", "tshirt", "tee", "top", "tops", "blouse", "polo", "tunic", "kurti", "kurta", "hoodie", "sweatshirt", "sweater", "cardigan"},
    "bottoms": {"jeans", "trouser", "trousers", "pants", "shorts", "skirt", "leggings", "joggers", "chinos", "shalwar"},
    "dresses": {"dress", "dresses", "gown", "frock", "maxi dress", "abaya", "saree", "lehenga"},
    "outerwear": {"jacket", "coat", "blazer", "parka", "windbreaker", "vest", "shawl"},
    "activewear": {"activewear", "sportswear", "tracksuit", "gym wear", "yoga pants", "sports bra"},
    "underwear_sleep": {"underwear", "lingerie", "bra", "boxers", "briefs", "nightwear", "pajama", "pyjama", "sleepwear"},
    "shoes": {"shoes", "shoe", "sneakers", "trainers", "boots", "sandals", "heels", "loafers", "slippers", "flats", "footwear"},
    "bags": {"bag", "bags", "handbag", "backpack", "tote", "clutch", "wallet", "purse", "luggage", "suitcase", "duffel"},
    "jewelry": {"jewelry", "jewellery", "ring", "rings", "necklace", "bracelet", "earring", "earrings", "pendant", "bangle", "anklet"},
    "watches": {"watch", "watches", "smartwatch", "chronograph"},
    "accessories": {"belt", "scarf", "hat", "cap", "sunglasses", "glasses", "tie", "socks", "hijab", "dupatta"},

    # Electronics
    "phones": {"phone", "smartphone", "iphone", "mobile", "tablet", "ipad"},
    "computers": {"laptop", "notebook", "desktop", "computer", "macbook", "chromebook", "monitor"},
    "audio": {"headphone", "headphones", "earbuds", "earphones", "airpods", "speaker", "speakers", "soundbar", "microphone"},
    "cameras": {"camera", "dslr", "mirrorless", "gopro", "lens", "tripod", "drone"},
    "tv_video": {"tv", "television", "projector"},
    "gaming": {"gaming", "console", "playstation", "xbox", "nintendo", "controller", "gamepad"},
    "tech_accessories": {"charger", "cable", "power bank", "powerbank", "adapter", "screen protector", "mouse", "keyboard", "usb", "memory card", "ssd", "hard drive"},

    # Home & appliances
    "kitchen_appliances": {"blender", "juicer", "mixer", "grinder", "air fryer", "airfryer", "toaster", "kettle", "coffee maker", "espresso", "microwave", "oven", "food processor", "chopper", "sandwich maker", "rice cooker", "pressure cooker", "hob", "hood", "stove"},
    "large_appliances": {"refrigerator", "fridge", "freezer", "washing machine", "dryer", "dishwasher", "water dispenser"},
    "climate": {"air conditioner", "heater", "fan", "cooler", "humidifier", "dehumidifier", "air purifier", "geyser"},
    "cleaning_appliances": {"vacuum", "vacuum cleaner", "mop", "steam cleaner"},
    "personal_appliances": {"hair dryer", "straightener", "curler", "epilator", "shaver", "trimmer", "iron", "steamer", "massager"},
    "cookware": {"cookware", "pan", "pot", "frying pan", "kadai", "tawa", "casserole", "knife", "cutlery", "utensil", "tableware", "dinner set", "crockery"},
    "furniture": {"sofa", "chair", "table", "bed", "mattress", "wardrobe", "desk", "shelf", "cabinet", "dresser", "ottoman", "furniture"},
    "home_decor": {"decor", "rug", "carpet", "curtain", "curtains", "cushion", "lamp", "lighting", "mirror", "vase", "wall art", "candle", "frame"},
    "bedding_bath": {"bedding", "bed sheet", "bedsheet", "duvet", "comforter", "pillow", "blanket", "towel", "quilt"},

    # Sports & outdoors
    "fitness_equipment": {"treadmill", "dumbbell", "dumbbells", "barbell", "weights", "exercise bike", "yoga mat", "resistance band", "kettlebell", "gym"},
    "sports_gear": {"football", "soccer", "cricket", "basketball", "volleyball", "hockey", "badminton", "tennis", "racket", "bat", "jersey"},
    "outdoor": {"camping", "tent", "hiking", "sleeping bag", "fishing", "cycling", "bicycle", "bike", "scooter", "skateboard"},
    "nutrition": {"protein", "whey", "creatine", "supplement", "supplements", "vitamins", "bcaa", "pre workout"},

    # Kids, pets, other
    "toys": {"toy", "toys", "lego", "doll", "puzzle", "board game", "action figure", "rc car"},
    "baby": {"baby", "diaper", "diapers", "stroller", "crib", "pacifier", "baby food", "infant"},
    "pets": {"pet", "dog", "cat", "pet food", "leash", "aquarium", "litter"},
    "grocery": {"grocery", "tea", "coffee", "snacks", "rice", "flour", "honey", "spices", "juice"},
    "health": {"medicine", "first aid", "thermometer", "blood pressure", "glucometer", "sanitizer", "wheelchair"},
    # NB: "pen"/"pencil"/"marker" removed — they collide hard with beauty (eyebrow
    # pencil, eyeliner pen, lip marker) and other verticals; a real stationery store
    # still matches on book/stationery/notebook/diary/planner.
    "books_stationery": {"book", "books", "stationery", "notebook", "notepad", "diary", "planner"},
    "tools_auto": {"drill", "screwdriver", "toolkit", "tool", "tools", "tyre", "tire", "engine oil", "helmet", "motorcycle"},
    "garden": {"garden", "plant", "plants", "seeds", "planter", "lawn"},

    # Cross-vertical merch concepts
    "bundles_sets": {"bundle", "bundles", "kit", "combo", "pack of", "gift set"},
    "sale_offers": {"clearance", "deal", "deals", "offers"},
    "gift": {"gift", "gifts", "gift box", "gift card", "voucher"},
}

ALIAS_STEMS: Set[str] = set()  # populated below, after stem() is defined


# Units used to extract attribute tokens like "30ml", "5l", "128gb", "55 inch".
UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s?(ml|l|litre|liter|g|kg|mg|oz|gb|tb|mb|inch|inches|cm|mm|w|kw|watt|watts|v|volt|mah|hz|pcs|pc|piece|pieces|pack|pair|pairs|seater|ton|btu|rpm|mp)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Tokenizing
# ---------------------------------------------------------------------------

def text_blob(*parts: Any) -> str:
    return " ".join(clean_text(p) for p in parts if clean_text(p)).lower()


def stem(word: str) -> str:
    """Light plural stemmer so 'mascaras' matches 'mascara', 'dresses' matches 'dress'."""
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("sses") or word.endswith("shes") or word.endswith("ches") or word.endswith("xes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and not word.endswith("us"):
        return word[:-1]
    return word


def tokenize(value: Any) -> List[str]:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [stem(t) for t in text.split() if t and t not in STOPWORDS and len(t) > 1]


def token_set(value: Any) -> Set[str]:
    return set(tokenize(value))


# Populate module-level alias stems now that stem() exists.
for _aliases in CATEGORY_ALIASES.values():
    for _a in _aliases:
        if " " not in _a:
            ALIAS_STEMS.add(_a)
            ALIAS_STEMS.add(stem(_a))


def core_tokens(value: Any, brand_tokens: Set[str] | None = None) -> Set[str]:
    """Name tokens minus marketing adjectives and site brand tokens."""
    tokens = token_set(value) - MARKETING_TOKENS
    if brand_tokens:
        tokens -= brand_tokens
    return tokens


def attribute_tokens(value: Any) -> Set[str]:
    """Extract size/spec attributes like 30ml, 5l, 128gb, 55inch."""
    text = clean_text(value).lower()
    found = set()
    for m in UNIT_PATTERN.finditer(text):
        qty, unit = m.group(1), m.group(2).lower()
        unit = {"litre": "l", "liter": "l", "inches": "inch",
                "watt": "w", "watts": "w", "volt": "v", "pc": "pcs",
                "piece": "pcs", "pieces": "pcs", "pair": "pairs"}.get(unit, unit)
        found.add(f"{qty}{unit}")
    return found


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def seq_ratio(a: Any, b: Any) -> float:
    a_s = clean_text(a).lower()
    b_s = clean_text(b).lower()
    if not a_s or not b_s:
        return 0.0
    return SequenceMatcher(None, a_s, b_s).ratio()


def detect_brand_tokens(products: List[Dict[str, Any]], min_products: int = 4, min_share: float = 0.34) -> Set[str]:
    """Tokens appearing in a large share of one site's product names are brand
    or house-style tokens (e.g. 'gabrini', 'sivanna'); they must not drive
    cross-site matching. Fully dynamic - no hardcoded brand list."""
    names = [p.get("name") for p in products if clean_text(p.get("name"))]
    if len(names) < min_products:
        return set()
    counts: Dict[str, int] = {}
    for name in names:
        for t in token_set(name):
            counts[t] = counts.get(t, 0) + 1
    threshold = max(3, int(len(names) * min_share))
    # Category alias words (mascara, shirt, blender...) are product-type words,
    # not brand names - never treat them as brand tokens even if frequent.
    return {t for t, c in counts.items() if c >= threshold} - ALIAS_STEMS


# ---------------------------------------------------------------------------
# Category inference (vertical-agnostic)
# ---------------------------------------------------------------------------

def infer_category_label(*parts: Any) -> Optional[str]:
    blob = text_blob(*parts)
    if not blob:
        return None
    tokens = set(tokenize(blob))
    best_label, best_score = None, 0.0
    for label, aliases in CATEGORY_ALIASES.items():
        score = 0.0
        for alias in aliases:
            if " " in alias:
                if alias in blob:
                    score += 2.0  # phrase hit is a strong signal
            elif stem(alias) in tokens:
                score += 1.0
        if score > best_score:
            best_label, best_score = label, score
    return best_label if best_score > 0 else None


def infer_product_type(product: Dict[str, Any]) -> Optional[str]:
    # Name is the strongest signal; use it alone first so description noise
    # (cross-sell text etc.) cannot flip the category.
    label = infer_category_label(product.get("name"))
    if label:
        return label
    return infer_category_label(
        product.get("category"), product.get("productType"),
        product.get("shortDescription"), product.get("descriptionText"),
    )


# ---------------------------------------------------------------------------
# Price helpers (relative, currency-aware)
# ---------------------------------------------------------------------------

def price_closeness(a: Optional[float], b: Optional[float], same_currency: bool) -> float:
    """1.0 when prices are equal, decaying with log-ratio; 0 when unknown or
    currencies differ. Vertical- and currency-agnostic."""
    if not same_currency or a is None or b is None:
        return 0.0
    try:
        a_f, b_f = float(a), float(b)
    except Exception:
        return 0.0
    if a_f <= 0 or b_f <= 0:
        return 0.0
    ratio = abs(math.log(a_f / b_f))
    return max(0.0, 1.0 - ratio / math.log(3))  # reaches 0 once one price is 3x the other


def relative_price_band(value: Optional[float], reference_prices: List[float]) -> Optional[str]:
    """Band relative to the observed price distribution (never absolute thresholds)."""
    if value is None or not reference_prices:
        return None
    sorted_prices = sorted(reference_prices)
    n = len(sorted_prices)
    q1 = sorted_prices[min(n - 1, max(0, round(n * 0.25) - 1))]
    q2 = sorted_prices[min(n - 1, max(0, round(n * 0.50) - 1))]
    q3 = sorted_prices[min(n - 1, max(0, round(n * 0.75) - 1))]
    v = float(value)
    if v <= q1:
        return "entry"
    if v <= q2:
        return "mid_low"
    if v <= q3:
        return "mid_high"
    return "premium"


def price_gap(user_price: Optional[float], comp_price: Optional[float]) -> Dict[str, Any]:
    if user_price is None or comp_price is None:
        return {"absolute": None, "percentVsUser": None, "direction": "unknown"}
    diff = round(float(comp_price) - float(user_price), 2)
    pct_diff = round((diff / float(user_price)) * 100, 2) if user_price else None
    direction = "competitor_higher" if diff > 0 else "competitor_lower" if diff < 0 else "same"
    return {"absolute": diff, "percentVsUser": pct_diff, "direction": direction}


def price_stats(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    vals = [float(p["priceValue"]) for p in products if p.get("priceValue") is not None]
    return {
        "pricedCount": len(vals),
        "min": min(vals) if vals else None,
        "max": max(vals) if vals else None,
        "average": round(mean(vals), 2) if vals else None,
        "median": round(median(vals), 2) if vals else None,
        "currency": next((p.get("currency") for p in products if p.get("currency")), None),
    }


# ---------------------------------------------------------------------------
# Product compaction
# ---------------------------------------------------------------------------

def compact_product(p: Dict[str, Any], reference_prices: List[float] | None = None) -> Dict[str, Any]:
    return {
        "name": p.get("name"),
        "productUrl": p.get("productUrl"),
        "category": p.get("category"),
        "inferredType": infer_product_type(p),
        "vendor": p.get("vendor"),
        "priceValue": p.get("priceValue"),
        "currency": p.get("currency"),
        "priceCompareAt": p.get("priceCompareAt"),
        "isOnSale": p.get("isOnSale"),
        "discountPercent": p.get("discountPercent"),
        "priceTextRaw": p.get("priceTextRaw"),
        "priceBand": relative_price_band(p.get("priceValue"), reference_prices or []),
        "availability": p.get("availability"),
        "attributes": sorted(attribute_tokens(p.get("name"))),
        "shortDescription": p.get("shortDescription"),
        "variantCount": p.get("variantCount"),
        "variantOptions": (p.get("variantOptions") or [])[:12],
        "swatches": (p.get("swatches") or [])[:12],
        "imageCount": p.get("imageCount"),
        "sourcePages": p.get("sourcePages"),
    }


# ---------------------------------------------------------------------------
# Collection matching
# ---------------------------------------------------------------------------

def collection_identity(collection: Dict[str, Any]) -> Dict[str, Any]:
    url = collection.get("url") or ""
    title = collection.get("title") or collection.get("name") or ""
    # URL slug is more reliable than the page title (titles often carry the site name).
    slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ") if url else ""
    category = infer_category_label(slug) or infer_category_label(title) or infer_category_label(url, title)
    tokens = (token_set(slug) | token_set(title)) - MARKETING_TOKENS
    return {"category": category, "tokens": tokens, "url": url, "title": title, "slug": slug}


def collection_match_score(user_col: Dict[str, Any], comp_col: Dict[str, Any]) -> Tuple[float, List[str]]:
    u = collection_identity(user_col)
    c = collection_identity(comp_col)
    reasons: List[str] = []
    score = 0.0
    if u["category"] and c["category"]:
        if u["category"] == c["category"]:
            score += 0.6
            reasons.append(f"same_inferred_category:{u['category']}")
        else:
            score -= 0.3  # categorized differently: penalize hard
            reasons.append("different_inferred_category")
    overlap = jaccard(u["tokens"], c["tokens"])
    if overlap:
        score += min(0.25, overlap * 0.9)
        reasons.append("keyword_overlap")
    name_ratio = seq_ratio(u["slug"] or u["title"], c["slug"] or c["title"])
    if name_ratio >= 0.5:
        score += min(0.15, name_ratio * 0.15)
        reasons.append("name_similarity")
    return max(0.0, min(score, 1.0)), reasons


def _norm_url(u: Any) -> str:
    """Normalize a URL for equality: drop scheme/query/fragment/www/trailing slash."""
    if not u:
        return ""
    s = str(u).strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("?")[0].split("#")[0]
    s = re.sub(r"^www\.", "", s)
    return s.rstrip("/")


def match_collections(user: Dict[str, Any], competitor: Dict[str, Any]) -> List[Dict[str, Any]]:
    """1:1 assignment of user↔competitor collections.

    Honors the user's EXPLICIT onboarding mapping first (URL-based, forced,
    confidence 1.0) so deliberately-paired collections match even when their
    names are completely different (e.g. "luxury-pret" ↔ "collection-noya").
    The remaining collections are then matched greedily by name/category
    similarity.
    """
    user_cols = user.get("collections", [])
    comp_cols = competitor.get("collections", [])

    matches: List[Dict[str, Any]] = []
    used_u: set = set()
    used_c: set = set()

    def _add(ui, ci, confidence, reasons):
        u_col, c_col = user_cols[ui], comp_cols[ci]
        category = collection_identity(u_col)["category"] or collection_identity(c_col)["category"]
        matches.append({
            "category": category or "unknown",
            "confidence": confidence,
            "matchReasons": reasons,
            "userCollection": u_col,
            "competitorCollection": c_col,
        })

    # 1) User-mapped pairs (from onboarding) — forced, name-agnostic.
    mappings = (
        competitor.get("_userCollectionMappings")
        or (competitor.get("raw") or {}).get("_userCollectionMappings")
        or []
    )
    if mappings:
        u_by_url: Dict[str, int] = {}
        for ui, u_col in enumerate(user_cols):
            k = _norm_url(u_col.get("url"))
            if k:
                u_by_url.setdefault(k, ui)
        c_by_url: Dict[str, int] = {}
        for ci, c_col in enumerate(comp_cols):
            k = _norm_url(c_col.get("url"))
            if k:
                c_by_url.setdefault(k, ci)
        for mp in mappings:
            if not isinstance(mp, dict):
                continue
            ui = u_by_url.get(_norm_url(mp.get("ownerUrl")))
            ci = c_by_url.get(_norm_url(mp.get("competitorUrl")))
            if ui is None or ci is None or ui in used_u or ci in used_c:
                continue
            used_u.add(ui)
            used_c.add(ci)
            _add(ui, ci, 1.0, ["user_mapped"])

    # When the user gave EXPLICIT mappings, compare exactly those pairs and nothing
    # else — the collections they didn't map stay as breadth signals (owner-only /
    # competitor-only), not auto-invented pairs. Score-based greedy matching only
    # runs as a fallback when there was no usable explicit mapping.
    forced = bool(used_u)

    # 2) Score-based greedy assignment for the rest (fallback only).
    if not forced:
        pairs = []
        for ui, u_col in enumerate(user_cols):
            if ui in used_u:
                continue
            for ci, c_col in enumerate(comp_cols):
                if ci in used_c:
                    continue
                score, reasons = collection_match_score(u_col, c_col)
                if score >= 0.35:
                    pairs.append((score, reasons, ui, ci))
        pairs.sort(key=lambda x: x[0], reverse=True)

        for score, reasons, ui, ci in pairs:
            if ui in used_u or ci in used_c:
                continue
            used_u.add(ui)
            used_c.add(ci)
            _add(ui, ci, round(score, 3), reasons)

    return sorted(matches, key=lambda m: m["confidence"], reverse=True)


# ---------------------------------------------------------------------------
# Product -> collection membership
# ---------------------------------------------------------------------------

def product_belongs_to_collection(product: Dict[str, Any], collection: Dict[str, Any]) -> bool:
    # ONLY products actually shown on the collection's crawled page count — matched
    # via the product's recorded source page (sourcePages). The previous
    # category-inference fallback pulled in catalog products that were NOT on the
    # page, inflating the product lists/counts; it's removed so we show and count
    # strictly what the live page displayed.
    col_url = clean_text(collection.get("url")).lower()
    for sp in product.get("sourcePages") or []:
        if clean_text(sp.get("url")).lower() == col_url:
            return True
    return False


def products_for_collection(site: Dict[str, Any], collection: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [p for p in site.get("products", []) if product_belongs_to_collection(p, collection)]


# ---------------------------------------------------------------------------
# Product matching
# ---------------------------------------------------------------------------

def product_match_score(
    user_product: Dict[str, Any],
    comp_product: Dict[str, Any],
    user_brand_tokens: Set[str] | None = None,
    comp_brand_tokens: Set[str] | None = None,
) -> Tuple[float, List[str]]:
    reasons: List[str] = []
    score = 0.0

    u_type = infer_product_type(user_product)
    c_type = infer_product_type(comp_product)

    # Category gate: products classified into DIFFERENT categories are never a
    # like-for-like pair, whatever their adjectives say.
    if u_type and c_type and u_type != c_type:
        return 0.0, ["different_product_type"]

    if u_type and c_type and u_type == c_type:
        score += 0.35
        reasons.append(f"same_product_type:{u_type}")

    # Core-noun overlap: marketing adjectives and brand tokens removed.
    u_core = core_tokens(user_product.get("name"), user_brand_tokens)
    c_core = core_tokens(comp_product.get("name"), comp_brand_tokens)
    core_overlap = jaccard(u_core, c_core)
    if core_overlap:
        score += min(0.3, core_overlap * 0.75)
        reasons.append("core_name_overlap")

    # Shared spec attributes (30ml, 5l, 128gb...) are strong evidence.
    attr_shared = attribute_tokens(user_product.get("name")) & attribute_tokens(comp_product.get("name"))
    if attr_shared:
        score += min(0.15, 0.08 * len(attr_shared))
        reasons.append("shared_attributes:" + ",".join(sorted(attr_shared)))

    # Relative price closeness (same currency only).
    same_currency = bool(
        user_product.get("currency") and user_product.get("currency") == comp_product.get("currency")
    )
    closeness = price_closeness(user_product.get("priceValue"), comp_product.get("priceValue"), same_currency)
    if closeness > 0:
        score += closeness * 0.1
        reasons.append("price_proximity")

    # Description overlap as weak supporting evidence.
    desc_overlap = jaccard(
        core_tokens(user_product.get("descriptionText") or user_product.get("shortDescription"), user_brand_tokens),
        core_tokens(comp_product.get("descriptionText") or comp_product.get("shortDescription"), comp_brand_tokens),
    )
    if desc_overlap:
        score += min(0.1, desc_overlap * 0.3)
        reasons.append("description_overlap")

    return min(score, 1.0), reasons


def match_tier(score: float) -> str:
    if score >= 0.62:
        return "strong"
    if score >= 0.45:
        return "moderate"
    return "weak"


def match_products(
    user_products: List[Dict[str, Any]],
    comp_products: List[Dict[str, Any]],
    category: Optional[str] = None,
    limit: int = int(os.environ.get("MATCH_PRODUCTS_LIMIT", "40")),
    threshold: float = 0.45,
) -> Dict[str, Any]:
    """Globally-greedy 1:1 product matching with a like-for-like category gate.

    `limit` caps products per side. Matching is O(limit^2) PER category, and it's
    also run catalog-wide, so a large store (breakout: ~1,900 products across ~19
    categories) at the old default of 150 was ~450k fuzzy comparisons — several
    minutes, past the request timeout. 40 keeps the top-N signal while running in
    seconds. Tune via MATCH_PRODUCTS_LIMIT.
    """
    u_list = user_products[:limit]
    c_list = comp_products[:limit]

    # Auto product-matching is OFF by default. The fuzzy name-pairing produced
    # unreliable pairs, and its O(limit^2) loop (run per category AND catalog-wide)
    # dominated compare time. Like-for-like now comes from the user's explicit
    # collection/page mappings + price/assortment aggregates. We still expose the
    # product LISTS (for the catalog tabs) but skip the pairwise matching entirely.
    # Re-enable with ENABLE_PRODUCT_MATCHING=1.
    if os.environ.get("ENABLE_PRODUCT_MATCHING", "0") != "1":
        ref = [
            float(p["priceValue"])
            for p in (user_products + comp_products)
            if p.get("priceValue") is not None
        ]
        user_all = [compact_product(p, ref) for p in user_products]
        comp_all = [compact_product(p, ref) for p in comp_products]
        return {
            "matchedProductCount": 0,
            "userUnmatchedCount": len(user_all),
            "competitorUnmatchedCount": len(comp_all),
            "medianPriceGapPercentVsUser": None,
            "matches": [],
            "userUnmatchedProducts": user_all[:250],
            "competitorUnmatchedProducts": comp_all[:250],
        }

    u_brand = detect_brand_tokens(u_list)
    c_brand = detect_brand_tokens(c_list)

    reference_prices = [
        float(p["priceValue"]) for p in (u_list + c_list) if p.get("priceValue") is not None
    ]

    pairs = []
    for ui, up in enumerate(u_list):
        for ci, cp in enumerate(c_list):
            score, reasons = product_match_score(up, cp, u_brand, c_brand)
            if score >= threshold:
                pairs.append((score, reasons, ui, ci))
    pairs.sort(key=lambda x: x[0], reverse=True)

    matches, used_u, used_c = [], set(), set()
    for score, reasons, ui, ci in pairs:
        if ui in used_u or ci in used_c:
            continue
        used_u.add(ui)
        used_c.add(ci)
        up, cp = u_list[ui], c_list[ci]
        matches.append({
            "confidence": round(score, 3),
            "matchTier": match_tier(score),
            "matchReasons": reasons,
            "userProduct": compact_product(up, reference_prices),
            "competitorProduct": compact_product(cp, reference_prices),
            "priceGap": price_gap(up.get("priceValue"), cp.get("priceValue")),
            "positioningComparisonSignals": compare_product_positioning(up, cp),
        })

    user_unmatched = [compact_product(u_list[i], reference_prices) for i in range(len(u_list)) if i not in used_u]
    competitor_unmatched = [compact_product(c_list[i], reference_prices) for i in range(len(c_list)) if i not in used_c]

    matched_gaps = [m["priceGap"]["percentVsUser"] for m in matches if m["priceGap"]["percentVsUser"] is not None]
    return {
        "matchedProductCount": len(matches),
        "userUnmatchedCount": len(user_unmatched),
        "competitorUnmatchedCount": len(competitor_unmatched),
        "medianPriceGapPercentVsUser": round(median(matched_gaps), 2) if matched_gaps else None,
        "matches": sorted(matches, key=lambda m: m["confidence"], reverse=True),
        # Cap generously so the "All products" Catalog tabs can render the full
        # collection (a 69-product collection was showing only 30 because this
        # was sliced to 30). Counts above stay exact; this only bounds payload
        # size for very large catalogs.
        "userUnmatchedProducts": user_unmatched[:250],
        "competitorUnmatchedProducts": competitor_unmatched[:250],
    }


# ---------------------------------------------------------------------------
# Positioning signals (generic, cross-vertical, grouped by theme)
# ---------------------------------------------------------------------------

POSITIONING_SIGNALS = {
    "durability": ["waterproof", "durable", "long lasting", "heavy duty", "resistant", "smudge proof", "scratch proof"],
    "quality": ["premium", "professional", "luxury", "high quality", "original", "authentic", "imported"],
    "value": ["affordable", "budget", "value", "sale", "discount", "deal", "free shipping", "free delivery"],
    "innovation": ["smart", "digital", "advanced", "new formula", "latest", "technology", "innovative"],
    "ethical": ["vegan", "cruelty free", "organic", "natural", "eco", "sustainable", "recyclable", "halal"],
    "convenience": ["easy", "portable", "lightweight", "quick", "instant", "compact", "wireless", "rechargeable"],
    "trust": ["warranty", "guarantee", "certified", "tested", "dermatologist", "hypoallergenic", "official"],
}


def compare_product_positioning(up: Dict[str, Any], cp: Dict[str, Any]) -> Dict[str, Any]:
    u_blob = text_blob(up.get("name"), up.get("shortDescription"), up.get("descriptionText"))
    c_blob = text_blob(cp.get("name"), cp.get("shortDescription"), cp.get("descriptionText"))
    user_signals, comp_signals = [], []
    for theme, words in POSITIONING_SIGNALS.items():
        if any(w in u_blob for w in words):
            user_signals.append(theme)
        if any(w in c_blob for w in words):
            comp_signals.append(theme)
    return {
        "userSignals": user_signals,
        "competitorSignals": comp_signals,
        "sharedSignals": sorted(set(user_signals) & set(comp_signals)),
        "userOnlySignals": sorted(set(user_signals) - set(comp_signals)),
        "competitorOnlySignals": sorted(set(comp_signals) - set(user_signals)),
    }


# ---------------------------------------------------------------------------
# 1-vs-1 comparison block
# ---------------------------------------------------------------------------

def build_one_to_one_comparison(user: Dict[str, Any], competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    competitor_blocks = []
    for comp in competitors:
        col_matches = match_collections(user, comp)
        enriched = []
        for m in col_matches:
            user_products = products_for_collection(user, m["userCollection"])
            comp_products = products_for_collection(comp, m["competitorCollection"])
            product_matches = match_products(user_products, comp_products, category=m.get("category"))
            # LIVE on-page product counts (what each collection page actually shows)
            # are authoritative over the looser catalog-membership match — so the
            # counts and the assortment gap agree with the live collection pages
            # everywhere (UI + AI narrative). Fall back to the matched-set size only
            # when a page didn't report its own count.
            _u_live = m["userCollection"].get("productCount")
            _c_live = m["competitorCollection"].get("productCount")
            u_count = _u_live if isinstance(_u_live, int) and _u_live >= 0 else len(user_products)
            c_count = _c_live if isinstance(_c_live, int) and _c_live >= 0 else len(comp_products)
            enriched.append({
                **m,
                "userCollectionProductCount": u_count,
                "competitorCollectionProductCount": c_count,
                "priceStats": {
                    "user": price_stats(user_products),
                    "competitor": price_stats(comp_products),
                },
                "assortmentGap": {
                    "userProductCount": u_count,
                    "competitorProductCount": c_count,
                    "difference": c_count - u_count,
                    "direction": "competitor_broader" if c_count > u_count else "user_broader" if u_count > c_count else "same",
                },
                "productMatching": product_matches,
                "aiPromptHint": "Use these matched collection and product pairs for like-for-like analysis only. Matches are gated by inferred product type, so pairs are always within the same category.",
            })

        # Catalog-wide matching also covers products outside matched collections.
        overall = match_products(user.get("products", []), comp.get("products", []))
        competitor_blocks.append({
            "competitorKey": comp.get("key"),
            "competitorDomain": comp.get("domain"),
            "matchedCollectionCount": len(enriched),
            "collectionMatchups": enriched,
            "catalogWideProductMatching": {
                "description": "Best like-for-like product pairs across the full catalogs (not restricted to matched collections).",
                "matchedProductCount": overall["matchedProductCount"],
                "medianPriceGapPercentVsUser": overall["medianPriceGapPercentVsUser"],
                "topMatches": overall["matches"][:25],
                "userUnmatchedCount": overall["userUnmatchedCount"],
                "competitorUnmatchedCount": overall["competitorUnmatchedCount"],
            },
        })
    return {
        "displayType": "one_to_one_matchups",
        "description": "Deterministic collection and product matching for like-for-like competitor comparisons across any ecommerce vertical.",
        "userDomain": user.get("domain"),
        "competitors": competitor_blocks,
    }
