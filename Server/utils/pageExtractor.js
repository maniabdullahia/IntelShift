import axios from "axios";
import robotsParser from "robots-parser";
import * as cheerio from "cheerio";
import fs from "fs";

// A real browser UA — Shopify/Cloudflare block generic bot agents on the JSON
// endpoints (products.json / collections.json), which left us with URL-only
// data (no titles). This makes those endpoints serve us the real titles.
const USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

const DEFAULT_OPTIONS = {
  timeout: 20000,
  maxSitemaps: 25,
  maxTotalUrls: 1200,
  // Show the catalog, capped so a huge store can't make the picker/tree
  // unusable or the fetch crawl forever. 1000 covers virtually every real store.
  maxProducts: 1000,
  maxCollections: 400,
  maxServices: 80,
  maxPricing: 20,
  maxOtherPages: 200,
  respectRobots: true,
  returnGrouped: true
};

function normalizeSiteUrl(siteUrl) {
  const url = new URL(siteUrl.startsWith("http") ? siteUrl : `https://${siteUrl}`);
  return url.origin;
}

function cleanUrl(rawUrl) {
  try {
    const url = new URL(rawUrl.trim());

    url.hash = "";

    for (const key of [...url.searchParams.keys()]) {
      if (
        key.startsWith("utm_") ||
        ["fbclid", "gclid", "mc_cid", "mc_eid", "variant", "color"].includes(key)
      ) {
        url.searchParams.delete(key);
      }
    }

    let finalUrl = url.toString();

    if (url.pathname !== "/" && finalUrl.endsWith("/")) {
      finalUrl = finalUrl.slice(0, -1);
    }

    return finalUrl;
  } catch {
    return null;
  }
}

function sameDomain(url, siteUrl) {
  try {
    const root = new URL(siteUrl).hostname.replace(/^www\./, "");
    const host = new URL(url).hostname.replace(/^www\./, "");

    return host === root || host.endsWith(`.${root}`);
  } catch {
    return false;
  }
}

function isBlockedUrl(url) {
  const lower = url.toLowerCase();

  const blocked = [
    "/cart",
    "/basket",
    "/checkout",
    "/account",
    "/login",
    "/signin",
    "/sign-in",
    "/register",
    "/wishlist",
    "/favorites",
    "/orders",
    "/search",
    "/cdn-cgi/",
    "/api/",
    "/auth/",
    "/mybag",
    "/shop/mybag",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".svg",
    ".css",
    ".js",
    ".json",
    ".pdf",
    ".zip",
    ".mp4"
  ];

  return blocked.some((item) => lower.includes(item));
}

function isProductUrl(url) {
  const path = new URL(url).pathname.toLowerCase();

  return [
    /\/products?\/[^/]+/,
    /\/product\/[^/]+/,
    /\/product-page\/[^/]+/,           // Wix Stores
    /\/collections\/[^/]+\/products\/[^/]+/,
    /\/[a-z0-9-]+\/p\/[^/]+/,          // Squarespace (collection/p/slug)
    /\/p\/.*?\/_\/prod\d+/,
    /\/t\/[^/]+\/[a-z0-9-]+/,
    /\/item\/[^/]+/,
    /\/catalog\/product\/view/
  ].some((pattern) => pattern.test(path));
}

function isCollectionUrl(url) {
  const path = new URL(url).pathname.toLowerCase();

  if (isProductUrl(url)) return false;

  return [
    /\/collections?(\/|$)/,
    /\/categories?(\/|$)/,
    /\/catalog(\/|$)/,
    /\/shop(\/|$)/,
    /\/w\/[^/]+/,
    /\/c\/[^/]+/
  ].some((pattern) => pattern.test(path));
}

function categorizeUrl(url, siteUrl) {
  const parsed = new URL(url);
  const path = parsed.pathname.toLowerCase();

  if (parsed.origin === siteUrl && (path === "/" || path === "")) {
    return "homepage";
  }

  if (isProductUrl(url)) return "products";

  if (isCollectionUrl(url)) return "collections";

  if (/pricing|prices|plans|packages|rates|subscription/.test(path)) {
    return "pricing";
  }

  if (/services?|solutions?|repair|installation|consulting|support|maintenance/.test(path)) {
    return "services";
  }

  if (/about|contact|privacy|terms|shipping|returns|faq|help|blog|news|careers/.test(path)) {
    return "otherPages";
  }

  return null;
}

function hasReachedLimits(grouped, options) {
  const total =
    grouped.homepage.size +
    grouped.products.size +
    grouped.collections.size +
    grouped.services.size +
    grouped.pricing.size +
    grouped.otherPages.size;

  // Only stop on the OVERALL cap. Hitting the product cap alone must NOT end the
  // crawl (that starved collections) — canAddToCategory already prevents adding
  // more products past their cap, so we keep scanning for collections/pages.
  return total >= options.maxTotalUrls;
}

function canAddToCategory(grouped, category, options) {
  if (category === "homepage") return grouped.homepage.size < 1;
  if (category === "products") return grouped.products.size < options.maxProducts;
  if (category === "collections") return grouped.collections.size < options.maxCollections;
  if (category === "services") return grouped.services.size < options.maxServices;
  if (category === "pricing") return grouped.pricing.size < options.maxPricing;
  if (category === "otherPages") return grouped.otherPages.size < options.maxOtherPages;

  return false;
}

function extractLocsFromXml(xml) {
  const locs = [];
  const regex = /<loc>\s*([^<]+?)\s*<\/loc>/gi;

  let match;

  while ((match = regex.exec(xml)) !== null) {
    locs.push(match[1].trim());
  }

  return locs;
}

function isLikelySitemapUrl(url) {
  const lower = url.toLowerCase();

  return (
    lower.includes("sitemap") ||
    lower.endsWith(".xml") ||
    lower.endsWith(".xml.gz")
  );
}

function scoreSitemapUrl(url) {
  const lower = url.toLowerCase();

  let score = 0;

  // Collections/categories first — they're the high-value pages to track and
  // they must be scanned before the (often huge) product sitemap so products
  // don't exhaust the crawl budget before collections are found.
  if (lower.includes("collection")) score += 120;
  if (lower.includes("category")) score += 120;
  if (lower.includes("catalog")) score += 110;
  if (lower.includes("product")) score += 90;
  if (lower.includes("page")) score += 60;

  if (lower.includes("blog")) score -= 30;
  if (lower.includes("article")) score -= 30;
  if (lower.includes("post")) score -= 30;
  if (lower.includes("image")) score -= 80;
  if (lower.includes("video")) score -= 80;
  if (lower.includes("news")) score -= 40;

  return score;
}

function prioritizeSitemaps(sitemaps) {
  return [...new Set(sitemaps)]
    .filter(Boolean)
    .sort((a, b) => scoreSitemapUrl(b) - scoreSitemapUrl(a));
}

async function fetchText(url, options) {
  const response = await axios.get(url, {
    timeout: options.timeout,
    headers: {
      "User-Agent": USER_AGENT,
      Accept: "text/xml,application/xml,text/html,*/*"
    },
    responseType: "text",
    validateStatus: (status) => status >= 200 && status < 400
  });

  return response.data;
}

async function getRobots(siteUrl, options) {
  const robotsUrl = `${siteUrl}/robots.txt`;

  try {
    const robotsTxt = await fetchText(robotsUrl, options);
    return robotsParser(robotsUrl, robotsTxt);
  } catch {
    return robotsParser(robotsUrl, "");
  }
}

function createGroupedResult(siteUrl) {
  return {
    homepage: new Set([siteUrl]),
    products: new Set(),
    collections: new Set(),
    services: new Set(),
    pricing: new Set(),
    otherPages: new Set()
  };
}

function addUrlToGrouped({ rawUrl, siteUrl, robots, grouped, options, category: forced }) {
  const url = cleanUrl(rawUrl);

  if (!url) return;
  if (!sameDomain(url, siteUrl)) return;
  if (isBlockedUrl(url)) return;

  if (options.respectRobots && robots && robots.isAllowed(url, USER_AGENT) === false) {
    return;
  }

  // `forced` lets the catalog path assert the category (we KNOW it's a
  // collection/product from the API), so it works for any URL shape — Shopify
  // /collections/x, WooCommerce /product-category/x, etc.
  const category = forced || categorizeUrl(url, siteUrl);

  if (!category) return;
  if (!canAddToCategory(grouped, category, options)) return;

  grouped[category].add(url);
}

// ── Data-driven collection grouping ───────────────────────────────────────
// Vertical-agnostic: we do NOT hard-code fashion categories. Buckets are
// derived from the store's OWN collection names, so it works the same for
// apparel, pet food, cricket gear, cosmetics, etc. Two passes:
//   1) universal INTENT buckets (Sale / New / Best Sellers / Gifts) — these
//      mean the same thing in every vertical.
//   2) the rest are clustered by their most COMMON shared word (document
//      frequency ≥ 2), which surfaces the store's real categories from its own
//      vocabulary ("cat"/"dog", "cricket"/"bats", "lipstick"/"skincare", …).
// Anything with no shared word lands in "Other Collections" — never dropped.

const INTENT_BUCKETS = [
  { label: "Sale & Clearance", kw: ["sale", "clearance", "discount", "outlet", "offer", "deal", "% off", "reduced", "markdown"] },
  { label: "New Arrivals", kw: ["new arrival", "new-arrival", "new in", "newin", "just in", "just-in", "latest", "new collection", "newest"] },
  { label: "Best Sellers", kw: ["best seller", "bestseller", "best-sell", "top seller", "trending", "popular", "most loved", "must have", "must-have"] },
  { label: "Featured", kw: ["featured", "editor", "staff pick", "curated", "shop the look"] },
  { label: "Gifts", kw: ["gift", "gifting", "hamper", "bundle"] },
];

const GROUP_STOPWORDS = new Set([
  "collection", "collections", "shop", "all", "the", "and", "for", "of", "by",
  "our", "store", "official", "buy", "products", "product", "page", "view",
  "with", "your", "a", "an", "to", "in", "on", "range", "series", "edit",
]);

const titleCaseWord = (s) => s.replace(/\b\w/g, (c) => c.toUpperCase());

function tokenizeName(name) {
  return (name || "")
    .toLowerCase()
    .replace(/['’]s\b/g, "")          // possessive: men's → men
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .map((t) => t.trim())
    .filter((t) => t.length >= 3 && !GROUP_STOPWORDS.has(t) && !/^\d+$/.test(t));
}

// Optional top level for products: audience, read from product tags. Exact
// token match (not substring) so "women" never trips the "men" bucket.
const AUDIENCE_BUCKETS = [
  { label: "Women", kw: ["women", "womens", "woman", "female", "ladies"] },
  { label: "Men", kw: ["men", "mens", "man", "male", "gents"] },
  { label: "Kids", kw: ["kids", "kid", "children", "child", "baby", "infant", "toddler", "junior", "boys", "boy", "girls", "girl"] },
  { label: "Unisex", kw: ["unisex"] },
];

function audienceFromTags(tags) {
  const arr = Array.isArray(tags)
    ? tags
    : typeof tags === "string" ? tags.split(",") : [];
  const low = arr.map((t) => String(t).toLowerCase().trim()).filter(Boolean);
  for (const a of AUDIENCE_BUCKETS) {
    if (a.kw.some((k) => low.includes(k))) return a.label;
  }
  return null;
}

function classifyCollections(entries) {
  const groupByUrl = new Map();
  const remaining = [];

  // Pass 1 — universal intents.
  for (const e of entries) {
    const t = (e.title || "").toLowerCase();
    const hit = t ? INTENT_BUCKETS.find((b) => b.kw.some((k) => t.includes(k))) : null;
    if (hit) groupByUrl.set(e.url, hit.label);
    else remaining.push(e);
  }

  // Pass 2 — cluster the rest by their most common shared token.
  const df = new Map();
  const toksByUrl = new Map();
  for (const e of remaining) {
    const toks = e.title ? tokenizeName(e.title) : [];
    toksByUrl.set(e.url, toks);
    for (const t of new Set(toks)) df.set(t, (df.get(t) || 0) + 1);
  }
  for (const e of remaining) {
    const toks = toksByUrl.get(e.url) || [];
    let best = null;
    let bestDf = 1; // require df >= 2 to form a shared bucket
    for (const t of toks) {
      const d = df.get(t) || 0;
      if (d > bestDf) { best = t; bestDf = d; }
    }
    groupByUrl.set(e.url, best ? titleCaseWord(best) : "Other Collections");
  }
  return groupByUrl;
}

// Products carry a `product_type` in products.json — a cleaner grouping signal
// than names. Bucket by type; fall back to the same shared-word clustering as
// collections when a product has no type. Applied to all catalogs (consistent
// 2-level layout regardless of size).
function classifyProducts(entries, typesByUrl = new Map()) {
  const groupByUrl = new Map();
  const remaining = [];

  // Pass 1 — product_type (e.g. "Bottom", "Shirt", "Footwear").
  for (const e of entries) {
    const t = (typesByUrl.get(e.url) || "").trim();
    if (t) groupByUrl.set(e.url, titleCaseWord(t.toLowerCase()));
    else remaining.push(e);
  }

  // Pass 2 — shared-word clustering for typeless products.
  if (remaining.length) {
    const df = new Map();
    const toksByUrl = new Map();
    for (const e of remaining) {
      const toks = e.title ? tokenizeName(e.title) : [];
      toksByUrl.set(e.url, toks);
      for (const t of new Set(toks)) df.set(t, (df.get(t) || 0) + 1);
    }
    for (const e of remaining) {
      const toks = toksByUrl.get(e.url) || [];
      let best = null;
      let bestDf = 1;
      for (const t of toks) {
        const d = df.get(t) || 0;
        if (d > bestDf) { best = t; bestDf = d; }
      }
      groupByUrl.set(e.url, best ? titleCaseWord(best) : "Other Products");
    }
  }
  return groupByUrl;
}

// ── Collection KIND classifier ────────────────────────────────
// Multi-brand stores (beauty retailers, marketplaces) mix three very different
// kinds of collection: real product CATEGORIES ("Cleansers", "Foundation"),
// BRAND pages ("COSRX", "Maybelline"), and MARKETING/editorial pages ("Best
// Sellers", "Gifts under $20", "Summer Sale"). Only categories are worth
// auto-recommending for tracking. We tag each collection so the picker can
// prioritise categories and demote the rest (still selectable manually).
// Signals, in order: marketing regex → the store's own vendor list (brand) →
// the store's own product_type words (category) → a proper-noun fallback.
// Brand + fallback only fire on genuinely multi-brand stores, so a single-brand
// store's own collections are never mislabelled.
const MARKETING_RE = /(%|\boff\b|\bsale\b|discount|clearance|\bdeals?\b|\bgifts?\b|gift ?cards?|best ?sellers?|bestselling|new arrivals?|\baward\b|award-?winning|exclusive|back in stock|\bpicks?\b|favou?rites?|\btop\b|\bbundles?\b|heritage|earth day|\bfounders?\b|collective|\bspring\b|\bsummer\b|\bfall\b|\bwinter\b|\bholiday\b|under \$|\bunder \d|blind box|build your own|guaranteed|as seen|check-?test|\bevents?\b|early access|trending|limited edition)/i;

const normName = (s) =>
  String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();

// Menu grouping labels that are merchandising CROSS-CUTS, not real taxonomy tiers
// — they re-slice the same categories under different lenses ("Shop by Activity",
// "Shop by Color", "Featured", "Trending"). We drop them from the nav ancestry so
// the tree's levels stay a clean taxonomy (Gender › Category › Sub …).
const MERCH_TIER_RE = /(shop by|featured|explore|new in|new arrivals?|trending|best ?sellers?|last chance|on sale|^sale$|^all$)/i;

// Crude singulariser so "Toners" matches the product_type "Toner", "Masks" →
// "Mask", "Cleansers" → "Cleanser". Applied to BOTH sides of the token match.
const stemWord = (w) => {
  if (w.length <= 3) return w;
  if (w.endsWith("ies")) return w.slice(0, -3) + "y";
  if (/(ch|sh|ss|x|z)es$/.test(w)) return w.slice(0, -2);
  if (w.endsWith("es") && w.length > 4) return w.slice(0, -1);
  if (w.endsWith("s") && !w.endsWith("ss")) return w.slice(0, -1);
  return w;
};

// Generic words that carry no category signal on their own (so the proper-noun
// fallback and the type-token match don't trip on them).
const CAT_STOP = new Set([
  "the", "and", "for", "with", "your", "our", "all", "new", "best", "shop",
  "skin", "care", "free", "of", "to", "in", "a", "s", "by", "buy", "online",
]);

function classifyCollection(title, { vendorSet, typeTokens, multiBrand }) {
  const t = String(title || "");
  if (!t.trim()) return "unknown";
  if (MARKETING_RE.test(t)) return "marketing";
  const n = normName(t);
  if (multiBrand && vendorSet.has(n)) return "brand"; // exact vendor name = brand page
  const toks = n.split(" ").filter((w) => w.length > 1 && !CAT_STOP.has(w)).map(stemWord);
  if (toks.some((w) => typeTokens.has(w))) return "category"; // shares a product_type word
  // Only a bare single-token proper noun falls back to brand — multi-word unknown
  // titles are more likely descriptive categories, so we keep them trackable.
  if (multiBrand && toks.length === 1) return "brand";
  return "unknown";
}

// Gender is the true storefront L1 on fashion stores (Women / Men), but it often
// lives as a URL segment / Shopify tag-filter (/collections/<category>/womens)
// rather than a nav wrapper — and SPA mega-menus (Gymshark) hang the gender tab
// off its submenu by aria-controls, not DOM nesting, so a structural nav parser
// can't see it. We recover it straight from the URL instead: any clean gender
// segment becomes the top-level group so the tree shows Women / Men as L1.
const GENDER_LABEL = {
  womens: "Women", women: "Women", ladies: "Women", female: "Women",
  mens: "Men", men: "Men", male: "Men",
  kids: "Kids", girls: "Girls", boys: "Boys", unisex: "Unisex",
};
const genderOf = (u) => {
  try {
    const segs = new URL(u).pathname.toLowerCase().replace(/\/+$/, "").split("/").filter(Boolean);
    for (const s of segs) if (GENDER_LABEL[s]) return GENDER_LABEL[s];
    return null;
  } catch {
    return null;
  }
};

function groupedToPlainObject(grouped, titles = new Map(), productTypes = new Map(), productTags = new Map(), menuPaths = new Map(), counts = new Map(), vendors = new Set()) {
  // Emit {url, title, inNav} so the UI can show real product/collection NAMES
  // instead of URL slugs and badge pages that appear in the storefront nav.
  // Collections also get a `groups` path so the UI can nest them.
  const withTitles = (set) =>
    [...set].map((u) => ({ url: u, title: titles.get(u) || null, inNav: menuPaths.has(u) }));

  // Build the store's own vendor set (brands) and product_type token set
  // (categories) so we can classify each collection. multiBrand gates the whole
  // brand-vs-category split — a single-vendor store never triggers it.
  const vendorSet = new Set([...vendors].map(normName).filter(Boolean));
  const typeTokens = new Set();
  for (const ty of new Set(productTypes.values())) {
    for (const w of normName(ty).split(" ")) {
      if (w.length > 1 && !CAT_STOP.has(w)) typeTokens.add(stemWord(w));
    }
  }
  const multiBrand = vendorSet.size >= 4;

  // Collections: prefer the STOREFRONT MENU hierarchy (curated, deduped, exactly
  // as shoppers see it). When we have a menu, collections not in it are gap-fill
  // and land under "More Collections". With no menu at all, fall back to the
  // data-driven name clustering (previous behaviour).
  const collectionsRaw = withTitles(grouped.collections);

  // De-duplicate by the collection's FULL path (not just the last segment). The
  // same collection can slip in twice — once from the menu and once from the
  // gap-fill/sitemap — with slightly different URLs (host/trailing slash). Using
  // the whole path keeps genuinely different collections apart: a base
  // "/collections/zip-jackets" and its filtered "/collections/zip-jackets/mens"
  // and "/collections/zip-jackets/womens" are all distinct. Keep the menu-placed
  // copy so it stays in its proper tier. Pure in-memory, no fetches.
  const pathKey = (u) => {
    try {
      return new URL(u).pathname.replace(/\/+$/, "").toLowerCase();
    } catch {
      return String(u || "").toLowerCase();
    }
  };
  const byPath = new Map();
  for (const c of collectionsRaw) {
    const k = pathKey(c.url);
    const cur = byPath.get(k);
    if (!cur) {
      byPath.set(k, c);
    } else if (menuPaths.has(c.url) && !menuPaths.has(cur.url)) {
      byPath.set(k, c); // prefer the menu-sourced entry
    }
  }
  const collections = [...byPath.values()];

  const hasMenu = collections.some((c) => menuPaths.has(c.url));
  const collGroups = hasMenu ? null : classifyCollections(collections);
  for (const c of collections) {
    const mpRaw = menuPaths.get(c.url) || [];
    const gender = genderOf(c.url);
    // Real taxonomy tiers only: drop merchandising cross-cuts and any tier that
    // merely repeats the gender we promote to L1.
    const tiers = mpRaw.filter(
      (t) =>
        t &&
        !MARKETING_RE.test(t) &&
        !MERCH_TIER_RE.test(t) &&
        (!gender || normName(t) !== normName(gender))
    );
    // Group path = Gender (L1, from the URL) › clean menu tiers › (collection leaf).
    // Gender is the split shoppers see; the menu tiers add real depth (e.g.
    // Men › Clothing › Shirts). Capped at 3 header levels → up to an L4 leaf.
    if (gender) c.groups = [gender, ...tiers];
    else if (tiers.length) c.groups = tiers;
    else if (mpRaw.length) c.groups = mpRaw; // menu path was all merch — keep something
    else if (hasMenu) c.groups = ["More Collections"];
    else c.groups = [collGroups.get(c.url) || "Other Collections"];
    c.groups = c.groups.slice(0, 3);
    // Number of products in this collection (Shopify products_count / Woo count),
    // so the UI can show "Collection · N products" and budget selections.
    const n = counts.get(c.url);
    if (typeof n === "number" && n >= 0) c.count = n;
    // category | brand | marketing | unknown — lets the picker recommend general
    // categories and demote brand/promo collections.
    c.kind = classifyCollection(c.title, { vendorSet, typeTokens, multiBrand });
  }

  // Products: type bucket, with an OPTIONAL Audience level on top when tags
  // give ≥2 audiences (→ 3 levels: Audience › Type › item). Otherwise 2 levels
  // (Type › item). Fully graceful when tags/types are absent.
  const products = withTitles(grouped.products);
  const typeGroups = classifyProducts(products, productTypes);

  const audByUrl = new Map();
  const audiences = new Set();
  for (const p of products) {
    const a = audienceFromTags(productTags.get(p.url));
    if (a) { audByUrl.set(p.url, a); audiences.add(a); }
  }
  const useAudience = audiences.size >= 2;

  for (const p of products) {
    const type = typeGroups.get(p.url) || "Other Products";
    p.groups = useAudience ? [audByUrl.get(p.url) || "Other", type] : [type];
  }

  // Bucket ORDER = tree priority. Lead with the tracking units — Collections
  // (e-commerce) and Pricing (SaaS) — then the rest, with catch-all pages last.
  return {
    Homepage: withTitles(grouped.homepage),
    Collections: collections,
    Pricing: withTitles(grouped.pricing),
    Products: products,
    Services: withTitles(grouped.services),
    "Other Pages": withTitles(grouped.otherPages)
  };
}

// Sitemaps only give URLs (→ ugly slugs) and often omit collections. Prefer the
// LIVE catalog: pull products + collections from Shopify's JSON endpoints, which
// carry real TITLES, plus the homepage's own nav links. Titles are recorded in
// `titles` (keyed by the cleaned URL) so the tree can display names.
async function discoverFromNavAndApi({ siteUrl, robots, grouped, options, titles, productTypes, productTags, menuPaths, counts, vendors }) {
  const catalog = options.catalog;

  if (catalog && (catalog.menu?.length || catalog.collections?.length || catalog.products?.length)) {
    // Preferred: catalog fetched reliably via the Python browser path
    // (cloudscraper→Playwright), so titles are consistent on protected stores.
    const base = catalog.base || siteUrl;

    // products_count per collection (Shopify products_count / Woo category count).
    // Keyed by BOTH the full URL and the last path segment (handle/slug), so a menu
    // link matches even when its host/scheme/trailing-slash differs from the API's
    // URL — a common reason counts looked "missing" on Shopify stores.
    const slugOf = (u) => {
      try {
        const segs = new URL(u).pathname.replace(/\/+$/, "").toLowerCase().split("/").filter(Boolean);
        return segs[segs.length - 1] || "";
      } catch {
        return "";
      }
    };
    const countByUrl = new Map();
    const countBySlug = new Map();
    for (const c of catalog.collections || []) {
      const raw = c.url || (c.handle ? `${base}/collections/${c.handle}` : null);
      const cu = raw ? cleanUrl(raw) : null;
      const n = c.products_count;
      if (typeof n !== "number" || n < 0) continue;
      if (cu) countByUrl.set(cu, n);
      if (c.handle) countBySlug.set(String(c.handle).toLowerCase(), n);
      if (raw) countBySlug.set(slugOf(raw), n);
    }
    const countFor = (rawUrl, cleaned) => {
      if (cleaned && countByUrl.has(cleaned)) return countByUrl.get(cleaned);
      const s = slugOf(rawUrl);
      if (s && countBySlug.has(s)) return countBySlug.get(s);
      return undefined;
    };

    // (a) MENU collections first — the merchant's curated, hierarchical list.
    // Record the menu ancestor path so the tree nests them exactly as in the
    // storefront nav. This is the deduped, live picture a shopper actually sees.
    // Pathname of a URL (lowercased, no trailing slash) — for comparing which
    // collection a URL points at, independent of host/slash differences.
    const pathOf = (u) => {
      try {
        return new URL(u).pathname.replace(/\/+$/, "").toLowerCase();
      } catch {
        return "";
      }
    };

    const menuUrls = new Set();
    // Base collections that the menu exposes only via FILTERED sub-views, e.g.
    // the menu links /collections/zip-jackets/mens + /womens (but not the plain
    // /collections/zip-jackets). We track the base "/collections/zip-jackets" so
    // gap-fill won't re-add the generic base — the specific mens/womens ones the
    // merchant chose are more useful. Only sites that use this pattern (Gymshark)
    // are affected; base-collection sites have an empty set here → no change.
    const menuFilteredBases = new Set();
    for (const m of catalog.menu || []) {
      if (!m || !m.url) continue;
      const cu = cleanUrl(m.url);
      if (!cu) continue;
      if (m.title) titles.set(cu, m.title);
      if (menuPaths && Array.isArray(m.path) && m.path.length) menuPaths.set(cu, m.path.slice(0, 3));
      if (counts) {
        const n = countFor(m.url, cu);
        if (typeof n === "number") counts.set(cu, n);
      }
      menuUrls.add(cu);
      // /collections/<X>/<Y> → record base /collections/<X>
      const segs = pathOf(m.url).split("/").filter(Boolean);
      if (segs[0] === "collections" && segs.length >= 3) {
        menuFilteredBases.add("/" + segs.slice(0, 2).join("/"));
      }
      addUrlToGrouped({ rawUrl: m.url, siteUrl, robots, grouped, options, category: "collections" });
    }

    // (b) Gap-fill: collections from the API that AREN'T in the menu (hidden /
    // extra ones). Kept so nothing important is lost; grouped under "More
    // Collections" downstream so they don't masquerade as curated menu entries.
    const hasMenu = menuUrls.size > 0;
    // A category permalink that structurally encodes its type. On Shopify (and
    // well-configured WooCommerce) these are reliable. A BARE root-level slug
    // (/bolero/) is not: on stores with custom permalinks the Store API reports
    // the raw taxonomy slug, not the real storefront URL (/braut-bolero/). When
    // we already have a real menu, we trust it and drop those unreliable ones.
    const isStructuralCat = (u) =>
      /\/(collections?|product-category|product[_-]cat|shop|categor(y|ies)|catalog|c|w)(\/|$)/i.test(pathOf(u));
    for (const c of catalog.collections || []) {
      // Prefer a full URL (WooCommerce permalink); fall back to Shopify handle.
      const raw = c.url || (c.handle ? `${base}/collections/${c.handle}` : null);
      if (!raw) continue;
      const cu = cleanUrl(raw);
      if (cu && menuUrls.has(cu)) continue; // already shown via the menu
      // Skip the generic base when the menu already offers filtered sub-views.
      if (menuFilteredBases.has(pathOf(raw))) continue;
      // With a real menu, skip Store-API categories whose permalink is a bare
      // root slug — those are the unreliable ones the menu supersedes.
      if (hasMenu && !isStructuralCat(raw)) continue;
      if (cu && c.title && !titles.has(cu)) titles.set(cu, c.title);
      if (cu && counts && typeof c.products_count === "number" && c.products_count >= 0) counts.set(cu, c.products_count);
      addUrlToGrouped({ rawUrl: raw, siteUrl, robots, grouped, options, category: "collections" });
    }

    for (const p of catalog.products || []) {
      if (grouped.products.size >= options.maxProducts) break;
      const raw = p.url || (p.handle ? `${base}/products/${p.handle}` : null);
      if (!raw) continue;
      const pu = cleanUrl(raw);
      if (pu && p.title) titles.set(pu, p.title);
      if (pu && p.product_type) productTypes.set(pu, p.product_type);
      if (pu && p.tags) productTags.set(pu, p.tags);
      if (vendors && p.vendor) vendors.add(p.vendor);
      addUrlToGrouped({ rawUrl: raw, siteUrl, robots, grouped, options, category: "products" });
    }
  } else {
    // Fallback (no catalog / Python unavailable): fetch the Shopify JSON directly.
    // Works on non-protected stores; may be intermittently challenged otherwise.
    try {
      for (let page = 1; page <= 4; page++) {
        const res = await axios.get(
          `${siteUrl}/collections.json?limit=250&page=${page}`,
          {
            timeout: 12000,
            headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
            validateStatus: (s) => s >= 200 && s < 400,
          }
        );
        const cols = (res.data && res.data.collections) || [];
        if (!cols.length) break;
        for (const c of cols) {
          if (c.products_count === 0) continue;
          if (c.handle) {
            const cu = cleanUrl(`${siteUrl}/collections/${c.handle}`);
            if (cu && c.title) titles.set(cu, c.title);
            addUrlToGrouped({
              rawUrl: `${siteUrl}/collections/${c.handle}`,
              siteUrl, robots, grouped, options,
            });
          }
        }
        if (cols.length < 250) break;
      }
    } catch {
      // not Shopify, or endpoint blocked — fine
    }

    try {
      let page = 1;
      while (grouped.products.size < options.maxProducts && page <= 6) {
        const res = await axios.get(
          `${siteUrl}/products.json?limit=250&page=${page}`,
          {
            timeout: 12000,
            headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
            validateStatus: (s) => s >= 200 && s < 400,
          }
        );
        const prods = (res.data && res.data.products) || [];
        if (!prods.length) break;
        for (const p of prods) {
          if (grouped.products.size >= options.maxProducts) break;
          if (p.handle) {
            const pu = cleanUrl(`${siteUrl}/products/${p.handle}`);
            if (pu && p.title) titles.set(pu, p.title);
            if (pu && p.product_type) productTypes.set(pu, p.product_type);
            if (pu && p.tags) productTags.set(pu, p.tags);
            if (vendors && p.vendor) vendors.add(p.vendor);
            addUrlToGrouped({
              rawUrl: `${siteUrl}/products/${p.handle}`,
              siteUrl, robots, grouped, options,
            });
          }
        }
        if (prods.length < 250) break;
        page++;
      }
    } catch {
      // not Shopify, or endpoint blocked — fine
    }
  }

  // (2) Homepage links (nav + featured sections).
  try {
    const html = await fetchText(siteUrl, options);
    const $ = cheerio.load(html);
    $("a[href]").each((_, el) => {
      const href = $(el).attr("href");
      if (!href) return;
      let abs;
      try { abs = new URL(href, siteUrl).toString(); } catch { return; }
      addUrlToGrouped({ rawUrl: abs, siteUrl, robots, grouped, options });
    });
  } catch {
    // homepage unreachable — sitemaps still run below
  }
}

async function getImportantPagesFast(siteUrl, userOptions = {}) {
  const options = {
    ...DEFAULT_OPTIONS,
    ...userOptions
  };

  const normalizedSiteUrl = normalizeSiteUrl(siteUrl);
  const robots = await getRobots(normalizedSiteUrl, options);

  const grouped = createGroupedResult(normalizedSiteUrl);
  // url → real display title (product/collection names from the live catalog).
  const titles = new Map();
  // url → product_type (type-level grouping) and url → tags (audience level).
  const productTypes = new Map();
  const productTags = new Map();
  // url → menu ancestor path, so collections nest exactly as in the storefront nav.
  const menuPaths = new Map();
  // url → number of products in that collection (Shopify products_count / Woo count).
  const counts = new Map();
  // Distinct product vendors (brands) — the signal that a store is multi-brand and
  // which collections are brand pages vs real categories.
  const vendors = new Set();

  // Populate collections + nav pages FIRST, so a large product sitemap can't
  // consume the crawl budget before the merchant's key collections are found.
  await discoverFromNavAndApi({ siteUrl: normalizedSiteUrl, robots, grouped, options, titles, productTypes, productTags, menuPaths, counts, vendors });

  // Squarespace (and similar) name products as CHILDREN of a collection —
  // /shop-supernatural/<product-slug> — with no /products/ or /p/ marker, so the
  // URL pattern alone can't tell a product from a sub-page. But we already know
  // the ROOT-LEVEL collections from the nav, so any 2-segment URL whose parent is
  // one of them is a product. We restrict this to SINGLE-segment (root) parents so
  // it never touches Shopify's /collections/<x>/<filter> sub-collections.
  const pathnameOf = (u) => {
    try { return new URL(u).pathname.replace(/\/+$/, "").toLowerCase(); } catch { return ""; }
  };
  const rootCollectionPaths = new Set(
    [...grouped.collections]
      .map(pathnameOf)
      .filter((p) => p && p.split("/").filter(Boolean).length === 1)
  );
  const isChildOfRootCollection = (u) => {
    const segs = pathnameOf(u).split("/").filter(Boolean);
    return segs.length === 2 && rootCollectionPaths.has("/" + segs[0]);
  };

  // Nav menu + live catalog API (Shopify collections.json / Woo categories) are
  // the AUTHORITATIVE, live source of collections. If they already found any,
  // treat that set as complete and stop the sitemap from adding more collections
  // (sitemap collection URLs are often stale, duplicated, or hidden pages that
  // aren't in the storefront nav — the "junk" we don't want in the picker).
  const collectionsAuthoritative = grouped.collections.size > 0;

  let sitemapUrls = robots.getSitemaps();

  if (!sitemapUrls.length) {
    sitemapUrls = [
      `${normalizedSiteUrl}/sitemap.xml`,
      `${normalizedSiteUrl}/sitemap_index.xml`,
      `${normalizedSiteUrl}/sitemap_products_1.xml`,
      `${normalizedSiteUrl}/product-sitemap.xml`,
      `${normalizedSiteUrl}/sitemap-product.xml`
    ];
  }

  const sitemapQueue = prioritizeSitemaps(sitemapUrls);
  const scannedSitemaps = new Set();

  while (
    sitemapQueue.length > 0 &&
    scannedSitemaps.size < options.maxSitemaps &&
    !hasReachedLimits(grouped, options)
  ) {
    const sitemapUrl = sitemapQueue.shift();

    if (!sitemapUrl || scannedSitemaps.has(sitemapUrl)) continue;

    scannedSitemaps.add(sitemapUrl);

    try {
      const xml = await fetchText(sitemapUrl, options);
      const locs = extractLocsFromXml(xml);

      const childSitemaps = [];
      const pageUrls = [];

      for (const loc of locs) {
        const cleaned = cleanUrl(loc);

        if (!cleaned) continue;

        if (isLikelySitemapUrl(cleaned)) {
          childSitemaps.push(cleaned);
        } else {
          pageUrls.push(cleaned);
        }
      }

      if (childSitemaps.length) {
        sitemapQueue.push(...prioritizeSitemaps(childSitemaps));
      }

      const catOf = (u) =>
        isChildOfRootCollection(u) ? "products" : categorizeUrl(u, normalizedSiteUrl);

      const prioritizedPageUrls = pageUrls.sort((a, b) => {
        const categoryA = catOf(a);
        const categoryB = catOf(b);

        const weight = {
          products: 5,
          collections: 4,
          pricing: 3,
          services: 3,
          otherPages: 1,
          homepage: 0
        };

        return (weight[categoryB] || 0) - (weight[categoryA] || 0);
      });

      for (const pageUrl of prioritizedPageUrls) {
        // Force "products" for children of a root-level collection (Squarespace
        // etc.); otherwise let addUrlToGrouped categorise by URL pattern.
        const forced = isChildOfRootCollection(pageUrl) ? "products" : undefined;
        const cat = forced || catOf(pageUrl);

        // The nav/catalog owns collections — skip sitemap-only ones so stale or
        // hidden collections never leak into the tree.
        if (collectionsAuthoritative && cat === "collections") continue;

        addUrlToGrouped({
          rawUrl: pageUrl,
          siteUrl: normalizedSiteUrl,
          robots,
          grouped,
          options,
          category: forced
        });

        if (hasReachedLimits(grouped, options)) break;
      }
    } catch {
      // Ignore failed sitemap and continue
    }
  }

  if (options.returnGrouped) {
    return {
      website: normalizedSiteUrl,
      scannedSitemaps: scannedSitemaps.size,
      categories: groupedToPlainObject(grouped, titles, productTypes, productTags, menuPaths, counts, vendors)
    };
  }

  return new Set([
    ...grouped.homepage,
    ...grouped.products,
    ...grouped.collections,
    ...grouped.services,
    ...grouped.pricing,
    ...grouped.otherPages
  ]);
}

export default getImportantPagesFast;