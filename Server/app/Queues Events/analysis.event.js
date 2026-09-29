import { QueueEvents } from "bullmq";

import connection from "../config/redis.js";

import analysisQueue from "../queues/analysis.queue.js";
import competitorQueue from "../queues/competitor.queue.js";

import JobService from "../services/job.service.js";

import Page from "../models/page.js";
import Competitor from "../models/competitor.js";
import Notification from "../models/notification.js";

import { publishSocketEvent } from "../../utils/eventBus.publisher.js";

/*
| A tracked page returned a definitive 404 during a scan. Mark it offline, notify
| the user to replace it, and let the competitor rebuild continue (a settled page).
| Its mapped counterpart is skipped at comparison time (see workspace.worker).
*/
const handlePageOffline = async ({ pageId, competitorId, workspaceId, userId, url, httpStatus }) => {
  await Page.findByIdAndUpdate(pageId, {
    scanStatus: "Failed",
    offline: true,
    offlineSince: new Date(),
    httpStatus: httpStatus || 404,
  });
  publishSocketEvent("page.analysis.failed", { pageId, competitorId, workspaceId, status: "Failed", offline: true });

  try {
    const comp = competitorId ? await Competitor.findById(competitorId).select("name role").lean() : null;
    const whose = !comp || comp.role === "Owner" ? "your" : `${comp.name}'s`;
    await Notification.create({
      userId,
      type: "page_offline",
      title: "A tracked page is no longer available",
      body: `${whose} page ${url} returned 404 and was skipped this run. Replace it with another page to keep the comparison accurate.`,
      link: "/dashboard",
    });
  } catch (nErr) {
    console.warn("Offline notification failed (continuing):", nErr.message);
  }

  await maybeQueueCompetitorRebuild({ competitorId, workspaceId, userId });
};

/*
|--------------------------------------------------------------------------
| Queue Events
|--------------------------------------------------------------------------
*/

const queueEvents = new QueueEvents(
  "analysis",
  { connection }
);

/*
|--------------------------------------------------------------------------
| Competitor rebuild trigger
|--------------------------------------------------------------------------
| Once EVERY page for a competitor has settled (Completed OR Failed), build the
| competitor snapshot from whatever completed. This MUST run from both the
| completed AND the failed handler — otherwise, if the last page to settle is a
| failure, the rebuild never fires and the whole workspace hangs at "generating
| reports". Idempotent via the fixed jobId so a simultaneous complete+fail can't
| enqueue two rebuilds.
*/
const maybeQueueCompetitorRebuild = async ({ competitorId, workspaceId, userId }) => {
  if (!competitorId) return;

  const totalPages = await Page.countDocuments({ competitorId });
  const settledPages = await Page.countDocuments({
    competitorId,
    scanStatus: { $in: ["Completed", "Failed"] },
  });

  if (totalPages > 0 && totalPages === settledPages) {
    await competitorQueue.add(
      "rebuild",
      { competitorId, workspaceId, userId },
      { jobId: `rebuild-${competitorId}`, removeOnComplete: true }
    );
  }
};

/*
|--------------------------------------------------------------------------
| WAITING
|--------------------------------------------------------------------------
*/

queueEvents.on("waiting", async ({ jobId }) => {
  const job = await analysisQueue.getJob(jobId);
  if (!job) return;

  await JobService.create(job);
  await JobService.event(job, "waiting", "Job queued");
});

/*
|--------------------------------------------------------------------------
| ACTIVE
|--------------------------------------------------------------------------
*/

queueEvents.on("active", async ({ jobId }) => {
  const job = await analysisQueue.getJob(jobId);
  if (!job) return;

  await JobService.start(job);

  const { pageId, competitorId, workspaceId } = job.data;

  /*
  |--------------------------------------------------
  | Page → Analyzing
  |--------------------------------------------------
  */

  await Page.findByIdAndUpdate(pageId, {
    scanStatus: "Analyzing",
  });

  publishSocketEvent("page.analysis.started", { pageId, competitorId, workspaceId, status: "Analyzing" });

  /*
  |--------------------------------------------------
  | Competitor → Pending
  |--------------------------------------------------
  */

  if (competitorId) {
    await Competitor.findByIdAndUpdate(competitorId, {
      scanStatus: "Pending",
    });
  }
  publishSocketEvent("competitor.analysis.started", { competitorId, workspaceId, status: "Pending" });
});



/*
|--------------------------------------------------------------------------
| PROGRESS
|--------------------------------------------------------------------------
*/

queueEvents.on("progress", async ({ jobId, data }) => {
  const job = await analysisQueue.getJob(jobId);
  if (!job) return;

  await JobService.progress(job, data);

  // Include the routing IDs (like started/completed) so the event router can
  // deliver it to the workspace room — without workspaceId it can't be routed.
  const { pageId, competitorId, workspaceId } = job.data;
  publishSocketEvent("page.analysis.progress", {
    pageId,
    competitorId,
    workspaceId,
    progress: data?.progress,
    status: "Analyzing",
  });
});

/*
|--------------------------------------------------------------------------
| COMPLETED
|--------------------------------------------------------------------------
*/

queueEvents.on("completed", async ({ jobId, returnvalue }) => {
  const job = await analysisQueue.getJob(jobId);
  if (!job) return;

  await JobService.completed(job, returnvalue);

  const {
    pageId,
    competitorId,
    workspaceId,
    userId,
    analysis,
    offline,
    httpStatus,
    url,
  } = returnvalue;

  // Page 404'd — mark offline + notify instead of storing junk as "Completed".
  if (offline) {
    await handlePageOffline({ pageId, competitorId, workspaceId, userId, url, httpStatus });
    return;
  }

  /*
  |--------------------------------------------------
  | Update Page
  |--------------------------------------------------
  */

  await Page.findByIdAndUpdate(pageId, {
    scanStatus: "Completed",
    analysisData: analysis,
    offline: false,
    httpStatus: 200,
    updatedAt: new Date(),
  });


  publishSocketEvent("page.analysis.completed", { pageId, competitorId, workspaceId, status: "Completed" });

  /*
  |--------------------------------------------------
  | Competitor Rebuild Logic
  |--------------------------------------------------
  */

  await maybeQueueCompetitorRebuild({ competitorId, workspaceId, userId });
});

/*
|--------------------------------------------------------------------------
| FAILED
|--------------------------------------------------------------------------
*/

queueEvents.on("failed", async ({ jobId, failedReason }) => {
  const job = await analysisQueue.getJob(jobId);
  if (!job) return;

  await JobService.failed(job, new Error(failedReason));

  const { pageId, workspaceId, competitorId, userId } = job.data;

  await Page.findByIdAndUpdate(pageId, {
    scanStatus: "Failed",
  });

  publishSocketEvent("page.analysis.failed", { pageId, workspaceId, competitorId, status: "Failed" });

  // A failed page is still a settled page — advance the competitor so the last
  // page failing can never freeze the workspace.
  await maybeQueueCompetitorRebuild({ competitorId, workspaceId, userId });
});

export default queueEvents;