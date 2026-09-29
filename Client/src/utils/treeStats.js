/* Walk a page tree once and derive the stats the onboarding page-pickers need:
 *   - totalPages    : number of selectable URLs (mega-retailer signal)
 *   - countByUrl    : url → product count for collections that carry one
 *   - collCount     : how many collections we found (counted or not)
 *   - coverageRatio : share of collections that actually have a count
 *
 * coverageRatio drives whether we HARD-enforce the product budget: a store where
 * most collections have no count would produce an unreliable partial estimate,
 * so we only enforce when coverage is healthy and otherwise let the page limit
 * govern. A node is treated as a collection when it sits under a "Collections"
 * bucket, its URL has a collection marker, or it already carries a count.
 */
const isCollectionsBucket = (name) =>
  /collection/i.test(name || "") && !/product|other/i.test(name || "");

const hasCollectionMarker = (u) =>
  /\/(collections?|product-category|product[_-]cat|categor(y|ies)|shop)\b/i.test(u || "");

/* Index / utility pages that LOOK like collections but aren't real ones — the
   bare "/collections" listing, "/collections/all", a "/shop" or category root.
   They carry a collection marker in their URL but hold no focused catalog, so
   they should never be auto-selected (the breakout.com.pk "/collections" bug). */
const isIndexPage = (u) => {
  let path = u || "";
  try {
    path = new URL(u).pathname;
  } catch {
    /* keep raw */
  }
  const p = path.replace(/\/+$/, "").toLowerCase();
  return (
    p === "" ||
    /\/(collections|shop|store|products|product-category|product[_-]cat|categor(y|ies))$/.test(p) ||
    /\/collections\/all$/.test(p)
  );
};

/* An individual product page (Shopify /products/<handle>, Woo /product/<slug>) —
   NOT a collection like /product-category/. These aren't the tracking unit (we
   monitor collections/pages), and a large store carries hundreds-to-thousands of
   them, which bloats the tree, the selection memos, and the competitor mapping
   dropdowns to the point of hanging. We prune them from the picker entirely. */
export const isProductPage = (u) => {
  let path = u || "";
  try {
    path = new URL(u).pathname;
  } catch {
    /* keep raw */
  }
  const p = path.toLowerCase();
  return /\/products?\/[^/]+/.test(p) && !/\/product[-_](category|cat|tag|categories)/.test(p);
};

/* Return a copy of the tree keeping AT MOST `limit` individual product pages (the
   first ones in nav/discovery order), dropping the rest and any bucket left empty.
   Products aren't the tracking unit and a big store carries thousands of them,
   which hangs the picker; a small capped sample keeps browsing possible while
   staying fast (anything missed can be added by pasting its URL). Pass limit=0 to
   drop products entirely. O(n), run once when the tree loads. */
export function capProductPages(treeData, limit = 150) {
  if (!treeData || typeof treeData !== "object") return treeData;
  let kept = 0;
  const walk = (nodes) => {
    const out = {};
    for (const [key, node] of Object.entries(nodes)) {
      if (!node || typeof node !== "object") continue;
      const children = node.children ? walk(node.children) : {};
      const childCount = Object.keys(children).length;
      // Product-page leaf: keep up to `limit`, drop the rest.
      if (node.url && isProductPage(node.url) && childCount === 0) {
        if (kept >= limit) continue;
        kept += 1;
      }
      // Drop a header/bucket (no url) left empty once its products were dropped.
      if (!node.url && childCount === 0 && node.children && Object.keys(node.children).length) continue;
      out[key] = { ...node, children };
    }
    return out;
  };
  return walk(treeData);
}

/* How many individual product pages the crawl found (before any cap). Lets the
   picker decide, per site, whether to show a browsable product catalog or switch
   to guided paste/search — and to honestly label a shown sample as a subset. */
export function countProductPages(treeData) {
  if (!treeData || typeof treeData !== "object") return 0;
  let n = 0;
  const walk = (nodes) => {
    for (const node of Object.values(nodes || {})) {
      if (!node || typeof node !== "object") continue;
      const childCount = node.children ? Object.keys(node.children).length : 0;
      if (node.url && isProductPage(node.url) && childCount === 0) n += 1;
      if (node.children) walk(node.children);
    }
  };
  walk(treeData);
  return n;
}

const isPricingLike = (u, name) =>
  /pricing|\/plans?(\/|$)|packages?|subscription|\/sale(\/|$)|offers?/i.test(`${u || ""} ${name || ""}`);

const isFeatureLike = (u, name) =>
  /features?|solutions?|product(s)?(\/|$)|use[-_]?cases?|platform/i.test(`${u || ""} ${name || ""}`);

/* A synthetic menu-group header the tree injects to mirror the storefront nav
   (e.g. "Men", "Clothing"). It carries no url, and its slug is "grp-<label>" —
   but NOT the "grp-bucket-*" top-level tab (Collections / Products). A collection
   leaf's menu LEVEL is 1 + how many of these headers sit above it, so ancestry
   (and therefore containment) comes straight from the nav we already parsed. */
const isMenuGroup = (node) =>
  !!node &&
  node.url == null &&
  typeof node.slug === "string" &&
  node.slug.startsWith("grp-") &&
  !node.slug.startsWith("grp-bucket-");

/* Dynamic merchandising surfaces — New In, Sale, Best Sellers, Trending. They
   change constantly and reveal a competitor's live strategy, so they earn a
   default slot regardless of catalog level. */
const isDynamicPage = (name, u) =>
  /\b(new|new[-\s]?in|arrivals?|sale|clearance|best[-\s]?sell|bestsellers?|trending|featured|drops?)\b/i.test(
    `${name || ""} ${u || ""}`
  );

/* Plan page-budgets, kept in sync with the seeder — used only to name the
   smallest paid plan that would comfortably cover a catalog's category spine. */
export const PLAN_TIERS = [
  { name: "Starter", pages: 20 },
  { name: "Growth", pages: 50 },
  { name: "Pro", pages: 150 },
];

/* Every selectable collection leaf with its menu ancestry, so callers can reason
   about levels (L1/L2/L3) and containment purely from nav structure — no product
   counts. `groups` is the ordered list of menu-group ancestors (["Men","Clothing"]),
   `level` = groups.length + 1, `branch` = the top-level branch it lives under. */
function collectCollections(treeData) {
  const out = [];
  const walk = (nodes, groupChain, underCollections) => {
    for (const node of Object.values(nodes || {})) {
      if (!node || typeof node !== "object") continue;
      const nextChain = isMenuGroup(node) ? [...groupChain, node.name] : groupChain;
      const here = underCollections || isCollectionsBucket(node.name);
      const isCollectionLeaf =
        node.url && !isIndexPage(node.url) && (here || hasCollectionMarker(node.url));
      if (isCollectionLeaf) {
        out.push({
          url: node.url,
          name: node.name || "",
          groups: groupChain,
          level: groupChain.length + 1,
          dynamic: isDynamicPage(node.name, node.url),
          branch: groupChain[0] || node.name || "",
          kind: node.kind || null, // category | brand | marketing | unknown (backend)
          inNav: !!node.inNav,
        });
      }
      if (node.children) walk(node.children, nextChain, here);
    }
  };
  walk(treeData, [], false);
  return out;
}

const lc = (s) => (s || "").toLowerCase();

/* Collections worth AUTO-RECOMMENDING for tracking: real product categories, not
   brand pages ("COSRX") or marketing/editorial pages ("Gifts under $20", "Best
   Sellers"). `kind` is tagged by the backend from the store's own vendor +
   product_type data, and is only ever "brand" on genuinely multi-brand stores —
   so a single-brand store's collections are all kept. Missing kind (non-Shopify
   or older payloads) is treated as trackable, so nothing regresses. */
const isTrackableKind = (c) => c.kind !== "brand" && c.kind !== "marketing";

/* Facet / attribute "collections" — a size, length, or colour SLICE of a real
   category ("5 Inch Shorts", "Black Gym Sets", "XL", "315"). They're views of a
   category, not the category itself, so we never AUTO-suggest them (they stay
   fully browsable for manual selection). Deliberately conservative: colour only
   counts as a facet when it's colour + a known apparel word, so "Green Tea
   Cleanser" and the like are never mistaken for a facet. */
const FACET_COLORS =
  "black|white|blue|red|green|pink|purple|grey|gray|brown|beige|navy|burgundy|maroon|orange|yellow|cream|tan|khaki|olive|teal|charcoal|lilac";
const FACET_APPAREL =
  "gym sets?|leggings|shorts|hoodies|joggers|tops?|tracksuits?|sets?|tees?|t ?shirts?|tshirts?|sports bras?|bras?|jackets?|shirts?|pants|sweatshirts?|crop tops?|vests?";
const facetColorRe = new RegExp(`^(${FACET_COLORS}) (${FACET_APPAREL})$`);
function isFacet(name, url) {
  let s = (name || "").toLowerCase().trim();
  if (!s) {
    try {
      s = decodeURIComponent(new URL(url).pathname.split("/").filter(Boolean).pop() || "").replace(/-/g, " ");
    } catch {
      s = "";
    }
  }
  s = s.toLowerCase().replace(/[^a-z0-9" ]+/g, " ").replace(/\s+/g, " ").trim();
  if (!s) return false;
  if (/\b\d+\s*(inch|cm|mm)\b/.test(s) || /\d+\s*"/.test(s)) return true; // "5 inch", 8"
  if (/^\d+(\.\d+)?$/.test(s)) return true; // bare number like "315"
  if (/^(xs|s|m|l|xl|xxl|xxxl|2xl|3xl|4xl|small|medium|large|x large|petite|tall|plus size|one size)$/.test(s))
    return true; // size code
  if (facetColorRe.test(s)) return true; // "black gym sets", "blue leggings"
  return false;
}

const isSuggestable = (c) => isTrackableKind(c) && !isFacet(c.name, c.url);

/* A "hub" is a category that has sub-items. The nav flattener appends a hub's
   own title to its group path (but not a plain leaf's), so a collection whose
   name equals its LAST group label is reliably a hub — regardless of how the raw
   depth got capped. This is what lets us pick mid-level categories cleanly. */
const isHub = (c) =>
  c.groups.length > 0 && lc(c.name) === lc(c.groups[c.groups.length - 1]);

/* The catalog "spine": one coherent tier of categories to track — the level just
   below the top branches (Men/Women/Kids). Per branch we drop the branch root
   ("Men" itself), then:
     • if the branch exposes hubs (mid categories with their own sub-items), keep
       the hubs and drop their descendant leaves — so we track "Men Clothing", not
       "Men Clothing" AND "Men T-Shirts";
     • otherwise keep the direct sub-category leaves.
   This holds whether the merchant's menu is two or three levels deep, and never
   suggests an ancestor alongside its descendants. Shared by the default picker
   and the oversized assessment so they always agree. */
function spineOf(cols) {
  const nonDynamic = cols.filter((c) => !c.dynamic);
  const byBranch = new Map();
  for (const c of nonDynamic) {
    const b = lc(c.branch);
    if (!byBranch.has(b)) byBranch.set(b, []);
    byBranch.get(b).push(c);
  }

  const spine = [];
  for (const [branch, items] of byBranch) {
    // Drop the branch root ("Men") only when the branch has other members — a
    // genuinely standalone top-level collection keeps its slot.
    const hasOthers = items.length > 1;
    const cand = items.filter(
      (c) => !(lc(c.name) === branch && c.groups.length <= 1 && hasOthers)
    );

    const hubs = cand.filter(isHub);
    if (hubs.length) {
      const hubNames = new Set(hubs.map((h) => lc(h.name)));
      for (const c of cand) {
        if (isHub(c)) spine.push(c);
        else if (!c.groups.some((g) => hubNames.has(lc(g)))) spine.push(c); // leaf not under a hub
      }
    } else {
      spine.push(...cand);
    }
  }

  const hasHierarchy = nonDynamic.some((c) => c.groups.length > 0);
  return { spine, hasHierarchy };
}

/* Round-robin a set of collections across their top branches (Men / Women / Kids)
   so the budget spreads evenly instead of piling into one corner of the store. */
function roundRobinByBranch(items) {
  const byBranch = new Map();
  for (const c of items) {
    const b = (c.branch || "").toLowerCase();
    if (!byBranch.has(b)) byBranch.set(b, []);
    byBranch.get(b).push(c);
  }
  const queues = [...byBranch.values()];
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
  return ordered;
}

/* SaaS / generic fallback when there's no catalog structure: pricing first,
   then features, then any other page. */
function computeFallbackPages(treeData, limit) {
  const pricing = [];
  const features = [];
  const others = [];
  const walk = (nodes) => {
    for (const node of Object.values(nodes || {})) {
      if (!node || typeof node !== "object") continue;
      if (node.url && !isIndexPage(node.url)) {
        if (isPricingLike(node.url, node.name)) pricing.push(node.url);
        else if (isFeatureLike(node.url, node.name)) features.push(node.url);
        else others.push(node.url);
      }
      if (node.children) walk(node.children);
    }
  };
  walk(treeData);
  const seen = new Set();
  const out = [];
  for (const u of [...pricing, ...features, ...others]) {
    if (seen.has(u) || !u) continue;
    seen.add(u);
    out.push(u);
    if (out.length >= limit) break;
  }
  return out;
}

/* A sensible default selection so the user never starts from a blank slate, now
 * built on nav STRUCTURE rather than flat nav order:
 *   1. one or two dynamic pages (New In / Sale / Best Sellers) — high-signal;
 *   2. the catalog SPINE — mid-level (L2) categories if present, else top-level
 *      (L1) — round-robined across branches for even coverage.
 * The spine is a single level throughout, so an ancestor and its descendant are
 * never both suggested (deeper L3 tracking is left to manual browse). Homepage is
 * handled separately. Returns up to `limit` de-duplicated URLs. */
export function computeDefaultPages(treeData, limit) {
  if (!treeData || !limit) return [];

  const cols = collectCollections(treeData);
  if (!cols.length) return computeFallbackPages(treeData, limit);

  // Suggestable = real categories only: no brand/marketing pages, and no facet
  // slices (sizes, lengths, colours like "/collections/2-inch").
  const suggestable = cols.filter(isSuggestable);

  // Menu-first: the storefront nav is the merchant's curated, high-signal set, so
  // suggest ONLY nav-featured collections when the nav gives us a usable number.
  // Fall back to the full suggestable set when the nav is thin/absent (extraction
  // miss, or a site with no real nav) so we never leave the user with nothing.
  const inNav = suggestable.filter((c) => c.inNav);
  const pool = inNav.length >= 3 ? inNav : suggestable;

  const out = [];
  const seen = new Set();
  const add = (url) => {
    if (url && !seen.has(url) && out.length < limit) {
      seen.add(url);
      out.push(url);
    }
  };

  // 1) Dynamic merchandising pages — reserve a slot or two. Keep the genuinely
  //    useful ones (New In / Sale / Best Sellers) but skip brand pages.
  const dynCap = Math.max(1, Math.min(2, Math.floor(limit * 0.25)));
  pool.filter((c) => c.dynamic && c.kind !== "brand").slice(0, dynCap).forEach((c) => add(c.url));

  // 2) The category SPINE — one coherent level, spread across branches.
  const { spine } = spineOf(pool);
  roundRobinByBranch(spine).forEach((c) => add(c.url));

  return out;
}

/* Decide which oversized-catalog notice (if any) to show, keyed on whether the
 * category SPINE fits the plan's page budget — NOT raw collection count, which
 * mislabels focused brands (breakout has 150+ collections but a small spine).
 *   • "ok"      → the spine fits this plan; no notice.
 *   • "upgrade" → bigger than THIS plan covers, but a real brand we handle well;
 *                 nudge to the smallest plan that fits.
 *   • "mega"    → too large even for Pro (hard ceiling); the marketplace /
 *                 mega-retailer limitation, shown on every plan.
 * NOTE: the precise multi-vendor marketplace SIGNAL isn't wired into the tree
 * response yet, so tier-3 uses a conservative size ceiling as a stand-in, biased
 * toward "upgrade" so we never wrongly tell a focused brand it's unsupported. */
export function assessCatalog(treeData, budget) {
  const cols = collectCollections(treeData);
  if (!cols.length) return { tier: "ok", spineSize: 0, total: 0, recommendedPlan: null };

  // spineSize = how many category pages it takes to cover this store — the ONLY
  // axis that maps to plan page-budgets (Starter 20 / Growth 50 / Pro 150). Built
  // from SUGGESTABLE categories only (brand, marketing, and facet slices excluded),
  // so a multi-brand store with 150 brand pages but 30 categories reads as 30, not
  // 180 — which stops us wrongly flagging it as a mega-retailer.
  const { spine } = spineOf(cols.filter(isSuggestable));
  const spineSize = spine.length;
  const total = cols.length;

  // Beyond Pro's reach → marketplace / mega-retailer, shown on every plan.
  const MEGA_SIZE = 200;
  if (spineSize > MEGA_SIZE) return { tier: "mega", spineSize, total, recommendedPlan: null };

  // Bigger than THIS plan's budget → nudge to the smallest plan that covers it
  // (≤20 → Starter, ≤50 → Growth, ≤150 → Pro; 150–200 → Pro, its ceiling).
  if (budget && spineSize > budget) {
    const fit = PLAN_TIERS.find((p) => p.pages >= spineSize);
    return {
      tier: "upgrade",
      spineSize,
      total,
      recommendedPlan: fit || PLAN_TIERS[PLAN_TIERS.length - 1],
    };
  }

  return { tier: "ok", spineSize, total, recommendedPlan: null };
}

export function walkTreeStats(treeData) {
  let totalPages = 0;
  let collCount = 0;
  const collectionUrls = [];

  const walk = (nodes, underCollections) => {
    for (const node of Object.values(nodes || {})) {
      if (!node || typeof node !== "object") continue;
      const here = underCollections || isCollectionsBucket(node.name);
      if (node.url) {
        totalPages += 1;
        if (here || hasCollectionMarker(node.url)) {
          collCount += 1;
          collectionUrls.push(node.url);
        }
      }
      if (node.children) walk(node.children, here);
    }
  };

  walk(treeData, false);

  return { totalPages, collCount, collectionUrls };
}

/* Map every real page URL to its human-readable name/title from the crawl tree.
   Used by the competitor mapping step so it can match on the actual page name
   ("Eye Makeup") and not just the URL slug. Group headers (url === null) are
   skipped. */
export function collectTitles(treeData) {
  const map = {};
  const walk = (nodes) => {
    for (const node of Object.values(nodes || {})) {
      if (!node || typeof node !== "object") continue;
      if (node.url && node.name) map[node.url] = node.name;
      if (node.children) walk(node.children);
    }
  };
  walk(treeData);
  return map;
}
