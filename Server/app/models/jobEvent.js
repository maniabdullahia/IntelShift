import mongoose from "mongoose";

const JobEventSchema = new mongoose.Schema(
  {
    jobId: {
      type: String,
      required: true,
      index: true,
    },

    queueName: {
      type: String,
      required: true,
      index: true,
    },

    event: {
      type: String,
      required: true,
      index: true,
    },

    /*
    |--------------------------------------------------------------------------
    | Human Readable
    |--------------------------------------------------------------------------
    */

    message: {
      type: String,
      default: null,
    },

    /*
    |--------------------------------------------------------------------------
    | Event Data
    |--------------------------------------------------------------------------
    */

    metadata: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },

    /*
    |--------------------------------------------------------------------------
    | Progress Snapshot
    |--------------------------------------------------------------------------
    */

    progress: {
      type: Number,
      default: null,
    },

    /*
    |--------------------------------------------------------------------------
    | Timing
    |--------------------------------------------------------------------------
    */

    timestamp: {
      type: Date,
      default: Date.now,
      index: true,
    },

    /*
    |--------------------------------------------------------------------------
    | Worker Info
    |--------------------------------------------------------------------------
    */

    workerId: String,

    hostname: String,
  },
  {
    timestamps: true,
  }
);

const JobEvent = mongoose.model("JobEvent", JobEventSchema);

export default JobEvent;
