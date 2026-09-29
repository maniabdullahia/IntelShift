import mongoose from "mongoose";

import Plan from "../models/plan.js";
import { scheduleDowngrade, cancelDowngrade } from "../services/downgrade.service.js";

// POST /downgrade/schedule  { planId, keepCompetitorIds } — defer to renewal
const scheduleDowngradeController = async (req, res) => {
  try {
    const { planId, keepCompetitorIds = [], keepPageIds = [] } = req.body;
    if (!planId) return res.status(400).json({ message: "planId is required" });

    const query = mongoose.isValidObjectId(planId)
      ? { $or: [{ _id: planId }, { name: planId }] }
      : { name: planId };
    const newPlan = await Plan.findOne(query);
    if (!newPlan) return res.status(400).json({ message: "Invalid planId" });

    const result = await scheduleDowngrade({
      userId: req.user.id,
      newPlan,
      keepCompetitorIds,
      keepPageIds,
    });

    return res.json({
      scheduled: true,
      effectiveAt: result.effectiveAt,
      keepCompetitorIds: result.keepCompetitorIds,
      message: "Downgrade scheduled for the end of your current billing period.",
    });
  } catch (error) {
    console.error("Schedule downgrade failed:", error);
    return res.status(400).json({ message: error.message });
  }
};

// POST /downgrade/cancel — cancel a scheduled downgrade
const cancelDowngradeController = async (req, res) => {
  try {
    await cancelDowngrade(req.user.id);
    return res.json({ cancelled: true, message: "Scheduled downgrade cancelled." });
  } catch (error) {
    console.error("Cancel downgrade failed:", error);
    return res.status(400).json({ message: error.message });
  }
};

export { scheduleDowngradeController, cancelDowngradeController };
