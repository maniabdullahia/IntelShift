import mongoose from "mongoose";

const changeReportSchema = new mongoose.Schema(
  {
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Workspace",
      required: true,
      index: true,
    },

    competitorId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Competitor",
      required: true,
      index: true,
    },

    // Monitoring period
    periodStart: {
      type: Date,
      required: true,
    },

    periodEnd: {
      type: Date,
      required: true,
    },

    // When this report was generated
    monitoredAt: {
      type: Date,
      default: Date.now,
      index: true,
    },

    // Output returned from Python (/diff-snapshots)
    report: {
      type: mongoose.Schema.Types.Mixed,
      required: true,
    },

    // Optional AI interpretation
    aiInterpretation: {
      strategicIntent: String,
      whyThisMatters: [String],
      recommendedActions: [String],
    },

    // Denormalized fields for quick filtering/sorting
    changeScore: {
      type: Number,
      default: 0,
      index: true,
    },

    overallSeverity: {
      type: String,
      enum: ["low", "medium", "high", "critical"],
      default: "low",
      index: true,
    },

    totalChanges: {
      type: Number,
      default: 0,
    },

    read: {
      type: Boolean,
      default: false,
      index: true,
    },

    // Whether a change alert (email / notification) has already been sent for
    // this report — prevents re-alerting the same changes on later ticks.
    alerted: {
      type: Boolean,
      default: false,
      index: true,
    },
  },
  {
    timestamps: true,
  }
);

// One report per competitor per monitoring period
changeReportSchema.index(
  { competitorId: 1, periodStart: 1, periodEnd: 1 },
  { unique: true }
);

export default mongoose.model("ChangeReport", changeReportSchema);