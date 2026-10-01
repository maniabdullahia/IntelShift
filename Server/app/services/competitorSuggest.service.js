import { getCatalogCached, getStoreCategoriesFast, quickCatalog, probeStore, sampleStorePrices, getStoreProductTotal, checkScale } from "../../api/python/analyzer.js";
import { webSearch } from "../../utils/search.js";
import { llmComplete, parseJsonLoose } from "../../utils/llm.js";
import { getBusinessTypeLists } from "../../api/python/analyzer.js";
import { taxonomyFromKeywords, taxonomySimilarity } from "../../utils/taxonomy.js";
import { getCachedProfile } from "./storeProfile.service.js";

/* ────────────────────────────────────────────────────────────────
   Competitor discovery — SEARCH-FIRST, no LLM.

   The old approach asked a language model for competitors, which
   hallucinated brands and URLs. This one starts from REAL search
   results and lets verification decide what's a genuine competitor:

     1. Profile the store: region + category signals.
     2. Discover: region-localised searches (SearXNG → DDG fallback)
        built from the category signals → real candidate URLs.
     3. Verify each candidate and DROP anything that fails:
          • exists (resolves / responds),
          • REGIONAL (serves the user's region) — required,
          • real ECOMMERCE (priced catalog) — best-effort (kept if
            the catalog probe is blocked but the site is regional).
     4. Rank (confirmed stores, then category overlap, then search
        rank) and return the top few with their REAL URLs.

   Currently tuned for ecommerce; the same skeleton extends to SaaS /
   business later by changing the queries and the "is it real" check.
──────────────────────────────────────────────────────────────── */

// ALWAYS excluded: mega global marketplaces (too big / not comparable — these are
// enterprise-only and never a self-serve competitor for anyone) + social / infra /
// content. Dropped for EVERY store, whatever type the user is.
const HARD_EXCLUDED = [
  // Global mega-marketplaces & aggregators
  "amazon.", "daraz.", "etsy.", "ebay.", "aliexpress.", "alibaba.", "temu.",
  "noon.", "walmart.", "flipkart.", "myntra.", "ajio.", "shein.", "wish.",
  // Social / infra / content
  "shopify.com", "wix.com", "wordpress.", "facebook.", "instagram.", "tiktok.",
  "youtube.", "pinterest.", "twitter.", "x.com", "google.", "wikipedia.",
  "linktr.ee", "linktree.", "reddit.", "quora.", "medium.", "blogspot.",
  "pk.linkedin.", "linkedin.", "trustpilot.", "yelp.",
];

// Multi-brand retailers / general marketplaces. NOT a competitor for a SINGLE
// BRAND, but they ARE the right competitors for a general / multi-brand store —
// so these (and generic marketplace-name tokens) are excluded only when the USER
// is a single brand, and KEPT when the user is a multi-brand / general store.
const MULTIBRAND_RETAILERS = [
  "cosmetics.pk", "just4girls.pk", "goto.com.pk", "symbios.pk", "telemart.pk",
  "shophive.com", "ishopping.pk", "clicky.pk", "homeshopping.pk", "yayvo.com",
  "shopon.pk", "dikhawa.pk", "oshi.pk", "mega.pk", "priceoye.pk",
];

const MARKETPLACE_TOKENS = ["marketplace", "mall", "bazaar", "bazar", "superstore", "megastore"];

// ccTLD → market.
const TLD_REGION = {
  pk: "Pakistan", in: "India", bd: "Bangladesh", lk: "Sri Lanka", np: "Nepal",
  au: "Australia", nz: "New Zealand", uk: "United Kingdom", ie: "Ireland",
  ca: "Canada", us: "United States", ae: "UAE", sa: "Saudi Arabia",
  qa: "Qatar", kw: "Kuwait", om: "Oman", bh: "Bahrain", eg: "Egypt",
  za: "South Africa", ng: "Nigeria", ke: "Kenya", ma: "Morocco",
  my: "Malaysia", sg: "Singapore", id: "Indonesia", ph: "Philippines",
  th: "Thailand", vn: "Vietnam", tr: "Turkey", de: "Germany", fr: "France",
  es: "Spain", it: "Italy", nl: "Netherlands", se: "Sweden", pl: "Poland",
};

// Currency → market (the confirmed onboarding currency is the strongest region
// signal — a Pakistan store on a .com prices in PKR).
const CURRENCY_REGION = {
  USD: "United States", PKR: "Pakistan", INR: "India", BDT: "Bangladesh",
  LKR: "Sri Lanka", NPR: "Nepal", AUD: "Australia", NZD: "New Zealand",
  GBP: "United Kingdom", CAD: "Canada", AED: "UAE", SAR: "Saudi Arabia",
  QAR: "Qatar", KWD: "Kuwait", OMR: "Oman", BHD: "Bahrain", EGP: "Egypt",
  ZAR: "South Africa", NGN: "Nigeria", KES: "Kenya", MAD: "Morocco",
  MYR: "Malaysia", SGD: "Singapore", IDR: "Indonesia", PHP: "Philippines",
  THB: "Thailand", VND: "Vietnam", TRY: "Turkey", PLN: "Poland", SEK: "Sweden",
  JPY: "Japan", CNY: "China", KRW: "South Korea", HKD: "Hong Kong",
  CHF: "Switzerland", ILS: "Israel", MXN: "Mexico", BRL: "Brazil", RUB: "Russia",
  // EUR is intentionally omitted — it spans many countries, so it can't anchor
  // a single region; a EUR store falls back to "unknown" (unfiltered).
};
const REGION_CURRENCY = Object.fromEntries(
  Object.entries(CURRENCY_REGION).map(([cur, reg]) => [reg, cur])
);

// Currency → ISO-2 country, used ONLY to localise a competitor's geo-gated URL
// (zara.com → zara.com/us) — NOT for the region hard-filter. Includes the big
// single-country currencies that aren't in CURRENCY_REGION.
const CURRENCY_COUNTRY = {
  USD: "US", GBP: "GB", CAD: "CA", AUD: "AU", NZD: "NZ", JPY: "JP", CNY: "CN",
  HKD: "HK", KRW: "KR", INR: "IN", PKR: "PK", BDT: "BD", LKR: "LK", AED: "AE",
  SAR: "SA", QAR: "QA", KWD: "KW", OMR: "OM", BHD: "BH", EGP: "EG", ZAR: "ZA",
  NGN: "NG", KES: "KE", MAD: "MA", MYR: "MY", SGD: "SG", IDR: "ID", PHP: "PH",
  THB: "TH", VND: "VN", TRY: "TR", PLN: "PL", SEK: "SE", NOK: "NO", DKK: "DK",
  CHF: "CH", ILS: "IL", MXN: "MX", BRL: "BR", RUB: "RU", CLP: "CL", COP: "CO",
};

// Region → ISO-2 country code, to localise the web search.
const REGION_COUNTRY = {
  Pakistan: "PK", India: "IN", Bangladesh: "BD", "Sri Lanka": "LK", Nepal: "NP",
  Australia: "AU", "New Zealand": "NZ", "United Kingdom": "GB", Ireland: "IE",
  Canada: "CA", "United States": "US", UAE: "AE", "Saudi Arabia": "SA",
  Qatar: "QA", Kuwait: "KW", Oman: "OM", Bahrain: "BH", Egypt: "EG",
  "South Africa": "ZA", Nigeria: "NG", Kenya: "KE", Morocco: "MA",
  Malaysia: "MY", Singapore: "SG", Indonesia: "ID", Philippines: "PH",
  Thailand: "TH", Vietnam: "VN", Turkey: "TR", Japan: "JP", China: "CN",
  "South Korea": "KR", "Hong Kong": "HK", Switzerland: "CH", Israel: "IL",
  Mexico: "MX", Brazil: "BR", Russia: "RU",
  // Eurozone markets — resolved from the store's content language when EUR can't
  // pin one (see LANGUAGE_REGION).
  Germany: "DE", France: "FR", Italy: "IT", Spain: "ES", Netherlands: "NL",
  Portugal: "PT", Austria: "AT", Belgium: "BE", Finland: "FI", Greece: "GR",
  Poland: "PL", Sweden: "SE",
};

// Store CONTENT LANGUAGE → market. Used only as a LAST-RESORT region hint when
// the currency is too ambiguous to anchor a country (a EUR store). We map only
// clearly single-market European languages; English is intentionally omitted
// (spans US/UK/AU/…) and languages that also map to non-EUR markets (es→Mexico,
// pt→Brazil, fr→Canada) are safe here because those markets resolve via their
// own non-EUR currency BEFORE we ever fall back to language.
const LANGUAGE_REGION = {
  de: "Germany", fr: "France", it: "Italy", es: "Spain", nl: "Netherlands",
  pt: "Portugal", pl: "Poland", sv: "Sweden", fi: "Finland", el: "Greece",
};

// Eurozone-ish markets share a currency (EUR) and an open market, so for a
// European store we treat a competitor in ANY of these as in-region — that keeps
// pan-European competitors while still excluding US/UK/etc.
const EUROZONE_REGIONS = new Set([
  "Germany", "France", "Italy", "Spain", "Netherlands", "Portugal", "Austria",
  "Belgium", "Finland", "Greece", "Ireland",
]);
const EUROZONE_TLDS = new Set([
  "de", "fr", "it", "es", "nl", "pt", "at", "be", "fi", "gr", "ie", "eu",
]);

// Country name / adjective appearing in a host (keunePAKISTAN.com).
const HOST_KEYWORD_REGION = [
  ["pakistan", "Pakistan"], ["bangladesh", "Bangladesh"], ["srilanka", "Sri Lanka"],
  ["india", "India"], ["nepal", "Nepal"], ["australia", "Australia"],
  ["canada", "Canada"], ["saudi", "Saudi Arabia"], ["emirates", "UAE"],
  ["dubai", "UAE"], ["malaysia", "Malaysia"], ["singapore", "Singapore"],
  ["indonesia", "Indonesia"], ["nigeria", "Nigeria"], ["kenya", "Kenya"],
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A single brand's catalog has one vendor; a multi-brand marketplace has many.
// ≥ this many distinct vendors ⇒ marketplace.
const MARKETPLACE_VENDOR_THRESHOLD = 5;

// "brand" | "marketplace" | null (unknown — couldn't inspect the site).
// Two independent signals: Shopify vendor diversity (works when vendor is set),
// and a homepage "shop by brand" directory (works on ANY platform). Either one
// firing ⇒ marketplace. We only say "brand" when we actually inspected the site
// and found neither.
function siteType(probe) {
  if (!probe) return null;
  const vc = probe.vendorCount; // null = not read (non-Shopify / blocked)
  const ms = probe.marketplaceSignals; // null = homepage not read

  if ((vc != null && vc >= MARKETPLACE_VENDOR_THRESHOLD) || (ms != null && ms >= 1)) {
    return "marketplace";
  }
  // Confident "brand" only if we saw the homepage (ms read) or the catalog (vc
  // read) and found no marketplace signal.
  if (ms != null || vc != null) return "brand";
  return null; // couldn't inspect at all
}

function toOrigin(url) {
  try {
    return new URL(url.startsWith("http") ? url : `https://${url}`).origin;
  } catch {
    return null;
  }
}

function normDomain(u) {
  try {
    return String(u || "")
      .trim()
      .replace(/^https?:\/\//i, "")
      .replace(/\/.*$/, "")
      .replace(/^www\./i, "")
      .toLowerCase();
  } catch {
    return "";
  }
}

// A leading country-code subdomain (us.brand.com, uk.brand.com) → ISO-2 country.
function subdomainCountry(domain) {
  const first = String(domain || "").toLowerCase().split(".")[0];
  return /^[a-z]{2}$/.test(first) ? first.toUpperCase() : null;
}

// ccTLD region of a host, if any (pk, co.uk → uk). null for gTLDs.
function ccTldRegion(hostOrDomain) {
  try {
    const host = String(hostOrDomain || "").toLowerCase();
    const multi = host.match(/\.(?:com|co|net|org|gov|edu)\.([a-z]{2})$/);
    const code = multi ? multi[1] : host.split(".").pop();
    return TLD_REGION[code] ? { code, region: TLD_REGION[code] } : null;
  } catch {
    return null;
  }
}

// Region priority: confirmed currency → host keyword → ccTLD.
function resolveRegion(origin, currency) {
  const cur = String(currency || "").trim().toUpperCase();
  if (CURRENCY_REGION[cur]) return CURRENCY_REGION[cur];
  let host = "";
  try {
    host = new URL(origin).hostname.toLowerCase();
  } catch {
    host = "";
  }
  for (const [kw, region] of HOST_KEYWORD_REGION) if (host.includes(kw)) return region;
  return ccTldRegion(host)?.region || null;
}

// userMultiBrand: when the USER's store is itself a multi-brand / general store,
// multi-brand retailers and marketplace-named shops are valid competitors, so we
// only apply those soft exclusions to single-brand users. Mega-marketplaces and
// non-stores are always excluded.
// Marketplace + multinational-brand lists from the Python business-type
// classifier (business_type.py) — the SAME giants the onboarding gate routes to
// Enterprise. Loaded once per suggestion run; empty if Python is unreachable.
let sharedGiants = { labels: new Set(), hosts: new Set() };
const registrableLabel = (d) => {
  const parts = String(d || "").toLowerCase().split(".").filter(Boolean);
  if (parts.length < 2) return parts[0] || "";
  if (["co", "com", "net", "org", "gov", "edu", "ac"].includes(parts[parts.length - 2]) && parts.length >= 3) {
    return parts[parts.length - 3].replace(/-/g, "");
  }
  return parts[parts.length - 2].replace(/-/g, "");
};
async function loadSharedGiants() {
  const lists = await getBusinessTypeLists();
  if (!lists) return;
  sharedGiants = {
    labels: new Set([...(lists.marketplaces || []), ...(lists.multinationalBrands || [])]),
    hosts: new Set([...(lists.marketplaceHosts || []), ...(lists.multinationalHosts || [])]),
  };
}

function isExcluded(domain, userMultiBrand = false) {
  const d = domain.toLowerCase();
  // Non-commercial domains are never a store (orgs, govt, universities, news).
  if (/\.(org|gov|edu|mil|ac|int)(\.[a-z]{2})?$/.test(d)) return true;
  if (HARD_EXCLUDED.some((m) => d.includes(m))) return true;
  // Business Types 1–2 (large marketplaces, multinational brands) are Enterprise —
  // never a self-serve competitor suggestion.
  if (sharedGiants.hosts.has(d) || sharedGiants.labels.has(registrableLabel(d))) return true;
  if (!userMultiBrand) {
    if (MULTIBRAND_RETAILERS.some((m) => d.includes(m))) return true;
    if (MARKETPLACE_TOKENS.some((t) => d.includes(t))) return true;
  }
  return false;
}

function slugify(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function cleanName(s) {
  return String(s || "").replace(/\s+/g, " ").trim();
}

// Fallback display name when the probe couldn't read a <title>.
function titleFromDomain(domain) {
  const slug = (domain.split(".")[0] || domain).replace(/[-_]+/g, " ").trim();
  return slug.replace(/\b\w/g, (c) => c.toUpperCase());
}

// The pages the owner tracks reveal what they care about — /collections/luxury-pret
// → "luxury pret". These feed both the search queries and the overlap check.
function hintsFromPages(pages) {
  // Structural URL segments that aren't real categories — includes WooCommerce's
  // "/product-category/" and "/product-tag/" so "product category" never becomes
  // a search term.
  const SKIP = /^(collections?|products?|product[-_]categor(y|ies)|product[-_]cat|product[-_]tags?|pages?|shop|store|category|categories|brand|c|p|en|home|index)$/i;
  const out = [];
  for (const p of pages || []) {
    const raw = typeof p === "string" ? p : p?.url || "";
    if (!raw) continue;
    try {
      const path = new URL(raw.startsWith("http") ? raw : `https://${raw}`).pathname;
      for (const seg of path.split("/").filter(Boolean)) {
        if (SKIP.test(seg)) continue;
        const words = seg.replace(/\.html?$/i, "").replace(/[-_]+/g, " ").trim();
        if (words && !/^\d+$/.test(words)) out.push(words);
      }
    } catch {
      /* ignore */
    }
  }
  return [...new Set(out)].slice(0, 20);
}

// ── Nav menu → the store's REAL product categories ──────────────────────────
// The nav L1/L2 is the sharpest "what they sell" signal — a store's own
// merchandising taxonomy (Shorts, Leggings, Serums), far more specific than a
// broad umbrella term ("activewear") or raw product_type. These labels seed the
// competitor search so we find genuinely-comparable stores, not category giants.

// Nav labels that are audience SEGMENTS — not product categories. A gendered L1
// (Men/Women) contributes its child categories, never itself.
const NAV_SEGMENT = new Set([
  "men", "mens", "man", "women", "womens", "woman", "ladies", "gents",
  "kids", "kid", "boys", "boy", "girls", "girl", "unisex", "baby", "babies",
  "children", "childrens", "him", "her", "home", "shop", "all", "everything",
  "shop all", "view all", "new", "featured",
]);
// Marketing / utility / editorial nav — never a product category.
const NAV_STOP_RE = /\b(sale|clearance|outlet|last\s*chance|final\s*sale|new\s*in|new\s*arrivals?|newest|just\s*in|back\s*in\s*stock|restock(ed)?|coming\s*soon|must[\s-]*haves?|seasonal|limited\s*edition|exclusives?|online\s*exclusive|shop\s*all|view\s*all|see\s*all|best\s*sell|bestsell|trending|featured|popular|gift|gifts|gift\s*cards?|bundles?|about|contact|blog|journal|stories|lookbook|faqs?|help|support|account|login|log\s*in|sign\s*in|register|track|orders?|wholesale|stockists?|rewards|loyalty|careers|press|our\s*story|sustainability|reviews?|find\s*a\s*store|store\s*locator|locations?|shipping|returns|exchanges?|size\s*guide)\b/i;
// Sizes / lengths / colours — facets, not categories.
const NAV_FACET_RE = /^(\d+(\.\d+)?\s*("|”|in|inch|inches|cm|mm)?|xs|xxs|s|m|l|xl|xxl|xxxl|small|medium|large|one\s*size|black|white|red|blue|green|pink|grey|gray|navy|beige|brown|purple|yellow|orange|gold|silver)$/i;
// Promotional / discount collection names ("20% off", "40% Off and Above",
// "20 extra off", "up to 50", "flat 30") — marketing, never a category seed. The
// "off" checks are number/percent-anchored so real categories like "Off Shoulder"
// survive.
const NAV_PROMO_RE = /(\d+\s*%|%\s*off|\bextra\s+off\b|\b\d+\s*off\b|\boff\s+(?:and\s+above|select|your)\b|\bsave\s+\d+|\bdeals?\b|\bbundles?\b|\bflat\s+\d+|\bup\s+to\s+\d+)/i;
// Physical MEASUREMENTS / lengths ("5 Inch Shorts", "8-Inch", "2 in 1 Shorts") —
// facet variants of a category, not the category itself.
const NAV_MEASURE_RE = /\b\d+\s*(?:"|”|-?\s*inch(?:es)?|-?\s*in\b|cm|mm)\b|\b\d+\s*in\s*1\b/i;
// Seasonal DROP / date codes ("22-FALL", "23-SUM BOYS TEES", "2023-Spring",
// "23marchsale", "Winter '24") — merchandising drops, never a product category, so
// they make useless competitor-search seeds. Two shapes: a leading year/2-digit code
// (then a separator or letter), or a season word adjacent to a 2–4 digit number.
const NAV_SEASON_RE = /^\d{2,4}([-\/.\s]|[a-z])|\b\d{2,4}\s*[-\/']?\s*(fall|fw|ss|aw|win(?:ter)?|sum(?:mer)?|spr(?:ing)?|aut(?:umn)?)\b|\b(fall|winter|summer|spring|autumn)\s*[-\/']?\s*\d{2,4}\b/i;

const cleanNavLabel = (s) => String(s || "").replace(/\s+/g, " ").trim();

const isGoodNavCategory = (label) => {
  const l = cleanNavLabel(label).toLowerCase();
  if (l.length < 2 || l.length > 40) return false;
  if (/^\d+$/.test(l)) return false;
  if (NAV_SEGMENT.has(l)) return false;
  if (NAV_STOP_RE.test(l)) return false;
  if (NAV_PROMO_RE.test(l)) return false;
  if (NAV_MEASURE_RE.test(l)) return false;
  if (NAV_SEASON_RE.test(l)) return false;
  if (NAV_FACET_RE.test(l)) return false;
  return true;
};

/* Extract the store's product categories from its nav menu. getCatalog returns
   the menu FLATTENED as {title, path[]} entries — title = the leaf category
   ("Shorts"), path = its ancestor groups (["Men","Bottoms"]). We take the specific
   leaf titles plus any non-segment group labels, dropping audience segments
   (Men/Women), marketing (Sale/New In) and facets (sizes/colours). Leaf-first so
   the most specific labels lead. Returns cleaned, de-duplicated category strings. */
function navCategories(menu, limit = 30) {
  const leaves = [];
  const groups = [];
  for (const entry of Array.isArray(menu) ? menu : []) {
    if (!entry) continue;
    if (isGoodNavCategory(entry.title)) leaves.push(cleanNavLabel(entry.title).toLowerCase());
    for (const g of Array.isArray(entry.path) ? entry.path : []) {
      if (isGoodNavCategory(g)) groups.push(cleanNavLabel(g).toLowerCase());
    }
  }
  // Specific leaves first, then broader group labels, de-duplicated.
  return [...new Set([...leaves, ...groups])].slice(0, limit);
}

// Words that carry no category signal for clustering (gender, generic retail).
const CAT_CLUSTER_STOP = new Set([
  "and", "for", "the", "with", "your", "our", "all", "new", "sale", "best",
  "shop", "store", "collection", "collections", "products", "product",
  "womens", "women", "mens", "men", "kids", "girls", "boys", "unisex", "online",
]);

/* Group the tracked categories into CLUSTERS by shared words, then return them
   ordered BREADTH-FIRST (one per cluster, then seconds, …) plus the cluster count.
   This makes the competitor search cover the different AREAS a wide catalog spans
   (makeup + skincare + haircare) instead of the first N page-order categories,
   which can all be shades of one area and miss whole competitor sets. */
function representativeCategories(cats) {
  const clean = [...new Set(cats.map((c) => c.trim().toLowerCase()).filter(Boolean))];
  if (clean.length <= 1) return { ordered: clean, clusterCount: clean.length };

  const tokensOf = (c) =>
    c.split(/[^a-z0-9]+/).filter((w) => w.length > 2 && !CAT_CLUSTER_STOP.has(w));
  const df = new Map();
  const toks = new Map();
  for (const c of clean) {
    const t = tokensOf(c);
    toks.set(c, t);
    for (const w of new Set(t)) df.set(w, (df.get(w) || 0) + 1);
  }
  // Cluster key = the token this category shares with the MOST others (df > 1);
  // a category that shares nothing is its own cluster (a distinct area).
  const clusters = new Map();
  for (const c of clean) {
    let key = c;
    let bestDf = 1;
    for (const w of toks.get(c)) {
      const d = df.get(w) || 0;
      if (d > bestDf) {
        bestDf = d;
        key = w;
      }
    }
    if (!clusters.has(key)) clusters.set(key, []);
    clusters.get(key).push(c);
  }
  // Round-robin across clusters → breadth before depth.
  const queues = [...clusters.values()];
  const ordered = [];
  let active = true;
  while (active) {
    active = false;
    for (const q of queues) {
      if (q.length) {
        ordered.push(q.shift());
        active = true;
      }
    }
  }
  return { ordered, clusterCount: clusters.size };
}

/* Pick a competitor's regional storefront URL from its hreflang alternates so a
   geo-gated site opens the RIGHT country store. Matches the user's country code
   against the alternate's hreflang (en-US, us) or its URL path (/us/). Returns
   the localised URL, or the original if there's no better match. */
function localizeUrl(rootUrl, locales, country) {
  if (!country || !Array.isArray(locales) || !locales.length) return rootUrl;
  const cc = country.toLowerCase();
  const byHreflang = locales.find((l) => {
    const h = String(l.hreflang || "").toLowerCase();
    return h === cc || h.endsWith(`-${cc}`);
  });
  const byPath =
    !byHreflang &&
    locales.find((l) => {
      try {
        const seg = (new URL(l.url).pathname.toLowerCase().split("/").filter(Boolean)[0] || "");
        // matches /us/, /en_us/, /us-en/, /en-us/ …
        return seg === cc || seg.split(/[-_]/).includes(cc);
      } catch {
        return false;
      }
    });
  const hit = byHreflang || byPath;
  if (!hit || !hit.url) return rootUrl;
  try {
    return new URL(hit.url, rootUrl).href.replace(/\/$/, "");
  } catch {
    return rootUrl;
  }
}

/* Classify the store's overall CATEGORY in a few words (e.g. "gym & activewear
   clothing", "color cosmetics", "hair care products") from its own catalog
   signals. This is a safe LLM use — pure classification, no URLs to hallucinate —
   and gives the competitor search a broad umbrella term beyond the individual
   page categories. Returns "" on any failure so the search still runs without it. */
// Pick n items spread EVENLY across an array (not just the first n), so a broad
// catalog is represented by categories from across it — not only its alphabetical
// head (which for a general store is whatever sorts first, e.g. "Accessories, Anime,
// Babies…" — biasing everything toward that slice).
function sampleSpread(arr, n) {
  const a = (arr || []).filter(Boolean);
  if (a.length <= n) return a;
  const out = [];
  const stride = a.length / n;
  for (let i = 0; i < n; i++) out.push(a[Math.floor(i * stride)]);
  return [...new Set(out)];
}

async function classifyStoreCategory(selfDomain, industry, cats, taxonomyPath = "") {
  if (!cats.length && !industry && !taxonomyPath) return "";
  try {
    // Sample ACROSS the catalog so a wide store isn't judged by its first few
    // alphabetical categories.
    const prompt = `In 2 to 4 words, name the overall PRODUCT CATEGORY this online store sells. Reply with ONLY the category phrase — no punctuation, no explanation.

Store: ${selfDomain}
Industry: ${industry || "unknown"}
${taxonomyPath ? `Classified as: ${taxonomyPath}
` : ""}Sells: ${sampleSpread(cats, 20).join(", ") || "unknown"}

If the store spans many unrelated categories (e.g. clothing, beauty, home, toys, electronics), answer exactly: general merchandise.
Examples of good answers: "activewear clothing", "color cosmetics", "hair care products", "athletic footwear", "general merchandise".
Category:`;
    const raw = await llmComplete(prompt, { maxTokens: 24 });
    const line = String(raw || "").split("\n")[0].replace(/["'.:]/g, "").trim();
    if (line && line.length <= 40 && line.split(/\s+/).length <= 5) return line.toLowerCase();
  } catch (err) {
    console.error("classifyStoreCategory error:", err?.message || err);
  }
  return "";
}

/* Classify each discovered domain by NAME/knowledge into brand / marketplace /
   other. This is the ONE signal that doesn't need a (often-blocked) probe — the
   model knows Naheed is a marketplace, a news site is "other", etc. Decisive,
   retried, safe (classification, no URLs). Returns Map<domain, type>; unknown
   domains are absent. */
async function classifyDomainsFull(domains, region, category) {
  if (!domains.length) return new Map();
  const prompt = `Classify each website for a competitor search. Output one type per domain:
- "brand": an online shop that sells its OWN single brand's products.
- "marketplace": a multi-brand retailer / shop selling MANY different brands (department stores, beauty superstores, general marketplaces such as Naheed, Daraz).
- "other": NOT a product shop — news, blog, listicle, directory, service/booking site, organisation.
Context: ${category || "retail"} sites${region ? ` in ${region}` : ""}.

Domains:
${domains.map((d) => `- ${d}`).join("\n")}

Classify DECISIVELY using what you know about each site (and its name). Reply ONLY JSON: {"brand":[…],"marketplace":[…],"other":[…]}. Every domain in exactly one list.`;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const raw = await llmComplete(prompt, { maxTokens: 900 });
      const parsed = parseJsonLoose(raw);
      const map = new Map();
      if (parsed && typeof parsed === "object") {
        for (const type of ["marketplace", "other", "brand"]) {
          for (const d of parsed[type] || []) {
            const nd = normDomain(d);
            if (nd && !map.has(nd)) map.set(nd, type);
          }
        }
      }
      if (map.size) return map;
    } catch (err) {
      console.error(`classifyDomainsFull attempt ${attempt + 1}:`, err?.message || err);
    }
  }
  console.warn("🔎 [suggest] classifyDomainsFull returned nothing");
  return new Map();
}

/* Classify each store as a SINGLE BRAND or a MULTI-BRAND MARKETPLACE using its
   PROBED product titles — a marketplace's titles are full of many DIFFERENT
   brand names; a single brand's are all its own. Safe LLM use (classification,
   no URLs). Retries once so a single flaky response doesn't skip filtering.
   Returns Map<domain, "brand"|"marketplace">. */
async function classifyByTitles(cands, region, category) {
  const withTitles = cands.filter((c) => (c.titles || []).length);
  if (!withTitles.length) return new Map();

  const body = cands
    .map((c) => {
      const sample = (c.titles || []).slice(0, 12).join("; ");
      return `- ${c.domain} — ${c.name || ""}\n  products: ${sample || "unknown"}`;
    })
    .join("\n");
  const prompt = `Classify each online store as "brand" (sells only its OWN single brand's products) or "marketplace" (a multi-brand retailer whose products span MANY different brands). Judge mainly by the product titles: many different brand names in the titles ⇒ marketplace.
Context: ${category || "retail"} stores${region ? ` in ${region}` : ""}.

${body}

Reply with ONLY JSON: {"brand":["domain", …], "marketplace":["domain", …]}. Put every store in exactly one list.`;

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const raw = await llmComplete(prompt, { maxTokens: 700 });
      const parsed = parseJsonLoose(raw);
      const map = new Map();
      if (parsed && typeof parsed === "object") {
        for (const d of parsed.marketplace || []) {
          const nd = normDomain(d);
          if (nd) map.set(nd, "marketplace");
        }
        for (const d of parsed.brand || []) {
          const nd = normDomain(d);
          if (nd && !map.has(nd)) map.set(nd, "brand");
        }
      }
      if (map.size) return map; // success
    } catch (err) {
      console.error(`classifyByTitles attempt ${attempt + 1} error:`, err?.message || err);
    }
  }
  console.warn("🔎 [suggest] classifyByTitles returned no classification");
  return new Map();
}

// Which of the owner's tracked categories a competitor actually carries.
function coverage(pickLabels, storeText) {
  const text = ` ${String(storeText || "").toLowerCase()} `;
  const out = [];
  for (const label of pickLabels) {
    const words = label.toLowerCase().split(/\s+/).filter((w) => w.length > 2);
    if (words.some((w) => text.includes(w) || text.includes(w.replace(/s$/, "")))) out.push(label);
  }
  return [...new Set(out)];
}

/* LLM peer-set discovery — a NON-SEO candidate source. Web search ranks by SEO
   authority (category giants win); the model instead knows real peer sets, so we
   ask it for competitors of SIMILAR size/positioning and merge those domains into
   the candidate pool. Hallucinated / dead domains are caught by the same
   verification every candidate goes through. Best-effort → [] on any failure. */
async function llmPeerDomains(selfDomain, category, ownCategories, region, isMultiBrand) {
  try {
    const cats = sampleSpread(ownCategories || [], 12).join(", ");
    const prompt = `List up to 12 real online ${isMultiBrand ? "multi-brand retailers" : "direct competitor brands"} for this store.
Store: ${selfDomain}
Sells: ${category || cats || "unknown"}${cats && category ? ` (${cats})` : ""}
${region ? `Market: ${region}. Prefer stores serving this market.` : ""}

Rules:
- Real, currently-operating ONLINE STORES of SIMILAR size and positioning.
- NOT giant marketplaces (Amazon, eBay, Daraz) and NOT category-leader megabrands.
- Return bare registrable domains only (e.g. "brand.com"), no paths.
Reply ONLY JSON: {"domains":["a.com","b.com", ...]}.`;
    const raw = await llmComplete(prompt, { maxTokens: 400 });
    const parsed = parseJsonLoose(raw);
    const list = Array.isArray(parsed?.domains) ? parsed.domains : [];
    const out = [];
    for (const d of list) {
      const nd = normDomain(d);
      if (nd && nd !== selfDomain) out.push(nd);
    }
    return [...new Set(out)];
  } catch (err) {
    console.warn("🔎 [suggest] llmPeerDomains failed (continuing):", err?.message || err);
    return [];
  }
}

// ── Similarity scoring (real competitors, not just SEO-strong stores) ─────────
// A real competitor resembles the user's store: similar PRICE BAND, catalog SIZE,
// CATEGORY overlap, ASSORTMENT and MARKET. We score each verified candidate on
// these and re-rank; giants are excluded separately. Every signal is best-effort —
// missing data down-weights (never crashes), and its weight is redistributed.
const _TITLE_STOP = new Set([
  "the", "and", "for", "with", "your", "our", "new", "sale", "set", "kit", "pack",
  "size", "black", "white", "men", "mens", "women", "womens", "kids", "unisex",
  "gift", "card", "shop", "all", "collection", "edition", "premium", "classic",
]);
function _priceStats(prices) {
  const xs = (prices || []).filter((x) => Number.isFinite(x) && x > 0).sort((a, b) => a - b);
  if (!xs.length) return null;
  const q = (p) => xs[Math.min(xs.length - 1, Math.max(0, Math.floor(p * (xs.length - 1))))];
  return { median: q(0.5), lo: q(0.25), hi: q(0.75), count: xs.length };
}
function _priceSim(a, b) {
  if (!a || !b || a.median <= 0 || b.median <= 0) return null;
  return Math.min(a.median, b.median) / Math.max(a.median, b.median); // 1 = same band
}
function _sizeSim(a, b) {
  if (!Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) return null;
  return Math.min(a, b) / Math.max(a, b);
}
function _titleTokens(titles) {
  const s = new Set();
  for (const t of titles || []) {
    for (const w of String(t).toLowerCase().split(/[^a-z0-9]+/)) {
      if (w.length >= 3 && !_TITLE_STOP.has(w)) s.add(w);
    }
  }
  return s;
}
function _jaccard(a, b) {
  if (!a.size || !b.size) return 0;
  let inter = 0;
  for (const x of a) if (b.has(x)) inter++;
  return inter / (a.size + b.size - inter);
}
// Weighted blend that renormalises over the signals we actually have.
function _blend(parts) {
  let sum = 0, wsum = 0;
  for (const [val, w] of parts) {
    if (val == null || Number.isNaN(val)) continue;
    sum += val * w; wsum += w;
  }
  return wsum ? sum / wsum : 0;
}

/**
 * Discover verified, regional competitors for a store via web search.
 * Returns [{ name, domain, url, reason, matchedCategories, similarityScore, whyMatch }].
 */
export async function suggestCompetitors(url, industry, pages = [], currency = "", userCategories = [], ownerProfile = null) {
  const origin = toOrigin(url);
  if (!origin) return [];
  const selfDomain = normDomain(origin);

  // Store profile from onboarding (Steps 2–4): business type, market, taxonomy.
  // Passed by the recon worker from the saved owner doc, else from the readiness
  // cache. Every use below is optional — without it the old heuristics run.
  const profile = ownerProfile || getCachedProfile(origin) || null;
  const ownTaxonomy = profile?.taxonomy?.industry ? profile.taxonomy : null;
  const ownType = profile?.businessType ?? null;
  try { await loadSharedGiants(); } catch { /* keep built-in exclusions */ }

  // User-typed target categories (from the "target specific categories" control).
  // When present, they REPLACE auto-detection as the search seeds — so this also
  // rescues stores whose catalog we can't read (the search still runs on what the
  // user knows they sell), and skips the slow catalog crawl entirely.
  const userCats = [...new Set(
    (Array.isArray(userCategories) ? userCategories : String(userCategories || "").split(","))
      .map((c) => String(c || "").trim().toLowerCase())
      .filter((c) => c.length >= 2 && c.length <= 40)
  )].slice(0, 12);

  // Classify the user's own site early (brand vs marketplace) — its probe also
  // detects the store's CURRENCY, which we use as a region fallback below.
  const userProbePromise = probeStore(origin, false).catch(() => null);

  // Region: confirmed currency → host keyword → ccTLD. If STILL unknown (e.g. a
  // .com store with no region hint and no passed currency), fall back to the
  // user's OWN store's detected currency (a PK store priced in PKR resolves to
  // Pakistan). We never assume a default region — unknown stays unknown.
  let region = resolveRegion(origin, currency);
  // A detected home country (Shopify store settings / JSON-LD address) beats a
  // currency guess: a Pakistani store priced in USD is still a Pakistan store.
  const marketCountry = profile?.market?.confidence !== "low" ? profile?.market?.country : null;
  if (marketCountry) {
    const byCountry = Object.entries(REGION_COUNTRY).find(([, iso]) => iso === marketCountry)?.[0];
    if (byCountry) region = byCountry;
  }
  let fallbackCurrency = "";
  if (!region) {
    const up = await userProbePromise;
    fallbackCurrency = up?.currency ? String(up.currency).toUpperCase() : "";
    if (fallbackCurrency) region = CURRENCY_REGION[fallbackCurrency] || null;
    // Still unknown (a EUR store — currency can't pin one country) → use the
    // store's CONTENT LANGUAGE as a region hint (de_DE → Germany). This lets the
    // regional gate keep European competitors and drop US ones.
    if (!region && up?.language) {
      const lang = String(up.language).split("-")[0].toLowerCase();
      region = LANGUAGE_REGION[lang] || null;
      if (region) console.log(`🔎 [suggest] region from language "${up.language}" -> ${region}`);
    }
  }
  const country = REGION_COUNTRY[region];
  const regionCurrency = REGION_CURRENCY[region];
  // The user's country for URL localisation (geo-gated competitors). Confirmed
  // currency first, then the own-store fallback currency, then the region.
  const effectiveCurrency = String(currency || "").toUpperCase() || fallbackCurrency;
  const userCountry = CURRENCY_COUNTRY[effectiveCurrency] || country || null;
  const pageHints = hintsFromPages(pages);

  // Category signal from the owner's own store. FAST PATH FIRST: a direct JSON
  // read of the store's categories — Shopify /collections.json or WooCommerce's
  // Store API — returns real category titles (Foundation, Lipsticks, …) in ~1s.
  // The full catalog is slow (its nav-menu extraction can escalate to a browser
  // render and blow past any timeout), so we only fall back to it when neither
  // fast path applies (Wix / Squarespace / custom, or blocked).
  let categoryHints = [];
  let navCats = [];
  let fastCats = [];
  let fastRawCount = 0;
  let quickCats = [];
  let quickCurrency = "";
  // Skip ALL catalog detection when the user supplied their own categories — their
  // list is the seed, and we avoid the slow (sometimes 20–50s) crawl entirely.
  if (!userCats.length) {
  try {
    const fast = await getStoreCategoriesFast(origin);
    fastRawCount = fast.length;
    fastCats = fast.map((c) => c.title).filter((t) => isGoodNavCategory(t));
  } catch {
    /* proceed without */
  }
  // Fetch the curated catalog (nav menu + product types) when EITHER the fast path
  // gave nothing (non-Shopify / blocked), OR it returned a big, noisy collection
  // list. Large stores like Gymshark dump 150+ collections full of facets/promos,
  // where the merchant's NAV MENU (Men/Women → Shorts, Leggings) is a far cleaner
  // seed than the raw dump. Time-boxed; reads the cache warmed on detect-stores.
  const NOISY_COLLECTION_COUNT = 40;
  if (!fastCats.length || fastRawCount > NOISY_COLLECTION_COUNT) {
    try {
      const cat = await Promise.race([
        getCatalogCached(origin),
        new Promise((resolve) => setTimeout(() => resolve(null), 20000)),
      ]);
      if (cat) {
        navCats = navCategories(cat.menu || []);
        if (!fastCats.length) {
          const types = [...new Set((cat.products || []).map((p) => p.product_type).filter(Boolean))];
          const cols = (cat.collections || []).map((c) => c.title).filter(Boolean);
          categoryHints = [...new Set([...types, ...cols])].slice(0, 25);
        }
      }
    } catch {
      /* proceed without */
    }
  }
  // Fallback for Cloudflare-blocked / JS-rendered stores where the fast Shopify/Woo
  // JSON AND the full catalog render both came up empty (e.g. stdbeauty): read the
  // category names straight from ONE rendered homepage — the same nav links the
  // onboarding validator sees. Only runs when we otherwise have nothing.
  if (![...navCats, ...fastCats, ...pageHints, ...categoryHints].length) {
    try {
      const qc = await quickCatalog(origin);
      // Homepage-nav labels come raw (unlike navCategories, which pre-filters), so
      // strip a leading "Shop " ("Shop Women" → "Women") and drop merchandising /
      // segment junk ("Last Chance", "New Accessories", "Back In Stock") that make
      // useless search seeds. Fall back to the raw list only if filtering empties it.
      const rawQuick = (qc.categories || []).map((c) => String(c).trim()).filter(Boolean);
      const goodQuick = rawQuick
        .map((c) => c.replace(/^shop\s+/i, ""))
        .filter((c) => isGoodNavCategory(c));
      quickCats = goodQuick.length ? [...new Set(goodQuick.map((c) => c.toLowerCase()))] : rawQuick;
      quickCurrency = qc.currency || "";
      if (quickCats.length) console.log(`🔎 [suggest] quick-catalog recovered ${quickCats.length} categories from rendered homepage: [${quickCats.slice(0, 10).join(", ")}]`);
    } catch { /* proceed without */ }
  }
  // If the store exposed no region but the rendered homepage gave us a currency,
  // use it to localise the search queries (e.g. PKR → Pakistan).
  if (!region && quickCurrency) region = CURRENCY_REGION[quickCurrency] || region;
  } // end catalog detection (skipped when userCats provided)

  const ownCategories = userCats.length
    ? [...new Set(userCats)]
    : [...new Set([...navCats, ...fastCats, ...pageHints, ...categoryHints, ...quickCats])];

  // ── DEBUG: what did we actually fetch/extract from the store URL? ──────────
  // Shows, per source, how many category signals we read from the site so you can
  // see exactly what onboarding "saw". If everything is 0, the store couldn't be
  // read (blocked / JS-only / non-standard platform) and the category below is a
  // blind LLM guess from the domain + industry — the usual cause of a wrong label.
  const _sample = (a, n = 8) => `[${(a || []).slice(0, n).join(", ")}${(a || []).length > n ? ", …" : ""}]`;
  console.log(
    `🔎 [suggest] fetched signals for ${origin}: ` +
    `shopify/woo fast=${fastCats.length}/${fastRawCount} ${_sample(fastCats)} | ` +
    `nav=${navCats.length} ${_sample(navCats)} | ` +
    `trackedPageHints=${(pageHints || []).length} ${_sample(pageHints)} | ` +
    `catalogHints=${categoryHints.length} ${_sample(categoryHints)} | ` +
    `→ ownCategories=${ownCategories.length} ${_sample(ownCategories, 12)}`
  );
  if (!ownCategories.length) {
    console.warn(
      `⚠️ [suggest] NO category signals could be fetched from ${origin} — the store's ` +
      `catalog/nav was unreadable (blocked, JS-only, or a non-Shopify/Woo platform). ` +
      `The category is therefore an LLM guess from the domain + industry only, and is ` +
      `likely wrong. This is the same fetch failure that leaves the market undetected.`
    );
  }

  // ── Build one region-localised query PER tracked category ────────────────
  // A genuine competitor sells MANY of the same categories, so it turns up in
  // many of these searches; a one-off store appears in only one. We search each
  // category and then rank candidates by how many searches they appeared in
  // (frequency = breadth of overlap). Short, single-category queries also return
  // far more real stores than one long phrase.
  // Real category collections lead — nav (when read) or the fast /collections.json
  // titles — so the search finds specific, comparable competitors instead of
  // category giants. Fall back to tracked pages, then catalog product types.
  const catsRaw = (
    userCats.length ? userCats
      : navCats.length ? navCats
      : fastCats.length ? fastCats
      : pageHints.length ? pageHints
      : categoryHints.length ? categoryHints
      : quickCats
  ).map((c) => c.trim()).filter(Boolean);
  // Order categories breadth-first across their distinct AREAS, so a wide catalog
  // is represented (not just its first eight page-order categories).
  const { ordered, clusterCount } = representativeCategories(catsRaw);
  // The first pass of the round-robin is one representative PER area; sampling a
  // spread of THAT (below) picks categories from across the whole catalog rather
  // than only the alphabetically-first areas.
  const perAreaReps = ordered.slice(0, clusterCount);
  // A catalog with many distinct areas is a general / multi-category store — its
  // searches must span the breadth, and must NOT be anchored to one narrow umbrella
  // (which would drag every query toward a single slice, e.g. "baby clothing").
  const broadCatalog = clusterCount >= 12;
  const rw = region || "";

  // Breadth-scaled query budget, hard-capped at 6 TOTAL queries (incl. the
  // umbrella). A genuine competitor recurs across the breadth-first areas, so 6
  // representative searches surface it without hammering the free search provider
  // or dragging out onboarding. Deliberately INDEPENDENT of the plan's page limit.
  const MAX_QUERIES = 6;
  const QUERY_CAP = Math.max(3, Math.min(MAX_QUERIES, Math.ceil(clusterCount * 1.5)));

  // Umbrella category (LLM classification) — a broad term that finds direct
  // competitors of the same KIND, alongside the per-category searches.
  const category = await classifyStoreCategory(selfDomain, industry, ownCategories, ownTaxonomy?.path || "");

  // Build the search queries. We GROUND every query with the store's overall
  // category so brand-specific collection names still search sensibly: a store's
  // own collections are often marketing names ("Night", "Glam Collection", "Mini")
  // that match nothing on their own, but "<collection> <category>" anchors them to
  // what the store actually sells. We also ALWAYS lead with a pure "<category>
  // <region>" query — broad, reliable, finds same-kind competitors even when every
  // collection name is noise. We avoid "online store" / "best … brands" phrasing —
  // those surface blogs, listicles and directories instead of real shops.
  const catStr = (category || "").trim();
  // Trust the category classifier over raw catalog breadth. A single brand can
  // have a WIDE range — Gymshark has 17 nav areas but is clearly "activewear
  // clothing" — so breadth alone must NOT mark it "general". Otherwise its
  // umbrella query is dropped and its per-category queries go unanchored (bare
  // "womens", "last chance", "headwear" → search noise), and it gets treated as
  // a multi-brand marketplace. Breadth implies "general" ONLY when the classifier
  // couldn't name a specific vertical (empty, or an explicit general/marketplace
  // label). A genuinely general store (exportleftovers) still classifies as
  // "general merchandise", so that case is preserved.
  const classifierGeneral = /general merchandise|multi-?category|marketplace|variety|department store/i.test(catStr);
  const hasSpecificVertical = !!catStr && !classifierGeneral;
  // Business Type 3 (General Marketplace) from onboarding is authoritative.
  const isGeneral = ownType === 3 || classifierGeneral || (broadCatalog && !hasSpecificVertical);
  const queries = [];
  // Narrow store: lead with the umbrella (finds broad same-kind competitors), then
  // per-category queries anchored to it. General/multi-category store: SKIP the
  // umbrella (it's meaningless / just returns marketplaces) and search a spread of
  // real categories on their own, so competitors are found across the whole breadth.
  if (catStr && !isGeneral) queries.push([catStr, rw].filter(Boolean).join(" ").trim());
  const queryCats = sampleSpread(perAreaReps, isGeneral ? MAX_QUERIES : MAX_QUERIES - 1);
  for (const c of queryCats) {
    const q = isGeneral
      ? [c, rw].filter(Boolean).join(" ").trim()
      : [c, catStr, rw].filter(Boolean).join(" ").trim();
    if (q) queries.push(q);
  }
  if (!queries.length) queries.push((rw || "online store").trim());
  // Hard cap at MAX_QUERIES total (umbrella + top breadth-first categories).
  const uniqQueries = [...new Set(queries.filter(Boolean))].slice(0, MAX_QUERIES);

  console.log(
    `🔎 [suggest] ${selfDomain} region=${region || "?"} cur=${(currency || regionCurrency || "?")} category="${category || "?"}" general=${isGeneral} | nav=${navCats.length} fast=${fastCats.length} seed="${queryCats.join(", ")}" | areas=${clusterCount} cap=${QUERY_CAP} | ${uniqQueries.length} queries`
  );

  // Is the USER a single brand, or a multi-brand / general store? This decides
  // whether multi-brand retailers count as competitors (they DO for a general
  // store, they DON'T for a single brand). Signals: broad category breadth (a
  // general store — works even when vendors can't be read), vendor diversity or a
  // shop-by-brand directory (a vertical multi-brand store), or an explicit
  // general/marketplace classification.
  const userProbeForType = await userProbePromise.catch(() => null);
  // Breadth counts toward multi-brand ONLY when there's no specific vertical —
  // same reasoning as isGeneral above. Real multi-brand signals (vendor diversity,
  // shop-by-brand markers, or an explicit general/marketplace classification) still
  // stand on their own, so a vertical multi-brand store is unaffected.
  const fastMultiBrand =
    (broadCatalog && !hasSpecificVertical) ||
    (userProbeForType?.vendorCount != null && userProbeForType.vendorCount >= MARKETPLACE_VENDOR_THRESHOLD) ||
    (userProbeForType?.marketplaceSignals != null && userProbeForType.marketplaceSignals >= 1) ||
    classifierGeneral;

  // Title-diversity fallback: catches a VERTICAL multi-brand store (e.g. a cosmetics
  // shop carrying MAC, Maybelline, …) that the fast signals miss — narrow categories,
  // vendors not readable. Only runs when the fast signals were inconclusive and we
  // have the user's own product titles, so it costs one extra LLM call at most.
  let titleMultiBrand = false;
  const ownTitles = userProbeForType?.titles || [];
  if (!fastMultiBrand && ownTitles.length >= 5) {
    try {
      const byTitles = await classifyByTitles(
        [{ domain: selfDomain, name: selfDomain, titles: ownTitles }],
        region,
        category
      );
      titleMultiBrand = byTitles?.get(selfDomain) === "marketplace";
    } catch (e) {
      console.warn("🔎 [suggest] own-title classify failed (continuing):", e?.message || e);
    }
  }

  // Onboarding business type wins when known: Types 3/4 are multi-brand, 5 is a
  // single brand. Otherwise fall back to the heuristics above.
  const userMultiBrand = ownType === 3 || ownType === 4 ? true
    : ownType === 5 && profile?.businessTypeConfidence !== "low" ? false
    : fastMultiBrand || titleMultiBrand;
  console.log(
    `🔎 [suggest] user store: ${userMultiBrand ? "multi-brand/general" : "single brand"} ` +
    `(areas=${clusterCount} vendors=${userProbeForType?.vendorCount ?? "?"} signals=${userProbeForType?.marketplaceSignals ?? "?"} ` +
    `titleDiversity=${titleMultiBrand ? "multi" : (fastMultiBrand ? "n/a" : "single")})`
  );

  // ── Discover candidate domains via search (with frequency voting) ─────────
  const votes = new Map(); // domain → { count, firstRank }
  for (const q of uniqQueries) {
    // eslint-disable-next-line no-await-in-loop
    const results = await webSearch(q, { count: 10, country });
    console.log(`🔎 [suggest]   q="${q}" -> ${results.length} results`);
    const seenThisQuery = new Set();
    for (const r of results) {
      const d = normDomain(r.url);
      if (!d || d === selfDomain || isExcluded(d, userMultiBrand) || seenThisQuery.has(d)) continue;
      seenThisQuery.add(d);
      const v = votes.get(d) || { count: 0, firstRank: votes.size };
      v.count += 1;
      votes.set(d, v);
    }
    // eslint-disable-next-line no-await-in-loop
    await sleep(700); // gentle pacing so the SearXNG engines don't rate-limit
  }

  // Rank by how many category searches a domain appeared in (breadth of overlap),
  // then by how early it was discovered. Take the strongest for verification.
  let domains = [...votes.entries()]
    .sort((a, b) => b[1].count - a[1].count || a[1].firstRank - b[1].firstRank)
    .slice(0, 24)
    .map(([d]) => d);

  // Merge in a NON-SEO candidate source: peer domains from the model's knowledge.
  // These enter verification + similarity re-rank like any other candidate, so a
  // hallucinated or off-target one is filtered out downstream.
  try {
    const peers = await llmPeerDomains(selfDomain, category, ownCategories, region, userMultiBrand);
    const have = new Set(domains);
    const extra = peers.filter((d) => d && d !== selfDomain && !have.has(d) && !isExcluded(d, userMultiBrand));
    if (extra.length) {
      console.log(`🔎 [suggest] LLM peer-set added ${extra.length}: ${extra.slice(0, 8).join(", ")}`);
      domains = [...domains, ...extra].slice(0, 30);
    }
  } catch { /* web-search candidates still stand */ }
  const voteCount = (d) => votes.get(d)?.count || 0;
  console.log(
    `🔎 [suggest] discovered ${domains.length} domains (top votes: ${domains.slice(0, 5).map((d) => `${d}×${voteCount(d)}`).join(", ")})`
  );
  if (!domains.length) return [];

  // User site type — default to "brand" when we can't tell (most stores are).
  const userProbe = await userProbePromise;
  // Match competitor TYPE to the user's type: a single brand competes with single
  // brands; a multi-brand / general store competes with other multi-brand stores.
  const userType = userMultiBrand ? "marketplace" : "brand";

  // Type-classify by name/knowledge (doesn't need a probe). Drop non-stores
  // ("other") and the wrong type (marketplaces for a brand user, or vice versa).
  // Unknown domains are kept and vetted by the probe / title filter below.
  const nameType = await classifyDomainsFull(domains, region, category);
  if (nameType.size) {
    const dropped = [];
    domains = domains.filter((d) => {
      const t = nameType.get(d);
      if (!t) return true;
      if (t === "other") {
        dropped.push(`${d}(other)`);
        return false;
      }
      if (t !== userType) {
        dropped.push(`${d}(${t})`);
        return false;
      }
      return true;
    });
    if (dropped.length) console.log(`🔎 [suggest] LLM classify dropped ${dropped.length}: ${dropped.join(", ")}`);
  }
  if (!domains.length) return [];

  // Does a candidate serve the user's region? Decisive signals first (a country
  // subdomain like us.brand.com, or a ccTLD): these must MATCH. For a gTLD
  // (.com/.net) — which has no country in the name — we accept it unless its
  // storefront currency clearly belongs to a DIFFERENT region. So a US .com
  // priced in USD (or one we couldn't read the currency of) counts as regional;
  // only a conflicting currency rules it out. The search is already localised,
  // so most gTLD results are in-region anyway.
  // For a European (eurozone) store, "in-region" means anywhere in the eurozone —
  // competitors share the EUR market — not just the exact country.
  const userEuro = EUROZONE_REGIONS.has(region);
  const isRegional = (domain, probe) => {
    if (!region) return true;
    // us.brand.com / uk.brand.com → the subdomain names the country.
    const subCc = subdomainCountry(domain);
    if (subCc) {
      if (userEuro && EUROZONE_TLDS.has(subCc.toLowerCase())) return true;
      return subCc === country;
    }
    // ccTLD is decisive.
    const cc = ccTldRegion(domain);
    if (cc) {
      if (userEuro && EUROZONE_TLDS.has(cc.code)) return true;
      return cc.region === region;
    }
    // Host names the region (…pakistan…).
    for (const [kw, rg] of HOST_KEYWORD_REGION) if (rg === region && domain.includes(kw)) return true;
    // gTLD: reject only if the store's currency clearly belongs elsewhere.
    const cur = probe?.currency ? String(probe.currency).toUpperCase() : "";
    if (cur) {
      if (userEuro) {
        // A eurozone store's competitor should be EUR-priced (or currency-unknown).
        // A concrete NON-EUR currency (USD, GBP, …) means a different market → drop.
        if (cur !== "EUR" && CURRENCY_COUNTRY[cur]) return false;
      } else {
        const curRegion = CURRENCY_REGION[cur];
        if (curRegion && curRegion !== region) return false;
      }
    }
    return true; // gTLD, in-region or currency-unknown → keep
  };

  // ── Verify (regional required; ecommerce best-effort) ────────────────────
  // Collect a BUFFER (more than the final 6) so the title-based type gate below
  // can drop a couple of marketplaces and still leave a full list.
  const PROBE_TARGET = 10;
  const verified = [];
  const drops = [];
  const BATCH = 3; // smaller batches + a pause between them → less Cloudflare
  for (let i = 0; i < domains.length && verified.length < PROBE_TARGET; i += BATCH) {
    if (i > 0) await sleep(500); // eslint-disable-line no-await-in-loop
    const slice = domains.slice(i, i + BATCH);
    // eslint-disable-next-line no-await-in-loop
    const probes = await Promise.all(
      slice.map(async (d) => {
        let probe = null;
        try {
          probe = await probeStore(`https://${d}`, false);
        } catch {
          /* keep null */
        }
        return { d, probe: probe || {} };
      })
    );

    for (const { d, probe } of probes) {
      if (verified.length >= PROBE_TARGET) break;
      // A probe that timed out / couldn't be read → we can't verify the site, so
      // we deliberately DON'T recommend it (slow/hard-to-probe sites are usually
      // big aggregators or ones we can't analyse well anyway).
      const exists = probe.exists || probe.reachable;
      if (!exists) {
        drops.push(`${d}(unverified)`);
        continue;
      }
      if (!isRegional(d, probe)) {
        drops.push(`${d}(not-regional)`);
        continue;
      }
      // Is it an ecommerce STORE? Candidates already passed the LLM type filter
      // (brand, not "other"), so:
      //   • catalog reads with prices  → confirmed, OR
      //   • homepage looks like a shop  → store (catalog just blocked), OR
      //   • homepage couldn't be read AT ALL (fully Cloudflare-blocked) → keep,
      //     trusting the LLM's brand classification.
      // A homepage we DID read that shows NO shop markers → drop (contradicts
      // the classification: it's a brochure/other).
      const isStore = !!(probe.reachable && probe.hasPricing);
      const homepageRead = probe.looksLikeStore === true || probe.looksLikeStore === false;
      let storeOk = isStore || probe.looksLikeStore === true;
      if (!storeOk && !homepageRead) storeOk = true; // fully blocked but LLM-vetted brand
      if (!storeOk) {
        drops.push(`${d}(not-store)`);
        continue;
      }
      // Type match: a brand user gets brands; a marketplace user gets
      // marketplaces. Known-mismatch is dropped; unknown type is kept but
      // ranked below confirmed same-type matches.
      const candType = siteType(probe);
      if (candType && candType !== userType) {
        drops.push(`${d}(type:${candType})`);
        continue;
      }
      const text = [
        ...(probe.categories || []),
        ...(probe.productTypes || []),
        ...(probe.titles || []),
      ].join(" ");
      const matched = coverage(ownCategories, text);
      const name = cleanName(probe.siteName) || titleFromDomain(d);
      // Send geo-gated stores to the user's regional storefront (zara.com → /us).
      const url = localizeUrl(`https://${d}`, probe.locales, userCountry);
      verified.push({
        name,
        domain: d,
        url,
        reason: "",
        matchedCategories: matched,
        _typed: candType === userType,
        _isStore: isStore,
        _cov: matched.length,
        _votes: voteCount(d), // how many category searches it appeared in
        _titles: (probe.titles || []).slice(0, 14),
        _currency: probe.currency ? String(probe.currency).toUpperCase() : "",
      });
    }
  }

  if (drops.length) console.log(`🔎 [suggest] dropped ${drops.length}: ${drops.join(", ")}`);

  // Final, accurate type gate using the PROBED product titles. A marketplace's
  // titles mention many DIFFERENT brand names; a single brand's don't. This
  // catches the multi-brand retailers the name-based filter couldn't tell apart
  // (colorshow.pk, reana.pk). Only drops confident mismatches.
  if (verified.length) {
    const typeByTitles = await classifyByTitles(
      verified.map((v) => ({ domain: v.domain, name: v.name, titles: v._titles })),
      region,
      category
    );
    if (typeByTitles.size) {
      const wrong = [];
      const filtered = verified.filter((v) => {
        const t = typeByTitles.get(v.domain);
        if (t && t !== userType) {
          wrong.push(`${v.domain}(${t})`);
          return false;
        }
        return true;
      });
      if (wrong.length) console.log(`🔎 [suggest] title type-filter dropped: ${wrong.join(", ")}`);
      // Never let a bad LLM response empty the list.
      if (filtered.length) verified.splice(0, verified.length, ...filtered);
    }
  }

  // Coarse pre-rank (same-type → confirmed store → search-breadth → coverage), then
  // take the strongest few to DEEP-probe for similarity. We only deep-probe the top
  // set to bound latency.
  verified.sort(
    (a, b) =>
      Number(b._typed) - Number(a._typed) ||
      Number(b._isStore) - Number(a._isStore) ||
      b._votes - a._votes ||
      b._cov - a._cov
  );
  const DEEP = 8;
  const deep = verified.slice(0, DEEP);

  // ── Similarity re-rank: score each deep candidate against the user's store on
  //    price band, catalog size, category overlap, assortment and market. Exclude
  //    giants. Falls back to the coarse order if scoring can't run. ───────────────
  try {
    const withTimeout = (p, ms, fb) =>
      Promise.race([Promise.resolve(p).catch(() => fb), new Promise((r) => setTimeout(() => r(fb), ms))]);

    // User baseline (once): price band, catalog size, assortment tokens, currency.
    const [userSample, userTotalRaw] = await Promise.all([
      withTimeout(sampleStorePrices(origin), 9000, { prices: [], titles: [], count: 0 }),
      withTimeout(getStoreProductTotal(origin), 12000, null),
    ]);
    const userPrice = _priceStats(userSample.prices);
    const userTotal = Number.isFinite(userTotalRaw) ? userTotalRaw : null;
    const userTitleTokens = _titleTokens([...(ownTitles || []), ...(userSample.titles || [])]);
    const userCur = String(currency || userProbeForType?.currency || regionCurrency || "").toUpperCase();
    const ownCatN = Math.max(1, (ownCategories || []).length);

    // Deep-probe candidates in parallel: price+title sample, catalog size, scale.
    await Promise.all(deep.map(async (c) => {
      const [sample, totalRaw] = await Promise.all([
        withTimeout(sampleStorePrices(`https://${c.domain}`), 9000, { prices: [], titles: [], count: 0 }),
        withTimeout(getStoreProductTotal(`https://${c.domain}`), 12000, null),
      ]);
      const total = Number.isFinite(totalRaw) ? totalRaw : null;
      let scale = null;
      try { scale = await withTimeout(checkScale({ url: `https://${c.domain}`, totalProducts: total }), 12000, null); } catch { /* ignore */ }
      c._enterprise = scale?.scaleTier === "enterprise" || scale?.isMarketplace === true;

      const priceSim = _priceSim(userPrice, _priceStats(sample.prices));
      const sizeSim = _sizeSim(userTotal, total);
      const catSim = Math.min(1, (c._cov || 0) / ownCatN);
      const assortSim = _jaccard(userTitleTokens, _titleTokens([...(c._titles || []), ...(sample.titles || [])]));
      const marketSim = userCur && c._currency ? (c._currency === userCur ? 1 : 0.6) : null;
      // Step 4: same Industry → Category → Subcategory as the user's store?
      // Prevents suggesting stores that sell similar items to a different audience.
      const candTax = taxonomyFromKeywords({ titles: [...(c._titles || []), ...(sample.titles || [])] });
      const taxSim = ownTaxonomy && candTax.industry ? taxonomySimilarity(ownTaxonomy, candTax) : null;
      c._taxPath = candTax.path;
      c._offVertical = taxSim === 0 && candTax.confidence !== "low";

      c._sim = _blend([
        [priceSim, 0.30],
        [sizeSim, 0.15],
        [catSim, 0.15],
        [taxSim, 0.15],
        [assortSim, 0.15],
        [marketSim, 0.10],
      ]);
      // Human-readable reasons for the strongest signals.
      const why = [];
      if (priceSim != null && priceSim >= 0.6) why.push("similar price range");
      if (sizeSim != null && sizeSim >= 0.5) why.push("similar catalog size");
      if ((c._cov || 0) > 0) why.push(`overlaps ${c._cov} of your categories`);
      if (assortSim >= 0.12) why.push("similar products");
      if (taxSim != null && taxSim >= 0.85) why.push(`same category (${ownTaxonomy.category})`);
      if (marketSim === 1) why.push("same market");
      c._why = why.slice(0, 3).join(" · ");
    }));

    // Giant exclusion — drop enterprise-scale / marketplace-scale domains entirely
    // (never peers for a self-serve store), unless that would empty the list.
    const nonGiant = deep.filter((c) => !c._enterprise);
    const droppedGiants = deep.filter((c) => c._enterprise).map((c) => c.domain);
    if (droppedGiants.length) console.log(`🔎 [suggest] excluded giants: ${droppedGiants.join(", ")}`);
    // Off-vertical (a confidently different industry) — dropped unless that
    // would leave nothing to suggest.
    const onVertical = nonGiant.filter((c) => !c._offVertical);
    const offV = nonGiant.filter((c) => c._offVertical).map((c) => `${c.domain}(${c._taxPath})`);
    if (offV.length) console.log(`🔎 [suggest] excluded off-vertical: ${offV.join(", ")}`);
    const pool = onVertical.length ? onVertical : nonGiant.length ? nonGiant : deep;

    // Re-rank by similarity (tie-break: same-type, then search breadth).
    pool.sort(
      (a, b) => (b._sim || 0) - (a._sim || 0) || Number(b._typed) - Number(a._typed) || b._votes - a._votes
    );
    const kept = pool.slice(0, 6).map((c) => ({
      name: c.name, domain: c.domain, url: c.url,
      reason: c.reason, matchedCategories: c.matchedCategories,
      similarityScore: Math.round((c._sim || 0) * 100) / 100,
      whyMatch: c._why || "",
    }));
    console.log(`🔎 [suggest] similarity-ranked ${kept.length} [${kept.map((c) => `${c.domain}(${c.similarityScore})`).join(", ")}]`);
    return kept;
  } catch (simErr) {
    console.warn("🔎 [suggest] similarity re-rank failed — using coarse order:", simErr?.message || simErr);
    const kept = verified
      .slice(0, 6)
      .map(({ name, domain, url, reason, matchedCategories }) => ({ name, domain, url, reason, matchedCategories }));
    console.log(`🔎 [suggest] verified ${kept.length} [${kept.map((c) => c.domain).join(", ")}]`);
    return kept;
  }
}
