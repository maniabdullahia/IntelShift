import User from "../models/user.js";
import Plan from "../models/plan.js";
import Subscription from "../models/subscription.js";
import paddle from "./paddle.service.js";


/**
 *
 * Creates a new subscription record in the database based on Paddle subscription details.
 * @param {string} userId User ID associated with the subscription
 * @param {string} priceId Paddle Price ID for the subscription
 * @param {string} SubscriptionId Paddle Subscription ID
 * @param {string} customerId Paddle Customer ID
 * @param {string|null} trxId Paddle Transaction ID (optional, can be null for trial subscriptions)
 * @param {string} plan Plan name (e.g., "trial", "starter", "growth", "pro")
 * @param {string} status Subscription status (e.g., "trialing", "active", "past_due", "canceled", "paused")
 * @param {Date|string} currentPeriodStart Start date of the current billing period (Date object or ISO string)
 * @param {Date|string|null} nextBilledAt Next billing date (Date object or ISO string, optional for trial subscriptions)
 * @returns Created subscription document
 */
const createSubscription = async (userId, priceId, SubscriptionId, customerId, trxId, planId, status, currentPeriodStart, nextBilledAt) => {
    const user = await User.findById(userId);
    if (!user) {
        throw new Error("User not found");
    }

    const planExist = await Plan.find({ priceId });
    if (!planExist) {
        throw new Error("Plan not found");
    }

    const subscription = new Subscription({
        userId: userId,
        subscriptionId: SubscriptionId,
        customerId: customerId,
        priceId: priceId,
        transactionId: trxId,
        planId: planId,
        status: status,
        currentPeriodStart: new Date(currentPeriodStart),
        nextBilledAt: nextBilledAt ? new Date(nextBilledAt) : null,
    });

    await subscription.save();

    return subscription;
}

/**
 * Retrieves the most recent subscription for a given user ID.
 * @param {string} userId User ID to search for
 * @returns Subscription document or null if not found
 */
const getSubscriptionByUserId = async (userId) => {
    const subscription = await Subscription.findOne({ userId }).sort({ createdAt: -1 });
    return subscription;
}


const upgradePlan = async (userId, newPlanId) => {
    const subscription = await getSubscriptionByUserId(userId);

    if (!subscription) {
        throw new Error("Subscription not found for user");
    }

    const newPlan = await Plan.findOne({ planId: newPlanId });
    if (!newPlan) {
        throw new Error("New plan not found");
    }

    // Call Paddle API to change the subscription plan
    try {

    } catch (error) {
        throw new Error("Failed to upgrade subscription plan");
    }
}

const createTrialSubscription = async (userId, priceId, planId) => {
    const user = await User.findById(userId);
    if (!user) {
        throw new Error("User not found");
    }

    const planExist = await Plan.find({ priceId });
    if (!planExist) {
        throw new Error("Plan not found");
    }

    // 14-day free trial. trialEnd bounds both the dashboard countdown and the
    // monitoring window (the scheduler stops re-monitoring once a scan would fall
    // past trialEnd — with the weekly cadence that yields two re-monitors, at ~day 7
    // and ~day 14, inside the period).
    const TRIAL_DAYS = Number(process.env.TRIAL_DAYS) || 14;
    const now = new Date();
    const trialEnd = new Date(now.getTime() + TRIAL_DAYS * 24 * 60 * 60 * 1000);

    const subscription = new Subscription({
        userId: userId,
        priceId: priceId,
        planId: planId,
        status: "trialing",
        currentPeriodStart: now,
        currentPeriodEnd: trialEnd,
        trialStart: now,
        trialEnd: trialEnd,
        nextBilledAt: null,
    });
    await subscription.save();

    return subscription;
}

const deleteSubscription = async (userId) => {  
    try {

        if(!userId) {
            throw new Error("User ID is required to delete subscription");
        }

        const subscription = await Subscription.findOneAndDelete({ userId });
        if (!subscription) {
            throw new Error("Subscription not found for user");
        }

        // Call Paddle API to cancel the subscription

    } catch (error) {
        throw new Error("Failed to delete subscription");
    }
}



export {
    createSubscription,
    getSubscriptionByUserId,
    createTrialSubscription,
    upgradePlan,
    deleteSubscription
}
