import SocketGateway from "../../../socket/gateway.js";
import User from "../../../models/user.js";
import Workspace from "../../../models/workspace.js";
import Subscription from "../../../models/subscription.js";
import Plan from "../../../models/plan.js";
import { recomputeNextScanForOwner } from "../../../services/workspace.service.js";

const handleSubscriptionCreated = async (data) => {

    try {
        const userId = data.custom_data.userId;
        const priceId = data?.items[0].price.id;
        const subscriptionId = data.id;
        const customerId = data.customer_id;
        const trxId = data.transaction_id;
        let planId = data?.custom_data.planId;
        const status = data.status;
        const currentPeriodStart = data?.created_at;
        const nextBilledAt = data.next_billed_at ? new Date(data.next_billed_at) : null;

        // Resolve the plan from the price if custom_data.planId is missing/invalid,
        // so the stored plan always matches what Paddle actually billed.
        const planByPrice = await Plan.findOne({ priceId }).select("_id name planReportingFrequency");
        if (planByPrice) planId = planByPrice._id;

        console.log("Handling subscription.created event:", { userId, priceId, subscriptionId, planId, status });

        // UPSERT by userId — a trial user already has ONE subscription record.
        // Creating a second one leaves the `user.subscription` (justOne) virtual
        // resolving to the stale trial record, so we UPDATE the existing one
        // instead. This is what converts trial → paid.
        const kept = await Subscription.findOneAndUpdate(
            { userId },
            {
                $set: {
                    userId,
                    subscriptionId,
                    customerId,
                    priceId,
                    transactionId: trxId,
                    planId,
                    status,
                    currentPeriodStart: currentPeriodStart ? new Date(currentPeriodStart) : new Date(),
                    nextBilledAt,
                    currentPeriodEnd: nextBilledAt,
                },
            },
            { upsert: true, new: true, setDefaultsOnInsert: true }
        );

        // Stamp the first-ever billing moment once — this anchors the 14-day
        // money-back window and must never move on later renewals/plan changes.
        // Also record the checkout consent-to-immediate-start (audit trail).
        const consentGiven = String(data?.custom_data?.consentToImmediateStart) === "true";
        const consentAt = data?.custom_data?.consentAt ? new Date(data.custom_data.consentAt) : null;
        let needsSave = false;
        if (trxId && !kept.firstBilledAt) {
            kept.firstBilledAt = new Date();
            needsSave = true;
        }
        if (consentGiven && !kept.consentToImmediateStart) {
            kept.consentToImmediateStart = true;
            kept.consentAt = consentAt || new Date();
            needsSave = true;
        }
        if (needsSave) {
            await kept.save().catch((e) => console.error("subscription stamp save failed:", e.message));
        }

        // Self-heal any pre-existing duplicate subscriptions for this user (e.g.
        // a leftover trial record), so the `justOne` virtual resolves correctly.
        await Subscription.deleteMany({ userId, _id: { $ne: kept._id } });

        const user = await User.findById(userId);
        if (user) {
            // Paddle statuses (active/trialing) → our account enum.
            user.accountStatus = "active";
            if (planByPrice?.name) user.plan = planByPrice.name;
            await user.save().catch((e) => console.error("User activate save failed:", e.message));
        }

        console.log('User activated =>', user?._id);

        // Arm (or re-arm) monitoring on the plan's cadence. This starts monitoring
        // on the trial->paid conversion, and restarts it if a previously canceled
        // user re-subscribes (their nextScanAt was cleared when they lapsed).
        try {
            await recomputeNextScanForOwner(userId, planByPrice?.planReportingFrequency);
        } catch (e) {
            console.error("Failed to arm monitoring on subscription.created:", e.message);
        }

        const workspace = await Workspace.findOne({ ownerId: userId });

        console.log("Emitting user.subscription.created event to user:", workspace?.id);
        console.log("User data:", user);
        SocketGateway.user(userId, "subscription.created", {
            userId,
            subscriptionId,
            status,
            workspaceId: workspace?.id || null,
        });


    } catch (error) {
        console.error("Error handling subscription.created event:", error);
        throw error; // Rethrow to let the caller handle it (e.g., retry logic)
    }
};

/**
 * Sync any subscription state change from Paddle (status flips like
 * active -> past_due -> active, pause/resume, plan switches done in Paddle's UI,
 * and scheduled cancellations) into our record. We deliberately do NOT touch the
 * workspace's nextScanAt here for past_due/paused — the scheduler's entitlement
 * gate skips those ticks and auto-resumes when the status returns to active, so
 * the schedule is never lost. Terminal cancellation is handled separately.
 */
const handleSubscriptionUpdated = async (data) => {
    try {
        const subscriptionId = data.id;
        const status = data.status;
        const priceId = data?.items?.[0]?.price?.id ?? null;
        const nextBilledAt = data.next_billed_at ? new Date(data.next_billed_at) : null;
        // scheduled_change = { action: 'cancel'|'pause'|'resume', effective_at }
        const cancelAtPeriodEnd = data?.scheduled_change?.action === "cancel";

        const update = { status, cancelAtPeriodEnd };
        if (nextBilledAt) {
            update.nextBilledAt = nextBilledAt;
            update.currentPeriodEnd = nextBilledAt;
        }

        // Keep plan in sync if Paddle reports a different price (e.g. a plan
        // switch performed directly in Paddle rather than through our app).
        let planByPrice = null;
        if (priceId) {
            planByPrice = await Plan.findOne({ priceId }).select("_id name");
            if (planByPrice) {
                update.planId = planByPrice._id;
                update.priceId = priceId;
            }
        }

        const sub = await Subscription.findOneAndUpdate(
            { subscriptionId },
            { $set: update },
            { new: true }
        );

        // Mirror the plan label onto the user only while paid-current.
        if (sub && planByPrice?.name && (status === "active" || status === "trialing")) {
            await User.findByIdAndUpdate(sub.userId, { plan: planByPrice.name }).catch(() => {});
        }

        console.log("subscription.updated synced:", { subscriptionId, status, plan: planByPrice?.name });
    } catch (error) {
        console.error("Error handling subscription.updated event:", error);
        throw error;
    }
};

/**
 * Terminal cancellation — the subscription is fully over (either an immediate
 * cancel or the end of a scheduled one). Mark it canceled and stop monitoring
 * for good; the entitlement gate would also catch this, but clearing nextScanAt
 * here means the workspace is dropped from the due-scan query right away.
 */
const handleSubscriptionCanceled = async (data) => {
    try {
        const subscriptionId = data.id;
        const sub = await Subscription.findOneAndUpdate(
            { subscriptionId },
            { $set: { status: "canceled", canceledAt: new Date(), cancelAtPeriodEnd: false } },
            { new: true }
        );

        if (sub) {
            await Workspace.findOneAndUpdate({ ownerId: sub.userId }, { nextScanAt: null });
            SocketGateway.user(String(sub.userId), "subscription.canceled", {
                subscriptionId,
                status: "canceled",
            });
        }

        console.log("subscription.canceled processed — monitoring stopped:", subscriptionId);
    } catch (error) {
        console.error("Error handling subscription.canceled event:", error);
        throw error;
    }
};

export {
    handleSubscriptionCreated,
    handleSubscriptionUpdated,
    handleSubscriptionCanceled,
}