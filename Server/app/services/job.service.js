import Job from "../models/job.js";
import JobEvent from "../models/jobEvent.js";

class JobService {

  /*
  |--------------------------------------------------------------------------
  | Normalize Job Object (IMPORTANT FIX)
  |--------------------------------------------------------------------------
  */

  static normalize(job) {
    return {
      jobId: job.id,

      queueName: job.queueName || "unknown",

      jobName: job.name || "unknown",

      data: job.data || {},

      userId: job.data?.userId || null,

      workspaceId: job.data?.workspaceId || null,

      competitorId: job.data?.competitorId || null,

      pageId: job.data?.pageId || null,

      attempts: job.opts?.attempts || 1,
    };
  }

  /*
  |--------------------------------------------------------------------------
  | Create Job (IDEMPOTENT FIX)
  |--------------------------------------------------------------------------
  */

  static async create(job) {

    const data = this.normalize(job);

    const existingJob = await Job.findOne({
      jobId: data.jobId,
    });

    if (existingJob) return existingJob;

    return await Job.create({
      jobId: data.jobId,
      queueName: data.queueName,
      jobName: data.jobName,
      status: "waiting",
      progress: 0,
      data: data.data,
      userId: data.userId,
      workspaceId: data.workspaceId,
      competitorId: data.competitorId,
      pageId: data.pageId,
      maxAttempts: data.attempts,
    });
  }

  /*
  |--------------------------------------------------------------------------
  | Start Job
  |--------------------------------------------------------------------------
  */

  static async start(job) {

    const data = this.normalize(job);

    await Job.updateOne(
      { jobId: data.jobId },
      {
        status: "active",
        startedAt: new Date(),
      }
    );

    await this.event(
      job,
      "active",
      "Job started"
    );
  }

  /*
  |--------------------------------------------------------------------------
  | Progress (SAFE UPDATE)
  |--------------------------------------------------------------------------
  */

  static async progress(job, progress) {

    const data = this.normalize(job);

    const safeProgress =
      Math.max(0, Math.min(100, progress || 0));

    await Job.updateOne(
      { jobId: data.jobId },
      {
        progress: safeProgress,
      }
    );

    await this.event(
      job,
      "progress",
      `Progress ${safeProgress}%`,
      safeProgress
    );
  }

  /*
  |--------------------------------------------------------------------------
  | Completed (FIXED TIMING LOGIC)
  |--------------------------------------------------------------------------
  */

  static async completed(job, result = null) {

    const data = this.normalize(job);

    const startedAt =
      job.processedOn
        ? new Date(job.processedOn)
        : new Date();

    const completedAt =
      job.finishedOn
        ? new Date(job.finishedOn)
        : new Date();

    const duration =
      completedAt - startedAt;

    await Job.updateOne(
      { jobId: data.jobId },
      {
        status: "completed",
        progress: 100,
        completedAt,
        duration,
      }
    );

    await this.event(
      job,
      "completed",
      "Job completed successfully",
      100
    );
  }

  /*
  |--------------------------------------------------------------------------
  | Failed Job (ENHANCED)
  |--------------------------------------------------------------------------
  */

  static async failed(job, error) {

    const data = this.normalize(job);

    await Job.updateOne(
      { jobId: data.jobId },
      {
        status: "failed",
        failedReason: error?.message || "Unknown error",
        stacktrace: error?.stack
          ? [error.stack]
          : [],
        failedAt: new Date(),
      }
    );

    await this.event(
      job,
      "failed",
      error?.message || "Job failed"
    );
  }

  /*
  |--------------------------------------------------------------------------
  | Event Logger (DEDUP SAFE)
  |--------------------------------------------------------------------------
  */

  static async event(
    job,
    event,
    message = null,
    progress = null,
    metadata = {}
  ) {

    const data = this.normalize(job);

    /*
    |--------------------------------------------------
    | OPTIONAL: prevent duplicate spam events
    |--------------------------------------------------
    */

    const lastEvent = await JobEvent.findOne({
      jobId: data.jobId,
      event,
    }).sort({ createdAt: -1 });

    // optional throttle (prevents duplicates within 1 sec)
    if (
      lastEvent &&
      Date.now() - lastEvent.createdAt < 1000
    ) {
      return;
    }

    await JobEvent.create({
      jobId: data.jobId,
      queueName: data.queueName,
      event,
      message,
      progress,
      metadata,
    });
  }
}

export default JobService;