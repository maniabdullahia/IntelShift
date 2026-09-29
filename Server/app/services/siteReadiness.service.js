// siteReadiness.service.js — the SINGLE onboarding-grade "can we actually read
// this store?" gate. Confirms the homepage + a collection + a product page are
// reachable (rendering JS sites in a real browser), reads the currency, and runs
// the scale/marketplace gateway. Used by the /validate-site endpoint AND by every
// flow that adds or replaces a competitor, so a protected / unreadable /
// enterprise-scale site (e.g. fabletics.com behind bot protection) is rejected
// EVERYWHERE — not just during onboarding.

import {
    validateSite as validateSiteApi,
    getStoreProductTotal,
    checkScale,
    getStoreCategoriesFast,
} from "../../api/python/analyzer.js";

// A store's /collections.json (and Woo's category list) is its full BACKEND set —
// polluted with admin, meta/smart, promo and seasonal collections that aren't real
// product categories a shopper (or the user) would pick as a "focus". This drops
// them so the onboarding Focus step shows real categories (Bottoms, Leggings, Tops)
// instead of "All Products", "40% Off and Above" or "…- DO NOT DELETE".
const _JUNK_CATEGORY_RE = new RegExp([
    // admin / internal
    "do not delete", "\\btest\\b", "hidden", "draft", "\\bwip\\b", "internal", "staging",
    // meta / whole-catalog / smart collections
    "^all products", "all products", "excluding outlet", "full[- ]?priced", "^all$",
    "shop all", "everything", "^featured", "^new(\\b| in| arrivals)", "best ?sellers?",
    "^products$", "catalog", "collabs?-?allproducts",
    // promo / discount / merchandising
    "% ?off", "\\d+ ?extra off", "off and above", "best of sale", "\\bsale\\b",
    "clearance", "outlet", "\\bdeals?\\b", "bundle", "wishlist", "build your",
    // gifting / seasonal editorial
    "gift ?card", "^gifts? for", "gifts? under", "\\$\\d", "back to school",
    "airport", "christmas", "black friday", "cyber", "valentine", "summer sale",
    "winter sale", "^shop by", "^best of", "essentials? collection",
].join("|"), "i");

const _isRealCategory = (name) => {
    const n = String(name || "").trim();
    if (n.length < 2 || n.length > 45) return false;
    return !_JUNK_CATEGORY_RE.test(n);
};

// Canonical, blocker-respecting failure messages. Kept here as the single source
// of truth so the onboarding gate and the add/replace gate read identically.
export const BLOCKED_MESSAGE =
    "We couldn't access this store — it uses bot protection or access rules (robots.txt / Cloudflare) that block automated reading. IntelShift respects those protections and doesn't bypass them, so this site can't be monitored.";
export const GENERAL_UNREADABLE_MESSAGE =
    "We couldn't fully read this store. It likely uses access protection that stops automated reading — and we respect that, so it can't be monitored. Please try a different store URL.";

/**
 * Run the readiness check + scale gateway for a URL.
 * @returns the raw readiness payload with `.scale` attached
 *          ({ ok, stages, currency, platform, fetched, scale }).
 */
export const checkSiteReadiness = async (url) => {
    const result = await validateSiteApi(url);

    // Scale/marketplace gateway — best-effort + fail-open, so a gate error never
    // blocks a real store. Only when the site validated (fetchable).
    if (result && result.fetched !== false) {
        try {
            const platform = result.platform || result.displayPlatform || "";
            const totalProducts = await getStoreProductTotal(url, platform);
            result.scale = await checkScale({ url, platform, totalProducts });
        } catch (scaleErr) {
            console.warn("scale gate skipped (allowing):", scaleErr?.message || scaleErr);
            result.scale = { scaleTier: "self_serve", isMarketplace: false, totalProducts: null, reason: "gate_error" };
        }

        // Detected categories for the onboarding "focus categories" step — fast
        // Shopify/Woo read (~1s). Empty for custom/JS/blocked stores, in which case
        // the focus step falls back to "analyze all". Sorted by product count so the
        // top categories lead; deduped by name; capped for a clean picker.
        try {
            const raw = await getStoreCategoriesFast(url);
            const seen = new Set();
            const mapped = (raw || [])
                .filter((c) => c && c.title)
                .map((c) => ({
                    name: String(c.title).trim(),
                    handle: c.handle || c.slug || null,
                    productCount: typeof c.productsCount === "number" ? c.productsCount : null,
                }))
                .filter((c) => {
                    const k = c.name.toLowerCase();
                    if (!c.name || seen.has(k)) return false;
                    seen.add(k);
                    return true;
                });
            // Drop backend junk (admin/meta/promo/seasonal) so the Focus step shows
            // real product categories. Fall back to the unfiltered list only if the
            // filter would leave it empty (a store with only meta collections).
            const real = mapped.filter((c) => _isRealCategory(c.name));
            result.categories = (real.length ? real : mapped)
                .sort((a, b) => (b.productCount ?? -1) - (a.productCount ?? -1))
                .slice(0, 70);
        } catch (catErr) {
            console.warn("category read skipped:", catErr?.message || catErr);
            result.categories = [];
        }
    }

    return result;
};

/**
 * Turn a readiness payload into a pass/fail verdict with a user-facing reason,
 * mirroring the onboarding client's messaging so the experience is identical
 * wherever a competitor is added.
 * @returns { ok:true, currency } | { ok:false, code, message, scale? }
 */
export const readinessVerdict = (result) => {
    // Giants (Amazon/Daraz) and marketplaces can't be self-served — route to
    // "talk to us", even if the site itself is readable.
    if (result?.scale?.scaleTier === "enterprise") {
        return {
            ok: false,
            code: "ENTERPRISE",
            scale: result.scale,
            message:
                "This store is too large for self-serve monitoring (a marketplace or enterprise-scale catalog). Contact us to set it up.",
        };
    }

    if (result?.ok) {
        return { ok: true, currency: result.currency || "" };
    }

    // We DON'T surface the raw stage reason ("couldn't open a product page") — that
    // reads like our crawler failed. In practice these failures are almost always a
    // site that blocks automated access (bot protection / Cloudflare / robots rules),
    // so we frame it that way: IntelShift respects those protections and doesn't try
    // to bypass them. Homepage-level failure = clearly blocked; a later-stage failure
    // gets the softer general wording (may be protection, or just not a standard
    // shoppable store we can read end-to-end).
    const s = result?.stages || {};
    const message = !s.homepage?.ok ? BLOCKED_MESSAGE : GENERAL_UNREADABLE_MESSAGE;
    return { ok: false, code: "UNREADABLE", message };
};

export default checkSiteReadiness;
