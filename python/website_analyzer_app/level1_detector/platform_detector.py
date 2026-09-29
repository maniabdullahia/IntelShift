import re


# ============================================================
# USER-FACING PLATFORM LABELS
# ------------------------------------------------------------
# `platform` (below) is an INTERNAL routing key — it decides which analyzer
# runs (only Shopify / WordPress / Wix have dedicated analyzers; everything
# else routes to "Unknown"). That routing key must never be shown to users:
# "Unknown" only means "no dedicated analyzer", not "no technology".
#
# `displayPlatform` is the human-facing label. It names the real tech stack we
# detected (React, Magento, Webflow, …) even when the site routes to the
# Unknown analyzer, and falls back to a friendly term when we genuinely can't
# tell — never the bare word "Unknown".
# ============================================================

UNDETECTED_LABEL = "Custom / Undetected"

_PLATFORM_LABELS = {
    "Shopify": "Shopify",
    "WordPress": "WordPress",
    "WooCommerce / WordPress": "WooCommerce (WordPress)",
    "Wix": "Wix",
    "Webflow": "Webflow",
    "Magento": "Magento",
    "Next.js / React": "React / Next.js",
    "React": "React",
    "Vue": "Vue.js",
    "HubSpot CMS": "HubSpot CMS",
    "Squarespace": "Squarespace",
    "BigCommerce": "BigCommerce",
}

# Frameworks / CMSes we can confidently NAME for display even though they route
# to the Unknown analyzer. Ordered by how specific/telling the signal is.
_DISPLAYABLE_FRAMEWORKS = [
    "Magento", "Webflow", "Squarespace", "BigCommerce",
    "Next.js / React", "React", "Vue", "HubSpot CMS",
]


def _friendly_label(name):
    if not name or name == "Unknown":
        return UNDETECTED_LABEL
    return _PLATFORM_LABELS.get(name, name)


def _best_display_from_scores(scores, min_score=2):
    """Highest-scoring nameable framework for display, or None if none qualify."""
    best, best_score = None, min_score - 1
    for fw in _DISPLAYABLE_FRAMEWORKS:
        s = scores.get(fw, 0)
        if s > best_score:
            best, best_score = fw, s
    return _friendly_label(best) if best else None


def detect_platform(html: str, url: str, headers: dict):
    html_l = (html or "").lower()
    url_l = (url or "").lower()
    headers_l = str(headers or {}).lower()

    # ============================================================
    # TIER 1 — DEFINITIVE PLATFORM STRUCTURE (checked FIRST, decides instantly)
    # ------------------------------------------------------------
    # Each known platform leaves infrastructure fingerprints that CANNOT appear
    # on a site not built with it: its own CDN, asset paths, JS globals or
    # response headers. If any are present we decide immediately and skip the
    # heuristic scoring entirely. Only Shopify / WordPress / Wix have dedicated
    # analyzers; WooCommerce runs on WordPress, so it maps to the WordPress
    # analyzer. Everything else is handled by the Unknown analyzer.
    # ============================================================
    # EXCLUSIVE infrastructure only — a CDN host, hosted domain, or platform
    # response header that literally cannot appear unless the site IS served by
    # Shopify. Deliberately EXCLUDES JS globals (window.shopify, Shopify.routes,
    # Shopify.theme) and embed classes (shopify-payment-button, shopify-checkout-
    # api-token): a clone can define those globals to mimic Shopify, and any site
    # can drop in a Shopify Buy Button — so they must NOT single-handedly force the
    # Shopify analyzer. They still count in the Tier-2 heuristic (shopify_signals),
    # where a guess with no infra is downgraded to Unknown.
    shopify_definitive = [
        "cdn.shopify.com", "shopifycdn.com", "/cdn/shop/", "myshopify.com",
        "monorail-edge.shopifysvc",
        "x-shopify", "x-shopid", "x-shopify-stage", "x-sorting-hat-shopid",
    ]
    wordpress_definitive = [
        "/wp-content/", "wp-content/themes", "wp-content/uploads",
        "wp-content/plugins", "/wp-includes/", "/wp-json/", "wp-emoji",
        "wp-block-", "wp-embed.min.js",
        # WooCommerce (WordPress-based -> WordPress analyzer)
        "wp-content/plugins/woocommerce", "wc-cart-fragments", "wc-ajax",
        "woocommerce-page", "woocommerce-store-api",
    ]
    wix_definitive = [
        "static.wixstatic.com", "static.parastorage.com", "wixstatic.com",
        "parastorage.com", "wix-thunderbolt", "wix-warmup-data",
        "wixsite.com", "wixstores", "_wixcssstates", "x-wix",
    ]

    def _count_definitive(signals):
        return sum(1 for s in signals if s in html_l or s in url_l or s in headers_l)

    definitive_counts = {
        "Shopify": _count_definitive(shopify_definitive),
        "WordPress": _count_definitive(wordpress_definitive),
        "Wix": _count_definitive(wix_definitive),
    }
    definitive_hits = {k: v for k, v in definitive_counts.items() if v > 0}

    if definitive_hits:
        # Most infrastructure markers wins; ties resolved by a stable priority
        # (self-hosted WordPress paths are the strongest signal).
        _priority = {"WordPress": 3, "Shopify": 2, "Wix": 1}
        platform = max(definitive_hits, key=lambda k: (definitive_hits[k], _priority[k]))
        is_headless = platform == "Shopify" and any(
            s in html_l for s in ("__next_data__", "/_next/static", "data-reactroot", "react-dom")
        )
        return {
            "platform": platform,
            "displayPlatform": _friendly_label(platform),
            "platformConfidence": 0.98,
            "isKnownPlatform": True,
            "isHeadless": is_headless,
            "platformSignals": {**definitive_counts, "_tier": "definitive"},
        }

    # ============================================================
    # TIER 2 — HEURISTIC FALLBACK (only reached when NO definitive structure)
    # ------------------------------------------------------------
    # No known-platform infrastructure was found, so the site is NOT Shopify,
    # WordPress or Wix. The scoring below recognises other frameworks (all routed
    # to the Unknown analyzer) and exposes diagnostic signals. Any known-platform
    # guess made here is downgraded to Unknown at the final decision.
    # ============================================================

    scores = {
        "Shopify": 0,
        "WooCommerce / WordPress": 0,
        "WordPress": 0,
        "Wix": 0,
        "Webflow": 0,
        "Magento": 0,
        "Next.js / React": 0,
        "React": 0,
        "Vue": 0,
        "HubSpot CMS": 0,
        "Squarespace": 0,
        "BigCommerce": 0
    }

    shopify_signals = [
        "cdn.shopify.com", "shopify.theme", "shopify.routes",
        "window.shopify", "shopify.shop", "shopify-checkout-api-token",
        "myshopify.com", "shopify-section", "/cart.js", "/cart/add",
        "shopify-payment-button", "shopify-buy", "shopify-features",
        "shopifyanalytics", "shopify_pay", "shopify-checkout-api-token",
        "shopify-analytics", "shopify_analytics", "shopify_marketing",
        "shopify_essential", "shopify.designmode", "shopify.country",
        "powered-by\":\"shopify", "powered-by': 'shopify",
        "powered-by': \"shopify", "powered-by=shopify"
    ]

    wordpress_signals = [
        "wp-content/", "wp-includes/", "/wp-json/",
        "wp-emoji-release", "wordpress.org", "wp-block-"
    ]

    woocommerce_signals = [
        "woocommerce", "wc-cart-fragments", "wp-content/plugins/woocommerce",
        "woocommerce-page", "woocommerce-product", "woocommerce-cart",
        "woocommerce-checkout", "add_to_cart_button",
        "single_add_to_cart_button", "wc-ajax", "?add-to-cart="
    ]

    wix_signals = [
        "static.wixstatic.com", "static.parastorage.com", "wix-code",
        "wixsite.com", "wixstores", "x-wix", "wix-thunderbolt",
        "wix-window", "wix-bi"
    ]

    # Keep Webflow strict. Some enterprise/custom sites may include
    # website-files CDN assets without being true Webflow sites.
    webflow_signals = [
        "webflow.js",
        "webflow.io",
        "uploads-ssl.webflow.com",
        "w-webflow-badge"
    ]

    magento_signals = [
        "magento", "mage/cookies", "static/frontend", "mageplaza",
        "mage-cache", "mage-cache-storage", "customer-data.js",
        "catalog/product/view", "checkout/cart"
    ]

    next_signals = [
        "__next_data__", "/_next/static", "next-head-count",
        "_next/image", "__next_f", "next-router"
    ]

    react_signals = [
        "data-reactroot", "react-dom", "reactroot", "__react",
        "react.development.js", "react.production.min.js"
    ]

    # CMS markers: only present when the page is BUILT ON HubSpot CMS.
    hubspot_signals = [
        "hs_cos_wrapper", "hubspot-wrapper", "hs-menu-wrapper",
        "hubspotusercontent",
    ]
    # Embed markers: forms/tracking scripts that ANY site can include
    # (e.g. anthropic.com embeds HubSpot forms but is not HubSpot CMS).
    hubspot_embed_signals = [
        "hs-scripts.com", "hs-analytics.net", "hs-banner.com",
        "hsforms.net", "hsforms.com",
    ]

    squarespace_signals = [
        "squarespace.com", "static1.squarespace.com", "sqs-block",
        "squarespace-cdn.com", "sqs-layout",
    ]

    bigcommerce_signals = [
        "bigcommerce.com", "cdn11.bigcommerce.com", "stencil-utils",
        "bigcommerce.stencil",
    ]

    vue_signals = [
        "vue.js", "__vue__", "data-v-", "vue-router", "vuex"
    ]

    signal_map = {
        "Shopify": shopify_signals,
        "WordPress": wordpress_signals,
        "WooCommerce / WordPress": woocommerce_signals,
        "Wix": wix_signals,
        "Webflow": webflow_signals,
        "Magento": magento_signals,
        "Next.js / React": next_signals,
        "React": react_signals,
        "Vue": vue_signals,
        "HubSpot CMS": hubspot_signals,
        "Squarespace": squarespace_signals,
        "BigCommerce": bigcommerce_signals
    }

    for platform, signals in signal_map.items():
        for signal in signals:
            if signal in html_l or signal in url_l or signal in headers_l:
                scores[platform] += 1

    # HubSpot embeds (forms/tracking) add at most +1 total: they indicate
    # HubSpot MARKETING usage, not that the site is built on HubSpot CMS.
    if any(sig in html_l or sig in headers_l for sig in hubspot_embed_signals):
        scores["HubSpot CMS"] += 1

    # -------------------------
    # Strong header boosts
    # -------------------------

    if "x-shopify" in headers_l:
        scores["Shopify"] += 6

    if "powered-by" in headers_l and "shopify" in headers_l:
        scores["Shopify"] += 6

    if "server-timing" in headers_l and "pagetype;desc=" in headers_l:
        scores["Shopify"] += 5

    if "page_cache:" in headers_l and (
        "collectiondetailscontroller" in headers_l
        or "productdetailscontroller" in headers_l
        or "indexcontroller" in headers_l
    ):
        scores["Shopify"] += 6

    if "x-request-id" in headers_l and "shopify" in headers_l:
        scores["Shopify"] += 3

    if "x-wix" in headers_l:
        scores["Wix"] += 5

    # wixstatic.com / parastorage.com CDN URLs are exclusive to Wix -- very strong signal
    if "static.wixstatic.com" in html_l or "static.parastorage.com" in html_l:
        scores["Wix"] += 4

    if "x-powered-by" in headers_l and "next.js" in headers_l:
        scores["Next.js / React"] += 5

    if "x-magento" in headers_l:
        scores["Magento"] += 5

    # -------------------------
    # Shopify asset / route boosts
    # -------------------------

    if "/cdn/shop/" in html_l or "/cdn/shop/" in headers_l:
        scores["Shopify"] += 5

    if (
        re.search(r"/cdn/shop/t/\d+/assets/", html_l)
        or re.search(r"/cdn/shop/t/\d+/assets/", headers_l)
    ):
        scores["Shopify"] += 5

    if "section-main-product.css" in html_l or "section-main-product.css" in headers_l:
        scores["Shopify"] += 4

    if "section-main-collection.css" in html_l or "section-main-collection.css" in headers_l:
        scores["Shopify"] += 4

    if "/products/" in url_l:
        scores["Shopify"] += 3

    if "/collections/" in url_l:
        scores["Shopify"] += 3

    if "/blogs/" in url_l:
        scores["Shopify"] += 2

    # -------------------------
    # WordPress hosting override
    # -------------------------
    # wp-content/ and /wp-json/ are definitive WordPress server-side signals —
    # they cannot appear on Shopify or Wix infrastructure.  When present, add a
    # strong WordPress boost and cancel any Shopify URL-path bonus that was
    # awarded solely because the URL path looks Shopify-like (/products/, etc.).
    wp_definitive = "wp-content/" in html_l or "/wp-json/" in html_l
    if wp_definitive:
        scores["WordPress"] += 4
        scores["Shopify"] = max(0, scores["Shopify"] - 3)
        scores["Wix"] = max(0, scores["Wix"] - 3)

    if "myshopify.com" in url_l:
        scores["Shopify"] += 6

    if "wixsite.com" in url_l:
        scores["Wix"] += 5

    # Webflow URL-only boost. Do not boost just because CDN assets exist.
    if "webflow.io" in url_l:
        scores["Webflow"] += 5

    # -------------------------
    # Ecommerce route boosts
    # -------------------------

    if "/product/" in url_l or "/product-category/" in url_l:
        if scores["WooCommerce / WordPress"] > 0 or scores["WordPress"] > 0:
            scores["WooCommerce / WordPress"] += 2

    if "wp-content/plugins/woocommerce" in html_l:
        scores["WooCommerce / WordPress"] += 4

    # -------------------------
    # Conflict handling
    # -------------------------

    if scores["WooCommerce / WordPress"] >= 2:
        scores["WordPress"] = max(0, scores["WordPress"] - 3)

    if scores["Wix"] >= 2:
        scores["React"] = max(0, scores["React"] - 3)
        scores["Next.js / React"] = max(0, scores["Next.js / React"] - 1)

    if scores["Next.js / React"] >= 2:
        scores["React"] = max(0, scores["React"] - 3)

    # Shopify + React/Next co-occurrence = headless storefront (Shopify
    # backend, React frontend). Shopify wins the vote; remember the topology.
    is_headless = False
    if scores["Shopify"] >= 3 and scores["Next.js / React"] >= 2:
        is_headless = True
        scores["Next.js / React"] = max(0, scores["Next.js / React"] - 3)

    if scores["Shopify"] >= 3 and scores["React"] >= 2:
        is_headless = True
        scores["React"] = max(0, scores["React"] - 3)

    # Webflow is no longer treated as a strong platform unless evidence is strong.
    strong_platforms = [
        "Shopify",
        "WooCommerce / WordPress",
        "WordPress",
        "Wix",
        "Magento"
    ]

    strong_detected = any(scores[p] >= 2 for p in strong_platforms)

    if strong_detected:
        scores["React"] = max(0, scores["React"] - 3)
        scores["Vue"] = max(0, scores["Vue"] - 3)

    # -------------------------
    # Webflow confidence guard
    # -------------------------

    has_strong_webflow_evidence = (
        "webflow.io" in url_l
        or "webflow.io" in headers_l
        or "webflow.io" in html_l
        or "webflow.js" in html_l
        or "w-webflow-badge" in html_l
        or "uploads-ssl.webflow.com" in html_l
    )

    if not has_strong_webflow_evidence:
        scores["Webflow"] = 0

    if scores["Webflow"] < 3 and "webflow.io" not in url_l:
        scores["Webflow"] = 0

    # -------------------------
    # Headless storefront detection (weak-signal net)
    # -------------------------
    # Catches headless stores whose Shopify signals were too weak (score 2)
    # for the strong rule above.
    _react_score = max(scores["Next.js / React"], scores["React"])
    if scores["Shopify"] >= 2 and _react_score >= 2:
        scores["Shopify"] += _react_score
        is_headless = True
    elif scores["BigCommerce"] >= 2 and _react_score >= 2:
        scores["BigCommerce"] += _react_score
        is_headless = True

    # Prefer Unknown over weak visual/framework/platform clues.
    max_score = max(scores.values())

    if max_score <= 2:
        weak_winner = max(scores, key=scores.get)

        if weak_winner in ["Webflow", "React", "Vue", "HubSpot CMS", "Squarespace", "BigCommerce"]:
            return {
                "platform": "Unknown",
                "displayPlatform": _best_display_from_scores(scores) or UNDETECTED_LABEL,
                "platformConfidence": 0.25,
                "isKnownPlatform": False,
                "isHeadless": is_headless,
                "platformSignals": {
                    **scores,
                    "Unknown": 1
                }
            }

    # -------------------------
    # Final decision
    # -------------------------

    platform = max(scores, key=scores.get)
    score = scores[platform]

    # Tier 1 would already have returned for a REAL known platform. Reaching
    # here means no definitive structure was found, so a heuristic guess of a
    # known platform is untrustworthy — its dedicated analyzer must NOT be used.
    if platform in ("Shopify", "WordPress", "WooCommerce / WordPress", "Wix"):
        return {
            "platform": "Unknown",
            "displayPlatform": _best_display_from_scores(scores) or UNDETECTED_LABEL,
            "platformConfidence": 0.30,
            "isKnownPlatform": False,
            "isHeadless": False,
            "platformSignals": {**scores, "_tier": "heuristic-downgraded"},
        }

    if score <= 0:
        platform = "Unknown"
        confidence = 0.20
    elif score == 1:
        confidence = 0.45
    elif score == 2:
        confidence = 0.65
    elif score == 3:
        confidence = 0.78
    else:
        confidence = min(0.95, 0.78 + ((score - 3) * 0.04))

    if platform in _DISPLAYABLE_FRAMEWORKS and score >= 2:
        display_platform = _friendly_label(platform)
    else:
        display_platform = _best_display_from_scores(scores) or UNDETECTED_LABEL

    return {
        "platform": platform,
        "displayPlatform": display_platform,
        "platformConfidence": confidence,
        "isKnownPlatform": platform not in ("Unknown",),
        "isHeadless": is_headless,
        "platformSignals": scores
    }
