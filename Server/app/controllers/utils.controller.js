import axios from "axios";

import getImportantPagesFast from "../../utils/pageExtractor.js"
import UrlTree from "../../utils/urlTree.js";
import { detectStores as detectStoresApi, debugFetch as debugFetchApi, getCatalog, getCatalogCached, getStoreCategoriesFast, warmCatalog, getStoreCurrencyFast, getCollectionCount, suggestProductMatches } from "../../api/python/analyzer.js";
import { checkSiteReadiness } from "../services/siteReadiness.service.js";
import { suggestCompetitors as suggestCompetitorsService } from "../services/competitorSuggest.service.js";


function buildTreeFromResult(result) {
    const tree = new UrlTree({
        pagesToExclude: ["home"],
    });
    tree.insert(result);
    return tree.toJSON();
}

const buildTree = async (req, res) => {
    const { url } = req.body;
    if (!url) {
        return res.status(400).json({ error: "URL is required" });
    }
    // Fetch the Shopify catalog (real names + product_type) via the Python
    // browser path — reliable even on Cloudflare-protected stores, where a plain
    // Node request gets challenged intermittently. Best-effort: on failure the
    // extractor falls back to sitemap/nav discovery.
    let catalog = null;
    try {
        const cat = await getCatalog(url);
        // Use the catalog whenever it returned anything (Shopify OR WooCommerce).
        if (cat && (cat.menu?.length || cat.collections?.length || cat.products?.length)) catalog = cat;
    } catch {
        catalog = null;
    }
    const allowedPages = await getImportantPagesFast(url, { catalog });
    const tree = await buildTreeFromResult(allowedPages);
    res.json(tree);
}

const validateUrl = async (req, res) => {
    const { url } = req.body;

    if (!url) {
        return res.status(400).json({ message: "URL is required" });
    }

    let normalizedUrl;

    try {
        normalizedUrl = new URL(url).toString();
    } catch {
        return res.status(400).json({ message: "Invalid URL" });
    }

    try {
        const response = await axios.get(normalizedUrl, {
            timeout: 15000,
            maxRedirects: 5,
            validateStatus: () => true,
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        });

        if (response.status === 404) {
            return res.status(404).json({ message: "Website returned 404 Not Found" });
        }

        if (response.status >= 400) {
            return res.status(response.status).json({
                message: `Website could not be verified. Server returned ${response.status}.`,
            });
        }

        return res.json({ exists: true, status: response.status, url: normalizedUrl });
    } catch (error) {
        return res.status(502).json({
            message:
                error?.response?.statusText ||
                error?.message ||
                "Unable to verify website availability",
        });
    }
}



// Detect regional storefronts / currencies for a URL, so the onboarding UI can
// let the user confirm WHICH store (country) and currency to track. Returns
// store_locale_v1 (stores[], currencies[], current, multiRegion, multiCurrency).
const detectStores = async (req, res) => {
    const { url } = req.body;
    if (!url) {
        return res.status(400).json({ message: "URL is required" });
    }
    try {
        const result = await detectStoresApi(url);

        // Authoritative currency check — read the store's CONFIGURED currency from
        // its platform API instead of guessing from the page/URL. This fixes stores
        // whose homepage shows no priced products (so nothing visible to read) and
        // gTLD stores with no ccTLD hint. When found, it overrides the HTML-derived
        // currency (the platform config is the source of truth) and is surfaced in
        // the currencies list so the picker offers it.
        try {
            const authCurrency = await getStoreCurrencyFast(url);
            if (authCurrency && result && typeof result === "object") {
                if (result.current && typeof result.current === "object") {
                    result.current.currency = authCurrency;
                }
                if (Array.isArray(result.currencies)) {
                    if (!result.currencies.includes(authCurrency)) {
                        result.currencies.unshift(authCurrency);
                    }
                } else {
                    result.currencies = [authCurrency];
                }
                result.signals = Array.isArray(result.signals)
                    ? [...new Set([...result.signals, "store_api_currency"])]
                    : ["store_api_currency"];
            }
        } catch (curErr) {
            console.warn("authoritative currency check failed (continuing):", curErr?.message || curErr);
        }

        // Warm the catalog (collections + nav menu) for this store NOW, while the
        // user is still on the profile/competitor screens. The competitor suggester
        // needs the nav L1/L2 as its search seed; warming here means it reads a
        // ready cache instead of losing a cold fetch to its timeout. Fire-and-forget.
        warmCatalog(url);
        return res.json(result);
    } catch (error) {
        return res.status(502).json({
            message:
                error?.response?.data?.detail?.error ||
                error?.message ||
                "Unable to detect regional stores for this website",
        });
    }
}


// DEBUG — inspect exactly what the crawler fetches for a URL: the raw HTML view
// (method, status, title, text snippet) AND the category-API signals the
// competitor suggester reads. Lets you see WHY a store gets no/incorrect category.
// POST { url }. Not part of the app flow — a diagnostic aid.
const debugFetch = async (req, res) => {
    const { url } = req.body;
    if (!url) {
        return res.status(400).json({ message: "URL is required" });
    }
    const origin = (() => { try { return new URL(url.startsWith("http") ? url : `https://${url}`).origin; } catch { return url; } })();
    const out = { url, origin };

    // 1) Raw fetch view — what the browser/crawler actually saw.
    try {
        out.rawFetch = await debugFetchApi(url);
    } catch (e) {
        out.rawFetch = { error: e?.message || String(e) };
    }

    // 2) Category signals — the fast platform APIs the suggester reads for the
    //    store's categories. Empty here = the "wrong/blind category" cause.
    try {
        const fast = await getStoreCategoriesFast(origin);
        out.categoriesFast = { count: fast.length, titles: fast.map((c) => c.title).slice(0, 30) };
    } catch (e) {
        out.categoriesFast = { error: e?.message || String(e) };
    }

    // 3) Catalog (nav menu + product types + collections) — the fallback seed.
    try {
        const cat = await Promise.race([
            getCatalogCached(origin),
            new Promise((r) => setTimeout(() => r(null), 20000)),
        ]);
        out.catalog = cat
            ? {
                menuCount: (cat.menu || []).length,
                collectionCount: (cat.collections || []).length,
                productCount: (cat.products || []).length,
                collectionsSample: (cat.collections || []).map((c) => c.title).filter(Boolean).slice(0, 30),
                productTypesSample: [...new Set((cat.products || []).map((p) => p.product_type).filter(Boolean))].slice(0, 30),
            }
            : { note: "catalog fetch returned nothing (blocked, JS-only, non-standard platform, or timed out)" };
    } catch (e) {
        out.catalog = { error: e?.message || String(e) };
    }

    return res.json(out);
}


// Onboarding readiness gate — confirm we can actually read the site (homepage +
// collection + product) before letting the user confirm it. Returns the staged
// result + currency so the client can block "Next" and pre-fill the currency.
const validateSite = async (req, res) => {
    const { url } = req.body;
    if (!url) {
        return res.status(400).json({ message: "URL is required" });
    }
    try {
        // Shared readiness + scale gate (also used when adding/replacing a
        // competitor, so the checks are identical everywhere).
        const result = await checkSiteReadiness(url);
        return res.json(result);
    } catch (error) {
        return res.status(502).json({
            message:
                error?.response?.data?.detail?.error ||
                error?.message ||
                "Unable to validate this website",
        });
    }
}


// Suggest direct competitors for the user's store (LLM + verification).
const suggestCompetitors = async (req, res) => {
    const { url, industry, pages, currency, categories } = req.body;
    if (!url) {
        return res.status(400).json({ message: "URL is required" });
    }
    try {
        const suggestions = await suggestCompetitorsService(url, industry, pages || [], currency || "", categories || []);
        return res.json({ success: true, suggestions });
    } catch (error) {
        console.error("suggestCompetitors error:", error?.message || error);
        return res.status(502).json({ success: false, message: "Unable to suggest competitors", suggestions: [] });
    }
}

// Suggest product-to-product matches within a chosen collection pair. Local
// similarity always runs; useAi adds a cheap-model confirmation (Growth+).
// Suggestion-only — the client shows accept/reject; nothing is auto-asserted.
const productMatches = async (req, res) => {
    const { userProducts = [], competitorProducts = [], useAi = false } = req.body || {};
    if (!Array.isArray(userProducts) || !Array.isArray(competitorProducts)) {
        return res.status(400).json({ message: "userProducts and competitorProducts must be arrays", suggestions: [] });
    }
    try {
        const out = await suggestProductMatches({ userProducts, competitorProducts, useAi: !!useAi });
        return res.json({ success: true, ...out });
    } catch (error) {
        console.error("productMatches error:", error?.message || error);
        return res.status(502).json({ success: false, message: "Unable to suggest product matches", suggestions: [] });
    }
};

// Live product count for a single collection URL (lazy-loaded by the page picker).
const collectionCount = async (req, res) => {
    const { url } = req.body;
    if (!url) {
        return res.status(400).json({ message: "URL is required", count: null });
    }
    try {
        const count = await getCollectionCount(url);
        return res.json({ count });
    } catch (error) {
        console.error("collectionCount error:", error?.message || error);
        return res.status(502).json({ message: "Unable to get collection count", count: null });
    }
}

export {
    buildTree,
    validateUrl,
    detectStores,
    debugFetch,
    validateSite,
    suggestCompetitors,
    collectionCount,
    productMatches,
}