import User from "../models/user.js";
import Plan from "../models/plan.js";
import Subscription from "../models/subscription.js";

import { createTrialSubscription } from "../services/subscription.service.js";

const createSubscription = async (req, res) => {
    try {
        const { priceId } = req.body;
        const userId = req.user.id;

        if (!priceId) {
            return res.status(400).json({ message: "Price ID is required" });
        }

        const user = await User.findById(userId).select("+refreshToken");

        if (!user) {
            return res.status(404).json({ message: "User not found" });
        }

        // Find the plan by stripePriceId
        const plan = await Plan.findOne({ stripePriceId: priceId });

        if (!plan) {
            return res.status(400).json({ message: "Invalid plan price" });
        }

        // Create subscription in Stripe
        const stripeSubscription = await stripe.subscriptions.create({
            customer: user.stripeCustomerId,
            items: [{ price: priceId }],
            payment_behavior: "default_incomplete",
            expand: ["latest_invoice.payment_intent"],
        });

        // Create subscription record in database
        const subscription = await Subscription.create({
            userId: user._id,
            stripeCustomerId: user.stripeCustomerId,
            stripeSubscriptionId: stripeSubscription.id,
            stripePriceId: priceId,
            plan: plan.name,
            status: stripeSubscription.status,
            currentPeriodStart: stripeSubscription.current_period_start
                ? new Date(stripeSubscription.current_period_start * 1000)
                : null,
            currentPeriodEnd: stripeSubscription.current_period_end
                ? new Date(stripeSubscription.current_period_end * 1000)
                : null,
            trialStart: stripeSubscription.trial_start
                ? new Date(stripeSubscription.trial_start * 1000)
                : null,
            trialEnd: stripeSubscription.trial_end
                ? new Date(stripeSubscription.trial_end * 1000)
                : null,
            metadata: stripeSubscription.metadata || {},
        });

        // Activate user account
        if (user.accountStatus === "pending") {
            user.accountStatus = "active";
            user.plan = plan.name;
            await user.save();
        }

        return res.status(201).json({
            message: "Subscription created successfully",
            subscription: subscription.toObject(),
            stripeSubscription: {
                id: stripeSubscription.id,
                status: stripeSubscription.status,
                clientSecret:
                    stripeSubscription.latest_invoice?.payment_intent
                        ?.client_secret || null,
            },
        });
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};

const createFreeTrialSubscription = async (req, res) => {
    try {
        const { priceId, planId } = req.body;
        const userId = req.user.id;

        const subscription = await createTrialSubscription(userId, priceId, planId);

        return res.status(201).json({
            message: "Trial subscription created successfully",
            subscription: subscription.toObject(),
        });

    } catch (error) {
        console.error("Error creating trial subscription:", error);
        return res.status(500).json({ message: error.message });
    }
};

const getAllSubscriptions = async (req, res) => {
    try {
        const subscriptions = await Subscription.find().populate({
            path: "userId",
            select: "email",
            populate: {
                path: "workspace",
                select: "name description",
            }
        }).populate({
            path: "planId",
            select: "name displayName description price",
        });
        return res.status(200).json({ subscriptions });
    } catch (error) {
        console.error("Error fetching subscriptions:", error);
        return res.status(500).json({ message: error.message });
    }
};

const deleteSubscription = async (req, res) => {
    
}

export { createSubscription, createFreeTrialSubscription, getAllSubscriptions, deleteSubscription };