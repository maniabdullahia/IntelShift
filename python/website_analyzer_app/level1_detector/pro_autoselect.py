"""
pro_autoselect.py — Pro "complete-site" auto-selection & auto-pairing.

WHY
----
On the Pro plan the user picks *competitors*, not pages. Asking anyone to hand-pick
pages across 10 large stores is impossible, so we auto-select a bounded,
representative slice of each site and auto-pair collections across sites.

Two things make this scale:
  • Products are NOT crawled page-by-page — full variant/image/price depth comes from
    the bulk catalog API (catalog_enrich). So "complete site" means homepage +
    policy pages + a CAPPED set of the most important COLLECTIONS, never thousands
    of product pages.
  • Collections are auto-paired across sites by CANONICAL CATEGORY (not by name and
    not by risky per-product matching), so "Blush On" ↔ "Blush" lines up
    automatically and unmatched collections surface as assortment gaps.

This module is pure/deterministic and unit-tested; callers feed it the collection
list (from recon/catalog) and it returns the selection + the pairing.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# Collection handles that are never worth tracking as their own page (catch-all,
# duplicates of the homepage, or non-category listings).
JUNK_HANDLES = {
    "all", "all-products", "products", "frontpage", "home", "shop", "shop-all",
    "new", "new-arrivals", "best-sellers", "bestsellers", "featured", "sale",
    "everything",
}

# Compact canonical category map (fashion + beauty cover most PK/DTC stores). Each
# canonical name → the keywords that indicate it. Extendable / overridable by caller.
DEFAULT_CATEGORY_MAP: Dict[str, set] = {
    # Beauty
    "foundation": {"foundation", "bb cream", "cc cream", "cushion"},
    "concealer": {"concealer", "corrector"},
    "powder": {"powder", "setting powder", "compact"},
    "blush": {"blush", "blusher", "cheek"},
    "highlighter": {"highlighter", "highlight", "illuminator", "shading", "contour", "bronzer"},
    "lipstick": {"lipstick", "lip color", "lip colour", "lip gloss", "lip tint", "lippie", "lips"},
    "eyeliner": {"eyeliner", "eye liner", "kajal", "kohl"},
    "eyeshadow": {"eyeshadow", "eye shadow", "eye palette"},
    "eyebrow": {"eyebrow", "brow"},
    "mascara": {"mascara", "lash"},
    "skincare": {"skincare", "serum", "moisturizer", "moisturiser", "cleanser", "sunscreen", "spf", "toner"},
    "fragrance": {"fragrance", "perfume", "attar", "body spray", "cologne"},
    "nails": {"nail", "nailpolish", "nail polish"},
    # Fashion
    "shirts": {"shirt", "shirts", "kurta", "kurti", "top", "tops", "tee", "t-shirt"},
    "trousers": {"trouser", "pants", "bottoms", "shalwar", "trousers", "jeans", "denim"},
    "dresses": {"dress", "dresses", "gown", "frock", "maxi"},
    "unstitched": {"unstitched", "fabric", "lawn", "3 piece", "2 piece"},
    "outerwear": {"jacket", "coat", "hoodie", "sweatshirt", "outerwear", "shrug"},
    "activewear": {"activewear", "gym", "training", "sports", "legging", "leggings"},
    "footwear": {"shoe", "shoes", "footwear", "sneaker", "heels", "sandal", "khussa"},
    "bags": {"bag", "bags", "handbag", "clutch", "backpack", "tote"},
    "accessories": {"accessor", "jewel", "jewellery", "jewelry", "watch", "belt", "scarf", "cap", "sunglass"},
    "kids": {"kids", "boys", "girls", "children", "infant"},
    "men": {"men", "mens", "menswear", "gents"},
    "women": {"women", "womens", "womenswear", "ladies"},
}


def _norm_url(u: Optional[str]) -> str:
    return re.sub(r"/+$", "", (u or "").strip().lower())


def _handle(url: Optional[str]) -> str:
    if not url:
        return ""
    m = re.search(r"/collections/([^/?#]+)", url)
    if m:
        return m.group(1).strip().lower()
    try:
        path = urlparse(url).path.rstrip("/")
        return path.split("/")[-1].strip().lower()
    except Exception:
        return ""


def _has_query_noise(url: Optional[str]) -> bool:
    # Sort/filter/paginated variants of the same collection.
    return bool(url) and bool(re.search(r"[?&](sort_by|sort|page|filter|constraint|grid|view)=", url, re.I))


def canonical_category(title: Optional[str], url: Optional[str],
                       category_map: Optional[Dict[str, set]] = None) -> Optional[str]:
    cmap = category_map or DEFAULT_CATEGORY_MAP
    blob = f"{(title or '').lower()} {_handle(url)}".replace("-", " ")
    best = None
    for canon, kws in cmap.items():
        if any(kw in blob for kw in kws):
            best = canon
            break
    return best


def _is_junk(col: Dict[str, Any]) -> bool:
    h = _handle(col.get("url"))
    if not h:
        return True
    if h in JUNK_HANDLES:
        return True
    if _has_query_noise(col.get("url")):
        return True
    return False


def _score(col: Dict[str, Any], nav_handles: set) -> float:
    score = 0.0
    h = _handle(col.get("url"))
    if col.get("inNav") or h in nav_handles:
        score += 40
    pc = col.get("productCount") or col.get("product_count") or 0
    try:
        score += min(40.0, float(pc) / 5.0)  # 200+ products maxes this out
    except Exception:
        pass
    if canonical_category(col.get("title"), col.get("url")):
        score += 15  # a recognizable category is worth more than a misc listing
    try:
        score += float(col.get("importance") or 0)
    except Exception:
        pass
    return score


def _ai_prioritize(cleaned: List[Dict[str, Any]], cap: int) -> Optional[List[Dict[str, Any]]]:
    """Pro only: ask a cheap model which collections matter most to track. Since Pro
    has no human in the loop, this adds judgment the heuristic can't (e.g. hero
    categories vs filler). Best-effort — returns None to fall back to the heuristic."""
    try:
        from level1_detector.ai_assist import ai_json, ai_enabled  # type: ignore
    except Exception:
        return None
    if not ai_enabled() or len(cleaned) <= cap:
        return None
    # Give the model a compact list (handle + title + product count).
    items = [{"i": i, "title": c.get("title") or _handle(c.get("url")),
              "handle": _handle(c.get("url")), "products": c.get("productCount") or 0}
             for i, c in enumerate(cleaned)]
    system = ("You prioritise e-commerce collections for competitive tracking. Pick the "
              "collections that best represent the store's core assortment and buying "
              "intent — hero product categories over filler, seasonal, or duplicate listings.")
    user = ("From this list, return the indexes of the "
            f"{cap} most important collections to track, most important first, as JSON "
            '{"order":[indexes]}. Only use indexes present in the list.\n\n'
            + json.dumps(items)[:8000])
    out = ai_json(system, user, max_tokens=700)
    order = (out or {}).get("order")
    if not isinstance(order, list) or not order:
        return None
    seen, ranked = set(), []
    for idx in order:
        if isinstance(idx, int) and 0 <= idx < len(cleaned) and idx not in seen:
            seen.add(idx)
            ranked.append(cleaned[idx])
    # Append any the model omitted (heuristic order) so we never lose coverage.
    for i, c in enumerate(cleaned):
        if i not in seen:
            ranked.append(c)
    return ranked[: max(0, cap)] if ranked else None


def select_collections_for_complete_site(
    collections: List[Dict[str, Any]],
    cap: int = 95,
    nav_handles: Optional[List[str]] = None,
    use_ai: bool = False,
) -> List[Dict[str, Any]]:
    """Dedupe junk/duplicate collections, rank by importance, return the top `cap`.
    When use_ai and only when the list exceeds the cap, a cheap model re-prioritises
    (Pro's no-human selection); otherwise pure heuristic."""
    navset = {str(h).strip().lower() for h in (nav_handles or [])}
    seen_handles = set()
    cleaned: List[Dict[str, Any]] = []
    for col in collections or []:
        if not isinstance(col, dict) or _is_junk(col):
            continue
        h = _handle(col.get("url"))
        if h in seen_handles:
            continue
        seen_handles.add(h)
        cleaned.append(col)

    cleaned.sort(key=lambda c: _score(c, navset), reverse=True)

    if use_ai:
        ai_ranked = _ai_prioritize(cleaned, cap)
        if ai_ranked:
            return ai_ranked
    return cleaned[: max(0, cap)]


def auto_pair_collections(
    user_collections: List[Dict[str, Any]],
    competitor_collections: List[Dict[str, Any]],
    category_map: Optional[Dict[str, set]] = None,
) -> Dict[str, Any]:
    """Pair collections across two sites by canonical category. The representative
    (largest by product count) collection per category on each side is paired;
    unmatched categories become assortment gaps."""
    def _by_category(cols):
        buckets: Dict[str, Dict[str, Any]] = {}
        for c in cols or []:
            if not isinstance(c, dict) or _is_junk(c):
                continue
            cat = canonical_category(c.get("title"), c.get("url"), category_map)
            if not cat:
                continue
            cur = buckets.get(cat)
            if not cur or (c.get("productCount") or 0) > (cur.get("productCount") or 0):
                buckets[cat] = c
        return buckets

    u = _by_category(user_collections)
    c = _by_category(competitor_collections)

    pairs = []
    for cat in sorted(set(u) & set(c)):
        pairs.append({
            "category": cat,
            "userUrl": u[cat].get("url"),
            "userTitle": u[cat].get("title"),
            "competitorUrl": c[cat].get("url"),
            "competitorTitle": c[cat].get("title"),
        })
    user_only = sorted(set(u) - set(c))
    competitor_only = sorted(set(c) - set(u))
    return {
        "pairs": pairs,
        "userOnlyCategories": user_only,
        "competitorOnlyCategories": competitor_only,
        "pairedCount": len(pairs),
    }
