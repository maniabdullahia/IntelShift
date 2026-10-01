import axios from "axios";
import pythonApi from "../python.api.js";

const analyzeUrl = async (url) => {
    try {
        // A single page can legitimately take a while: JS-heavy pages need a
        // Playwright render, and collection pages also follow pagination. The
        // default 60s was too tight and timed those out — give it real headroom.
        const response = await pythonApi.post('/v1/analyze-page', { url }, { timeout: 240000 });
        return response.data;
    } catch (error) {
        console.error('Error analyzing URL:', error);
        throw error;
    }
}

// Probe a URL for regional storefronts / currencies (store_locale_v1) so the
// app can ask the user which store to track, instead of geolocating automatically.
const detectStores = async (url) => {
    try {
        // Allow extra time: the probe may escalate to a Playwright render to
        // capture JS-built country/currency selectors (default python timeout is 60s).
        const response = await pythonApi.post('/v1/detect-stores', { url }, { timeout: 120000 });
        return response.data;
    } catch (error) {
        console.error('Error detecting stores:', error);
        throw error;
    }
}

// Discover an ecommerce store's policy/info pages (shipping, returns, payment,
// FAQ) so they can be auto-analyzed even though nobody selects them to track.
// Pass the homepage's footer/nav links + platform (already crawled) to avoid an
// extra fetch. Returns [{ type, url, source }] (possibly empty). Best-effort.
const discoverPolicyPages = async ({ url, footerLinks = [], navLinks = [], platform = "" }) => {
    try {
        const response = await pythonApi.post(
            '/v1/policy-pages',
            { url, footerLinks, navLinks, platform },
            { timeout: 45000 }
        );
        return Array.isArray(response.data?.pages) ? response.data.pages : [];
    } catch (error) {
        console.warn('discoverPolicyPages failed (continuing):', error?.message || error);
        return [];
    }
}

// Pro complete-site: rank/cap the most important collections (no manual page
// picking) and, when competitorCollections are supplied, auto-pair them across the
// two sites by canonical category. Products come from the bulk catalog, so this is
// collections-only. Returns { selected, pairing? }; never throws.
const proAutoselect = async ({ collections = [], navHandles = [], cap = 95, competitorCollections = null, useAi = false }) => {
    try {
        const response = await pythonApi.post(
            '/v1/pro-autoselect',
            { collections, navHandles, cap, competitorCollections, useAi },
            { timeout: 60000 }
        );
        return response.data || { selected: [], selectedCount: 0 };
    } catch (error) {
        console.warn('proAutoselect failed (continuing):', error?.message || error);
        return { selected: [], selectedCount: 0 };
    }
}

// Growth+: suggest product-to-product matches within a chosen collection pair.
// Local similarity always; useAi adds a cheap-model confirmation pass. Suggestion-
// only — the user confirms. Returns { suggestions, source, count }; never throws.
const suggestProductMatches = async ({ userProducts = [], competitorProducts = [], useAi = false }) => {
    try {
        const response = await pythonApi.post(
            '/v1/suggest-product-matches',
            { userProducts, competitorProducts, useAi },
            { timeout: 45000 }
        );
        return response.data || { suggestions: [], source: "heuristic", count: 0 };
    } catch (error) {
        console.warn('suggestProductMatches failed (continuing):', error?.message || error);
        return { suggestions: [], source: "heuristic", count: 0 };
    }
}

// Scale/marketplace gateway — decide self-serve vs enterprise for a store.
// Marketplace-first (denylist + structural signals via robots), size only as a high
// backstop. Node computes the true catalog total; Python makes the decision.
// Returns { scaleTier, isMarketplace, totalProducts, reason } (never throws).
// BUSINESS_TYPE_ALLOWLIST (comma-separated registrable names, e.g. "gymshark,khaadi")
// lets support release a store wrongly classified as Type 1/2 (Enterprise)
// without a code change. Extra signals (brandModel, industryCount, regionCount,
// marketplaceMarker) come from the onboarding store profile.
const checkScale = async ({ url, platform = "", totalProducts = null, vendorCount = null, config = {}, ...signals }) => {
    const allowlist = String(process.env.BUSINESS_TYPE_ALLOWLIST || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
    const cfg = { ...(allowlist.length ? { allowlist } : {}), ...config };
    try {
        const response = await pythonApi.post(
            '/v1/scale-check',
            { url, platform, totalProducts, vendorCount, config: cfg, ...signals },
            { timeout: 30000 }
        );
        return response.data || { scaleTier: "self_serve", isMarketplace: false, totalProducts, reason: "no_response" };
    } catch (error) {
        console.warn('checkScale failed (allowing):', error?.message || error);
        // Fail-open: never block a real customer because the gate errored.
        return { scaleTier: "self_serve", isMarketplace: false, totalProducts, reason: "gate_error" };
    }
}

// Marketplace / multinational-brand lists from the Python business-type
// classifier, so suggestions exclude the same giants the onboarding gate blocks.
// Cached for an hour; null if Python is unreachable (callers keep built-ins).
let _btLists = null;
let _btListsAt = 0;
const getBusinessTypeLists = async () => {
    if (_btLists && Date.now() - _btListsAt < 3600_000) return _btLists;
    try {
        const response = await pythonApi.get('/v1/business-type/lists', { timeout: 10000 });
        _btLists = response.data || null;
        _btListsAt = Date.now();
        return _btLists;
    } catch (error) {
        console.warn('getBusinessTypeLists failed:', error?.message || error);
        return _btLists;
    }
}

// DEBUG — returns exactly what the crawler fetched for a URL (method, status,
// title, text snippet, per-attempt log). Reserve enough time for a Playwright
// fallback. Not used by the app flow; powers the /debug-fetch inspector route.
const debugFetch = async (url) => {
    const response = await pythonApi.post('/v1/debug-fetch', { url }, { timeout: 120000 });
    return response.data;
}

// Onboarding site-readiness check — confirms we can read homepage + a collection +
// a product (rendering JS sites in a real browser), and returns the currency. Slow
// by design (can render several pages), so give it a generous timeout.
const validateSite = async (url) => {
    const response = await pythonApi.post('/v1/validate-site', { url }, { timeout: 240000 });
    return response.data;
}

// Lean category read from a rendered homepage — fallback for competitor suggestion
// when /collections.json is Cloudflare-blocked and the full catalog render is slow.
// Renders one page, so bound it to ~60s. Returns { categories, currency } or nulls.
const quickCatalog = async (url) => {
    try {
        const response = await pythonApi.post('/v1/quick-catalog', { url }, { timeout: 60000 });
        return response.data || {};
    } catch (e) {
        console.warn('quickCatalog failed (continuing):', e?.message || e);
        return { categories: [], currency: null };
    }
}

// ── Catalog cache (per origin, TTL) ─────────────────────────────────────────
// The catalog fetch (collections + products + nav MENU) is the slow part of
// onboarding — the menu extraction can escalate to a real browser render (10–25s).
// It's requested more than once per store: the competitor suggester needs it, and
// so does recon. We cache the in-flight PROMISE by origin so concurrent callers
// share ONE fetch, and warm it early (on detect-stores) so it's ready by the time
// suggestion runs. Emptiness is never cached — a failed/blocked read can retry.
const _catalogCache = new Map(); // origin -> { at, promise }
const CATALOG_TTL_MS = 15 * 60 * 1000;

const _originOf = (u) => {
    try {
        return new URL(String(u).startsWith("http") ? u : `https://${u}`).origin;
    } catch {
        return String(u || "");
    }
};

// Cached wrapper around getCatalog, keyed by origin. Use this everywhere in the
// onboarding path so the catalog is fetched once and reused.
const getCatalogCached = (url, maxProducts = 1000) => {
    const key = _originOf(url);
    const hit = _catalogCache.get(key);
    if (hit && Date.now() - hit.at < CATALOG_TTL_MS) return hit.promise;

    const promise = getCatalog(key, maxProducts)
        .then((cat) => {
            const ok = cat && (cat.menu?.length || cat.collections?.length || cat.products?.length);
            // Don't cache an empty/blocked result — let a later call try again.
            if (!ok) _catalogCache.delete(key);
            return cat;
        })
        .catch((err) => {
            _catalogCache.delete(key);
            throw err;
        });

    _catalogCache.set(key, { at: Date.now(), promise });
    return promise;
};

// Fire-and-forget warm: kick off the catalog fetch early (e.g. the moment the
// owner's URL is probed at the profile step) so it's cached before it's needed.
const warmCatalog = (url) => {
    try {
        getCatalogCached(url).catch(() => {});
    } catch {
        /* ignore */
    }
};

// Fast, direct Shopify collections read. /collections.json is a public, quick
// endpoint (plain JSON, no browser render), so it returns the store's real
// category collections in ~1s — unlike the full catalog, whose nav-menu
// extraction can escalate to Playwright and blow past any onboarding timeout.
// Used to seed the competitor search reliably. Returns [{title, handle,
// productsCount}] or [] (non-Shopify, Cloudflare-blocked, or error).
const getShopifyCollectionsFast = async (url) => {
    const origin = _originOf(url);
    if (!origin) return [];
    try {
        const res = await axios.get(`${origin}/collections.json?limit=250`, {
            timeout: 9000,
            maxRedirects: 3,
            validateStatus: () => true,
            headers: {
                "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                Accept: "application/json,text/plain,*/*",
            },
        });
        if (res.status !== 200 || !res.data || !Array.isArray(res.data.collections)) return [];
        return res.data.collections
            .map((c) => ({ title: c.title, handle: c.handle, productsCount: c.products_count }))
            .filter((c) => c.title);
    } catch {
        return [];
    }
};

// Fast, direct WooCommerce categories read — the Store API
// (/wp-json/wc/store/v1/products/categories) is PUBLIC on modern WooCommerce and
// returns product categories as plain JSON in ~1s, the direct analog of Shopify's
// /collections.json. Returns [{title, slug, productsCount}] or [] (not
// WooCommerce, Store API disabled, or error).
const getWooCommerceCategoriesFast = async (url) => {
    const origin = _originOf(url);
    if (!origin) return [];
    try {
        const res = await axios.get(`${origin}/wp-json/wc/store/v1/products/categories?per_page=100`, {
            timeout: 9000,
            maxRedirects: 3,
            validateStatus: () => true,
            headers: {
                "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                Accept: "application/json,text/plain,*/*",
            },
        });
        if (res.status !== 200 || !Array.isArray(res.data)) return [];
        return res.data
            .map((c) => ({ title: c.name, slug: c.slug, productsCount: c.count }))
            // Keep categories that actually hold products (Store API sets count).
            .filter((c) => c.title && (c.productsCount == null || c.productsCount > 0));
    } catch {
        return [];
    }
};

// Platform-agnostic fast category seed: try Shopify, then WooCommerce. Returns
// [{title, ...}] or [] so the caller falls back to the heavy catalog only when
// neither fast path applies (Wix / Squarespace / custom, or blocked).
const getStoreCategoriesFast = async (url) => {
    const shop = await getShopifyCollectionsFast(url);
    if (shop.length) return shop;
    return await getWooCommerceCategoriesFast(url);
};

// Fast price + assortment sample for competitor SIMILARITY scoring. Reads one page
// of products straight from the public JSON API (Shopify /products.json or the Woo
// Store API) — ~1s, no browser. Returns { prices:[numbers], titles:[strings],
// count } so callers can compare price band + assortment + a rough catalog-size
// floor between two stores. Empty/zero on non-Shopify/Woo, blocked, or error
// (callers must down-weight, never crash).
const _UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const sampleStorePrices = async (url, limit = 100) => {
    const origin = _originOf(url);
    const empty = { prices: [], titles: [], count: 0 };
    if (!origin) return empty;
    // Shopify first.
    try {
        const res = await axios.get(`${origin}/products.json?limit=${limit}`, {
            timeout: 9000, maxRedirects: 3, validateStatus: () => true,
            headers: { "User-Agent": _UA, Accept: "application/json,text/plain,*/*" },
        });
        const products = res.status === 200 && res.data && Array.isArray(res.data.products) ? res.data.products : null;
        if (products && products.length) {
            const prices = [];
            const titles = [];
            for (const p of products) {
                if (p.title) titles.push(String(p.title));
                const v = Array.isArray(p.variants) ? p.variants[0] : null;
                const price = v && v.price != null ? parseFloat(v.price) : NaN;
                if (Number.isFinite(price) && price > 0) prices.push(price);
            }
            return { prices, titles, count: products.length };
        }
    } catch { /* fall through to Woo */ }
    // WooCommerce Store API.
    try {
        const res = await axios.get(`${origin}/wp-json/wc/store/v1/products?per_page=${limit}`, {
            timeout: 9000, maxRedirects: 3, validateStatus: () => true,
            headers: { "User-Agent": _UA, Accept: "application/json,text/plain,*/*" },
        });
        const products = res.status === 200 && Array.isArray(res.data) ? res.data : null;
        if (products && products.length) {
            const prices = [];
            const titles = [];
            for (const p of products) {
                if (p.name) titles.push(String(p.name));
                const pr = p.prices || {};
                const minor = typeof pr.currency_minor_unit === "number" ? pr.currency_minor_unit : 2;
                const raw = pr.price != null ? parseFloat(pr.price) : NaN;
                const price = Number.isFinite(raw) ? raw / Math.pow(10, minor) : NaN;
                if (Number.isFinite(price) && price > 0) prices.push(price);
            }
            return { prices, titles, count: products.length };
        }
    } catch { /* not Shopify/Woo, or blocked */ }
    return empty;
};

// AUTHORITATIVE store currency — the store's CONFIGURED currency straight from its
// platform API, not an HTML guess. This is the reliable answer for stores whose
// homepage shows no priced products (empty cart only) or sit on a gTLD, where the
// heuristics have nothing to read. WooCommerce's Store API exposes it on every
// product (prices.currency_code); Shopify's is already read from the page, so this
// targets the WooCommerce gap. Returns an ISO code or null.
const getStoreCurrencyFast = async (url) => {
    const origin = _originOf(url);
    if (!origin) return null;

    // Some hosts prepend PHP warnings/HTML to the JSON body (broken plugins), so
    // locate the JSON array/object rather than trusting a clean parse.
    const pickJson = (data) => {
        if (data && typeof data === "object") return data;
        if (typeof data === "string") {
            const a = data.indexOf("[{");
            const o = data.indexOf('{"');
            const cands = [a, o].filter((n) => n >= 0);
            if (cands.length) {
                try {
                    return JSON.parse(data.slice(Math.min(...cands)));
                } catch {
                    return null;
                }
            }
        }
        return null;
    };

    try {
        const res = await axios.get(`${origin}/wp-json/wc/store/v1/products?per_page=1`, {
            timeout: 9000,
            maxRedirects: 3,
            validateStatus: () => true,
            headers: {
                "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                Accept: "application/json,text/plain,*/*",
            },
        });
        const data = pickJson(res.data);
        const arr = Array.isArray(data) ? data : Array.isArray(data?.products) ? data.products : null;
        const code = arr && arr[0] && arr[0].prices && arr[0].prices.currency_code;
        if (typeof code === "string" && /^[A-Za-z]{3}$/.test(code)) return code.toUpperCase();
    } catch {
        /* ignore — not WooCommerce, blocked, or no products */
    }
    return null;
};

// Robustly fetch a Shopify store's collections + products (real titles +
// product_type) via the Python browser path, so onboarding page discovery gets
// reliable names even on Cloudflare-protected stores. Returns {collections, products}.
const getCatalog = async (url, maxProducts = 1000) => {
    try {
        // May escalate to a real browser (Playwright) if cloudscraper is blocked,
        // so allow generous time (default python timeout is 60s).
        const response = await pythonApi.post(
            '/v1/catalog',
            { url, maxProducts },
            { timeout: 120000 }
        );
        return response.data;
    } catch (error) {
        console.error('Error fetching catalog:', error?.message || error);
        return { success: false, platform: null, collections: [], products: [] };
    }
}

// Fast, browserless storefront probe for competitor-suggestion verification.
// Uses cloudscraper on the Python side to clear Cloudflare, so it reads
// Shopify/Woo JSON that a plain Node request gets 403'd on. Returns
// {reachable, platform, categories, productTypes, hasPricing}.
const probeStore = async (url, allowBrowser = false) => {
    try {
        const response = await pythonApi.post(
            '/v1/store-probe',
            { url, allowBrowser },
            // Probe does catalog + homepage fetches; browser fallback needs more.
            { timeout: allowBrowser ? 60000 : 22000 }
        );
        return response.data;
    } catch (error) {
        // 404 here means the Python /store-probe route isn't live (server needs a
        // restart) — very different from a candidate site being blocked. Surface it.
        const status = error?.response?.status;
        console.warn(
            `probeStore failed for ${url}: ${status ? `HTTP ${status}` : error?.code || error?.message || "error"}` +
                (status === 404 ? " — is the Python server restarted with /store-probe?" : "")
        );
        return { success: false, reachable: false, platform: null, categories: [], productTypes: [], hasPricing: false };
    }
}

// LIVE product count for one collection/category — what the storefront actually
// shows ("Showing N products"), not Shopify's inflated products_count. Used by the
// onboarding page-picker to budget selections against the plan. Returns a number
// or null (platforms/pages where a live count can't be read).
const getCollectionCount = async (url) => {
    try {
        const response = await pythonApi.post('/v1/collection-count', { url }, { timeout: 20000 });
        const n = response?.data?.count;
        return typeof n === "number" && n >= 0 ? n : null;
    } catch (error) {
        console.warn(`getCollectionCount failed for ${url}: ${error?.response?.status || error?.message || "error"}`);
        return null;
    }
}

// EXACT store-wide product total — one honest number, not the sum of per-collection
// counts (which double-counts any product shelved in multiple collections and badly
// inflates the total). Two cheap, exact sources:
//   • WooCommerce/WordPress — the WP REST/Store API returns the collection size in
//     the `X-WP-Total` response header, so one request with per_page=1 is enough.
//   • Shopify — the product sitemap(s) list every product URL exactly once, so we
//     count `/products/` <loc> entries across the product sitemaps (a few fetches,
//     no per-product pagination).
// Returns a number or null (unknown platform / blocked / no sitemap).
const getStoreProductTotal = async (url, platform = "", { earlyExit = 250000 } = {}) => {
    const origin = _originOf(url);
    if (!origin) return null;
    const headers = {
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        Accept: "application/json,text/xml,application/xml,text/plain,*/*",
    };
    const p = String(platform || "").toLowerCase();
    const maybeWoo = !p || p.includes("woo") || p.includes("word");
    const maybeShopify = !p || p.includes("shop");

    // WooCommerce / WordPress — exact total from the pagination header.
    if (maybeWoo) {
        try {
            const res = await axios.get(`${origin}/wp-json/wc/store/v1/products?per_page=1`, {
                timeout: 9000, maxRedirects: 3, validateStatus: () => true, headers,
            });
            const n = Number(res.headers?.["x-wp-total"]);
            if (Number.isFinite(n) && n > 0) return n;
        } catch { /* not Woo / blocked */ }
    }

    // Shopify — count product URLs across the product sitemap files.
    if (maybeShopify) {
        try {
            const idx = await axios.get(`${origin}/sitemap.xml`, {
                timeout: 9000, maxRedirects: 3, validateStatus: () => true, headers,
            });
            if (idx.status === 200 && typeof idx.data === "string") {
                const files = [...idx.data.matchAll(/<loc>\s*([^<\s]*sitemap_products_[^<\s]*)\s*<\/loc>/gi)].map((m) => m[1].trim());
                let total = 0;
                // Raised cap + early-exit: normal brand stores finish in a handful of
                // files; a genuinely enormous catalog stops counting as soon as it
                // crosses the backstop (we only need "≥ backstop", not the exact figure).
                for (const f of files.slice(0, 80)) {
                    try {
                        const sm = await axios.get(f, { timeout: 9000, maxRedirects: 3, validateStatus: () => true, headers });
                        if (sm.status === 200 && typeof sm.data === "string") {
                            total += (sm.data.match(/<loc>[^<]*\/products\//gi) || []).length;
                        }
                    } catch { /* skip this sitemap file */ }
                    if (total >= earlyExit) return total; // early-exit: over the line, stop counting
                }
                if (total > 0) return total;
            }
        } catch { /* no sitemap / blocked */ }
    }

    // Fallback — the store is likely Cloudflare-fronted, so the plain fetch above is
    // blocked. Reuse the browserful Python live-count on the "all products" listing
    // (/collections/all on Shopify, /shop on WooCommerce), which clears Cloudflare.
    try {
        if (maybeShopify) {
            const n = await getCollectionCount(`${origin}/collections/all`);
            if (typeof n === "number" && n > 0) return n;
        }
        if (maybeWoo) {
            const n = await getCollectionCount(`${origin}/shop`);
            if (typeof n === "number" && n > 0) return n;
        }
    } catch { /* live-count unavailable */ }
    return null;
};

// Lightweight reachability check for a single URL. Returns the HTTP status number,
// or null on a network error/timeout (inconclusive). Only a definitive 404 should
// be treated as "page gone" — 403/timeouts are usually Cloudflare blocking the
// checker, not a dead page, so callers must not treat those as offline.
const checkUrlStatus = async (url) => {
    const target = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    try {
        const res = await axios.get(target, {
            timeout: 10000,
            maxRedirects: 5,
            validateStatus: () => true,
            headers: {
                "User-Agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        });
        return res.status;
    } catch {
        return null;
    }
};

export {
    analyzeUrl,
    detectStores,
    debugFetch,
    discoverPolicyPages,
    checkScale,
    getBusinessTypeLists,
    proAutoselect,
    suggestProductMatches,
    validateSite,
    quickCatalog,
    getCatalog,
    getCatalogCached,
    getShopifyCollectionsFast,
    getWooCommerceCategoriesFast,
    getStoreCategoriesFast,
    sampleStorePrices,
    getStoreCurrencyFast,
    getStoreProductTotal,
    checkUrlStatus,
    warmCatalog,
    probeStore,
    getCollectionCount,
}