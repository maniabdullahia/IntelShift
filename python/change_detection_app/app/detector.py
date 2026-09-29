"""Same-site change detection engine (change_detection_v1).

Compares two site_snapshot_v2 files of the SAME site taken at different
times (e.g. weekly) and reports meaningful changes with severity scoring:

- catalog: products added / removed
- product: price change, sale started/ended, availability, rank, name/
  description changes, variant count
- collections: product count and price range shifts
- SaaS: pricing plans added/removed, plan price changes, billing changes
- site: platform / siteType change, page coverage, navigation changes
- homepage: positioning / feature toggles

Output includes an overall change score and a shouldSendToAI gate so the
weekly pipeline only spends AI tokens when something meaningful happened.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "change_detection_v1"

SEVERITY_SCORE = {"low": 10, "medium": 35, "high": 70, "critical": 100}
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "priceChangeThresholdPercent": 5.0,
    "bigPriceChangePercent": 15.0,
    "rankChangeThreshold": 3,
    "textSimilarityThreshold": 0.75,
    "ignoreLowChanges": False,
    "minimumSeverityForAI": "medium",
    "maxChangesInOutput": 300,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def text_changed(old: Any, new: Any, threshold: float) -> bool:
    a, b = clean(old).lower(), clean(new).lower()
    if not a and not b:
        return False
    if bool(a) != bool(b):
        return True
    return SequenceMatcher(None, a, b).ratio() < threshold


def product_key(product: Dict[str, Any]) -> str:
    url = clean(product.get("productUrl")).lower().rstrip("/")
    if url:
        return f"url::{url}"
    handle = clean(product.get("handle")).lower()
    if handle:
        return f"handle::{handle}"
    pid = clean(product.get("productId")).lower()
    if pid:
        return f"id::{pid}"
    return "name::" + clean(product.get("name")).lower()


def product_ref(product: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": product.get("name"),
        "productUrl": product.get("productUrl"),
        "category": product.get("category"),
    }


def price_of(product: Dict[str, Any]) -> Optional[float]:
    price = product.get("price")
    if isinstance(price, dict) and isinstance(price.get("current"), (int, float)):
        return float(price["current"])
    return None


def rank_of(product: Dict[str, Any]) -> Optional[int]:
    for sp in product.get("sourcePages") or []:
        if isinstance(sp, dict) and isinstance(sp.get("rank"), int):
            return sp["rank"]
    return None


def in_stock_of(product: Dict[str, Any]) -> Optional[bool]:
    availability = product.get("availability")
    if isinstance(availability, dict):
        return availability.get("inStock")
    return None


def change(type_: str, severity: str, why: str, **fields) -> Dict[str, Any]:
    return {"type": type_, "severity": severity, "whyImportant": why, **fields}


# ---------------------------------------------------------------------------
# Product-level diff
# ---------------------------------------------------------------------------

def diff_product(old: Dict[str, Any], new: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    ref = product_ref(new)

    old_price, new_price = price_of(old), price_of(new)
    if old_price and new_price and old_price != new_price:
        pct = (new_price - old_price) / old_price * 100
        if abs(pct) >= settings["priceChangeThresholdPercent"]:
            changes.append(change(
                "price_change",
                "high" if abs(pct) >= settings["bigPriceChangePercent"] else "medium",
                "Price moved beyond the configured threshold.",
                product=ref, oldValue=old_price, newValue=new_price,
                changePercent=round(pct, 2),
                direction="increase" if pct > 0 else "decrease",
            ))

    old_sale = bool((old.get("price") or {}).get("isOnSale")) if isinstance(old.get("price"), dict) else False
    new_sale = bool((new.get("price") or {}).get("isOnSale")) if isinstance(new.get("price"), dict) else False
    if old_sale != new_sale:
        discount = (new.get("price") or {}).get("discountPercent") if isinstance(new.get("price"), dict) else None
        changes.append(change(
            "sale_started" if new_sale else "sale_ended",
            "high",
            "Promotion state changed - a direct competitive pricing move.",
            product=ref, discountPercent=discount,
        ))

    old_stock, new_stock = in_stock_of(old), in_stock_of(new)
    if old_stock is not None and new_stock is not None and old_stock != new_stock:
        changes.append(change(
            "back_in_stock" if new_stock else "out_of_stock",
            "high" if not new_stock else "medium",
            "Stock availability changed.",
            product=ref, oldValue=old_stock, newValue=new_stock,
        ))

    old_rank, new_rank = rank_of(old), rank_of(new)
    if old_rank is not None and new_rank is not None:
        diff = old_rank - new_rank  # positive = moved up
        if abs(diff) >= settings["rankChangeThreshold"]:
            changes.append(change(
                "rank_change",
                "high" if abs(diff) >= 10 else "medium",
                "Listing position changed significantly - merchandising signal.",
                product=ref, oldRank=old_rank, newRank=new_rank, positionsMoved=diff,
            ))

    if text_changed(old.get("name"), new.get("name"), settings["textSimilarityThreshold"]):
        changes.append(change(
            "name_change", "medium",
            "Product renamed - possible repositioning or SEO change.",
            product=ref, oldValue=old.get("name"), newValue=new.get("name"),
        ))

    old_desc = (old.get("description") or {}).get("text") if isinstance(old.get("description"), dict) else old.get("shortDescription")
    new_desc = (new.get("description") or {}).get("text") if isinstance(new.get("description"), dict) else new.get("shortDescription")
    if old_desc and new_desc and text_changed(old_desc, new_desc, settings["textSimilarityThreshold"]):
        changes.append(change(
            "description_change", "low",
            "Product messaging changed significantly.",
            product=ref,
        ))

    old_var = len(old.get("variants") or []) or None
    new_var = len(new.get("variants") or []) or None
    if old_var and new_var and old_var != new_var:
        changes.append(change(
            "variant_count_change", "low",
            "Variant count changed - new shades, sizes or options.",
            product=ref, oldValue=old_var, newValue=new_var,
        ))

    return changes


# ---------------------------------------------------------------------------
# Section diffs
# ---------------------------------------------------------------------------

def diff_catalog(prev: Dict[str, Any], curr: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    old_products = {product_key(p): p for p in prev.get("products") or []}
    new_products = {product_key(p): p for p in curr.get("products") or []}

    for key in sorted(set(new_products) - set(old_products)):
        p = new_products[key]
        changes.append(change(
            "new_product", "high",
            "New product detected since the previous snapshot.",
            product=product_ref(p), price=price_of(p),
        ))
    for key in sorted(set(old_products) - set(new_products)):
        p = old_products[key]
        changes.append(change(
            "removed_product", "medium",
            "Previously seen product is no longer present in the analyzed pages.",
            product=product_ref(p),
        ))
    for key in sorted(set(old_products) & set(new_products)):
        changes.extend(diff_product(old_products[key], new_products[key], settings))
    return changes


def diff_collections(prev: Dict[str, Any], curr: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    old_cols = {clean(c.get("url")).lower(): c for c in (prev.get("site") or {}).get("collections") or []}
    new_cols = {clean(c.get("url")).lower(): c for c in (curr.get("site") or {}).get("collections") or []}
    for url in sorted(set(old_cols) & set(new_cols)):
        o, n = old_cols[url], new_cols[url]
        oc, nc = o.get("productCount"), n.get("productCount")
        if isinstance(oc, int) and isinstance(nc, int) and oc != nc:
            changes.append(change(
                "collection_size_change",
                "high" if abs(nc - oc) >= 5 else "medium",
                "Collection assortment size changed.",
                collection={"url": n.get("url"), "name": n.get("name")},
                oldValue=oc, newValue=nc, difference=nc - oc,
            ))
        op, np_ = (o.get("priceRange") or {}), (n.get("priceRange") or {})
        if op.get("min") and np_.get("min") and op["min"] != np_["min"]:
            changes.append(change(
                "collection_price_floor_change", "medium",
                "The cheapest price point in this collection moved.",
                collection={"url": n.get("url"), "name": n.get("name")},
                oldValue=op["min"], newValue=np_["min"],
            ))
    return changes


def diff_pricing_plans(prev: Dict[str, Any], curr: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """SaaS: compare site.pricingSummary and per-page pricing plans."""
    changes: List[Dict[str, Any]] = []

    def plans_of(snapshot):
        plans = {}
        for page in snapshot.get("pagesAnalyzed") or []:
            pricing = page.get("pricing") or (page.get("generalPage") or {}).get("pricing") or {}
            for pl in pricing.get("plans") or []:
                if isinstance(pl, dict) and pl.get("name"):
                    plans[clean(pl["name"]).lower()] = pl
        return plans

    old_plans, new_plans = plans_of(prev), plans_of(curr)
    if not old_plans and not new_plans:
        return changes

    for name in sorted(set(new_plans) - set(old_plans)):
        pl = new_plans[name]
        changes.append(change(
            "pricing_plan_added", "critical",
            "A new pricing plan appeared - packaging strategy changed.",
            plan={"name": pl.get("name"), "priceRaw": (pl.get("price") or {}).get("raw")},
        ))
    for name in sorted(set(old_plans) - set(new_plans)):
        pl = old_plans[name]
        changes.append(change(
            "pricing_plan_removed", "critical",
            "A pricing plan disappeared - packaging strategy changed.",
            plan={"name": pl.get("name")},
        ))
    for name in sorted(set(old_plans) & set(new_plans)):
        o_amt = ((old_plans[name].get("price") or {}).get("amount"))
        n_amt = ((new_plans[name].get("price") or {}).get("amount"))
        if isinstance(o_amt, (int, float)) and isinstance(n_amt, (int, float)) and o_amt != n_amt and o_amt > 0:
            pct = (n_amt - o_amt) / o_amt * 100
            changes.append(change(
                "plan_price_change", "critical" if abs(pct) >= 20 else "high",
                "A pricing plan price changed - direct monetization move.",
                plan={"name": new_plans[name].get("name")},
                oldValue=o_amt, newValue=n_amt, changePercent=round(pct, 2),
            ))
    return changes


def diff_site(prev: Dict[str, Any], curr: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    old_site, new_site = prev.get("site") or {}, curr.get("site") or {}

    # Prefer the user-facing tech label; fall back to the internal routing key.
    def _platform_label(site):
        return site.get("displayPlatform") or site.get("platform")

    old_platform = _platform_label(old_site)
    new_platform = _platform_label(new_site)
    _unconfident = {"", "unknown", "custom / undetected", "custom/undetected", "undetected"}
    platform_is_real_change = (
        old_platform and new_platform
        and old_platform != new_platform
        and str(old_platform).strip().lower() not in _unconfident
        and str(new_platform).strip().lower() not in _unconfident
    )
    if platform_is_real_change:
        changes.append(change(
            "platform_change", "high",
            "The site platform changed - likely a replatform/migration.",
            oldValue=old_platform, newValue=new_platform,
        ))

    if (old_site.get("siteType") and new_site.get("siteType")
            and old_site["siteType"] != new_site["siteType"]):
        changes.append(change(
            "siteType_change", "medium", "The detected business model changed.",
            oldValue=old_site["siteType"], newValue=new_site["siteType"],
        ))

    old_nav = set((old_site.get("navigation") or {}).get("topLabels") or [])
    new_nav = set((new_site.get("navigation") or {}).get("topLabels") or [])
    added, removed = sorted(new_nav - old_nav), sorted(old_nav - new_nav)
    if added or removed:
        changes.append(change(
            "navigation_change", "medium",
            "Main navigation changed - new categories or repositioned priorities.",
            addedLabels=added[:10], removedLabels=removed[:10],
        ))

    old_cats = set((old_site.get("catalog") or {}).get("categoriesDetected") or [])
    new_cats = set((new_site.get("catalog") or {}).get("categoriesDetected") or [])
    cat_added, cat_removed = sorted(new_cats - old_cats), sorted(old_cats - new_cats)
    if cat_added:
        changes.append(change(
            "categories_added", "high",
            "New product categories detected - assortment expansion.",
            categories=cat_added[:10],
        ))
    if cat_removed:
        changes.append(change(
            "categories_removed", "medium",
            "Previously seen categories are gone from the analyzed pages.",
            categories=cat_removed[:10],
        ))
    return changes


# Human labels + severity for each homepage capability, so a toggle reads as
# "Newsletter capture was added to the homepage" rather than a generic message.
_HOMEPAGE_FEATURE_META = {
    "hasNewsletter": ("Newsletter capture", "medium"),
    "hasVideo": ("Video content", "medium"),
    "hasDiscountMessaging": ("Discount messaging", "medium"),
    "hasTrustSignals": ("Trust signals", "medium"),
    "hasHero": ("Hero banner", "medium"),
    "hasAnnouncementBar": ("Announcement bar", "medium"),
    "hasTestimonials": ("Testimonials", "low"),
    "hasBlogPreview": ("Blog / content", "low"),
    "hasInstagramFeed": ("Instagram feed", "low"),
    "hasWhatsapp": ("WhatsApp", "low"),
    "hasCollectionBanners": ("Collection banners", "low"),
    "hasFeaturedProducts": ("Featured products", "low"),
    "hasFeaturedCollections": ("Featured collections", "low"),
}


def _humanize_feature(key: str) -> str:
    s = str(key or "")
    if s.startswith("has"):
        s = s[3:]
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s).strip()
    return (s[:1].upper() + s[1:]) if s else "Homepage feature"


def diff_homepage(prev: Dict[str, Any], curr: Dict[str, Any], settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []

    def homepage_of(snapshot):
        for page in snapshot.get("pagesAnalyzed") or []:
            if page.get("pageType") == "homepage":
                return page
        return {}

    old_hp, new_hp = homepage_of(prev), homepage_of(curr)
    if not old_hp or not new_hp:
        return changes

    old_hero = ((old_hp.get("homepageStrategy") or {}).get("hero") or {}).get("headline") or \
               ((old_hp.get("summary") or {}).get("positioning") or [None])[0]
    new_hero = ((new_hp.get("homepageStrategy") or {}).get("hero") or {}).get("headline") or \
               ((new_hp.get("summary") or {}).get("positioning") or [None])[0]
    if old_hero and new_hero and text_changed(old_hero, new_hero, settings["textSimilarityThreshold"]):
        changes.append(change(
            "hero_message_change", "high",
            "Homepage hero message changed - positioning/campaign shift.",
            oldValue=old_hero, newValue=new_hero,
        ))

    old_features = old_hp.get("features") or {}
    new_features = new_hp.get("features") or {}
    for key in sorted(set(old_features) | set(new_features)):
        o, n = bool(old_features.get(key)), bool(new_features.get(key))
        if o != n:
            label, sev = _HOMEPAGE_FEATURE_META.get(key, (_humanize_feature(key), "low"))
            changes.append(change(
                "homepage_feature_toggled", sev,
                f"{label} was {'added to' if n else 'removed from'} the homepage.",
                feature=key, featureLabel=label, oldValue=o, newValue=n,
            ))
    return changes


# ---------------------------------------------------------------------------
# Scoring + entry point
# ---------------------------------------------------------------------------

def summarize(changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {"totalChanges": len(changes), "criticalChanges": 0, "highChanges": 0,
              "mediumChanges": 0, "lowChanges": 0}
    by_type: Dict[str, int] = {}
    for c in changes:
        counts[f"{c.get('severity', 'low')}Changes"] = counts.get(f"{c.get('severity', 'low')}Changes", 0) + 1
        by_type[c["type"]] = by_type.get(c["type"], 0) + 1
    counts["changesByType"] = dict(sorted(by_type.items(), key=lambda x: -x[1]))
    return counts


def change_score(changes: List[Dict[str, Any]]) -> int:
    if not changes:
        return 0
    # Weighted: the strongest changes dominate; volume adds a little.
    scores = sorted((SEVERITY_SCORE.get(c.get("severity", "low"), 10) for c in changes), reverse=True)
    top = scores[:5]
    base = sum(top) / len(top)
    volume_bonus = min(15, max(0, len(changes) - 5))
    return min(100, round(base + volume_bonus))


def severity_from_score(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def detect_changes(
    previous_snapshot: Dict[str, Any],
    current_snapshot: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Diff two site_snapshot_v2 dicts of the same site."""
    cfg = {**DEFAULT_SETTINGS, **(settings or {})}

    old_domain = (previous_snapshot.get("site") or {}).get("domain")
    new_domain = (current_snapshot.get("site") or {}).get("domain")
    warnings: List[str] = []
    if old_domain and new_domain and old_domain != new_domain:
        warnings.append(
            f"Snapshots are from DIFFERENT domains ({old_domain} vs {new_domain}). "
            "Change detection expects two snapshots of the same site."
        )

    # ── Extraction-stability guard ─────────────────────────────────────────
    # If the SAME page was fetched by different methods (e.g. normal crawl vs
    # Jina fallback) between the two runs, catalog differences may be
    # extraction artifacts rather than real changes. Warn and dampen.
    extraction_unstable = False
    old_pages = {clean(p.get("url")).lower(): p for p in previous_snapshot.get("pagesAnalyzed") or []}
    new_pages = {clean(p.get("url")).lower(): p for p in current_snapshot.get("pagesAnalyzed") or []}
    for url in set(old_pages) & set(new_pages):
        o_crawl = old_pages[url].get("crawl") or {}
        n_crawl = new_pages[url].get("crawl") or {}
        o_ext = (old_pages[url].get("source") or {}).get("extractor")
        n_ext = (new_pages[url].get("source") or {}).get("extractor")
        if bool(o_crawl.get("crawlBlocked")) != bool(n_crawl.get("crawlBlocked")) or (
            o_ext and n_ext and o_ext != n_ext
        ):
            extraction_unstable = True
            warnings.append(
                f"Extraction method changed between runs for {url} "
                f"(blocked: {bool(o_crawl.get('crawlBlocked'))} -> {bool(n_crawl.get('crawlBlocked'))}, "
                f"extractor: {o_ext} -> {n_ext}). "
                "Product add/remove changes may be extraction artifacts, not real site changes."
            )
    missing_pages = set(old_pages) - set(new_pages)
    if missing_pages:
        extraction_unstable = True
        warnings.append(
            "Pages present in the previous run are missing from the current run: "
            + ", ".join(sorted(missing_pages)[:5])
            + ". Removed-product changes for those pages are unreliable."
        )

    changes: List[Dict[str, Any]] = []
    changes.extend(diff_site(previous_snapshot, current_snapshot))
    changes.extend(diff_catalog(previous_snapshot, current_snapshot, cfg))
    changes.extend(diff_collections(previous_snapshot, current_snapshot))
    changes.extend(diff_pricing_plans(previous_snapshot, current_snapshot, cfg))
    changes.extend(diff_homepage(previous_snapshot, current_snapshot, cfg))

    # When extraction is unstable, add/remove signals are untrustworthy:
    # downgrade them to low severity so they don't trigger AI sends or alarms.
    if extraction_unstable:
        for c in changes:
            if c["type"] in ("new_product", "removed_product", "collection_size_change",
                             "categories_added", "categories_removed"):
                c["severity"] = "low"
                c["unreliable"] = True
                c["whyImportant"] += " (LOW CONFIDENCE: extraction method changed between runs.)"

    if cfg["ignoreLowChanges"]:
        changes = [c for c in changes if c.get("severity") != "low"]

    changes.sort(key=lambda c: -SEVERITY_ORDER.get(c.get("severity", "low"), 1))
    truncated = len(changes) > cfg["maxChangesInOutput"]
    changes = changes[: cfg["maxChangesInOutput"]]

    score = change_score(changes)
    overall = severity_from_score(score)
    should_send = SEVERITY_ORDER.get(overall, 1) >= SEVERITY_ORDER.get(cfg["minimumSeverityForAI"], 2)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now_iso(),
        "domain": new_domain or old_domain,
        "previousGeneratedAt": previous_snapshot.get("generatedAt"),
        "currentGeneratedAt": current_snapshot.get("generatedAt"),
        "overallSeverity": overall,
        "changeScore": score,
        "shouldSendToAI": should_send,
        "summary": summarize(changes),
        "changes": changes,
        "changesTruncated": truncated,
        "extractionStable": not extraction_unstable,
        "warnings": warnings,
        "aiPromptHint": (
            "These are deterministic week-over-week changes for one site. "
            "Explain what the site owner should notice and do; do not invent changes."
        ),
    }
