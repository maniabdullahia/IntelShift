import { QueueEvents } from "bullmq";

import connection from "../config/redis.js";

import reconQueue from "../queues/recon.queue.js";
import Competitor from "../models/competitor.js";
import Workspace from "../models/workspace.js";

import { publishSocketEvent } from "../../utils/eventBus.publisher.js";

/*
| Advance the workspace from "recon" to "selecting" once EVERY site's recon has
| settled (Completed OR Failed) — mirrors the analysis queue's "all pages settled"
| rebuild trigger. Runs from both the completed and failed handlers so a final
| failing recon can't strand the workspace in "recon" forever. The guarded update
| (setupStage: "recon") makes it idempotent — only the first caller flips it.
*/
const maybeAdvanceToSelecting = async (workspaceId) => {
  if (!workspaceId) return;
  const total = await Competitor.countDocuments({ workspaceId });
  const settled = await Competitor.countDocuments({
    workspaceId,
    reconStatus: { $in: ["Completed", "Failed"] },
  });
  if (total > 0 && total === settled) {
    const ws = await Workspace.findOneAndUpdate(
      { _id: workspaceId, setupStage: "recon" },
      { $set: { setupStage: "selecting" } },
      { new: true }
    );
    if (ws) {
      console.log(`🧭 Workspace ${workspaceId} recon complete → setupStage=selecting`);
      publishSocketEvent("workspace.setup.stage", { workspaceId, setupStage: "selecting" });
    }
  }
};

/*
|--------------------------------------------------------------------------
| RECON Queue Events
|--------------------------------------------------------------------------
| Persists recon results onto the competitor as jobs settle, and pushes socket
| updates so the workspace can render each site's recon progressively (homepage
| insight first, collection index as it lands). Mirrors analysis.event.js.
*/

const queueEvents = new QueueEvents("recon", { connection });

/* ── ACTIVE → mark the site as capturing ──────────────────────────────── */
queueEvents.on("active", async ({ jobId }) => {
  const job = await reconQueue.getJob(jobId);
  if (!job) return;

  const { competitorId, workspaceId } = job.data;
  if (competitorId) {
    await Competitor.findByIdAndUpdate(competitorId, { reconStatus: "Processing" });
  }
  publishSocketEvent("recon.started", { competitorId, workspaceId, status: "Processing" });
});

/* ── COMPLETED → persist the recon blob onto the competitor ───────────── */
queueEvents.on("completed", async ({ jobId, returnvalue }) => {
  const job = await reconQueue.getJob(jobId);
  if (!job) return;

  const { competitorId, workspaceId, recon } = returnvalue || {};
  if (competitorId) {
    await Competitor.findByIdAndUpdate(competitorId, {
      recon,
      reconStatus: "Completed",
      reconCapturedAt: new Date(),
    });
  }
  publishSocketEvent("recon.completed", {
    competitorId,
    workspaceId,
    status: "Completed",
    collectionCount: recon?.collectionCount ?? null,
    hasHomepage: !!recon?.homepage,
  });

  await maybeAdvanceToSelecting(workspaceId);
});

/* ── FAILED → mark failed, keep the workspace moving ──────────────────── */
queueEvents.on("failed", async ({ jobId, failedReason }) => {
  const job = await reconQueue.getJob(jobId);
  if (!job) return;

  const { competitorId, workspaceId } = job.data;
  if (competitorId) {
    await Competitor.findByIdAndUpdate(competitorId, { reconStatus: "Failed" });
  }
  publishSocketEvent("recon.failed", { competitorId, workspaceId, status: "Failed", reason: failedReason });

  await maybeAdvanceToSelecting(workspaceId);
});

export default queueEvents;
