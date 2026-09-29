// recon.service.js
// ============================================================================
// Capture-first "recon": breadth-only reconnaissance of a store, captured BEFORE
// the user selects which pages to track. It reuses the same building blocks the
// onboarding page-picker already relies on — nothing here product-crawls.
//
// A recon blob contains:
//   • platform + currency
//   • the store's nav menu (what they sell, structurally)
//   • the FULL collection index (name, handle, url, live-ish product count)
//   • the classified page tree (kind = category/brand/marketing, inNav) that the
//     picker and the mapping suggester run on
//   • the homepage read header-to-footer: business-model summary, nav links,
//     hero/banner media, and the vision-read promos (offer + meaning)
//
// This is the authoritative input for page selection, mapping suggestions and the
// "what they have / what they're doing" comparison. Deep per-page crawling stays
// deferred to only the pages the user actually chooses to track.
// ============================================================================

import { getCatalogCached, analyzeUrl, getStoreProductTotal, quickCatalog } from "../../api/python/analyzer.js";
import getImportantPagesFast from "../../utils/pageExtractor.js";
import UrlTree from "../../utils/urlTree.js";
import reconQueue from "../queues/recon.queue.js";
import Competitor from "../models/competitor.js";

/** The site root ("/") for a given store URL — the homepage we read for recon. */
const homepageUrlOf = (url) => {
  try {
    const u = new URL(/^https?:\/\//i.test(url) ? url : `https://${url}`);
    return `${u.protocol}//${u.host}/`;
  } catch {
    return url;
  }
};

/**
 * Capture recon for a single store. Every phase is best-effort and isolated —
 * a failure in one (e.g. the homepage render) never discards the others, so a
 * partial recon is still useful for selection. Returns the recon blob.
 */
export const captureRecon = async ({ url, currency = "" }) => {
  const startedAt = Date.now();

  // 1) Catalog — collections + nav menu, with real titles + product_type. This
  //    is the breadth backbone; reliable even on Cloudflare-protected stores.
  let catalog = null;
  try {
    const cat = await getCatalogCached(url);
    if (cat && (cat.menu?.length || cat.collections?.length || cat.products?.length)) {
      catalog = cat;
    }
  } catch {
    catalog = null;
  }

  // Fallback for Cloudflare-blocked / JS-rendered stores where the heavy catalog
  // render times out or is blocked (e.g. stdbeauty): recover collections from ONE
  // rendered homepage — the same lean read the onboarding validator uses. Without
  // this, such stores capture 0 categories while standard stores capture theirs.
  if (!catalog) {
    try {
      const qc = await quickCatalog(url);
      if (qc && Array.isArray(qc.collections) && qc.collections.length) {
        catalog = {
          platform: null,
          menu: [],
          collections: qc.collections.map((c) => ({ title: c.title, url: c.url })),
          products: [],
          _source: "quick-catalog",
        };
        console.log(`🔎 recon: recovered ${catalog.collections.length} collections for ${url} via quick-catalog fallback`);
      }
    } catch { /* leave null */ }
  }

  // 2) Classified page/collection tree (kind + inNav) — the exact structure the
  //    picker renders and the mapping suggester scores against. Same pipeline as
  //    the /url-tree onboarding endpoint, just captured up front and persisted.
  let tree = null;
  try {
    const allowed = await getImportantPagesFast(url, { catalog });
    const t = new UrlTree({ pagesToExclude: ["home"] });
    t.insert(allowed);
    tree = t.toJSON();
  } catch (err) {
    console.warn(`recon: tree build failed for ${url}: ${err?.message || err}`);
    tree = null;
  }

  // 3) Homepage header-to-footer read — business model, nav, hero/banner media
  //    and the vision-read promos. One page, so cheap; this is the front face.
  let homepage = null;
  try {
    const hp = await analyzeUrl(homepageUrlOf(url));
    if (hp && typeof hp === "object") {
      homepage = {
        platform: hp.platform || catalog?.platform || null,
        siteName: hp.content?.siteName || null,
        summary: hp.homepage || null,
        nav: hp.navigation?.links || [],
        footerLinks: hp.navigation?.footerLinks || [],
        announcementBar: hp.content?.announcementBar || null,
        heroMedia: hp.content?.heroMedia || [],
        // Offers read out of image-only banners (offer + meaning) — see banner_vision.py
        promos: hp.content?.homepagePromos || [],
        featuredCollections: hp.ecommerce?.featuredCollections || [],
      };
    }
  } catch (err) {
    console.warn(`recon: homepage read failed for ${url}: ${err?.message || err}`);
    homepage = null;
  }

  // 4) Flat collection index straight from the catalog (name/handle/url/count),
  //    for quick listing and count budgeting without walking the tree.
  const collectionIndex = (catalog?.collections || []).map((c) => ({
    name: c.title || c.name || null,
    handle: c.handle || null,
    url: c.url || null,
    productCount: c.products_count ?? c.productCount ?? c.count ?? null,
  }));

  // 5) One EXACT store-wide product total (sitemap / WP header), instead of summing
  //    per-collection counts — those double-count multi-collection products. Best-
  //    effort: null just means the fit header omits the "· N products" tail.
  let productTotal = null;
  try {
    productTotal = await getStoreProductTotal(url, catalog?.platform || homepage?.platform || "");
  } catch {
    productTotal = null;
  }

  return {
    capturedAt: new Date(),
    tookMs: Date.now() - startedAt,
    platform: catalog?.platform || homepage?.platform || null,
    currency,
    menu: catalog?.menu || [],
    collectionIndex,
    collectionCount: collectionIndex.length,
    productTotal,
    tree,
    homepage,
  };
};

/**
 * Enqueue a recon job for every site in a workspace (owner + each competitor).
 * Progressive + non-blocking: each site is its own job so the workspace can open
 * and render results as they land. Idempotent per competitor via a fixed jobId.
 */
export const enqueueWorkspaceRecon = async ({ workspaceId, userId }) => {
  const competitors = await Competitor.find({ workspaceId })
    .select("_id role storeUrl websiteUrl currency")
    .lean();

  let queued = 0;
  for (const c of competitors) {
    const url = c.storeUrl || c.websiteUrl;
    if (!url) continue;
    await reconQueue.add(
      "recon-site",
      { competitorId: c._id, workspaceId, userId, url, currency: c.currency || "", role: c.role },
      { jobId: `recon-${c._id}`, removeOnComplete: true, removeOnFail: true }
    );
    queued += 1;
  }
  return { queued };
};
