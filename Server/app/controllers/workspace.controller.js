import Workspace from "../models/workspace.js";
import Analysis from "../models/analysis.js";
import ChangeReport from "../models/changeReport.js";
import Competitor from "../models/competitor.js";
import Page from "../models/page.js";
import { createCompetitorService, deleteCompetitorService } from "../services/competitor.service.js";
import { enqueueWorkspaceRecon } from "../services/recon.service.js";
import mongoose from "mongoose";
import analysisQueue from "../queues/analysis.queue.js";
import reconQueue from "../queues/recon.queue.js";

import { rescanWorkspace as rebuildWorkspace } from "../services/workspace.service.js";
import { getSubscriptionByUserId } from "../services/subscription.service.js";
import { getAnalysisById } from "../services/analysis.service.js";
import { getPlanById } from "../services/plan.service.js";

import { getNextScanAt } from "../../utils/scan.js";
import { checkUrlStatus, getCatalogCached, getStoreProductTotal } from "../../api/python/analyzer.js";
import { checkSiteReadiness, readinessVerdict } from "../services/siteReadiness.service.js";
import { profileFieldsFor } from "../services/storeProfile.service.js";


const createWorkspace = async (req, res) => {
    try {
        const { name, url, industry, selectedPages } = req.body;
        console.log('Creating workspace with data:', { name, url, industry });
        const { id } = req.user;
        const existing = await Workspace.findOne({ ownerId: id });
        if (existing) {
            return res.status(409).json({ message: "Workspace already exists" });
        }
        const workspace = new Workspace({
            ownerId: id,
            name: name,
            url: url,
            industry: industry
        });
        await workspace.save();

        req.body.role = "Owner";

        const competitor = {
            name: name,
            url: workspace.url,
            role: req.body.role,
            workspaceId: workspace._id,
            selectedPages: selectedPages
        }

        await createCompetitorService(competitor);

        res.status(201).json(workspace);

    } catch (error) {
        res.status(500).json({ message: error.message });
        Log.error('[CREATE WORKSPACE ERROR]', error);
    }
}

const getWorkspace = async (req, res) => {
    const { id } = req.user;

    try {
        const workspace = await Workspace.findOne({ ownerId: id })
            .populate({
                // Exclude analysisData AND the recon blob: both can be MEGABYTES
                // (the merged snapshot; recon carries the homepage read + full
                // collection index). This list endpoint only needs status/identity
                // fields — reconStatus survives the exclusion so setup progress can
                // render; the full recon is fetched on demand for the selection panel.
                path: "competitors",
                select: "-analysisData -recon",
                populate: {
                    path: "pages",
                    // Only status is needed for progress; analysisData per page is
                    // large and unused by any workspace-list view. pendingChange lets
                    // the UI exclude staged-but-not-yet-monitored pages from counts.
                    select: "url scanStatus mapStatus mappedOwnerUrl pendingChange offline",
                },
            })
            .populate({
                path: "analysis",
                select: "_id competitors.competitorId",
                populate: {
                    path: "competitors.competitorId",
                    select: "name",
                },
            });

        if (!workspace) {
            return res.status(404).json({
                message: "Workspace not found",
            });
        }

        const result = workspace.toObject();

        result.analysis = result.analysis.map((analysis) => ({
            analysisId: analysis._id,
            competitorId: analysis.competitors.competitorId?._id,
            competitorName: analysis.competitors.competitorId?.name,
        }));

        // Attach each competitor's change count + severity from its MOST RECENT
        // monitoring report, so the Competitors list shows real "recent changes"
        // (the number detected at the last run) instead of a hardcoded 0.
        const competitorIds = (result.competitors || []).map((c) => c._id);
        if (competitorIds.length) {
            const latest = await ChangeReport.aggregate([
                { $match: { competitorId: { $in: competitorIds } } },
                { $sort: { monitoredAt: -1 } },
                {
                    $group: {
                        _id: "$competitorId",
                        totalChanges: { $first: "$totalChanges" },
                        overallSeverity: { $first: "$overallSeverity" },
                        monitoredAt: { $first: "$monitoredAt" },
                    },
                },
            ]);
            const byId = new Map(latest.map((r) => [String(r._id), r]));
            result.competitors = (result.competitors || []).map((c) => {
                const r = byId.get(String(c._id));
                return {
                    ...c,
                    recentChanges: r?.totalChanges ?? 0,
                    recentSeverity: r?.overallSeverity || null,
                    lastMonitoredAt: r?.monitoredAt || null,
                };
            });
        }

        return res.json(result);
    } catch (error) {
        console.error("❌ Get workspace failed:", error);
        Log.error("[GET WORKSPACE ERROR]", error);

        return res.status(500).json({
            message: error.message,
        });
    }
};

const updateWorkspace = async (req, res) => {
    try {
        const { id } = req.user;
        const workspace = await Workspace.findOneAndUpdate(
            { ownerId: id },
            { $set: req.body },
            { new: true }
        );
        if (!workspace) {
            return res.status(404).json({ message: "Workspace not found" });
        }
        res.json(workspace);
    }
    catch (error) {
        res.status(500).json({ message: error.message });
        Log.error('[UPDATE WORKSPACE ERROR]', error);
    }
}

const deleteWorkspace = async (req, res) => {
    try {
        const { id } = req.user;
        const workspace = await Workspace.findOneAndDelete({ ownerId: id });
        if (!workspace) {
            return res.status(404).json({ message: "Workspace not found" });
        }
        await deleteCompetitorService(workspace._id);
        res.json({ message: "Workspace deleted successfully" });
    } catch (error) {
        res.status(500).json({ message: error.message });
        Log.error('[DELETE WORKSPACE ERROR]', error);
    }
}


const createWorkspaceWithCompetitor = async (req, res) => {
    const session = await mongoose.startSession();
    session.startTransaction();

    const { id: userId } = req.user;

    try {
        const {
            name,
            url,
            industry,
            selectedPages = [],
            competitorName,
            competitorUrl,
            competitorSelectedPages = [],
        } = req.body;

        const { id: ownerId } = req.user;

        // -------------------------------
        // ✅ CHECK EXISTING WORKSPACE
        // -------------------------------
        // const existing = await Workspace.findOne({ ownerId }).session(session);
        // if (existing) {
        //     await session.abortTransaction();
        //     session.endSession();
        //     return res.status(409).json({ message: "Workspace already exists" });
        // }

        // // -------------------------------
        // // ✅ CREATE WORKSPACE
        // // -------------------------------
        // const [workspace] = await Workspace.create(
        //     [
        //         {
        //             ownerId,
        //             name,
        //             url,
        //             industry,
        //         },
        //     ],
        //     { session }
        // );

        // const workspaceId = workspace._id;


        // console.log('Created workspace:', workspace);

        // // -------------------------------
        // // ✅ CREATE OWNER COMPETITOR
        // // -------------------------------
        // const ownerResult = await createCompetitorService(
        //     {
        //         name,
        //         url,
        //         role: "Owner",
        //         workspaceId,
        //         selectedPages,
        //     },
        //     session
        // );

        // // -------------------------------
        // // ✅ CREATE COMPETITOR (OPTIONAL)
        // // -------------------------------
        // let competitorResult = null;

        // if (competitorName && competitorUrl) {
        //     competitorResult = await createCompetitorService(
        //         {
        //             name: competitorName,
        //             url: competitorUrl,
        //             role: "Competitor",
        //             workspaceId,
        //             selectedPages: competitorSelectedPages,
        //         },
        //         session
        //     );
        // }

        // // -------------------------------
        // // ✅ COMMIT TRANSACTION
        // // -------------------------------
        // await session.commitTransaction();
        // session.endSession();

        // // -------------------------------
        // // ✅ QUEUE JOBS (AFTER COMMIT)
        // // -------------------------------
        // const allPages = [
        //     ...(ownerResult?.pages || []),
        //     ...(competitorResult?.pages || []),
        // ];

        // console.log(`[server] user ${userId} created workspace ${workspaceId} with ${allPages.length} pages to analyze`);
        // for (const page of allPages) {
        //     await analysisQueue.add("analyze-page", {
        //         pageId: page._id,
        //         url: page.url,
        //         competitorId: page.competitorId,
        //         workspaceId,
        //         userId
        //     });
        // }

        return res.status(201).json({
            message: "Workspace created successfully",
            workspace,
        });

    } catch (error) {
        await session.abortTransaction();
        session.endSession();

        console.error("❌ Create workspace failed:", error);
        return res.status(500).json({ message: error.message });
    }
};

const createWorkspaceWithCompetitors = async (req, res) => {
    const session = await mongoose.startSession();
    session.startTransaction();

    const { id: userId } = req.user;

    console.log('Creating workspace with competitors:', { userId, url: req.body?.url, competitors: (req.body?.competitors || []).length });
    try {
        const {
            workspaceName,
            url,
            industry,
            pages = [],
            currency = "",
            competitors = [],
        } = req.body;

        const { id: ownerId } = req.user;

        

        // -------------------------------
        // ✅ CHECK EXISTING WORKSPACE
        // -------------------------------
        const existing = await Workspace.findOne({ ownerId }).session(session);
        if (existing) {
            await session.abortTransaction();
            session.endSession();
            return res.status(409).json({ message: "Workspace already exists" });
        }

        // -------------------------------
        // ✅ CHECK SUBSCRIPTION
        // -------------------------------

        const subscription = await getSubscriptionByUserId(ownerId);
        const plan = subscription?.planId;

        if(!subscription || !plan) {
            await session.abortTransaction();
            session.endSession();
            return res.status(403).json({ message: "No active subscription found for user" });
        }

        // -------------------------------
        // ✅ CHECK PLAN DETAILS
        // -------------------------------

        const planDetails = await getPlanById(plan._id);
        if(!planDetails) {
            await session.abortTransaction();
            session.endSession();
            return res.status(404).json({ message: "Plan details not found" });
        }

        const planFrequency = planDetails?.planReportingFrequency;

        // -------------------------------
        // ✅ CREATE WORKSPACE
        // -------------------------------

        console.log(`🔴 Workpscae will next scan at: ${getNextScanAt(planFrequency)}`);
        const [workspace] = await Workspace.create(
            [
                {
                    ownerId,
                    name: workspaceName,
                    url,
                    industry,
                    nextScanAt: getNextScanAt(planFrequency),
                },
            ],
            { session }
        );

        const workspaceId = workspace._id;

        console.log('Created workspace:', workspace);

        // -------------------------------
        // ✅ CREATE OWNER COMPETITOR
        // -------------------------------
        const ownerResult = await createCompetitorService(
            {
                name: workspaceName,
                url,
                role: "Owner",
                workspaceId,
                selectedPages: pages,
                currency,
                storeUrl: url,
            },
            session
        );

        // -------------------------------
        // ✅ CREATE COMPETITORS (OPTIONAL)
        // -------------------------------
        const competitorResults = [];

        for (const competitor of competitors) {
            const { name: competitorName, url: competitorUrl, pages: competitorSelectedPages = [], pagePairs = [], region = "", storeUrl = "", currency = "" } = competitor;
            console.log('Creating competitor:', { competitorName, competitorUrl, competitorSelectedPages });

            if (competitorName && competitorUrl) {
                const competitorResult = await createCompetitorService(
                    {
                        name: competitorName,
                        url: competitorUrl,
                        role: "Competitor",
                        workspaceId,
                        selectedPages: competitorSelectedPages,
                        pagePairs,
                        region,
                        storeUrl,
                        currency,
                    },
                    session
                );
                competitorResults.push(competitorResult);
            }
        }

        // -------------------------------
        // ✅ COMMIT TRANSACTION
        // -------------------------------
        await session.commitTransaction();
        session.endSession();

        // -------------------------------
        // ✅ QUEUE JOBS (AFTER COMMIT)
        // -------------------------------
        const allPages = [
            ...(ownerResult?.pages || []),
            ...competitorResults.flatMap(result => result?.pages || []),
        ];

        console.log(`[server] user ${userId} created workspace ${workspaceId} with ${allPages.length} pages to analyze`);
        for (const page of allPages) {
            await analysisQueue.add("analyze-page", {
                pageId: page._id,
                url: page.url,
                competitorId: page.competitorId,
                workspaceId,
                userId
            });
        }

        return res.status(201).json({
            message: "Workspace created successfully",
            workspace,
        });

    } catch (error) {
        console.log(`❌ Create workspace with competitors failed: ${error.message}`);
        await session.abortTransaction();
        session.endSession();
    }

}

/*
|--------------------------------------------------------------------------
| CAPTURE-FIRST WORKSPACE CREATION
|--------------------------------------------------------------------------
| The new onboarding flow: collect ONLY urls (owner + competitors) + industry.
| No page selection, no page pairs, no deep-crawl jobs here. We create the
| workspace and every site as a Competitor doc (with zero pages), then enqueue
| breadth-only recon for each. Page selection + mapping happen later, inside the
| workspace, against the captured recon — and only THEN does the deep per-page
| crawl run (via the existing staged-page + analyze-page path).
*/
const createWorkspaceRecon = async (req, res) => {
    const session = await mongoose.startSession();
    session.startTransaction();

    const { id: ownerId } = req.user;

    try {
        const {
            workspaceName,
            url,
            // IntelShift targets e-commerce; the vertical is detected from the site
            // itself, so it's no longer collected in onboarding. Default it.
            industry = "E-Commerce",
            currency = "",
            region = "",
            storeUrl = "",
            competitors = [],
            // Onboarding focus categories: ordered (index 0 = highest priority).
            focusCategories = [],
            focusMode = "all",
        } = req.body;

        if (!workspaceName || !url) {
            await session.abortTransaction();
            session.endSession();
            return res.status(400).json({ message: "workspaceName and url are required" });
        }

        // One workspace per owner (same rule as the legacy flow).
        const existing = await Workspace.findOne({ ownerId }).session(session);
        if (existing) {
            await session.abortTransaction();
            session.endSession();
            return res.status(409).json({ message: "Workspace already exists" });
        }

        // Subscription / plan gate (mirrors createWorkspaceWithCompetitors).
        const subscription = await getSubscriptionByUserId(ownerId);
        const plan = subscription?.planId;
        if (!subscription || !plan) {
            await session.abortTransaction();
            session.endSession();
            return res.status(403).json({ message: "No active subscription found for user" });
        }
        const planDetails = await getPlanById(plan._id);
        if (!planDetails) {
            await session.abortTransaction();
            session.endSession();
            return res.status(404).json({ message: "Plan details not found" });
        }
        const planFrequency = planDetails?.planReportingFrequency;

        // Normalize focus categories: keep order, dedupe, cap at 5. "selected" only
        // when we actually have picks; otherwise "all" (behaves as today).
        const _focus = Array.isArray(focusCategories)
            ? [...new Set(focusCategories.map((c) => String(c || "").trim()).filter(Boolean))].slice(0, 5)
            : [];
        const _focusMode = focusMode === "selected" && _focus.length ? "selected" : "all";

        // Create the workspace — starts in the "recon" setup stage (capture-first).
        const [workspace] = await Workspace.create(
            [{
                ownerId, name: workspaceName, url, industry: industry || "E-Commerce",
                setupStage: "recon", nextScanAt: getNextScanAt(planFrequency),
                focusCategories: _focusMode === "selected" ? _focus : [],
                focusMode: _focusMode,
            }],
            { session }
        );
        const workspaceId = workspace._id;

        // Owner site — NO pages yet.
        await createCompetitorService(
            { name: workspaceName, url, role: "Owner", workspaceId, selectedPages: [], currency, region, storeUrl: storeUrl || url, ...profileFieldsFor(storeUrl || url) },
            session
        );

        // Competitor sites — NO pages yet.
        for (const c of competitors) {
            const { name: cName, url: cUrl, region: cRegion = "", storeUrl: cStoreUrl = "", currency: cCurrency = "" } = c || {};
            if (cName && cUrl) {
                await createCompetitorService(
                    { name: cName, url: cUrl, role: "Competitor", workspaceId, selectedPages: [], region: cRegion, storeUrl: cStoreUrl, currency: cCurrency, ...profileFieldsFor(cStoreUrl || cUrl) },
                    session
                );
            }
        }

        await session.commitTransaction();
        session.endSession();

        // Kick off breadth-only recon for every site (progressive, non-blocking).
        try {
            const { queued } = await enqueueWorkspaceRecon({ workspaceId, userId: ownerId });
            console.log(`[server] workspace ${workspaceId} created — queued recon for ${queued} site(s)`);
        } catch (reconErr) {
            // Recon is best-effort at creation; the workspace still exists and recon
            // can be retried. Never fail creation because the queue hiccuped.
            console.error("enqueueWorkspaceRecon failed (continuing):", reconErr?.message || reconErr);
        }

        return res.status(201).json({ message: "Workspace created; recon started", workspace });
    } catch (error) {
        await session.abortTransaction();
        session.endSession();
        console.error("❌ Create workspace (recon) failed:", error);
        return res.status(500).json({ message: error.message });
    }
};

/*
|--------------------------------------------------------------------------
| RECON — fetch captured recon for the selection panel
|--------------------------------------------------------------------------
| Returns each site's breadth recon (collection index + homepage summary + nav)
| so the in-workspace selection panel can render pages to pick + map. The heavy
| recon blob is excluded from the workspace list endpoint, so this fetches it
| explicitly (only when the panel opens).
*/
const rootUrl = (u) => {
    try {
        const url = new URL(/^https?:\/\//i.test(u) ? u : `https://${u}`);
        return `${url.protocol}//${url.host}/`;
    } catch {
        return u;
    }
};

/*
| Annotate each collection with its place in the store's NAV hierarchy, derived
| from the flattened menu ({title, url, path[]}). path is the chain of ancestor
| group labels; a node whose title equals the last path element is a GROUP (its
| parent is the element before it), otherwise it's a LEAF under the last element.
| We attach parentName (L1 above it), childCount (how many sub-categories nest
| under it) and inNav — so the picker can say "covers N sub-categories" and warn
| when a page is already covered by a tracked parent.
*/
const annotateHierarchy = (collectionIndex, menu) => {
    const nm = (u) => String(u || "").trim().replace(/\/+$/, "").toLowerCase();
    const entries = (Array.isArray(menu) ? menu : [])
        .filter((e) => e && e.title)
        .map((e) => ({ url: nm(e.url), title: String(e.title), path: Array.isArray(e.path) ? e.path : [] }));
    for (const e of entries) {
        const p = e.path;
        const last = p[p.length - 1];
        e.parentTitle = e.title === last ? (p[p.length - 2] ?? null) : (last ?? null);
    }
    const childCount = {};
    for (const e of entries) if (e.parentTitle) childCount[e.parentTitle] = (childCount[e.parentTitle] || 0) + 1;
    const byUrl = {};
    for (const e of entries) if (e.url) byUrl[e.url] = e;
    return (Array.isArray(collectionIndex) ? collectionIndex : []).map((c) => {
        const e = byUrl[nm(c.url)];
        return {
            ...c,
            inNav: !!e,
            parentName: e?.parentTitle || null,
            childCount: e ? (childCount[e.title] || 0) : 0,
            depth: e ? (e.parentTitle ? 2 : 1) : 1,
        };
    });
};

const getWorkspaceRecon = async (req, res) => {
    try {
        const { id: ownerId } = req.user;
        const workspace = await Workspace.findOne({ ownerId }).lean();
        if (!workspace) return res.status(404).json({ message: "Workspace not found" });

        const competitors = await Competitor.find({ workspaceId: workspace._id })
            .select("name domain role storeUrl websiteUrl recon reconStatus currency")
            .lean();

        const shape = (c) => ({
            competitorId: c._id,
            name: c.name,
            domain: c.domain,
            role: c.role,
            currency: c.currency || "",
            url: c.storeUrl || c.websiteUrl,
            homeUrl: rootUrl(c.storeUrl || c.websiteUrl),
            reconStatus: c.reconStatus,
            homepage: c.recon?.homepage
                ? { summary: c.recon.homepage.summary || null, nav: c.recon.homepage.nav || [], promos: c.recon.homepage.promos || [] }
                : null,
            collections: annotateHierarchy(c.recon?.collectionIndex, c.recon?.menu),
            productTotal: c.recon?.productTotal ?? null,
        });

        const owner = competitors.find((c) => c.role === "Owner");
        const rivals = competitors.filter((c) => c.role !== "Owner");

        // Stored competitor suggestions (generated once in the background after
        // recon) — powers the "Replace competitor" picker without re-running search.
        // Hide any that are already in the workspace.
        const haveDomains = new Set(
            competitors.map((c) => String(c.domain || "").toLowerCase()).filter(Boolean)
        );
        const suggestedCompetitors = (workspace.suggestedCompetitors || []).filter(
            (s) => !haveDomains.has(String(s.domain || "").toLowerCase())
        );

        return res.json({
            setupStage: workspace.setupStage,
            owner: owner ? shape(owner) : null,
            competitors: rivals.map(shape),
            draft: workspace.selectionDraft || null,
            suggestedCompetitors,
        });
    } catch (error) {
        console.error("❌ Get workspace recon failed:", error);
        return res.status(500).json({ message: error.message });
    }
};

/*
|--------------------------------------------------------------------------
| PREVIEW COLLECTIONS — recon-shape collections for an arbitrary store URL
|--------------------------------------------------------------------------
| Lets the "add competitor" flow show the SAME mapped picker as onboarding
| BEFORE the competitor exists: fetch its catalog + menu, annotate hierarchy
| (depth / inNav / childCount), and return it exactly like getWorkspaceRecon.
*/
const previewCollections = async (req, res) => {
    try {
        const { url } = req.body || {};
        if (!url) return res.status(400).json({ message: "URL is required" });

        let cat = null;
        try { cat = await getCatalogCached(url); } catch { cat = null; }

        const collectionIndex = (cat?.collections || []).map((c) => ({
            name: c.title || c.name || null,
            handle: c.handle || null,
            url: c.url || null,
            productCount: c.products_count ?? c.productCount ?? c.count ?? null,
        }));
        const collections = annotateHierarchy(collectionIndex, cat?.menu || []);

        let productTotal = null;
        try { productTotal = await getStoreProductTotal(url, cat?.platform || ""); } catch { productTotal = null; }

        return res.json({ collections, productTotal, platform: cat?.platform || null });
    } catch (error) {
        console.error("❌ Preview collections failed:", error);
        return res.status(500).json({ message: error.message, collections: [] });
    }
};

/*
|--------------------------------------------------------------------------
| SAVE SELECTION DRAFT — auto-save in-progress picks while "selecting"
|--------------------------------------------------------------------------
| Stores the picker's rows-by-competitor blob on the workspace so a logout or
| refresh never loses work. Restored by getWorkspaceRecon; cleared on commit.
*/
const saveSelectionDraft = async (req, res) => {
    try {
        const { id: ownerId } = req.user;
        const { draft } = req.body || {};
        const workspace = await Workspace.findOneAndUpdate(
            { ownerId },
            { selectionDraft: draft ?? null, selectionDraftAt: new Date() },
            { new: true }
        ).lean();
        if (!workspace) return res.status(404).json({ message: "Workspace not found" });
        return res.json({ ok: true, savedAt: workspace.selectionDraftAt });
    } catch (error) {
        console.error("❌ Save selection draft failed:", error);
        return res.status(500).json({ message: error.message });
    }
};

/*
|--------------------------------------------------------------------------
| COMMIT SELECTION — the user picked pages + mappings in the panel
|--------------------------------------------------------------------------
| Creates the tracked Page docs on the (already-existing) owner + competitors,
| advances setupStage → "analyzing", and queues the deep per-page crawl. The
| homepage is always included and anchors each site's analysis.
*/
const commitSelection = async (req, res) => {
    try {
        const { id: userId } = req.user;
        // ownerPages (if sent) is ignored — owner pages are derived from the
        // competitor mappings, so only mapped pages are ever created.
        const { competitors = [] } = req.body;

        const workspace = await Workspace.findOne({ ownerId: userId });
        if (!workspace) return res.status(404).json({ message: "Workspace not found" });
        const workspaceId = workspace._id;

        const owner = await Competitor.findOne({ workspaceId, role: "Owner" });
        if (!owner) return res.status(400).json({ message: "Owner site not found" });

        const norm = (u) => {
            let s = String(u || "").trim();
            if (!s) return "";
            if (!/^https?:\/\//i.test(s)) s = `https://${s}`;
            return s.replace(/\/+$/, "");
        };
        const homeOf = (u) => norm(rootUrl(u));

        // ── Reachability guard — block the commit if any MAPPED page is a definitive
        //    404 (a dead/renamed collection). Only 404 counts as gone; 403/timeouts
        //    are usually Cloudflare blocking our checker, not a dead page.
        const rivalDocs = await Competitor.find({ workspaceId, role: "Competitor" }).select("name storeUrl websiteUrl").lean();
        const rivalById = new Map(rivalDocs.map((c) => [String(c._id), c]));
        const nameFor = (u) => {
            const s = norm(u);
            const seg = decodeURIComponent(s.split("/").filter(Boolean).pop() || "").replace(/[-_]+/g, " ").trim();
            return seg || s;
        };
        const checkTargets = new Map(); // url → { url, side, storeName }
        const addTarget = (url, side, storeName) => {
            const u = norm(url);
            if (u && !checkTargets.has(u)) checkTargets.set(u, { url: u, side, storeName });
        };
        for (const comp of competitors) {
            const c = rivalById.get(String(comp?.competitorId));
            if (!c) continue;
            for (const row of Array.isArray(comp.pages) ? comp.pages : []) {
                addTarget(row?.url, "competitor", c.name);
                addTarget(row?.mappedOwnerUrl, "owner", owner.name);
            }
        }
        const targets = [...checkTargets.values()];
        const statuses = await Promise.all(targets.map((t) => checkUrlStatus(t.url).catch(() => null)));
        const deadPages = targets
            .map((t, i) => ({ ...t, status: statuses[i] }))
            .filter((t) => t.status === 404)
            .map((t) => ({ url: t.url, label: nameFor(t.url), side: t.side, storeName: t.storeName }));
        if (deadPages.length) {
            return res.status(422).json({
                message: "Some selected pages are no longer reachable (404). Replace them, then start analysis.",
                deadPages,
            });
        }

        const createdPages = [];
        const ownerHome = homeOf(owner.storeUrl || owner.websiteUrl);

        // ── Competitor pages — MAPPED-ONLY. Every competitor page must reference an
        //    owner page (the homepage always maps to the owner homepage). Any page
        //    with no owner mapping is skipped, so nothing unpaired ever gets tracked.
        const mappedOwnerUrls = new Set(); // owner urls actually paired to a competitor
        for (const comp of competitors) {
            if (!comp?.competitorId) continue;
            const c = await Competitor.findOne({ _id: comp.competitorId, workspaceId });
            if (!c || c.role === "Owner") continue;

            const compHome = homeOf(c.storeUrl || c.websiteUrl);
            const rows = [{ url: compHome, mappedOwnerUrl: ownerHome }, ...(Array.isArray(comp.pages) ? comp.pages : [])];

            const seen = new Set();
            const docs = [];
            for (const row of rows) {
                const url = norm(row?.url);
                const mapped = row?.mappedOwnerUrl ? norm(row.mappedOwnerUrl) : "";
                if (!url || !mapped || seen.has(url)) continue; // enforce: both sides required
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

        // ── Owner pages — the homepage plus ONLY owner pages that a competitor is
        //    actually mapped to. An unmapped owner page is never created/crawled.
        const ownerUrls = [...new Set([ownerHome, ...mappedOwnerUrls])].filter(Boolean);
        for (const url of ownerUrls) {
            const exists = await Page.findOne({ competitorId: owner._id, url });
            if (exists) continue;
            const p = await Page.create({ url, competitorId: owner._id, workspaceId, mapStatus: "none" });
            createdPages.push(p);
        }

        // Advance to analyzing, clear the saved draft, then queue the deep crawl.
        await Workspace.findByIdAndUpdate(workspaceId, { setupStage: "analyzing", selectionDraft: null, selectionDraftAt: null });

        for (const page of createdPages) {
            await analysisQueue.add("analyze-page", {
                pageId: page._id,
                url: page.url,
                competitorId: page.competitorId,
                workspaceId,
                userId,
            });
        }

        console.log(`[server] commitSelection: workspace ${workspaceId} → analyzing, queued ${createdPages.length} pages`);
        return res.status(200).json({ message: "Selection committed", pagesCreated: createdPages.length, setupStage: "analyzing" });
    } catch (error) {
        console.error("❌ Commit selection failed:", error);
        return res.status(500).json({ message: error.message });
    }
};

/*
|--------------------------------------------------------------------------
| REPLACE COMPETITOR — swap a poor-fit competitor during selection
|--------------------------------------------------------------------------
| Points an existing competitor slot at a new site, clears its recon + any
| pages, sends the workspace back to "recon" and re-captures just that site.
| When it settles, the recon worker advances the workspace back to "selecting".
*/
const replaceCompetitor = async (req, res) => {
    try {
        const { id: userId } = req.user;
        const { competitorId, url } = req.body;
        if (!competitorId || !url) {
            return res.status(400).json({ message: "competitorId and url are required" });
        }

        const workspace = await Workspace.findOne({ ownerId: userId });
        if (!workspace) return res.status(404).json({ message: "Workspace not found" });
        const workspaceId = workspace._id;

        const comp = await Competitor.findOne({ _id: competitorId, workspaceId, role: "Competitor" });
        if (!comp) return res.status(404).json({ message: "Competitor not found" });

        const cleanUrl = /^https?:\/\//i.test(url) ? url : `https://${url}`;
        let domain;
        try {
            domain = new URL(cleanUrl).hostname.replace(/^www\./, "");
        } catch {
            return res.status(400).json({ message: "That doesn't look like a valid website URL" });
        }

        const dup = await Competitor.findOne({ workspaceId, domain, _id: { $ne: comp._id } });
        if (dup) return res.status(409).json({ message: "That site is already in this workspace" });

        // Same readiness gate onboarding uses — confirm we can actually read the
        // store (homepage + collection + product) and it isn't enterprise-scale,
        // BEFORE we swap it in and queue recon. Without this, a bot-protected /
        // unreadable site (e.g. fabletics.com) gets accepted and then shows 0
        // categories. Fail-open only on an unexpected gate error, never on a
        // clean "unreadable" verdict.
        let profileFields = { accessStatus: "unverified", storeProfile: undefined };
        try {
            const readiness = await checkSiteReadiness(cleanUrl);
            const verdict = readinessVerdict(readiness);
            if (!verdict.ok) {
                return res.status(422).json({
                    message: verdict.message,
                    code: verdict.code,
                    ...(verdict.scale ? { scale: verdict.scale } : {}),
                    ...(verdict.englishAlternate ? { englishAlternate: verdict.englishAlternate } : {}),
                });
            }
            profileFields = { accessStatus: verdict.accessStatus, storeProfile: verdict.profile || undefined };
        } catch (gateErr) {
            console.warn("replaceCompetitor readiness gate error (adding as unverified):", gateErr?.message || gateErr);
        }

        const name = domain.split(".")[0].replace(/[-_]+/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase());

        await Page.deleteMany({ competitorId: comp._id });
        comp.name = name;
        comp.websiteUrl = cleanUrl;
        comp.domain = domain;
        comp.storeUrl = cleanUrl;
        comp.region = "";
        comp.currency = "";
        comp.recon = {};
        comp.reconStatus = "Pending";
        comp.reconCapturedAt = null;
        comp.accessStatus = profileFields.accessStatus;
        comp.storeProfile = profileFields.storeProfile;
        await comp.save();

        // Back to recon while the new site is captured; the recon worker flips the
        // workspace back to "selecting" once every site (incl. this one) settles.
        // Drop this competitor's draft rows — its old mappings point at the old site.
        const wsForDraft = await Workspace.findById(workspaceId).select("selectionDraft").lean();
        const nextDraft = wsForDraft?.selectionDraft && typeof wsForDraft.selectionDraft === "object"
            ? { ...wsForDraft.selectionDraft } : null;
        if (nextDraft) delete nextDraft[String(comp._id)];
        await Workspace.findByIdAndUpdate(workspaceId, { setupStage: "recon", selectionDraft: nextDraft });
        await reconQueue.add(
            "recon-site",
            { competitorId: comp._id, workspaceId, userId, url: cleanUrl, currency: "", role: "Competitor" },
            { jobId: `recon-${comp._id}`, removeOnComplete: true, removeOnFail: true }
        );

        return res.status(200).json({ message: "Competitor replaced; re-capturing", setupStage: "recon", name, domain });
    } catch (error) {
        console.error("❌ Replace competitor failed:", error);
        return res.status(500).json({ message: error.message });
    }
};

const markIntroCompleted = async (req, res) => {
    try {

        const { id: userId } = req.user;
        const workspace = await Workspace.findOneAndUpdate(
            { ownerId: userId },
            { $set: { introCompleted: true } },
            { new: true }
        );
        res.status(200).json({ message: "Intro marked as completed" });

    } catch (error) {
        console.error("❌ Mark intro completed failed:", error);
        return res.status(500).json({ message: error.message });
    }
}

// Admin Function

const getAllWorkspaces = async (req, res) => {
    try {
        const { page = 1, limit = 10 } = req.query;
        const workspaces = await Workspace.find()
            .skip((page - 1) * limit)
            .limit(limit)
            .select("-analysis -__v")
            .lean()
            .populate({
                path: 'ownerId',
                select: 'name email accountStatus',
                populate: {
                    path: 'subscription',
                    select: "planId status",
                    populate: {
                        path: 'planId',
                        select: 'displayName price limits'
                    }
                }
            })
            .populate({
                path: 'competitors',
                select: 'name role -_id -workspaceId'
            })

        console.log(`Fetched ${workspaces.length} workspaces from database`);

        res.json({ workspaces });

    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

const getWorkspaceById = async (req, res) => {
    try {
        const { workspaceId } = req.params;
        // if (!mongoose.Types.ObjectId.isValid(workspaceId)) {
        //     return res.status(400).json({ message: "Invalid workspace ID" });
        // }
        const workspace = await Workspace.findById(workspaceId)
            .select("-analysis -__v")
            .lean()
            .populate({
                path: 'ownerId',
                select: 'name email subscription accountStatus',
                populate: {
                    path: 'subscription',
                    select: 'planId status',
                    populate: {
                        path: 'planId',
                        select: 'displayName price limits',
                    }
                }
            })
            .populate('competitors', 'name url role selectedPages', null, { populate: { path: 'pages', select: 'url scanStatus ' } });
        if (!workspace) {
            return res.status(404).json({ message: "Workspace not found" });
        }

        const completedPagesCount = workspace.competitors.reduce((total, competitor) => {
            // Status is stored capitalised ("Completed"); compare case-insensitively
            // so the completion % actually reaches 100 when pages finish (otherwise
            // the UI stays stuck on "generating reports" forever).
            return total + (competitor.pages ? competitor.pages.filter(page => String(page.scanStatus).toLowerCase() === 'completed').length : 0);
        }, 0);

        const totalPagesCount = workspace.competitors.reduce((total, competitor) => {
            return total + (competitor.pages ? competitor.pages.length : 0);
        }, 0);

        const completionPercentage = totalPagesCount > 0 ? (completedPagesCount / totalPagesCount) * 100 : 0;

        const stats = {
            completedPages: completedPagesCount,
            totalPages: totalPagesCount,
            completionPercentage: completionPercentage.toFixed(2), // Rounded to 2 decimal places

            totalCompetitors: workspace.competitors.filter(comp => comp.role === 'Competitor').length,
            competitorLimit: workspace.ownerId?.subscription?.planId?.limits?.competitors || 'N/A',

            plan: workspace.ownerId?.subscription?.planId?.displayName || 'N/A',
            renewalDate: workspace.ownerId?.subscription?.nextBilledAt || 'N/A',
        };

        res.json({ workspace, stats });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

const rescanWorkspace = async (req, res) => {
    try {
        const { workspaceId } = req.params;

        if (!mongoose.Types.ObjectId.isValid(workspaceId)) {
            return res.status(400).json({ message: "Invalid workspace ID" });
        }
        const result = await rebuildWorkspace(workspaceId);
        res.status(200).json({ message: result });
    } catch (error) {
        console.error("❌ Rescan workspace failed:", error);
        return res.status(500).json({ message: error.message });
    }
}

const getAnalysis = async (req, res) => {
    try {
        const { analysisId } = req.params;

        if (!mongoose.Types.ObjectId.isValid(analysisId)) {
            return res.status(400).json({ message: "Invalid analysis ID" });
        }

        const analysis = await getAnalysisById(analysisId);
        if(!analysis) {
            return res.status(404).json({ message: "Analysis not found" });
        }

        res.status(200).json({ analysis });
    } catch (error) {
        console.error("❌ Get analysis failed:", error);
        return res.status(500).json({ message: error.message });
    }

}



export {
    createWorkspace,
    getWorkspace,
    updateWorkspace,
    deleteWorkspace,
    createWorkspaceWithCompetitor,
    createWorkspaceWithCompetitors,
    createWorkspaceRecon,
    getWorkspaceRecon,
    previewCollections,
    saveSelectionDraft,
    commitSelection,
    replaceCompetitor,
    markIntroCompleted,
    getAllWorkspaces,
    getWorkspaceById,
    rescanWorkspace,
    getAnalysis
}
