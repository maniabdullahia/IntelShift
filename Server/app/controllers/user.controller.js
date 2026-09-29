import mongoose from "mongoose";

import User from "../models/user.js";
import Plan from "../models/plan.js";
import Subscription from "../models/subscription.js";

import { hashPassword, comparePassword } from "../../utils/bcrypt.js";
import { deleteWorkspace, recomputeNextScanForOwner } from "../services/workspace.service.js";
import { updateSubscriptionPlan } from "../services/plan.service.js";
import { deleteSubscription } from "../services/subscription.service.js";

const getProfile = async (req, res) => {
    try {
        const id = req.user.id;

        // Self-heal: a past webhook bug could leave a user with duplicate
        // subscription records (a stale trial + the paid one), which made the
        // `subscription` virtual resolve to the wrong plan. Keep the newest.
        const subs = await Subscription.find({ userId: id }).sort({ createdAt: -1 }).select("_id");
        if (subs.length > 1) {
            await Subscription.deleteMany({ userId: id, _id: { $ne: subs[0]._id } });
        }

        const user = await User.findById(id)
            .select("-password -refreshToken -createdAt -updatedAt")
            .populate("workspace")
            .populate({
                path: "subscription",
                select: "-createdAt -updatedAt -__v",
                populate: {
                    path: "planId",
                    select: "name displayName limits isActive planReportingFrequency _id price"
                }
            });

        res.json(user);

    } catch (error) {
        res.status(500).json({
            message: error.message
        });
    }
};

const updateProfile = async (req, res) => {
    try {
        const { name, profilePicture } = req.body;
        const user = await User.findById(req.user.id);

        if (!user) {
            return res.status(404).json({ message: "User not found" });
        }
        // Email is the account identity — intentionally NOT editable here
        // (changes go through support). Any `email` in the body is ignored.
        if (name) {
            user.name = name;
        }

        if (typeof profilePicture === "string") {
            user.profilePicture = profilePicture;
        }

        await user.save();
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

/**
 * Update notification + change-alert preferences (Alert Settings screen).
 * Accepts partial { notifications, alerts } and merges into user.settings.
 */
const updateNotificationSettings = async (req, res) => {
    try {
        const { notifications, alerts } = req.body || {};
        const user = await User.findById(req.user.id);
        if (!user) return res.status(404).json({ message: "User not found" });

        if (!user.settings) user.settings = {};

        if (notifications && typeof notifications === "object") {
            user.settings.notifications = { ...user.settings.notifications, ...notifications };
        }
        if (alerts && typeof alerts === "object") {
            user.settings.alerts = { ...user.settings.alerts, ...alerts };
        }

        user.markModified("settings");
        await user.save();

        res.json({ message: "Settings updated", settings: user.settings });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

const deleteProfile = async (req, res) => {
    try {
        const userId = req.user.id;
        const user = await User.findById(userId);
        if (!user) {
            return res.status(404).json({ message: "User not found" });
        }
        await deleteWorkspace(userId);
        await deleteSubscription(userId);
        await User.findByIdAndDelete(userId);
        res.json({ message: "User deleted successfully" });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

const changePassword = async (req, res) => {
    try {
        const { currentPassword, newPassword } = req.body;
        const user = await User.findById(req.user.id);
        if (!user) {
            return res.status(404).json({ message: "User not found" });
        }
        const isMatch = await comparePassword(currentPassword, user.password);
        if (!isMatch) {
            return res.status(400).json({ message: "Current password is incorrect" });
        }
        user.password = await hashPassword(newPassword);
        await user.save();
        res.json({ message: "Password changed successfully" });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

const getAllUsers = async (req, res) => {
    // Only allow admins to access this endpoint and show paginated results
    try {
        const { page = 1, limit = 10 } = req.query;
        const users = await User.find().select("-password -refreshToken").limit(limit * 1).skip((page - 1) * limit).populate("workspace", "name").exec();
        res.json(users);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

const searchUsers = async (req, res) => {
    try {
        const { query } = req.query;
        const users = await User.find({ email: { $regex: query, $options: "i" } }).select("-password -refreshToken");
        res.json(users);
    }
    catch (error) {
        res.status(500).json({ message: error.message });
    }
};

const changePlan = async (req, res) => {
    try {
        const { planId, subscriptionId, priceId } = req.body;
        console.log("Received changePlan request with:", { planId, subscriptionId, priceId });
        if(!planId || !subscriptionId || !priceId) {
            return res.status(400).json({ message: "planId, subscriptionId, and priceId are required" });
        }
        const user = await User.findById(req.user.id);

        if (!user) {
            return res.status(404).json({ message: "User not found" });
        }

        const planQuery = mongoose.isValidObjectId(planId)
            ? { $or: [{ _id: planId }, { name: planId }] }
            : { name: planId };

        const plan = await Plan.findOne(planQuery);

        if (!plan) {
            return res.status(400).json({ message: "Invalid planId" });
        }

        const newSubscription = await updateSubscriptionPlan(subscriptionId, priceId);

        console.log("Received response from updateSubscriptionPlan:", JSON.stringify(newSubscription, null, 2));
        const status = newSubscription?.data?.status;
        const newPriceId = newSubscription?.data?.items[0]?.price?.id;

        console.log("Updated subscription details:", { status, newPriceId });

        const selectedPlan = await Plan.findOne({ priceId: newPriceId });

        if (!selectedPlan) {
            return res.status(400).json({ message: "No plan found for the given priceId" });
        }

        const subscription = await Subscription.findOneAndUpdate(
            { subscriptionId },
            {
                planId: selectedPlan?._id,
                status,
                priceId: newPriceId,
            },
            { new: true }
        );



        user.plan = selectedPlan?.name;


        // Activate account when plan is set
        if (user.accountStatus === "pending") {
            user.accountStatus = "active";
        }

        await user.save();

        // Re-align monitoring cadence to the new plan (upgrades start monitoring,
        // a downgrade to a one-time plan clears the next-scan marker).
        try {
            await recomputeNextScanForOwner(user._id, selectedPlan?.planReportingFrequency);
        } catch (cadenceErr) {
            console.error("Failed to recompute next scan on plan change:", cadenceErr.message);
        }

        const updatedUser = await User.findById(req.user.id)
            .select("-password -refreshToken -createdAt -updatedAt")
            .populate("workspace")
            .populate({
                "path": "subscription",
                "select": "-createdAt -updatedAt -__v",
                "populate": {
                    "path": "planId",
                    "select": "name displayName limits isActive planReportingFrequency _id price"
                }
            });

        res.status(200).json({
            message: "Plan changed successfully",
            user: updatedUser,
            // user: {
            //     _id: user._id,
            //     name: user.name,
            //     email: user.email,
            //     plan: user.plan,
            //     accountStatus: user.accountStatus,
            // },
            // plan: {
            //     id: selectedPlan._id,
            //     name: selectedPlan.name,
            //     displayName: selectedPlan.displayName,
            //     limits: selectedPlan.limits,
            //     features: selectedPlan.features,
            //     isActive: selectedPlan.isActive,
            // },
        });
    } catch (error) {
        console.error("Error in changePlan:", error);
        res.status(500).json({ message: error.message });
    }
};

const deleteMultipleUsers = async (req, res) => {
    try {
        const { userIds } = req.body;
        await User.deleteMany({ _id: { $in: userIds } });
        res.json({ message: "Users deleted successfully" });


    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};

// ADMIN CONTROLLER FUNCTIONS

const getUserById = async (req, res) => {
    try {
        const { userId } = req.params;
        const user = await User.findById(userId).select("-password -refreshToken").populate("workspace").populate("plan");
        if (!user) {
            return res.status(404).json({ message: "User not found" });
        }
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};


export {
    getProfile,
    updateProfile,
    updateNotificationSettings,
    deleteProfile,
    changePassword,
    getAllUsers,
    searchUsers,
    changePlan,
    deleteMultipleUsers,
    getUserById,
};
