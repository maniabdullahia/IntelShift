
import Competitor from "../models/competitor.js";
import Workspace from "../models/workspace.js";
import Page from "../models/page.js";
import Analysis from "../models/analysis.js";
import ChangeReport from "../models/changeReport.js";

import analysisQueue from "../queues/analysis.queue.js";
import { getNextScanAt } from "../../utils/scan.js";
import { applyPendingPageChanges } from "./page.service.js";
import { applyPendingCompetitorChanges } from "./competitor.service.js";

/**
 * Recompute a user's workspace next-scan time for a (possibly new) plan cadence.
 * Called on plan change so upgrades start monitoring and downgrades to a
 * one-time plan stop it (nextScanAt = null). No-op if the user has no workspace.
 *
 * @param {string} ownerId
 * @param {string} cadence plan.planReportingFrequency (once|daily|2D|3D|weekly|monthly)
 * @returns {Promise<Date|null>} the new nextScanAt (or null)
 */
const recomputeNextScanForOwner = async (ownerId, cadence) => {
    const workspace = await Workspace.findOne({ ownerId });
    if (!workspace) return null;

    const nextScanAt = cadence && cadence !== "once" ? getNextScanAt(cadence) : null;
    workspace.nextScanAt = nextScanAt;
    await workspace.save();
    return nextScanAt;
};

/**
 * Which competitors need their comparison + AI analysis (re)run this cycle.
 * A competitor qualifies when it has no analysis yet (first run) OR its latest
 * change report was significant enough to warrant AI (detector's shouldSendToAI).
 * Competitors with no meaningful change keep their existing analysis untouched.
 *
 * @param {string} workspaceId
 * @returns {Promise<string[]>} competitor ids needing re-analysis
 */
const getCompetitorsNeedingReanalysis = async (workspaceId) => {
    const competitors = await Competitor.find({ workspaceId, role: "Competitor" }).select("_id");
    const needing = [];

    for (const c of competitors) {
        const hasAnalysis = await Analysis.exists({ "competitors.competitorId": c._id });
        if (!hasAnalysis) {
            needing.push(c._id.toString());
            continue;
        }
        const latest = await ChangeReport.findOne({ competitorId: c._id })
            .sort({ monitoredAt: -1 })
            .lean();
        if (latest?.report?.shouldSendToAI) needing.push(c._id.toString());
    }

    return needing;
};

const deleteWorkspace = async (userId) => {
    try {
        // 1. Find workspace by ownerId
        const workspace = await Workspace.findOne({ ownerId: userId });

        if (!workspace) {
            throw new Error("Workspace not found");
        }

        const workspaceId = workspace._id;

        // 2. Get all competitors FIRST
        const competitors = await Competitor.find({ workspaceId }).select("_id");

        const competitorIds = competitors.map(c => c._id);

        // 3. Delete pages linked to competitors
        await Page.deleteMany({
            competitorId: { $in: competitorIds }
        });

        // 4. Delete competitors
        await Competitor.deleteMany({ workspaceId });

        // 5. Delete workspace
        await Workspace.findByIdAndDelete(workspaceId);

    } catch (error) {
        throw new Error(`Failed to delete workspace: ${error.message}`);
    }
};

const rescanWorkspace = async (workspaceId) => {
    try {
        const workspace = await Workspace.findById(workspaceId);

        if (!workspace) {
            throw new Error("Workspace not found");
        }

        const userId = workspace.ownerId;

        // Commit any staged competitor edits FIRST (removes are deleted, adds are
        // promoted), then staged page edits — this is what makes "changes apply on
        // the next run" true for both.
        await applyPendingCompetitorChanges(workspaceId);
        await applyPendingPageChanges(workspaceId);

        const competitors = await Competitor.find({ workspaceId }).select("_id");
        const competitorIds = competitors.map(c => c._id);

        // Only analyze live pages — anything still staged for removal is skipped.
        const pages = await Page.find({
            competitorId: { $in: competitorIds },
            pendingChange: { $ne: "remove" },
        });

        console.log(`Rescanning workspace: ${workspaceId}`);
        pages.forEach(async (page) => {
            console.log( {
                id: page._id.toString(),
                url: page.url,
                competitorId: page.competitorId.toString(),
                workspaceId: page.workspaceId.toString(),
            });
        })

        await Page.updateMany(
            { competitorId: { $in: competitorIds } },
            { $set: { scanStatus: 'pending' } }
        );

        for (const page of pages) {
            await analysisQueue.add('analyzePage', {
                pageId: page._id.toString(),
                url: page.url,
                competitorId: page.competitorId.toString(),
                workspaceId: page.workspaceId.toString(),
                userId: userId.toString(),
            });
        }

        return {
            pages: pages.map(page => ({
                id: page._id,
                url: page.url,
                competitorId: page.competitorId,
                workspaceId: page.workspaceId,
            }))
        }



    } catch (error) {
        throw new Error(`Failed to rescan workspace: ${error.message}`);
    }
}

export { deleteWorkspace, rescanWorkspace, getCompetitorsNeedingReanalysis, recomputeNextScanForOwner };