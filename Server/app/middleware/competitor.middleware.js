import Competitor from "../models/competitor.js";

export const competitorMiddleware = async (req, res, next) => {
    try {
        const { competitorId } = req.body;
        if (!competitorId) {
            return res.status(400).json({ message: "Competitor ID is required" });
        }
        const competitor = await Competitor.findById(competitorId);
        if (!competitor) {
            return res.status(404).json({ message: "Competitor not found" });
        }
        req.competitor = competitor;
        next();
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
};