import mongoose from "mongoose";

const analysisSchema = new mongoose.Schema({

    workspaceId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: "Workspace",
        index: true,
    },

    competitors: {
        ownerId: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "Competitor",
            required: true,
        },
        competitorId: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "Competitor",
            required: true,
        },
    },

    data: {
        comparison: {
            type: mongoose.Schema.Types.Mixed,
            default: {},
        },
        payload: {
            type: mongoose.Schema.Types.Mixed,
            default: {},
        },
        result: {
            type: mongoose.Schema.Types.Mixed,
            default: null,
        },
    }
}, { timestamps: true });

const Analysis = mongoose.model("Analysis", analysisSchema);

export default Analysis;
