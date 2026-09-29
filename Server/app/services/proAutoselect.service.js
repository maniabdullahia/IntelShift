// proAutoselect.service.js — Pro "complete-site" onboarding.
//
// On Pro the user only picks competitors; there's no page-selection step. Once
// recon has captured every site's catalog, this auto-selects a capped, prioritised
// set of collections per competitor, auto-pairs them to the owner's collections by
// canonical category (AI-assisted when available), creates the tracked Page docs,
// and enqueues analysis — mirroring commitSelection exactly, so the downstream
// analysis/merge/compare pipeline is unchanged. Products are enriched in bulk from
// the catalog API, so this stays collections-only and never crawls per product.

import Competitor from "../models/competitor.js";
import Page from "../models/page.js";
import Subscription from "../models/subscription.js";
import Workspace from "../models/workspace.js";
import analysisQueue from "../queues/analysis.queue.js";
import { proAutoselect } from "../../api/python/analyzer.js";

const norm = (u) => {
    let s = String(u || "").trim();
    if (!s) return "";
    if (!/^https?:\/\//i.test(s)) s = `https://${s}`;
    return s.replace(/\/+$/, "");
};
const rootUrl = (u) => {
    try { const x = new URL(norm(u)); return `${x.protocol}//${x.host}`; }
    catch { return norm(u); }
};
const handleFromUrl = (u) => {
    const m = /\/collections\/([^/?#]+)/.exec(u || "");
    return m ? m[1].toLowerCase() : null;
};

// Owner's plan complete-site config (from the active subscription's plan limits).
export const getCompleteSiteConfig = async (ownerUserId) => {
    try {
        const sub = await Subscription.findOne({ userId: ownerUserId }).populate("planId").lean();
        const limits = sub?.planId?.limits || {};
        return {
            completeSite: !!limits.completeSite,
            maxPageCap: Number(limits.maxPageCap) || 100,
            pairingScope: limits.pairingScope || "",
        };
    } catch {
        return { completeSite: false, maxPageCap: 0, pairingScope: "" };
    }
};

// Collection handles that appear in a recon nav menu (for prominence scoring).
const navHandlesFromMenu = (menu) => {
    const out = new Set();
    const walk = (items) => {
        for (const it of items || []) {
            const h = handleFromUrl(it?.url || it?.href);
            if (h) out.add(h);
            if (Array.isArray(it?.children)) walk(it.children);
            if (Array.isArray(it?.items)) walk(it.items);
        }
    };
    walk(menu);
    return [...out];
};

const collectionsFromRecon = (recon) =>
    (recon?.collectionIndex || [])
        .filter((c) => c?.url)
        .map((c) => ({ title: c.name, url: norm(c.url), productCount: c.productCount, inNav: false }));

/**
 * Auto-select + auto-pair + create pages + enqueue analysis for a complete-site
 * workspace. The CALLER must have already claimed the workspace (setupStage →
 * "analyzing") so this runs exactly once. Returns the number of pages created.
 * Throws if it can't build a usable selection (caller falls back to manual).
 */
export const autoSelectAndAnalyze = async (workspaceId, ownerUserId) => {
    const owner = await Competitor.findOne({ workspaceId, role: "Owner" });
    if (!owner) throw new Error("owner competitor not found");
    const rivals = await Competitor.find({ workspaceId, role: "Competitor" });
    if (!rivals.length) throw new Error("no competitors to analyze");

    const { maxPageCap } = await getCompleteSiteConfig(ownerUserId);
    const cap = Math.max(5, (Number(maxPageCap) || 100) - 5); // reserve homepage + policy pages

    let ownerCols = collectionsFromRecon(owner.recon);
    if (!ownerCols.length) throw new Error("owner has no collections to pair");

    // Focus categories steer Pro auto-select: sort the owner's collections so the
    // user's focus categories (in priority order) lead. The cap below trims from the
    // tail, so focus collections are guaranteed to survive it. Lens, not a filter —
    // the rest still follow and get paired if the cap allows.
    const ws = await Workspace.findById(workspaceId).select("focusCategories focusMode").lean();
    const focusList = (ws?.focusMode === "selected" && Array.isArray(ws?.focusCategories)) ? ws.focusCategories : [];
    if (focusList.length) {
        const rankOf = new Map(focusList.map((c, i) => [String(c || "").toLowerCase().trim(), i]));
        const colRank = (col) => {
            for (const k of [col?.name, col?.title, col?.handle]) {
                const v = String(k || "").toLowerCase().trim();
                if (rankOf.has(v)) return rankOf.get(v);
            }
            return Infinity;
        };
        ownerCols = [...ownerCols].sort((a, b) => colRank(a) - colRank(b));
    }

    const ownerNav = navHandlesFromMenu(owner.recon?.menu);
    const ownerHome = rootUrl(owner.storeUrl || owner.websiteUrl);

    const createdPages = [];
    const mappedOwnerUrls = new Set();
    let anyPairs = false;

    for (const c of rivals) {
        const rivalCols = collectionsFromRecon(c.recon);
        const rivalNav = navHandlesFromMenu(c.recon?.menu);

        // Rank/cap + auto-pair collections across the two sites (AI-assisted inside
        // the Python endpoint when enabled; heuristic otherwise).
        const res = await proAutoselect({
            collections: ownerCols,
            navHandles: [...new Set([...ownerNav, ...rivalNav])],
            cap,
            competitorCollections: rivalCols,
            useAi: true, // Pro has no human in the loop — let AI prioritise what matters
        });
        const pairs = res?.pairing?.pairs || [];
        if (pairs.length) anyPairs = true;

        const compHome = rootUrl(c.storeUrl || c.websiteUrl);
        const rows = [{ url: compHome, mappedOwnerUrl: ownerHome }]; // homepage anchor
        for (const p of pairs) {
            if (p?.competitorUrl && p?.userUrl) {
                rows.push({ url: norm(p.competitorUrl), mappedOwnerUrl: norm(p.userUrl) });
            }
        }

        const seen = new Set();
        const docs = [];
        for (const row of rows) {
            const url = norm(row.url);
            const mapped = norm(row.mappedOwnerUrl);
            if (!url || !mapped || seen.has(url)) continue; // both sides required
            seen.add(url);
            mappedOwnerUrls.add(mapped);
            const exists = await Page.findOne({ competitorId: c._id, url });
            if (exists) continue;
            docs.push({ url, competitorId: c._id, workspaceId, mappedOwnerUrl: mapped, mapStatus: "matched" });
        }
        if (docs.length) {
            const created = await Page.insertMany(docs);
            createdPages.push(...created);
        }
    }

    if (!anyPairs) throw new Error("no collection pairs produced");

    // Owner pages: homepage + only owner pages a competitor is actually mapped to.
    const ownerUrls = [...new Set([ownerHome, ...mappedOwnerUrls])].filter(Boolean);
    for (const url of ownerUrls) {
        const exists = await Page.findOne({ competitorId: owner._id, url });
        if (exists) continue;
        const p = await Page.create({ url, competitorId: owner._id, workspaceId, mapStatus: "none" });
        createdPages.push(p);
    }

    for (const page of createdPages) {
        await analysisQueue.add("analyze-page", {
            pageId: page._id,
            url: page.url,
            competitorId: page.competitorId,
            workspaceId,
            userId: ownerUserId,
        });
    }

    console.log(`[pro-autoselect] workspace ${workspaceId}: created ${createdPages.length} pages across ${rivals.length} competitors`);
    return createdPages.length;
};
