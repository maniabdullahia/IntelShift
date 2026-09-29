import Competitor from "../models/competitor.js";
import Workspace from "../models/workspace.js";
import ChangeReport from "../models/changeReport.js";
import MetricSnapshot from "../models/metricSnapshot.js";

import { getSubscriptionByUserId } from "../services/subscription.service.js";
import { getPlanById } from "../services/plan.service.js";

/*
|--------------------------------------------------------------------------
| COMPETITOR HISTORY (Historical tracking — Growth / Pro)
|--------------------------------------------------------------------------
| Reuses the ChangeReport records that accumulate every monitoring cycle.
|   - trial / starter -> locked (no historical access)
|   - growth          -> "basic": recent timeline
|   - pro             -> "advanced": full timeline + trend + export flag
*/

const TIER_BY_PLAN = { growth: "basic", pro: "advanced" };
const GROWTH_MAX_REPORTS = 30; // ~ retention cap for the growth tier

const getCompetitorHistory = async (req, res) => {
    try {
        const { competitorId } = req.params;

        const competitor = await Competitor.findById(competitorId).select("_id domain workspaceId role");
        if (!competitor) return res.status(404).json({ message: "Competitor not found" });

        const workspace = await Workspace.findById(competitor.workspaceId).select("ownerId");
        if (!workspace) return res.status(404).json({ message: "Workspace not found" });

        // Ownership check
        if (String(workspace.ownerId) !== String(req.user.id)) {
            return res.status(403).json({ message: "Forbidden" });
        }

        const subscription = await getSubscriptionByUserId(workspace.ownerId);
        const plan = await getPlanById(subscription?.planId);
        const tier = TIER_BY_PLAN[plan?.name] || "none";

        if (tier === "none") {
            return res.status(200).json({
                tier: "none",
                locked: true,
                requiredPlan: "growth",
                domain: competitor.domain,
                timeline: [],
                trend: [],
            });
        }

        const advanced = tier === "advanced";

        // Trend: every cycle's change activity (lightweight), oldest -> newest.
        const query = ChangeReport.find({ competitorId }).sort({ monitoredAt: -1 });
        if (!advanced) query.limit(GROWTH_MAX_REPORTS);
        const reports = await query;

        const trend = [...reports]
            .reverse()
            .map((r) => ({
                date: r.monitoredAt,
                changeScore: r.changeScore ?? 0,
                totalChanges: r.totalChanges ?? 0,
                severity: r.overallSeverity,
            }));

        // Timeline: cycles that actually had changes (the "story").
        const timeline = reports
            .filter((r) => (r.totalChanges ?? 0) > 0)
            .map((r) => ({
                id: r._id,
                monitoredAt: r.monitoredAt,
                periodStart: r.periodStart,
                periodEnd: r.periodEnd,
                changeScore: r.changeScore ?? 0,
                overallSeverity: r.overallSeverity,
                totalChanges: r.totalChanges ?? 0,
                changes: (r.report?.changes || []).map((c) => ({
                    type: c.type,
                    severity: c.severity,
                    whyImportant: c.whyImportant,
                    oldValue: c.oldValue,
                    newValue: c.newValue,
                    changePercent: c.changePercent,
                    product: c.product?.name || c.plan?.name || null,
                })),
            }));

        // Metric trends (price / catalog / availability over time) — ADVANCED (Pro) only.
        // This is the key differentiator over Growth's change timeline.
        let metrics = [];
        if (advanced) {
            const points = await MetricSnapshot.find({ competitorId }).sort({ capturedAt: 1 }).limit(200);
            metrics = points.map((p) => ({
                date: p.capturedAt,
                avgPrice: p.avgPrice,
                minPrice: p.minPrice,
                maxPrice: p.maxPrice,
                currency: p.currency,
                totalProducts: p.totalProducts,
                productsWithPrice: p.productsWithPrice,
                inStockCount: p.inStockCount,
                onSaleCount: p.onSaleCount,
                collectionsCount: p.collectionsCount,
            }));
        }

        return res.status(200).json({
            tier,
            advanced,
            domain: competitor.domain,
            totalCycles: reports.length,
            timeline,
            trend,
            metrics,
        });
    } catch (error) {
        console.error("Error fetching competitor history:", error);
        return res.status(500).json({ message: "Internal server error" });
    }
};

export { getCompetitorHistory };
