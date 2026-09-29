import { QueueEvents } from "bullmq";

import connection from "../config/redis.js";

import competitorQueue from "../queues/competitor.queue.js";
import workspaceQueue from "../queues/workspace.queue.js";
import alertQueue from "../queues/alert.queue.js";

import JobService from "../services/job.service.js";

import Competitor from "../models/competitor.js";

import { publishSocketEvent } from "../../utils/eventBus.publisher.js";
import { getCompetitorsNeedingReanalysis } from "../services/workspace.service.js";

/*
|--------------------------------------------------------------------------
| INIT QUEUE EVENTS
|--------------------------------------------------------------------------
*/

const queueEvents = new QueueEvents(
  "competitor",
  { connection: connection.duplicate() }
);

/*
|--------------------------------------------------------------------------
| Workspace-rebuild trigger
|--------------------------------------------------------------------------
| Once EVERY competitor has settled (Completed OR Failed), kick off the report
| generation. MUST run from both the completed AND the failed handler — if the
| last competitor to settle is a failure, and only the completed handler fired
| this, the workspace would hang forever at "generating reports". Idempotent via
| the fixed workspace jobId.
*/
async function maybeTriggerWorkspaceRebuild({ workspaceId, userId }) {
  if (!workspaceId) return;

  const pendingCompetitors = await Competitor.countDocuments({
    workspaceId,
    scanStatus: { $nin: ["Completed", "Failed"] },
  });

  if (pendingCompetitors !== 0) {
    console.log(
      `⏳ Waiting for ${pendingCompetitors} competitor(s) before rebuilding workspace ${workspaceId}`
    );
    return;
  }

  const competitorIds = await getCompetitorsNeedingReanalysis(workspaceId);

  if (competitorIds.length === 0) {
    console.log("🟢 No significant changes — skipping workspace re-analysis:", workspaceId);
  } else {
    console.log(`🚀 Rebuilding analysis for ${competitorIds.length} competitor(s):`, workspaceId);
    await workspaceQueue.add(
      "rebuildWorkspaceAnalysis",
      { workspaceId, userId, competitorIds },
      { jobId: `workspace-${workspaceId}`, removeOnComplete: true }
    );
  }

  await alertQueue.add(
    "changeAlert",
    { workspaceId },
    { jobId: `alert-${workspaceId}-${Date.now()}`, removeOnComplete: true, removeOnFail: true }
  );
}

async function initializeQueueEvents() {

  await queueEvents.waitUntilReady();


  /*
  |--------------------------------------------------------------------------
  | WAITING
  |--------------------------------------------------------------------------
  */

  queueEvents.on(
    "waiting",
    async ({ jobId }) => {

      const job =
        await competitorQueue.getJob(
          jobId
        );

      if (!job) return;

      await JobService.create(job);

      await JobService.event(
        job,
        "waiting",
        "Competitor job queued"
      );
    }
  );

  /*
  |--------------------------------------------------------------------------
  | ACTIVE
  |--------------------------------------------------------------------------
  */

  queueEvents.on(
    "active",
    async ({ jobId }) => {

      const job =
        await competitorQueue.getJob(
          jobId
        );

      if (!job) return;

      await JobService.start(job);

      const {
        competitorId,
        workspaceId,
      } = job.data;

      await Competitor.findByIdAndUpdate(
        competitorId,
        {
          scanStatus: "Processing",
        }
      );

      publishSocketEvent(
        "competitor.analysis.started",
        {
          workspaceId,
          competitorId,
          status: "Processing",
        }
      );
    }
  );

  /*
  |--------------------------------------------------------------------------
  | PROGRESS
  |--------------------------------------------------------------------------
  */

  queueEvents.on(
    "progress",
    async ({ jobId, data }) => {

      const job =
        await competitorQueue.getJob(
          jobId
        );

      if (!job) return;

      await JobService.progress(
        job,
        data
      );

      const {
        competitorId,
        workspaceId,
      } = job.data;

      publishSocketEvent(
        "competitor.analysis.progress",
        {
          workspaceId,
          competitorId,
          progress: data,
        }
      );
    }
  );

  /*
  |--------------------------------------------------------------------------
  | COMPLETED
  |--------------------------------------------------------------------------
  */

  queueEvents.on(
    "completed",
    async ({
      jobId,
      returnvalue,
    }) => {

      if(!returnvalue) {
        console.warn(
          "⚠️ Competitor completed event received with no return value:",
          jobId
        );

        return;
      }

      const job =
        await competitorQueue.getJob(
          jobId
        );

      if (!job) {
        console.warn(
          "⚠️ Competitor completed event received after job was removed:",
          jobId
        );
      }

      const completedJob = job || {
        id: jobId,
        queueName: "competitor",
        name: "rebuild",
        data: returnvalue || {},
        processedOn: Date.now(),
        finishedOn: Date.now(),
        opts: {},
      };

      await JobService.completed(
        completedJob,
        returnvalue
      );

      const {
        competitorId,
        workspaceId,
        userId,
        snapshot,
      } = returnvalue || completedJob.data;

      /*
      |--------------------------------------------------------------------------
      | UPDATE COMPETITOR
      |--------------------------------------------------------------------------
      */

      await Competitor.findByIdAndUpdate(
        competitorId,
        {
          analysisData: snapshot,

          scanStatus: "Completed",

          lastRebuiltAt:
            new Date(),

          updatedAt:
            new Date(),
        }
      );

      publishSocketEvent(
        "competitor.analysis.completed",
        {
          workspaceId,
          competitorId,
          status: "Completed",
        }
      );

      /*
      |--------------------------------------------------------------------------
      | REBUILD WORKSPACE
      |--------------------------------------------------------------------------
      */

      await maybeTriggerWorkspaceRebuild({ workspaceId, userId });
    }
  );

  /*
  |--------------------------------------------------------------------------
  | FAILED
  |--------------------------------------------------------------------------
  */

  queueEvents.on(
    "failed",
    async ({
      jobId,
      failedReason,
    }) => {

      const job =
        await competitorQueue.getJob(
          jobId
        );

      if (!job) return;

      await JobService.failed(
        job,
        new Error(failedReason)
      );

      const {
        competitorId,
        workspaceId,
        userId,
      } = job.data;

      await Competitor.findByIdAndUpdate(
        competitorId,
        {
          scanStatus: "Failed",
        }
      );

      publishSocketEvent(
        "competitor.analysis.failed",
        {
          workspaceId,
          competitorId,
          status: "Failed",
        }
      );

      // A failed competitor is still settled — advance the workspace so the last
      // competitor failing can never freeze it at "generating reports".
      await maybeTriggerWorkspaceRebuild({ workspaceId, userId });
    }
  );
}

/*
|--------------------------------------------------------------------------
| START
|--------------------------------------------------------------------------
*/

initializeQueueEvents().catch(
  (err) => {

    console.error(
      "❌ QueueEvents startup failed",
      err
    );

    process.exit(1);
  }
);

export default queueEvents;