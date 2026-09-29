import mongoose from "mongoose";

const planSchema = new mongoose.Schema({

    name: {
        type: String,
        enum: ["trial", "starter", "growth", "pro", "enterprise"],
        required: true,
        unique: true,
    },

    displayName: String,
    description: String,
    price: {
        type: Number,
        required: true,
    },

    priceId: {
        type: String,
        required: true,
    },

    // Enterprise is "contact us" — no public price / self-serve checkout.
    contactSales: {
        type: Boolean,
        default: false,
    },

    planReportingFrequency: {
        type: String,
        enum: ["daily", "2D", "3D", "5D", "weekly", "monthly", "once"],
        default: "weekly",
    },

    limits: {
        competitors: {
            type: Number,
            default: 1,
        },
        pagesPerCompetitor: {
            type: Number,
            default: 20,
        },
        reportFrequency: {
            type: String,
            enum: ["daily", "2D", "3D", "5D", "weekly", "monthly", "once"],
            default: "weekly",
        },
        // Auto-pairing scope for competitor onboarding:
        //   collections           → auto-pair collections only (user adds other pages by URL)
        //   collections_products  → collections + suggested product-level pairing
        //   complete_site         → fully automatic, no user page selection (Pro)
        //   full                  → everything, custom (Enterprise)
        pairingScope: {
            type: String,
            enum: ["collections", "collections_products", "complete_site", "full"],
            default: "collections",
        },
        // Let users add non-collection pages by URL (About, specific landing pages).
        allowUrlPages: {
            type: Boolean,
            default: true,
        },
        // Pro/Enterprise: auto-crawl a capped, representative slice of the whole site
        // with no manual page selection.
        completeSite: {
            type: Boolean,
            default: false,
        },
        // Hard cap on auto-selected pages per competitor in complete-site mode.
        maxPageCap: {
            type: Number,
            default: 0,
        },
        // Historical price/catalog trend timeline.
        historicalTimeline: {
            type: Boolean,
            default: false,
        },
    },

    features: [String],

    isActive: {
        type: Boolean,
        default: true,
    },

}, { timestamps: true });

export default mongoose.model("Plan", planSchema);