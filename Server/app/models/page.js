import mongoose from "mongoose";

const pageSchema = new mongoose.Schema(
  {
    url: {
      type: String,
      required: true,
      trim: true,
    },

    // Correspondence key used to keep an owner page aligned with the matching
    // competitor page (e.g. "Pricing", "Homepage"). Drives remap guidance.
    label: {
      type: String,
      trim: true,
      default: "",
    },

    // Page mapping (competitor pages only): the owner page URL this competitor
    // page is paired with, so comparisons run like-for-like. Set at onboarding
    // (auto-match + user confirm) and editable later.
    mappedOwnerUrl: {
      type: String,
      trim: true,
      default: "",
    },
    mapStatus: {
      type: String,
      enum: ["none", "matched", "no_equivalent"],
      default: "none",
      index: true,
    },

    // Staged edits take effect on the NEXT monitoring run, never instantly:
    //   "add"    → newly tracked, not yet analyzed
    //   "remove" → marked for removal, still shown as pending until next run
    pendingChange: {
      type: String,
      enum: ["none", "add", "remove"],
      default: "none",
      index: true,
    },

    // Soft-removal marker (set when pendingChange = "remove").
    retiredAt: {
      type: Date,
      default: null,
    },

    competitorId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Competitor",
      required: true,
      index: true,
    },

    // 🔥 Add this (important for Socket rooms & queries)
    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Workspace",
      required: true,
      index: true,
    },

    analysisData: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },

    scanStatus: {
      type: String,
      enum: ["Pending", "Analyzing", "Completed", "Failed"],
      default: "Pending",
      index: true,
    },

    // Offline marker: set when a crawl gets a definitive 404 (page gone/renamed).
    // Offline pages — and their mapped counterpart — are skipped in comparisons,
    // and the user is notified to replace them.
    offline: {
      type: Boolean,
      default: false,
      index: true,
    },
    offlineSince: {
      type: Date,
      default: null,
    },
    httpStatus: {
      type: Number,
      default: null,
    },
  },
  {
    timestamps: true,
    toJSON: { virtuals: true },
    toObject: { virtuals: true },
  }
);


// ----------------------------------------
// 🔗 Virtual: Competitor relation
// ----------------------------------------
pageSchema.virtual("competitor", {
  ref: "Competitor",
  localField: "competitorId",
  foreignField: "_id",
  justOne: true,
});


// ----------------------------------------
// 🧠 Computed field (clean response)
// ----------------------------------------
pageSchema.virtual("analysis").get(function () {
  return {
    data: this.analysisData,
    status: this.scanStatus,
    lastUpdated: this.updatedAt,
  };
});


// ----------------------------------------
// ⚡ Instance Methods (VERY useful)
// ----------------------------------------

pageSchema.methods.markAnalyzing = function () {
  this.scanStatus = "Analyzing";
  return this.save();
};

pageSchema.methods.markCompleted = function (analysisData) {
  this.scanStatus = "Completed";
  this.analysisData = analysisData;
  return this.save();
};

pageSchema.methods.markFailed = function () {
  this.scanStatus = "Failed";
  return this.save();
};


// ----------------------------------------
// 🚀 Static Methods (for services)
// ----------------------------------------

pageSchema.statics.updateStatus = function (pageId, updates) {
  return this.findByIdAndUpdate(
    pageId,
    { $set: updates },
    { new: true }
  );
};


// ----------------------------------------
// 🔍 Indexes (performance boost)
// ----------------------------------------

pageSchema.index({ competitorId: 1, url: 1 }, { unique: true });
pageSchema.index({ workspaceId: 1, scanStatus: 1 });


// ----------------------------------------
// ⚠️ Optional Hook (be careful with this)
// ----------------------------------------
// You can use this to auto-set analyzing state

// Sync-style middleware (no `next` callback): Mongoose auto-continues when the
// function takes no args and returns undefined. Avoids the "next is not a
// function" failure some driver/runtime combos hit on Page.create()/save().
pageSchema.pre("save", function () {
  if (this.isNew && !this.scanStatus) {
    this.scanStatus = "Pending";
  }
});


// ----------------------------------------
// 🧹 Clean output (optional but nice)
// ----------------------------------------

pageSchema.methods.toJSON = function () {
  const obj = this.toObject();
  delete obj.__v;
  return obj;
};


const Page = mongoose.model("Page", pageSchema);
export default Page;