import mongoose from "mongoose";

const aiUsageSchema = new mongoose.Schema({

    userId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: "User",
        required: true,
    },

    totalTokens: {
        type: Number,
        default: 0,
    },

    cost: {
        type: Number,
        default: 0,
    },

    isValidJson: {
        type: Boolean,
        default: true,
    },

    failure: {
        type: Number,
        default: 0,
    },

    failureReason: {
        type: String,
        default: "",
    },

}, { timestamps: true });

const AIUsage = mongoose.model("AIUsage", aiUsageSchema);

export default AIUsage;