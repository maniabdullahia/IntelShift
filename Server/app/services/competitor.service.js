import Competitor from "../models/competitor.js";
import Page from "../models/page.js";
import ChangeReport from "../models/changeReport.js";
import MetricSnapshot from "../models/metricSnapshot.js";
import Analysis from "../models/analysis.js";
import { AnalyzeURL } from "../../utils/Analyzer.js";
import analysisQueue from "../queues/analysis.queue.js";
import mongoose from "mongoose";
import Workspace from "../models/workspace.js";

/* ── Staged competitor add/remove (deferred to next monitoring run) ─────── */

const flagWorkspacePending = (workspaceId) =>
  Workspace.findByIdAndUpdate(workspaceId, {
    pendingPageChanges: true,
    pendingPageChangesAt: new Date(),
  });

/** Active competitors toward the plan limit (excludes ones staged for removal). */
export const activeCompetitorCount = (workspaceId) =>
  Competitor.countDocuments({ workspaceId, role: "Competitor", pendingChange: { $ne: "remove" } });

/** Hard-delete a competitor and everything hanging off it (no orphans). */
export const cascadeDeleteCompetitor = async (competitorId, workspaceId) => {
  await Page.deleteMany({ competitorId });
  await ChangeReport.deleteMany({ competitorId });
  await MetricSnapshot.deleteMany({ competitorId });
  // Analysis.competitors is a single { ownerId, competitorId } object (NOT an
  // array) — delete the whole comparison doc, don't $pull.
  await Analysis.deleteMany({ workspaceId, "competitors.competitorId": competitorId });
  await Competitor.findByIdAndDelete(competitorId);
};

/** Stage a competitor for removal at the next monitoring run (reversible). */
export const stageRemoveCompetitor = async ({ workspace, competitorId }) => {
  const competitor = await Competitor.findById(competitorId);
  if (!competitor) throw new Error("Competitor not found");
  if (String(competitor.workspaceId) !== String(workspace._id)) {
    throw new Error("Competitor does not belong to this workspace");
  }
  if (competitor.role === "Owner") throw new Error("Your own site can't be removed.");

  // A competitor that was only ever staged for adding can just be dropped now.
  if (competitor.pendingChange === "add") {
    await cascadeDeleteCompetitor(competitor._id, workspace._id);
    await flagWorkspacePending(workspace._id);
    return { dropped: true };
  }

  await Competitor.updateOne(
    { _id: competitor._id },
    { $set: { pendingChange: "remove", retiredAt: new Date() } }
  );
  await flagWorkspacePending(workspace._id);
  return { pending: true };
};

/** Cancel a staged competitor add/remove. */
export const undoCompetitorChange = async ({ workspace, competitorId }) => {
  const competitor = await Competitor.findById(competitorId);
  if (!competitor) throw new Error("Competitor not found");
  if (String(competitor.workspaceId) !== String(workspace._id)) {
    throw new Error("Competitor does not belong to this workspace");
  }
  if (competitor.pendingChange === "add") {
    await cascadeDeleteCompetitor(competitor._id, workspace._id);
    return { removed: true };
  }
  if (competitor.pendingChange === "remove") {
    await Competitor.updateOne(
      { _id: competitor._id },
      { $set: { pendingChange: "none", retiredAt: null } }
    );
  }
  return { restored: true };
};

/**
 * Commit staged competitor changes for a workspace — called at the start of a
 * monitoring run. Removes staged-removals (cascade) and promotes staged-adds
 * (queues their pages for analysis this run).
 */
export const applyPendingCompetitorChanges = async (workspaceId) => {
  const staged = await Competitor.find({
    workspaceId,
    pendingChange: { $in: ["add", "remove"] },
  }).select("_id pendingChange");

  let removed = 0;
  for (const comp of staged) {
    if (comp.pendingChange === "remove") {
      await cascadeDeleteCompetitor(comp._id, workspaceId);
      removed += 1;
    }
  }

  // Promote staged adds to normal competitors — rescanWorkspace queues all
  // active pages afterwards, so their pages get analyzed this run.
  const promoted = staged.filter((c) => c.pendingChange === "add").map((c) => c._id);
  if (promoted.length) {
    await Competitor.updateMany({ _id: { $in: promoted } }, { $set: { pendingChange: "none" } });
  }

  return { removed, added: promoted.length };
};


const normalizePairUrl = (raw) => {
    let u = String(raw || "").trim();
    if (!u) return "";
    if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
    return u.replace(/\/+$/, "");
};

const createCompetitorService = async (data, session = null) => {
    const {
        name,
        url,
        role = "Owner",
        workspaceId,
        selectedPages = [],
        // Onboarding mapping: [{ workspaceUrl, competitorUrl, status }]. Lets us
        // persist which owner page each competitor page is paired with.
        pagePairs = [],
        // Regional store / currency the user confirmed at onboarding. `url` is
        // already the chosen store's URL, so the crawl is pinned via it; these
        // are stored as metadata for display and currency-aware analysis.
        region = "",
        storeUrl = "",
        currency = "",
    } = data;

    // -------------------------------
    // ✅ VALIDATION
    // -------------------------------
    if (!name || !url || !workspaceId) {
        throw new Error("Missing required fields: name, url, workspaceId");
    }

    if (!mongoose.Types.ObjectId.isValid(workspaceId)) {
        throw new Error("Invalid workspaceId format");
    }

    // -------------------------------
    // ✅ CHECK WORKSPACE EXISTS
    // -------------------------------
    const workspace = await Workspace.findById(workspaceId).session(session);
    if (!workspace) {
        throw new Error("Workspace not found");
    }

    // -------------------------------
    // ✅ NORMALIZE DOMAIN
    // -------------------------------
    const domain = new URL(url).hostname.replace(/^www\./, "");

    // -------------------------------
    // ✅ PREVENT DUPLICATE (by domain)
    // -------------------------------
    const existing = await Competitor.findOne({ workspaceId, domain }).session(session);
    if (existing) {
        throw new Error("Competitor with this domain already exists in workspace");
    }

    // -------------------------------
    // ✅ CREATE COMPETITOR
    // -------------------------------
    const [competitor] = await Competitor.create(
        [
            {
                name,
                websiteUrl: url,
                role,
                workspaceId,
                domain,
                region,
                storeUrl: storeUrl || url,
                currency,
            },
        ],
        { session }
    );

    let createdPages = [];

    // -------------------------------
    // ✅ CREATE PAGES (if provided) 
    // -------------------------------
    if (Array.isArray(selectedPages) && selectedPages.length > 0) {
        // Map each competitor page URL -> the owner page it was paired with.
        const ownerByCompetitorUrl = new Map();
        for (const pair of pagePairs) {
            if (pair?.competitorUrl && pair?.workspaceUrl) {
                ownerByCompetitorUrl.set(
                    normalizePairUrl(pair.competitorUrl),
                    normalizePairUrl(pair.workspaceUrl)
                );
            }
        }

        const pageDocs = selectedPages.map((pageUrl) => {
            const mappedOwnerUrl = ownerByCompetitorUrl.get(normalizePairUrl(pageUrl)) || "";
            return {
                url: pageUrl,
                competitorId: competitor._id,
                workspaceId,
                mappedOwnerUrl,
                mapStatus: mappedOwnerUrl ? "matched" : "none",
            };
        });

        createdPages = await Page.insertMany(pageDocs, { session });
    }

    // ❗ IMPORTANT:
    // Return pages so controller queues AFTER transaction commit
    return { competitor, pages: createdPages };
};

const deleteCompetitorService = async (workspaceId) => {
    await Competitor.deleteMany({ workspaceId });
    await Page.deleteMany({ competitorId: { $in: await Competitor.find({ workspaceId }).select('_id') } });
}

const findCompetitorsByWorkspaceId = async (workspaceId) => {
    if (!mongoose.Types.ObjectId.isValid(workspaceId)) {
        throw new Error("Invalid workspaceId format");
    }

    const competitors = await Competitor.find({ workspaceId });
    return competitors;
}

export { createCompetitorService, deleteCompetitorService, findCompetitorsByWorkspaceId };