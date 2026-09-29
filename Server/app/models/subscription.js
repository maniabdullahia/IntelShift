import mongoose from "mongoose";

const subscriptionSchema = new mongoose.Schema({

    // =========================
    // RELATION
    // =========================
    userId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: "User",
        required: true,
        index: true,
    },

    // =========================
    // PADDLE IDS
    // =========================
    customerId: {
        type: String,
        // required: true,
        // index: true,
        default: null,
    },

    subscriptionId: {
        type: String,
        // required: true,
        // index: true,
        default: null,
    },

    priceId: {
        type: String,
        default: null,
    },

    transactionId: {
        type: String,
        default: null,
    },

    planId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: "Plan",
        default: null,
    },

    status: {
        type: String,
        enum: [
            "trialing",
            "active",
            "past_due",
            "canceled",
            "paused"
        ],
        default: "trialing",
        index: true,
    },

    // =========================
    // BILLING PERIOD (Paddle equivalent)








    
    // =========================
    currentPeriodStart: {
        type: Date,
        default: null,
    },

    currentPeriodEnd: {
        type: Date,
        default: null,
        index: true,
    },

    nextBilledAt: {
        type: Date,
        default: null,
    },

    cancelAtPeriodEnd: {
        type: Boolean,
        default: false,
    },

    canceledAt: {
        type: Date,
        default: null,
    },

    // First moment this user was ever billed (set once, never moved on renewal).
    // Drives the 14-day, first-time-subscriber money-back window.
    firstBilledAt: {
        type: Date,
        default: null,
    },

    // Set when a money-back refund has been issued, so it can't be claimed twice.
    refundedAt: {
        type: Date,
        default: null,
    },

    // Express consent (captured at checkout) to begin the service immediately,
    // and when it was given — the legal basis for starting monitoring before the
    // 14-day withdrawal window ends. Kept as an audit record.
    consentToImmediateStart: {
        type: Boolean,
        default: false,
    },

    consentAt: {
        type: Date,
        default: null,
    },

    // =========================
    // SCHEDULED DOWNGRADE
    // =========================
    // A downgrade the user requested that takes effect at the next renewal.
    // Until effectiveAt they keep the current (higher) plan; then we switch and
    // enforce the new limits, keeping only the competitors they chose.
    pendingDowngrade: {
        planId: { type: mongoose.Schema.Types.ObjectId, ref: "Plan", default: null },
        priceId: { type: String, default: null },
        effectiveAt: { type: Date, default: null, index: true },
        keepCompetitorIds: { type: [mongoose.Schema.Types.ObjectId], default: [] },
        // Pages the user chose to keep on each kept competitor. Any kept
        // competitor with no selection here is auto-trimmed (newest kept) at apply.
        keepPageIds: { type: [mongoose.Schema.Types.ObjectId], default: [] },
        requestedAt: { type: Date, default: null },
    },

    // =========================
    // TRIAL (Paddle supports trials via pricing or metadata)
    // =========================
    trialStart: {
        type: Date,
        default: null,
    },

    trialEnd: {
        type: Date,
        default: null,
    },

    // =========================
    // METADATA (Paddle webhook data)
    // =========================
    metadata: {
        type: Object,
        default: {},
    },

}, {
    timestamps: true,
});

const Subscription =
    mongoose.models.Subscription ||
    mongoose.model("Subscription", subscriptionSchema);

export default Subscription;