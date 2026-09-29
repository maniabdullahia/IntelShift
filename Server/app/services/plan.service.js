import mongoose from "mongoose";
import paddleApi from "../../api/paddle.api.js";
import plan from "../models/plan.js";

const updateSubscriptionPlan = async (subscriptionId, priceId, mode = "prorated_immediately") => {
    try {
        const current = await getActiveSubscription(subscriptionId);

        if (!current) {
            throw new Error("Active subscription not found");
            return;
        }


        const response = await paddleApi.patch(`/subscriptions/${subscriptionId}`, {
            proration_billing_mode: mode,
            items: [
                {
                    price_id: priceId,
                    quantity: 1
                }
            ]
        });

        return response.data;
    } catch (error) {
        console.error(
            "Paddle Error:",
            JSON.stringify(error.response?.data || error.message, null, 2)
        );
        throw error;
    }
};

const getActiveSubscription = async (subscriptionId) => {
    try {
        const response = await paddleApi.get(`/subscriptions/${subscriptionId}`);
        // console.log("Active subscription details:", JSON.stringify(response.data, null, 2));
        return response.data;
    } catch (error) {
        console.error("Error fetching active subscription:", error);
        throw error;
    }
};

const getPlanDetails = async (planId) => {
    try {
        // `planId` may be a Mongo ObjectId OR a plan name (e.g. the ?plan=starter
        // query param used on the signup link). Resolve by whichever it is, so a
        // name never triggers a CastError on findById.
        const query = mongoose.isValidObjectId(planId)
            ? { $or: [{ _id: planId }, { name: planId }] }
            : { name: planId };

        const planDetails = await plan.findOne(query);
        if (!planDetails) {
            throw new Error("Plan not found");
        }

        return planDetails;
    } catch (error) {
        console.error("Error fetching plan details:", error);
        throw error;
    }
}

const getPlanPriceId = async (planId) => {
    try {
        const planDetails = await getPlanDetails(planId);
        if (!planDetails || !planDetails.priceId) {
            throw new Error("Price ID not found for the given plan");
        }

        return planDetails.priceId;
    }
    catch (error) {
        console.error("Error fetching plan price ID:", error);
        throw error;
    }
};

const getPlanById = async (planId) => {
    try {
        const planDetails = await plan.findById(planId);
        if (!planDetails) {
            throw new Error("Plan not found");
        }

        return planDetails;
    } catch (error) {
        console.error("Error fetching plan by ID:", error);
        throw error;
    }
};

export { updateSubscriptionPlan, getActiveSubscription, getPlanDetails, getPlanPriceId, getPlanById };
