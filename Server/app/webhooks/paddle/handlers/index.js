
import { handleSubscriptionCreated, handleSubscriptionUpdated, handleSubscriptionCanceled } from "./subscription.handler.js";

const processEvent = async (event) => {

    console.log(
        "Processing Paddle event:",
        event.event_type,
        `[${event.data?.id}]`
    );

    const handlers = {

        "subscription.created": async (event) => {
            console.log("Subscription created:", event.data?.id, event.data?.status);
            await handleSubscriptionCreated(event.data);
        },

        "subscription.updated": async (event) => {
            await handleSubscriptionUpdated(event.data);
        },

        // Status-change events all carry the full subscription payload, so route
        // them through the same sync. The scheduler's entitlement gate then
        // pauses monitoring on past_due/paused and resumes it on active/resumed.
        "subscription.past_due": async (event) => {
            await handleSubscriptionUpdated(event.data);
        },

        "subscription.paused": async (event) => {
            await handleSubscriptionUpdated(event.data);
        },

        "subscription.resumed": async (event) => {
            await handleSubscriptionUpdated(event.data);
        },

        "subscription.activated": async (event) => {
            await handleSubscriptionUpdated(event.data);
        },

        "payment.succeeded": async (event) => {
            console.log("Payment succeeded:", event.data?.id, event.data?.subscription_id || "");
        },

        "subscription.canceled": async (event) => {
            await handleSubscriptionCanceled(event.data);
        },

        default: async (event) => {
            // console.log("No handler registered for:", event.event_type);
        }
    };

    const handler = handlers[event.event_type] || handlers.default;

    await handler(event);
};

export default processEvent;