import { Worker } from "bullmq";
import mongoose from "mongoose";
import connection from "../config/redis.js";

import { captureRecon } from "../services/recon.service.js";
import Competitor from "../models/competitor.js";
import Workspace from "../models/workspace.js";
import { suggestCompetitors as suggestCompetitorsService } from "../services/competitorSuggest.service.js";
import { autoSelectAndAnalyze, getCompleteSiteConfig } from "../services/proAutoselect.service.js";

mongoose.set("bufferCommands", false);

import dotenv from "dotenv";
dotenv.config();

/*
|--------------------------------------------------------------------------
| RECON WORKER
|--------------------------------------------------------------------------
| Captures breadth-only recon for one site (homepage + nav + collection index)
| and PERSISTS the result itself. Persistence + the setup-stage advance live
| here (not in a QueueEvents listener) so they don't depend on the API server
| being restarted, and so the large recon blob is written straight to Mongo
| instead of being shipped through the job's return value / event stream.
| Progress reaches the frontend via its 4s poll of GET /api/workspace.
*/

/*
| Advance the workspace from "recon" to "selecting" once EVERY site's recon has
| settled (Completed OR Failed). Guarded update makes it idempotent — only the
| first caller flips it — and it runs after both success and failure so a failing
| recon can't strand the workspace in "recon".
*/
const maybeAdvanceToSelecting = async (workspaceId) => {
  if (!workspaceId) return;
  const total = await Competitor.countDocuments({ workspaceId });
  const settled = await Competitor.countDocuments({
    workspaceId,
    reconStatus: { $in: ["Completed", "Failed"] },
  });
  if (total > 0 && total === settled) {
    // Pro complete-site: skip manual page selection entirely. Atomically CLAIM the
    // transition (recon → analyzing) so exactly one caller runs the auto-select; on
    // any failure, fall back to normal manual "selecting" so the user is never stuck.
    try {
      const wsMeta = await Workspace.findById(workspaceId).select("ownerId setupStage").lean();
      if (wsMeta?.setupStage === "recon") {
        const cfg = await getCompleteSiteConfig(wsMeta.ownerId);
        if (cfg.completeSite) {
          const claim = await Workspace.findOneAndUpdate(
            { _id: workspaceId, setupStage: "recon" },
            { $set: { setupStage: "analyzing" } },
            { new: true }
          );
          if (!claim) return; // another caller already advanced this workspace
          try {
            await autoSelectAndAnalyze(workspaceId, wsMeta.ownerId);
            console.log(`🧭 Workspace ${workspaceId} recon complete → complete-site auto-select → analyzing`);
          } catch (autoErr) {
            console.error(`pro auto-select failed for ${workspaceId}, falling back to manual selecting:`, autoErr?.message || autoErr);
            await Workspace.findByIdAndUpdate(workspaceId, { setupStage: "selecting" });
            generateAndStoreSuggestions(workspaceId);
          }
          return;
        }
      }
    } catch (gateErr) {
      console.warn(`complete-site gate check failed for ${workspaceId} (continuing to manual):`, gateErr?.message || gateErr);
    }

    const ws = await Workspace.findOneAndUpdate(
      { _id: workspaceId, setupStage: "recon" },
      { $set: { setupStage: "selecting" } },
      { new: true }
    );
    if (ws) {
      console.log(`🧭 Workspace ${workspaceId} recon complete → setupStage=selecting`);
      // Generate competitor suggestions ONCE, in the background, and store them on
      // the workspace so the "Replace competitor" picker shows them instantly (no
      // re-run). Fire-and-forget: the worker process outlives the request, so this
      // is safe, and a failure never blocks the flow. Only the first caller reaches
      // here (guarded update above), so it runs exactly once per workspace.
      generateAndStoreSuggestions(workspaceId);
    }
  }
};

const generateAndStoreSuggestions = async (workspaceId) => {
  try {
    const ws = await Workspace.findById(workspaceId).select("url industry suggestedCompetitors focusCategories focusMode").lean();
    if (!ws?.url) return;
    if ((ws.suggestedCompetitors || []).length) return; // already stored — don't redo
    const owner = await Competitor.findOne({ workspaceId, role: "Owner" }).select("currency").lean();
    // Feed the user's chosen focus categories (ordered = priority) into the search
    // so suggestions target what they care about; "all"/empty → auto-detect as before.
    const focus = ws.focusMode === "selected" && Array.isArray(ws.focusCategories) ? ws.focusCategories : [];
    const list = await suggestCompetitorsService(ws.url, ws.industry || "", [], owner?.currency || "", focus);
    const clean = (Array.isArray(list) ? list : [])
      .slice(0, 12)
      .map((s) => ({
        name: s.name || "",
        url: s.url || "",
        domain: s.domain || "",
        reason: s.reason || "",
        matchedCategories: Array.isArray(s.matchedCategories) ? s.matchedCategories : [],
        similarityScore: typeof s.similarityScore === "number" ? s.similarityScore : undefined,
        whyMatch: s.whyMatch || "",
      }))
      .filter((s) => s.url || s.domain);
    if (clean.length) {
      await Workspace.findByIdAndUpdate(workspaceId, {
        $set: { suggestedCompetitors: clean, suggestedCompetitorsAt: new Date() },
      });
      console.log(`🔎 Stored ${clean.length} competitor suggestions for workspace ${workspaceId}`);
    }
  } catch (e) {
    console.warn(`suggestion generation failed for ${workspaceId}: ${e?.message || e}`);
  }
};

async function startWorker() {
  try {
    await mongoose.connect(process.env.MONGO_URI);

    const reconWorker = new Worker(
      "recon",
      async (job) => {
        const { competitorId, workspaceId, url, currency } = job.data;

        if (!url) {
          throw new Error("recon job missing url");
        }

        // Mark the site as being read (the poll shows "Reading…").
        if (competitorId) {
          await Competitor.findByIdAndUpdate(competitorId, { reconStatus: "Processing" });
        }

        try {
          console.log(`🔎 Recon capturing: ${url} (competitor ${competitorId})`);
          const recon = await captureRecon({ url, currency });

          // Persist the recon blob + mark complete, straight to Mongo.
          await Competitor.findByIdAndUpdate(competitorId, {
            recon,
            reconStatus: "Completed",
            reconCapturedAt: new Date(),
          });

          console.log(
            `🔎 Recon done: ${url} — ${recon.collectionCount} collections, ` +
            `homepage=${recon.homepage ? "yes" : "no"}, ${recon.tookMs}ms`
          );

          await maybeAdvanceToSelecting(workspaceId);
          return { competitorId, workspaceId };
        } catch (err) {
          console.error(`🔥 Recon failed for ${url}: ${err?.message}`);
          if (competitorId) {
            await Competitor.findByIdAndUpdate(competitorId, { reconStatus: "Failed" });
          }
          // Still advance — a failed site is a settled site.
          await maybeAdvanceToSelecting(workspaceId);
          throw err;
        }
      },
      {
        connection,
        concurrency: 2,
        lockDuration: 300000,
      }
    );

    reconWorker.on("failed", (job, err) => {
      console.error("🔥 Recon job failed:", job?.id, err?.message);
    });

    reconWorker.on("completed", (job) => {
      console.log("🎉 Recon job completed:", job.id);
    });

    console.log("✅ Recon Worker started");
  } catch (err) {
    console.error("❌ Recon Worker startup failed:", err);
    process.exit(1);
  }
}

startWorker();
