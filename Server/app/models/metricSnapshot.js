import mongoose from "mongoose";

/*
|--------------------------------------------------------------------------
| METRIC SNAPSHOT
|--------------------------------------------------------------------------
| A lightweight, per-cycle capture of a competitor's headline catalog metrics
| (read straight from the snapshot's site.catalog). Powers the advanced (Pro)
| historical trends — price / catalog size / availability over time.
*/

const metricSnapshotSchema = new mongoose.Schema(
  {
    competitorId: { type: mongoose.Schema.Types.ObjectId, ref: "Competitor", required: true, index: true },
    workspaceId: { type: mongoose.Schema.Types.ObjectId, ref: "Workspace", index: true },
    capturedAt: { type: Date, default: Date.now, index: true },

    totalProducts: { type: Number, default: null },
    productsWithPrice: { type: Number, default: null },
    avgPrice: { type: Number, default: null },
    minPrice: { type: Number, default: null },
    maxPrice: { type: Number, default: null },
    currency: { type: String, default: null },
    inStockCount: { type: Number, default: null },
    onSaleCount: { type: Number, default: null },
    collectionsCount: { type: Number, default: null },
    categoriesCount: { type: Number, default: null },
  },
  { timestamps: true }
);

export default mongoose.model("MetricSnapshot", metricSnapshotSchema);
