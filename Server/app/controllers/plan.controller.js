import mongoose from "mongoose";

import Plan from "../models/plan.js";

const createPlan = async (req, res) => {
    try {
        const {
            name,
            displayName,
            stripePriceId,
            limits = {},
            features = {},
            isActive = true,
        } = req.body;

        if (!name || !stripePriceId) {
            return res.status(400).json({ message: "Name and stripePriceId are required" });
        }

        const existingPlan = await Plan.findOne({ name });
        if (existingPlan) {
            return res.status(400).json({ message: "Plan already exists" });
        }

        const plan = await Plan.create({
            name,
            displayName,
            stripePriceId,
            limits: {
                competitors: limits.competitors ?? 1,
                pagesPerCompetitor: limits.pagesPerCompetitor ?? 20,
                reportFrequency: limits.reportFrequency ?? "weekly",
            },
            features,
            isActive,
        });

        return res.status(201).json(plan);
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};

const getPlans = async (req, res) => {
    try {
        const plans = await Plan.find();

        // order plans by price ascending
        plans.sort((a, b) => a.price - b.price);
        return res.json(plans);
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};

const getPlan = async (req, res) => {
    try {
        const { planId } = req.body;

        if (!planId) {
            return res.status(400).json({ message: "Plan ID is required" });
        }

        const planQuery = mongoose.isValidObjectId(planId)
            ? { $or: [{ _id: planId }, { name: planId }] }
            : { name: planId };

        const plan = await Plan.findOne(planQuery);

        if (!plan) {
            return res.status(404).json({ message: "Plan not found" });
        }

        return res.json(plan);
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};

const updatePlan = async (req, res) => {
    try {
        const { planId, ...updates } = req.body;

        if (!planId) {
            return res.status(400).json({ message: "Plan ID is required" });
        }

        if (updates.name) {
            const existingPlan = await Plan.findOne({ name: updates.name, _id: { $ne: planId } });
            if (existingPlan) {
                return res.status(400).json({ message: "Plan name already exists" });
            }
        }

        const planQuery = mongoose.isValidObjectId(planId)
            ? { $or: [{ _id: planId }, { name: planId }] }
            : { name: planId };

        const plan = await Plan.findOneAndUpdate(planQuery, { $set: updates }, { new: true });

        if (!plan) {
            return res.status(404).json({ message: "Plan not found" });
        }

        return res.json(plan);
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};

const deletePlan = async (req, res) => {
    try {
        const { planId } = req.body;

        if (!planId) {
            return res.status(400).json({ message: "Plan ID is required" });
        }

        const planQuery = mongoose.isValidObjectId(planId)
            ? { $or: [{ _id: planId }, { name: planId }] }
            : { name: planId };

        const plan = await Plan.findOneAndDelete(planQuery);

        if (!plan) {
            return res.status(404).json({ message: "Plan not found" });
        }

        return res.json({ message: "Plan deleted successfully" });
    } catch (error) {
        return res.status(500).json({ message: error.message });
    }
};


export {
    createPlan,
    getPlans,
    getPlan,
    updatePlan,
    deletePlan,
};