import { QueueEvents } from "bullmq";

import connection from "../config/redis.js";

import workspaceQueue from "../queues/workspace.queue.js";
import JobService from "../services/job.service.js";

import Workspace from "../models/workspace.js";
import Competitor from "../models/competitor.js";

import { publishSocketEvent } from "../../utils/eventBus.publisher.js";


const queueEvents = new QueueEvents(
  "workspace",
  { connection }
);

/*
|--------------------------------------------------------------------------
| WAITING
|--------------------------------------------------------------------------
*/

queueEvents.on("waiting", async ({ jobId }) => {
  const job = await workspaceQueue.getJob(jobId);
  if (!job) return;

  await JobService.create(job);
  await JobService.event(job, "waiting", "Workspace queued");
});

/*
|--------------------------------------------------------------------------
| ACTIVE
|--------------------------------------------------------------------------
*/

queueEvents.on("active", async ({ jobId }) => {
  const job = await workspaceQueue.getJob(jobId);
  if (!job) return;

  await JobService.start(job);

  const { workspaceId } = job.data;

  await Workspace.findByIdAndUpdate(workspaceId, {
    scanStatus: "Processing",
  });

  publishSocketEvent("workspace.analysis.started", { workspaceId, status: "Processing" });
});

/*
|--------------------------------------------------------------------------
| PROGRESS
|--------------------------------------------------------------------------
*/

queueEvents.on("progress", async ({ jobId, data }) => {
  const job = await workspaceQueue.getJob(jobId);
  if (!job) return;

  await JobService.progress(job, data);

  publishSocketEvent("workspace.analysis.progress", { workspaceId: job.data.workspaceId, progress: data.progress });
});

/*
|--------------------------------------------------------------------------
| COMPLETED
|--------------------------------------------------------------------------
*/

queueEvents.on("completed", async ({ jobId, returnvalue }) => {
  const job = await workspaceQueue.getJob(jobId);
  if (!job) {
    console.warn(
      "⚠️ Workspace completed event received after job was removed:",
      jobId
    );
  }

  const completedJob = job || {
    id: jobId,
    queueName: "workspace",
    name: "rebuildWorkspaceAnalysis",
    data: returnvalue || {},
    processedOn: Date.now(),
    finishedOn: Date.now(),
    opts: {},
  };

  console.log("✅ Workspace completed:", returnvalue);

  await JobService.completed(completedJob, returnvalue);

  const { workspaceId, analysesCreated, competitorsTotal } = returnvalue;

  // Report the TRUTH so the UI can react: no reports saved → Failed (don't strand
  // the user on the loading screen); some-but-not-all → Partial; all → Completed.
  // MUST be capitalised to match the schema enum + what the frontend checks.
  let status = "Completed";
  if (typeof analysesCreated === "number") {
    if (analysesCreated === 0) status = "Failed";
    else if (competitorsTotal && analysesCreated < competitorsTotal) status = "Partial";
  }

  await Workspace.findByIdAndUpdate(workspaceId, {
    scanStatus: status,
    lastRebuiltAt: new Date(),
  });

  publishSocketEvent("workspace.analysis.completed", { workspaceId, status });
});



/*
|--------------------------------------------------------------------------
| FAILED
|--------------------------------------------------------------------------
*/

queueEvents.on("failed", async ({ jobId, failedReason }) => {
  const job = await workspaceQueue.getJob(jobId);
  if (!job) return;

  await JobService.failed(job, new Error(failedReason));

  const { workspaceId } = job.data;

  await Workspace.findByIdAndUpdate(workspaceId, {
    scanStatus: "Failed",
  });

  publishSocketEvent("workspace.analysis.failed", { workspaceId, status: "Failed" });
});

export default queueEvents;