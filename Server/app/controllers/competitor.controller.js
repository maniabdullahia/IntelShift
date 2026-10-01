import Competitor from "../models/competitor.js";
import Page from "../models/page.js";
import Workspace from "../models/workspace.js";
import analysisQueue from "../queues/analysis.queue.js";
import { AnalyzeURL } from "../../utils/Analyzer.js";
import { getWorkspacePlan, planAllowsPageManagement } from "../services/page.service.js";
import {
    stageRemoveCompetitor,
    undoCompetitorChange,
    activeCompetitorCount,
} from "../services/competitor.service.js";
import { checkSiteReadiness, readinessVerdict } from "../services/siteReadiness.service.js";


const createCompetitor = async (req, res) => {
    try {
        const { name, url, role = "Competitor", selectedPages = [], pagePairs = [] } = req.body;
        const workspaceId = req.workspace._id;

        const normalizePairUrl = (raw) => {
            let u = String(raw || "").trim();
            if (!u) return "";
            if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
            return u.replace(/\/+$/, "");
        };

        if (!url) {
            return res.status(400).json({ message: "URL is required" });
        }

        // Managing competitors is a paid capability — the free trial is view-only.
        const { plan } = await getWorkspacePlan(req.workspace);
        if (!planAllowsPageManagement(plan)) {
            return res.status(403).json({
                message: "Adding competitors is available on paid plans. Upgrade to manage your competitors.",
                code: "UPGRADE_REQUIRED",
            });
        }

        let domain;
        try {
            domain = new URL(/^https?:\/\//i.test(url) ? url : `https://${url}`).hostname.replace(/^www\./i, "").toLowerCase();
        } catch {
            return res.status(400).json({ message: "Invalid URL" });
        }

        // Same store regardless of scheme / www / trailing slash.
        const existing = await Competitor.findOne({ workspaceId, domain, pendingChange: { $ne: "remove" } });
        if (existing) {
            return res.status(400).json({ message: "Competitor already exists" });
        }

        // Plan limit FIRST — it's instant, while the readiness check below can
        // take minutes of browser rendering. Counts active competitors (excludes
        // any staged for removal), so removing one frees a slot.
        const limit = plan?.limits?.competitors;
        if (limit) {
            const count = await activeCompetitorCount(workspaceId);
            if (count >= limit) {
                return res.status(403).json({
                    message: `You've reached your plan's limit of ${limit} competitors. Remove one or upgrade first.`,
                    code: "PLAN_LIMIT",
                });
            }
        }

        // Same onboarding readiness gate — a competitor added here must be readable
        // (homepage + collection + product) and not enterprise-scale, exactly like
        // during onboarding. Blocks bot-protected / unreadable sites up front.
        try {
            const readiness = await checkSiteReadiness(url);
            const verdict = readinessVerdict(readiness);
            if (!verdict.ok) {
                return res.status(422).json({
                    message: verdict.message,
                    code: verdict.code,
                    ...(verdict.scale ? { scale: verdict.scale } : {}),
                });
            }
        } catch (gateErr) {
            console.warn("createCompetitor readiness gate error (allowing):", gateErr?.message || gateErr);
        }

        // Staged add — created now, but only ANALYZED on the next monitoring run.
        const competitor = await Competitor.create({
            name,
            workspaceId,
            role,
            websiteUrl: url,
            domain,
            analysisData: {},
            pendingChange: "add",
        });

        if (Array.isArray(selectedPages) && selectedPages.length > 0) {
            // Persist the 1:1 mapping (competitor page → the owner page it pairs with).
            const ownerByCompetitorUrl = new Map();
            for (const pair of pagePairs) {
                if (pair?.competitorUrl && pair?.workspaceUrl) {
                    ownerByCompetitorUrl.set(normalizePairUrl(pair.competitorUrl), normalizePairUrl(pair.workspaceUrl));
                }
            }
            const pageDocs = selectedPages.map((page) => {
                const mappedOwnerUrl = ownerByCompetitorUrl.get(normalizePairUrl(page)) || "";
                return {
                    url: page,
                    competitorId: competitor._id,
                    workspaceId,
                    mappedOwnerUrl,
                    mapStatus: mappedOwnerUrl ? "matched" : "none",
                };
            });
            await Page.insertMany(pageDocs); // no analysis queue — deferred to next run

            // Ensure the owner has a (staged) page for each mapped owner url, so every
            // pair is comparable when the next run analyzes them. Existing owner pages
            // are left as-is; only missing ones are created (staged like the competitor).
            const ownerUrls = [...new Set([...ownerByCompetitorUrl.values()].filter(Boolean))];
            if (ownerUrls.length) {
                const owner = await Competitor.findOne({ workspaceId, role: "Owner" });
                if (owner) {
                    const existingOwner = await Page.find({ competitorId: owner._id, url: { $in: ownerUrls } }).select("url");
                    const have = new Set(existingOwner.map((p) => p.url));
                    const ownerDocs = ownerUrls
                        .filter((u) => !have.has(u))
                        .map((u) => ({ url: u, competitorId: owner._id, workspaceId, mapStatus: "none", pendingChange: "add" }));
                    if (ownerDocs.length) await Page.insertMany(ownerDocs);
                }
            }
        }

        await Workspace.findByIdAndUpdate(workspaceId, { pendingPageChanges: true, pendingPageChangesAt: new Date() });

        const competitorWithPages = await Competitor.findById(competitor._id).populate("pages");
        return res.status(201).json({
            competitor: competitorWithPages,
            pending: true,
            message: "Competitor added — it'll be analyzed on your next monitoring run.",
        });
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};

const getCompetitor = async (req, res) => {
    try {
        const { workspaceId, competitorId } = req.body;
        if (!workspaceId || !competitorId) {
            return res.status(400).json({ message: "Workspace ID and Competitor ID are required" });
        }
        const competitor = await Competitor.findOne({
            workspaceId,
            _id: competitorId
        }).populate("pages");
        if (!competitor) {
            return res.status(404).json({ message: "Competitor not found" });
        }
        res.json(competitor);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

const updateCompetitor = async (req, res) => {
    const { competitorId } = req.body;

    try {
        if (!competitorId) {
            return res.status(400).json({ message: "Competitor ID is required" });
        }
        const competitor = await Competitor.findByIdAndUpdate(
            competitorId,
            { $set: req.body },
            { new: true }
        );
        res.json(competitor);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

const deleteCompetitor = async (req, res) => {
    const { competitorId } = req.body;

    try {
        if (!competitorId) {
            return res.status(400).json({ message: "Competitor ID is required" });
        }

        // Managing competitors is a paid capability — the free trial is view-only.
        const { plan } = await getWorkspacePlan(req.workspace);
        if (!planAllowsPageManagement(plan)) {
            return res.status(403).json({
                message: "Removing competitors is available on paid plans. Upgrade to manage your competitors.",
                code: "UPGRADE_REQUIRED",
            });
        }

        // Staged removal — the competitor is fully deleted at the next monitoring
        // run (reversible until then). A never-analyzed staged add is dropped now.
        const result = await stageRemoveCompetitor({ workspace: req.workspace, competitorId });
        return res.json({
            ...result,
            message: result.dropped
                ? "Competitor removed."
                : "Competitor marked for removal — it's fully removed at your next monitoring run.",
        });
    } catch (error) {
        const status = /can't be removed|does not belong/.test(error.message || "") ? 400 : 500;
        return res.status(status).json({ message: error.message });
    }
}

// POST /competitor/undo — cancel a staged competitor add/remove
const undoCompetitor = async (req, res) => {
    try {
        const { competitorId } = req.body;
        if (!competitorId) {
            return res.status(400).json({ message: "Competitor ID is required" });
        }
        const result = await undoCompetitorChange({ workspace: req.workspace, competitorId });
        return res.json({ ...result, message: "Staged change reverted." });
    } catch (error) {
        return res.status(400).json({ message: error.message });
    }
}

const getAllCompetitors = async (req, res) => {
    try {


        const { page = 1, limit = 10 } = req.query;
        const competitors = await Competitor
            .find()
            .select('workspaceId domain lastRebuiltAt')
            .populate({
                path: 'workspaceId',
                select: 'name'
            })
            .populate({
                path: 'pages',
                select: 'url scanStatus'
            })
            .skip((page - 1) * limit)
            .limit(limit);
        res.json(competitors);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

const getCompetitorById = async (req, res) => {
    try {
        const { competitorId } = req.params;
        if (!competitorId) {
            return res.status(400).json({ message: "Competitor ID is required" });
        }
        const competitor = await Competitor.findById(competitorId).populate("pages");
        if (!competitor) {
            return res.status(404).json({ message: "Competitor not found" });
        }
        res.json(competitor);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

export {
    createCompetitor,
    getCompetitor,
    updateCompetitor,
    deleteCompetitor,
    undoCompetitor,
    getAllCompetitors,
    getCompetitorById
}

