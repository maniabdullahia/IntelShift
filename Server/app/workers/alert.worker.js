import { Worker } from "bullmq";
import mongoose from "mongoose";
import connection from "../config/redis.js";

import dotenv from "dotenv";
dotenv.config();

import Workspace from "../models/workspace.js";
import Competitor from "../models/competitor.js";
import ChangeReport from "../models/changeReport.js";
import User from "../models/user.js";
import Notification from "../models/notification.js";

import { getSubscriptionByUserId } from "../services/subscription.service.js";
import { getPlanById } from "../services/plan.service.js";
import { sendChangeAlertMail } from "../services/email.service.js";
import { publishSocketEvent } from "../../utils/eventBus.publisher.js";

mongoose.set("bufferCommands", false);

/*
|--------------------------------------------------------------------------
| ALERT WORKER
|--------------------------------------------------------------------------
| Sends a "change alert" when a monitoring cycle detects high-impact competitor
| changes. Gated by plan (monitoring plans only) and the user's notification
| preferences. One digest per workspace per cycle; reports are marked `alerted`
| so the same changes never fire twice.
*/

const PRICING_TYPES = ["price", "plan_price", "sale", "pricing_plan", "discount"];
const HOMEPAGE_TYPES = ["hero", "headline", "description", "navigation", "name_change", "feature", "messaging"];

// Does a change report match the user's Alert Settings preferences?
function reportMatchesPrefs(r, prefs) {
    const sev = String(r.overallSeverity || "").toLowerCase();
    if (prefs.highImpact && (sev === "high" || sev === "critical")) return true;
    const changes = (r.report && r.report.changes) || [];
    const hasAny = (needles) =>
        changes.some((c) => needles.some((n) => String(c.type || "").toLowerCase().includes(n)));
    if (prefs.pricing && hasAny(PRICING_TYPES)) return true;
    if (prefs.homepage && hasAny(HOMEPAGE_TYPES)) return true;
    return false;
}

async function processAlert(job) {
    const { workspaceId } = job.data || {};
    if (!workspaceId) return;

    const workspace = await Workspace.findById(workspaceId).lean();
    if (!workspace) return;

    const user = await User.findById(workspace.ownerId).lean();
    if (!user) return;

    // ---- Plan gating: only monitoring plans get alerts (trial/once do not) ----
    const subscription = await getSubscriptionByUserId(workspace.ownerId);
    const plan = await getPlanById(subscription?.planId);
    const monitoringPlan = plan?.planReportingFrequency && plan.planReportingFrequency !== "once";
    if (!monitoringPlan) return;

    // ---- User preference gating ----
    const notif = user?.settings?.notifications || {};
    if (notif.alerts === false) return;

    // Default prefs if the user hasn't saved any yet (high-impact on).
    const prefs = { pricing: true, highImpact: true, homepage: false, ...(user?.settings?.alerts || {}) };
    if (!prefs.pricing && !prefs.highImpact && !prefs.homepage) return; // everything off

    // ---- Gather un-alerted reports, then filter by the user's alert prefs ----
    const competitors = await Competitor.find({ workspaceId, role: "Competitor" }).select("_id domain").lean();
    if (!competitors.length) return;
    const compById = new Map(competitors.map((c) => [String(c._id), c]));

    const candidateReports = await ChangeReport.find({
        competitorId: { $in: competitors.map((c) => c._id) },
        alerted: { $ne: true },
        totalChanges: { $gt: 0 },
    }).sort({ monitoredAt: -1 });

    const reports = candidateReports.filter((r) => reportMatchesPrefs(r, prefs));
    if (!reports.length) return;

    // One digest item per competitor (latest report wins).
    const seen = new Set();
    const items = [];
    for (const r of reports) {
        const key = String(r.competitorId);
        if (seen.has(key)) continue;
        seen.add(key);
        const comp = compById.get(key);
        items.push({
            domain: comp?.domain || r.report?.domain || "competitor",
            totalChanges: r.totalChanges,
            severity: r.overallSeverity,
            changeScore: r.changeScore,
            topChanges: (r.report?.changes || []).slice(0, 3).map((c) => c.whyImportant || c.type),
        });
    }

    // ---- Email channel ----
    if (notif.email !== false && user.email) {
        const dashboardUrl = `${process.env.CLIENT_URL || ""}/dashboard`;
        await sendChangeAlertMail(user.email, user.name, workspace.name, items, dashboardUrl);
    }

    // ---- In-app notification: persist (bell reads via HTTP) + live push ----
    const title = `${items.length} competitor${items.length === 1 ? "" : "s"} changed`;
    const body = items.map((i) => `${i.domain}: ${i.totalChanges} changes`).join("; ");
    try {
        await Notification.create({ userId: user._id, type: "change_alert", title, body, link: "/dashboard" });
    } catch (err) {
        console.error("Alert notification persist failed:", err.message);
    }

    try {
        await publishSocketEvent("notification.new", {
            userId: String(user._id),
            workspaceId: String(workspace._id),
            type: "change_alert",
            title,
            body,
        });
    } catch (err) {
        console.error("Alert socket publish failed:", err.message);
    }

    // ---- Mark reports as alerted so they don't fire again ----
    await ChangeReport.updateMany(
        { _id: { $in: reports.map((r) => r._id) } },
        { $set: { alerted: true } }
    );

    console.log(`📣 Change alert sent for workspace ${workspaceId} (${items.length} competitor(s))`);
}

async function startWorker() {
    try {
        await mongoose.connect(process.env.MONGO_URI);
        console.log("✅ Alert Worker MongoDB connected");

        const alertWorker = new Worker("alert", processAlert, {
            connection: connection.duplicate(),
            concurrency: 5,
        });

        alertWorker.on("failed", (job, err) => {
            console.error("🔥 Alert job failed:", job?.id, err?.message);
        });

        console.log("✅ Alert Worker started");
    } catch (error) {
        console.error("❌ Error starting Alert Worker:", error);
        process.exit(1);
    }
}

startWorker();
