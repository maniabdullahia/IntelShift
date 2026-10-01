import mongoose from "mongoose";

const competitorSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: true,
      trim: true,
    },

    role: {
      type: String,
      enum: ["Owner", "Competitor"],
      default: "Competitor",
    },

    workspaceId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Workspace",
      required: true,
      index: true,
    },

    websiteUrl: {
      type: String,
      required: true,
      trim: true,
    },

    domain: {
      type: String,
      required: true,
      index: true,
    },

    // ── Region / store pinning ────────────────────────────────────────────
    // Some sites run multiple regional storefronts (e.g. au.gymshark.com vs
    // us.gymshark.com) or multiple currencies. The user explicitly chooses one
    // when adding the competitor; every crawl is pinned to that choice so we
    // never geolocate automatically. `availableStores` caches what the store
    // detector found, so the picker can be re-shown without re-probing.
    region: {              // ISO country code the user picked, e.g. "PK"
      type: String,
      trim: true,
      default: "",
    },
    storeUrl: {            // the exact regional URL to crawl (may differ from domain)
      type: String,
      trim: true,
      default: "",
    },
    currency: {            // ISO 4217 currency for the chosen store, e.g. "PKR"
      type: String,
      trim: true,
      default: "",
    },
    availableStores: {     // [{ country, countryName, url, currency, hreflang }]
      type: mongoose.Schema.Types.Mixed,
      default: [],
    },

    analysisData: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },

    // ── Store profile (onboarding Steps 1–4) ──────────────────────────────
    // Written from the readiness check (validate-site + taxonomy + business
    // type). Shape: { accessStatus, accessIssues, journey, businessType,
    // businessTypeLabel, businessTypeConfidence, market, language, taxonomy,
    // profiledAt } — see services/storeProfile.service.js.
    storeProfile: {
      type: mongoose.Schema.Types.Mixed,
      default: undefined,
    },
    // Step 1 outcome, top-level so it can be queried/filtered:
    //   complete   — homepage, collection, product, cart & checkout readable
    //   incomplete — analysable, but part of the journey (search/cart/checkout)
    //                is blocked; reports must say so instead of assuming
    //   unverified — the readiness check itself failed (timeout); added anyway
    accessStatus: {
      type: String,
      enum: ["complete", "incomplete", "unverified", null],
      default: null,
    },

    // ── Recon (capture-first) ─────────────────────────────────────────────
    // Breadth-only reconnaissance captured BEFORE the user selects pages:
    // homepage (header-to-footer, nav, banner promos), the full collection
    // index (names, counts, kind, inNav) and the classified page tree. This is
    // deliberately separate from `analysisData` (the deep, per-page merged
    // snapshot) — recon powers page selection + mapping suggestions and the
    // "what they sell / what they're doing" summary; it does NOT product-crawl.
    recon: {
      type: mongoose.Schema.Types.Mixed,
      default: {},
    },
    reconStatus: {
      type: String,
      enum: ["Pending", "Processing", "Completed", "Failed"],
      default: "Pending",
      index: true,
    },
    reconCapturedAt: {
      type: Date,
      default: null,
    },

    scanStatus: {
      type: String,
      enum: ["Pending", "Processing", "Completed", "Failed"],
      default: "Pending",
      index: true,
    },

    // Staged add/remove — mirrors Page staging. Changes take effect at the next
    // monitoring run: "add" competitors are analyzed then; "remove" ones are
    // deleted then. Reversible until then.
    pendingChange: {
      type: String,
      enum: ["none", "add", "remove"],
      default: "none",
      index: true,
    },
    retiredAt: {
      type: Date,
      default: null,
    },

    lastRebuiltAt: {
      type: Date,
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
// 🔗 Virtual: Pages
// ----------------------------------------
competitorSchema.virtual("pages", {
  ref: "Page",
  localField: "_id",
  foreignField: "competitorId",
});


// ----------------------------------------
// 🧠 Instance Methods (state transitions)
// ----------------------------------------

competitorSchema.methods.markPending = function () {
  this.scanStatus = "Pending";
  return this.save();
};

competitorSchema.methods.markProcessing = function () {
  this.scanStatus = "Processing";
  return this.save();
};

competitorSchema.methods.markCompleted = function (analysisData = {}) {
  this.scanStatus = "Completed";
  this.analysisData = analysisData;
  this.lastRebuiltAt = new Date();
  return this.save();
};

competitorSchema.methods.markFailed = function () {
  this.scanStatus = "Failed";
  return this.save();
};


// ----------------------------------------
// ⚡ Static Methods (for services/workers)
// ----------------------------------------

competitorSchema.statics.updateStatus = function (id, updates) {
  return this.findByIdAndUpdate(
    id,
    { $set: updates },
    { new: true }
  );
};


// ----------------------------------------
// 🔍 Indexes (important for scaling)
// ----------------------------------------

// Prevent duplicate competitors per workspace/domain
competitorSchema.index(
  { workspaceId: 1, domain: 1 },
  { unique: true }
);

competitorSchema.index({ workspaceId: 1, scanStatus: 1 });


// ----------------------------------------
// 🧹 Clean API response
// ----------------------------------------

competitorSchema.methods.toJSON = function () {
  const obj = this.toObject();
  delete obj.__v;
  return obj;
};


const Competitor = mongoose.model("Competitor", competitorSchema);
export default Competitor;