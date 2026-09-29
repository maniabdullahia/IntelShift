import cron from "node-cron";

import Workspace from "../models/workspace.js";
import Competitor from "../models/competitor.js";

import { getNextScanAt } from "../../utils/scan.js";
import { rescanWorkspace } from "../services/workspace.service.js";
import { getSubscriptionByUserId } from "../services/subscription.service.js";
import { getPlanById } from "../services/plan.service.js";
import { processScheduledDeletions } from "../services/account.service.js";
import { applyDueDowngrades } from "../services/downgrade.service.js";

/*
|--------------------------------------------------------------------------
| MONITORING SCHEDULER
|--------------------------------------------------------------------------
| Runs in the main server process. Every few minutes it finds workspaces whose
| next scan is due and kicks off a monitoring rescan on the plan's cadence:
|
|   re-fetch pages -> rebuild snapshots -> Python diff (change report)
|     -> if a competitor changed significantly, its analysis is re-run
|     -> otherwise nothing else happens; we just wait for the next cadence.
|
| Free / one-time plans have nextScanAt = null, so they are never picked up.
*/

const CRON_EXPRESSION = process.env.MONITORING_CRON || "*/15 * * * *"; // every 15 min
const DELETION_CRON = process.env.DELETION_CRON || "0 3 * * *"; // daily at 03:00

let running = false;
let deletionRunning = false;

async function runDueScans() {
    if (running) return; // don't overlap ticks
    running = true;
    try {
        const now = new Date();
        const due = await Workspace.find({
            nextScanAt: { $ne: null, $lte: now },
        }).select("_id ownerId nextScanAt");

        if (!due.length) return;
        console.log(`⏰ Monitoring: ${due.length} workspace(s) due`);

        for (const ws of due) {
            try {
                const subscription = await getSubscriptionByUserId(ws.ownerId);
                const plan = await getPlanById(subscription?.planId);
                const cadence = plan?.planReportingFrequency ?? "once";

                // Billing-entitlement gate: only monitor while the subscription is
                // paid-current. This is the backstop — it holds even if a Paddle
                // webhook is ever missed, so a canceled or unpaid account can never
                // keep getting scanned.
                //   • canceled  -> stop for good (clear the marker).
                //   • past_due / paused -> transient (Paddle is dunning, or the user
                //     paused). Skip this tick but LEAVE nextScanAt due, so monitoring
                //     auto-resumes the instant they're active again, no schedule lost.
                const subStatus = subscription?.status;
                const entitled = subStatus === "active" || subStatus === "trialing";
                if (!entitled) {
                    if (subStatus === "canceled" || !subscription) {
                        await Workspace.findByIdAndUpdate(ws._id, { nextScanAt: null });
                        console.log(`⏸ Monitoring: workspace ${ws._id} subscription ${subStatus || "missing"} — stopped`);
                    } else {
                        console.log(`⏸ Monitoring: workspace ${ws._id} subscription ${subStatus} — skipping until active`);
                    }
                    continue;
                }

                // One-time / free plans never re-monitor — clear the marker and move on.
                if (cadence === "once") {
                    await Workspace.findByIdAndUpdate(ws._id, { nextScanAt: null });
                    continue;
                }

                // Skip if a scan is already in flight for this workspace; retry next tick.
                const busy = await Competitor.countDocuments({
                    workspaceId: ws._id,
                    scanStatus: "Processing",
                });
                if (busy > 0) {
                    console.log(`⏳ Monitoring: workspace ${ws._id} still scanning, skipping`);
                    continue;
                }

                // Trigger the rescan first, then advance the next-check date only on
                // success. A transient failure (e.g. Redis blip) leaves nextScanAt due
                // so it retries next tick instead of losing a whole cadence. The
                // "busy" guard above prevents re-triggering a scan that's in flight.
                await rescanWorkspace(ws._id.toString());

                let next = getNextScanAt(cadence, now);
                // Trial: stop re-monitoring once the NEXT scan would fall past the
                // trial window. With weekly cadence this leaves two re-monitors
                // (~day 7 and ~day 14) inside the 14-day trial, then stops.
                if (subStatus === "trialing" && subscription?.trialEnd && next && next > new Date(subscription.trialEnd)) {
                    next = null;
                    console.log(`🏁 Trial monitoring complete for workspace ${ws._id} (trial ends ${new Date(subscription.trialEnd).toISOString()})`);
                }
                await Workspace.findByIdAndUpdate(ws._id, { nextScanAt: next });
                console.log(
                    `⏰ Monitoring scan started for workspace ${ws._id}; next at ${next ? next.toISOString() : "n/a"}`
                );
            } catch (err) {
                console.error(`❌ Monitoring scan failed for workspace ${ws._id}:`, err.message);
            }
        }
    } catch (err) {
        console.error("❌ Monitoring scheduler tick failed:", err.message);
    } finally {
        running = false;
    }
}

// Daily housekeeping for staged account closures: reminder emails, deactivation
// at period end, and hard deletion once the grace window has passed.
async function runDeletionSweep() {
    if (deletionRunning) return;
    deletionRunning = true;
    try {
        await processScheduledDeletions();
    } catch (err) {
        console.error("❌ Account deletion sweep failed:", err.message);
    } finally {
        deletionRunning = false;
    }

    // Apply any plan downgrades whose renewal date has arrived.
    try {
        await applyDueDowngrades();
    } catch (err) {
        console.error("❌ Downgrade sweep failed:", err.message);
    }
}

export function startWorkspaceScheduler() {
    if (!cron.validate(CRON_EXPRESSION)) {
        console.error(`❌ Invalid MONITORING_CRON "${CRON_EXPRESSION}" — scheduler not started`);
        return;
    }
    cron.schedule(CRON_EXPRESSION, runDueScans);
    console.log(`✅ Monitoring scheduler started (${CRON_EXPRESSION})`);

    if (cron.validate(DELETION_CRON)) {
        cron.schedule(DELETION_CRON, runDeletionSweep);
        console.log(`✅ Account-closure scheduler started (${DELETION_CRON})`);
    } else {
        console.error(`❌ Invalid DELETION_CRON "${DELETION_CRON}" — closure sweep not started`);
    }
}

export default startWorkspaceScheduler;
