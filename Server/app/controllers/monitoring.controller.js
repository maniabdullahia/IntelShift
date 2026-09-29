
import { getPlanById } from "../services/plan.service.js";
import { getSubscriptionByUserId } from "../services/subscription.service.js";
import { findCompetitorsByWorkspaceId } from "../services/competitor.service.js";
import { getAnalysisByCompetitorId } from "../services/analysis.service.js";
import { computeEntitlement } from "../services/entitlement.service.js";

import Workspace from "../models/workspace.js";
import ChangeReport from "../models/changeReport.js";

/*
|--------------------------------------------------------------------------
| Reporting-frequency -> approximate runs-per-week, for the client's
| cadence labelling. `once` means monitoring is disabled.
|--------------------------------------------------------------------------
*/
const CADENCE_PER_WEEK = {
    daily: 7,
    "2D": 3.5,
    "3D": 2.33,
    weekly: 1,
    monthly: 0.25,
    once: 0,
};

const monitorChangeDetails = async (req, res) => {
    try {
        const { workspaceId } = req.params;

        // Workspace validation
        const workspace = await Workspace.findById(workspaceId);

        if (!workspace) {
            return res.status(404).json({ message: "Invalid Workspace" });
        }

        // Active subscription -> plan
        const subscription = await getSubscriptionByUserId(workspace?.ownerId);
        const plan = await getPlanById(subscription?.planId);

        const frequency = plan?.planReportingFrequency ?? "once";
        const cadencePerWeek = CADENCE_PER_WEEK[frequency] ?? 0;

        // Entitlement: a trial that has ended (or a canceled/absent sub) is
        // read-only — monitoring is paused regardless of what the plan's cadence
        // says. Without this, an ended trial keeps a monitoring plan's frequency
        // and its stale workspace.nextScanAt, so the UI wrongly shows "monitoring
        // set up — next check in N days" after the trial is over.
        const entitlement = computeEntitlement(subscription);
        const monitoringPaused = entitlement.readOnly;
        const monitoringEnabled = frequency !== "once" && !monitoringPaused;

        // Competitors (exclude the owner's own site)
        const allCompetitors = await findCompetitorsByWorkspaceId(workspaceId);
        const competitors = allCompetitors.filter((c) => c.role === "Competitor");

        let overallFinding = null;

        // Build the analysis-derived competitor strip + collect latest change reports.
        const competitorStrip = [];
        const reports = [];
        const aiByDomain = {};

        await Promise.all(
            competitors.map(async (competitor) => {
                const analysis = await getAnalysisByCompetitorId(competitor._id);

                // Latest change report for this competitor (most recent monitoring run).
                const latestReport = await ChangeReport.findOne({
                    competitorId: competitor._id,
                }).sort({ monitoredAt: -1 });

                // Count unread reports that actually contain changes — a
                // "nothing changed" report shouldn't inflate the unread badge.
                const unreadChanges = await ChangeReport.countDocuments({
                    competitorId: competitor._id,
                    read: false,
                    totalChanges: { $gt: 0 },
                });

                // Competitor strip card (only meaningful once an analysis exists).
                if (analysis) {
                    const finding =
                        analysis?.data?.result?.executiveSummary?.overallFinding ?? null;
                    if (finding && !overallFinding) overallFinding = finding;

                    competitorStrip.push({
                        domain: competitor.domain,
                        scoreVsYou:
                            analysis?.data?.result?.competitorProfiles?.[0]?.competitiveScore ??
                            null,
                        threatLevel:
                            analysis?.data?.result?.competitorProfiles?.[0]?.overallThreatLevel ??
                            null,
                        lastAnalyzedAt: competitor?.lastRebuiltAt ?? null,
                        analysisUrl: `/analysis/${analysis._id}`,
                        unreadChanges,
                    });
                }

                // change_detection_v1 report (already carries `domain`), for the
                // Dashboard "changes" section and the ChangeDetails view.
                if (latestReport?.report) {
                    const rep = latestReport.report;
                    reports.push(rep);

                    if (latestReport.aiInterpretation) {
                        const key = rep.domain || competitor.domain;
                        if (key) aiByDomain[key] = latestReport.aiInterpretation;
                    }
                }
            })
        );

        // Monitoring period from the most recent report, falling back to workspace timing.
        const latestAcross = await ChangeReport.findOne({ workspaceId }).sort({
            monitoredAt: -1,
        });

        return res.status(200).json({
            monitoringEnabled,
            // Trial ended (or canceled/absent sub): monitoring is paused. The UI
            // shows a "monitoring paused — upgrade to resume" state instead of a
            // scheduled next-check.
            monitoringPaused,
            trialExpired: entitlement.trialExpired,
            package: plan?.name ?? null,
            cadencePerWeek,
            // Reflect the last real change-detection run — NOT the initial analysis
            // scan. Null until the first ChangeReport exists, so the UI correctly
            // shows "monitoring set up, no report yet" rather than "no changes".
            lastMonitoredAt: latestAcross?.monitoredAt ?? null,
            // Suppress the stale next-scan time once monitoring is paused, so the
            // UI never advertises a check that won't happen.
            nextMonitoredAt: monitoringPaused ? null : (workspace?.nextScanAt ?? null),
            // Period comes from an actual report window (past dates); never the
            // future next-scan time, which read as a confusing "checked until <future>".
            periodStart: latestAcross?.periodStart ?? null,
            periodEnd: latestAcross?.periodEnd ?? null,
            overallFinding,
            competitors: competitorStrip,
            reports,
            aiByDomain,
        });
    } catch (error) {
        console.error("Error fetching change details:", error);
        return res.status(500).json({ message: "Internal server error" });
    }
};

export { monitorChangeDetails };
