import mongoose from "mongoose";

const workspaceSchema = new mongoose.Schema(
  {
    ownerId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      required: true,
      // index: true,
    },

    name: {
      type: String,
      required: true,
      trim: true,
    },

    url: {
      type: String,
      required: true,
      trim: true,
    },

    industry: {
      type: String,
      required: true,
      trim: true,
    },

    // ----------------------------------------
    // 🎯 Focus categories (onboarding)
    // ----------------------------------------
    // The categories the user said they care most about, captured in onboarding.
    // ORDERED — index 0 is highest priority. Empty [] means "no focus" (all).
    // Used as a lens (ranking/targeting), never a filter: competitor search,
    // competitor fit scoring, page pairing, Pro auto-select, small-plan page budget.
    focusCategories: {
      type: [String],
      default: [],
    },
    // "selected" when the user picked 1–5; "all" when they chose All / skipped /
    // we couldn't detect any categories → the system behaves as it does today.
    focusMode: {
      type: String,
      enum: ["all", "selected"],
      default: "all",
    },



    // ----------------------------------------
    // 🧠 Workspace-level status (VERY IMPORTANT)
    // ----------------------------------------
    scanStatus: {
      type: String,
      enum: ["Idle", "Processing", "Completed", "Partial", "Failed"],
      default: "Idle",
      index: true,
    },

    lastRebuiltAt: {
      type: Date,
      default: null,
    },

    introCompleted: {
      type: Boolean,
      default: false,
    },

    // Capture-first setup lifecycle. A recon-created workspace walks:
    //   recon      → capturing homepage/nav/collection index for every site
    //   selecting  → recon done; user picks pages + confirms mappings (in-workspace panel)
    //   analyzing  → pages chosen; deep per-page crawl + comparison running
    //   ready      → first reports available
    // Defaults to "ready" so legacy workspaces (created via the old page-first
    // flow, or pre-dating this field) are unaffected; only createWorkspaceRecon
    // starts a workspace at "recon".
    setupStage: {
      type: String,
      enum: ["recon", "selecting", "analyzing", "ready"],
      default: "ready",
      index: true,
    },

    nextScanAt: {
      type: Date,
      default: null,
    },

    // Capture-first: the user's in-progress page selections/mappings while the
    // workspace is in "selecting". Auto-saved from the picker so a logout/refresh
    // never loses work; cleared once the selection is committed.
    selectionDraft: {
      type: mongoose.Schema.Types.Mixed,
      default: null,
    },
    selectionDraftAt: {
      type: Date,
      default: null,
    },

    // Competitor suggestions generated ONCE in the background after recon completes,
    // so the "Replace competitor" picker can show them instantly without re-running
    // the (slow) search each time. Refreshed only when regenerated.
    suggestedCompetitors: {
      type: [
        {
          name: String,
          url: String,
          domain: String,
          reason: String,
          matchedCategories: [String],
          // Similarity re-rank output: 0–1 score + a short human reason
          // ("similar price range · overlaps 3 of your categories").
          similarityScore: Number,
          whyMatch: String,
        },
      ],
      default: [],
    },
    suggestedCompetitorsAt: {
      type: Date,
      default: null,
    },

    // Set when the user edits tracked pages between monitoring runs. Staged
    // changes are applied at the start of the next run, then this clears.
    pendingPageChanges: {
      type: Boolean,
      default: false,
    },
    pendingPageChangesAt: {
      type: Date,
      default: null,
    },

    // ----------------------------------------
    // 📊 Optional: quick stats (for dashboard)
    // ----------------------------------------
    stats: {
      competitorsCount: {
        type: Number,
        default: 0,
      },
      pagesCount: {
        type: Number,
        default: 0,
      },
      completedScans: {
        type: Number,
        default: 0,
      },
      failedScans: {
        type: Number,
        default: 0,
      },
    },
  },
  {
    timestamps: true,
    toJSON: { virtuals: true },
    toObject: { virtuals: true },
  }
);


// ----------------------------------------
// 🔗 Relations
// ----------------------------------------
workspaceSchema.virtual("competitors", {
  ref: "Competitor",
  localField: "_id",
  foreignField: "workspaceId",
});

workspaceSchema.virtual("analysis", {
  ref: "Analysis",
  localField: "_id",
  foreignField: "workspaceId",
});


// ----------------------------------------
// 🧠 Instance Methods (state control)
// ----------------------------------------

workspaceSchema.methods.markProcessing = function () {
  this.scanStatus = "Processing";
  return this.save();
};

workspaceSchema.methods.markCompleted = function () {
  this.scanStatus = "Completed";
  this.lastRebuiltAt = new Date();
  return this.save();
};

workspaceSchema.methods.markIdle = function () {
  this.scanStatus = "Idle";
  return this.save();
};

workspaceSchema.methods.markFailed = function () {
  this.scanStatus = "Failed";
  return this.save();
};

workspaceSchema.methods.markIntroCompleted = function () {
  this.introCompleted = true;
  return this.save();
}


// ----------------------------------------
// ⚡ Static method (for services/workers)
// ----------------------------------------

workspaceSchema.statics.updateStatus = function (id, updates) {
  return this.findByIdAndUpdate(
    id,
    { $set: updates },
    { new: true }
  );
};


// ----------------------------------------
// 🔍 Indexes
// ----------------------------------------
workspaceSchema.index({ ownerId: 1 });
workspaceSchema.index({ ownerId: 1, scanStatus: 1 });


// ----------------------------------------
// 🧹 Clean response
// ----------------------------------------

workspaceSchema.methods.toJSON = function () {
  const obj = this.toObject();
  delete obj.__v;
  return obj;
};


const Workspace = mongoose.model("Workspace", workspaceSchema);
export default Workspace;