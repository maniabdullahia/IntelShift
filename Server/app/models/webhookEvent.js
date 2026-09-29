
import mongoose from "mongoose";

const webhookEventSchema = new mongoose.Schema({
    eventId: {
        type: String,
        unique: true,
        required: true,
    },
    eventType: {
        type: String,
        required: true,
    },
    entityId: {
        type: String,
    },
    processedAt: {
        type: Date,
        default: Date.now,
    },
}, { timestamps: true });

const WebhookEvent = mongoose.model("WebhookEvent", webhookEventSchema);

export default WebhookEvent;