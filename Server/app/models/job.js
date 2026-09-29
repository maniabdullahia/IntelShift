import mongoose from "mongoose";

const JobSchema = new mongoose.Schema(
  {
    /*
    |--------------------------------------------------------------------------
    | BullMQ Identity
    |--------------------------------------------------------------------------
    */

    jobId: {
      type: String,
      required: true,
      unique: true,
      index: true,
    },

    queueName: {
      type: String,
      required: true,
      index: true,
    },

    jobName: {
      type: String,
      required: true,
    },

    /*
    |--------------------------------------------------------------------------
    | Status
    |--------------------------------------------------------------------------
    */

    status: {
      type: String,
      enum: [
        "waiting",
        "active",
        "completed",
        "failed",
        "delayed",
        "paused",
        "stalled",
      ],
      default: "waiting",
      index: true,
    },

    progress: {
      type: Number,
      default: 0,
      min: 0,
      max: 100,
    },

    /*
    |--------------------------------------------------------------------------
    | Relationships
    |--------------------------------------------------------------------------
    */

    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      index: true,
    },

    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Workspace",
      index: true,
    },

    competitorId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Competitor",
      index: true,
    },

    pageId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Page",
      index: true,
    },

    /*
    |--------------------------------------------------------------------------
    | Payload
    |--------------------------------------------------------------------------
    */

    data: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },

    result: {
      type: mongoose.Schema.Types.Mixed,
      default: null,
    },

    /*
    |--------------------------------------------------------------------------
    | Errors
    |--------------------------------------------------------------------------
    */

    failedReason: {
      type: String,
      default: null,
    },

    stacktrace: {
      type: [String],
      default: [],
    },

    /*
    |--------------------------------------------------------------------------
    | Attempts
    |--------------------------------------------------------------------------
    */

    attemptsMade: {
      type: Number,
      default: 0,
    },

    maxAttempts: {
      type: Number,
      default: 1,
    },

    retryCount: {
      type: Number,
      default: 0,
    },

    /*
    |--------------------------------------------------------------------------
    | Timing
    |--------------------------------------------------------------------------
    */

    queuedAt: {
      type: Date,
      default: Date.now,
    },

    startedAt: {
      type: Date,
      default: null,
    },

    completedAt: {
      type: Date,
      default: null,
    },

    failedAt: {
      type: Date,
      default: null,
    },

    duration: {
      type: Number,
      default: null,
    },

    /*
    |--------------------------------------------------------------------------
    | Worker Info
    |--------------------------------------------------------------------------
    */

    workerId: {
      type: String,
      default: null,
    },

    hostname: {
      type: String,
      default: null,
    },

    /*
    |--------------------------------------------------------------------------
    | AI Usage
    |--------------------------------------------------------------------------
    */

    ai: {
      provider: String,
      model: String,
      inputTokens: Number,
      outputTokens: Number,
      totalTokens: Number,
      estimatedCost: Number,
    },

    /*
    |--------------------------------------------------------------------------
    | Metadata
    |--------------------------------------------------------------------------
    */

    tags: {
      type: [String],
      default: [],
    },

    priority: {
      type: Number,
      default: 0,
    },

    parentJobId: {
      type: String,
      default: null,
      index: true,
    },

    correlationId: {
      type: String,
      default: null,
      index: true,
    },
  },
  {
    timestamps: true,
  }
);

const Job = mongoose.model("Job", JobSchema);
export default Job;