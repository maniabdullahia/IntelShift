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
import { classifyTaxonomy } from "../../utils/taxonomy.js";
import { llmComplete, parseJsonLoose } from "../../utils/llm.js";
import { profileFromReadiness, rememberProfile, domainKey } from "./storeProfile.service.js";

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
export const UNSUPPORTED_LANGUAGE_MESSAGE =
    "IntelShift currently supports English-language stores only, and this store's content isn't in English.";
const ENTERPRISE_MESSAGES = {
    1: "This is a large marketplace (many sellers, a very large catalog). Marketplaces like this are handled on our Enterprise plan — contact us to set it up.",
    2: "This is a global / multinational brand. Brands at this scale are handled on our Enterprise plan — contact us to set it up.",
};

/**
 * Run the readiness check + scale gateway for a URL.
 * @returns the raw readiness payload with `.scale` attached
 *          ({ ok, stages, currency, platform, fetched, scale }).
 */
export const checkSiteReadiness = async (url) => {
    const result = await validateSiteApi(url);

    if (result && result.fetched !== false) {

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

        // Step 4 — Industry → Category → Subcategory (AI picks from the fixed
        // taxonomy; keyword fallback). Also yields the single/multi-brand read
        // that Step 2 needs. Only for readable English stores.
        const sample = result.catalogSample || {};
        if (result.ok) {
            try {
                result.taxonomy = await classifyTaxonomy({
                    domain: domainKey(url),
                    categories: (result.categories || []).map((c) => c.name),
                    productTypes: sample.productTypes || [],
                    titles: sample.titles || [],
                    vendors: sample.vendorsTop || [],
                    llm: llmComplete,
                    parseJson: parseJsonLoose,
                });
            } catch (taxErr) {
                console.warn("taxonomy skipped:", taxErr?.message || taxErr);
                result.taxonomy = null;
            }
        }

        // Step 2 — business type (Types 1–5) + the self-serve/enterprise gate.
        // Runs even for unreadable sites: Amazon blocks bots, but the user must
        // see "contact us", not "we couldn't read it". Fail-open on gate error.
        try {
            const platform = result.platform || result.displayPlatform || sample.source || "";
            const totalProducts = await getStoreProductTotal(url, platform);
            result.scale = await checkScale({
                url,
                platform,
                totalProducts,
                vendorCount: sample.vendorCount ?? null,
                brandModel: result.taxonomy?.brandModel ?? null,
                industryCount: result.taxonomy?.industryCount ?? null,
                regionCount: result.signals?.regionCount ?? null,
                marketplaceMarker: result.signals?.marketplaceMarker ?? null,
            });
        } catch (scaleErr) {
            console.warn("scale gate skipped (allowing):", scaleErr?.message || scaleErr);
            result.scale = { scaleTier: "self_serve", isMarketplace: false, totalProducts: null, reason: "gate_error" };
        }

        // Remember the profile so creating the workspace/competitor right after
        // validation can persist it without re-crawling.
        result.profile = profileFromReadiness(result);
        if (result.ok) rememberProfile(url, result.profile);
    }

    return result;
};

/**
 * Turn a readiness payload into a pass/fail verdict with a user-facing reason,
 * mirroring the onboarding client's messaging so the experience is identical
 * wherever a competitor is added.
 * @returns { ok:true, currency, accessStatus, accessIssues, profile }
 *        | { ok:false, code: "ENTERPRISE"|"UNSUPPORTED_LANGUAGE"|"UNREADABLE", message, scale?, englishAlternate? }
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
                ENTERPRISE_MESSAGES[result.scale.businessType] ||
                "This store is too large for self-serve monitoring (a marketplace or enterprise-scale catalog). Contact us to set it up.",
        };
    }

    if (result?.unsupportedLanguage || result?.language?.isEnglish === false) {
        const alt = result?.language?.englishAlternate;
        return {
            ok: false,
            code: "UNSUPPORTED_LANGUAGE",
            englishAlternate: alt || null,
            message: alt
                ? `${UNSUPPORTED_LANGUAGE_MESSAGE} It has an English version — try ${alt}`
                : UNSUPPORTED_LANGUAGE_MESSAGE,
        };
    }

    if (result?.ok) {
        // Readable. "incomplete" = part of the journey (search / cart /
        // checkout) is blocked — we continue, but record it so reports say so
        // instead of assuming.
        return {
            ok: true,
            currency: result.currency || "",
            accessStatus: result.accessStatus === "incomplete" ? "incomplete" : "complete",
            accessIssues: result.accessIssues || [],
            profile: result.profile || null,
        };
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
