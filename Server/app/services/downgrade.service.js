import Subscription from "../models/subscription.js";
import Competitor from "../models/competitor.js";
import Page from "../models/page.js";
import ChangeReport from "../models/changeReport.js";
import MetricSnapshot from "../models/metricSnapshot.js";
import Analysis from "../models/analysis.js";
import Workspace from "../models/workspace.js";
import User from "../models/user.js";

import Notification from "../models/notification.js";

import { getSubscriptionByUserId } from "./subscription.service.js";
import { getPlanById, updateSubscriptionPlan } from "./plan.service.js";
import { recomputeNextScanForOwner } from "./workspace.service.js";
import { isHomepagePath } from "../../utils/pageMatch.js";

/*
|--------------------------------------------------------------------------
| PLAN DOWNGRADES (scheduled, apply at renewal)
|--------------------------------------------------------------------------
| Upgrades are immediate + prorated (handled in changePlan). Downgrades are
| deferred: the user keeps the current (higher) plan until the period ends,
| picks which competitors to keep within the new limits, and at renewal we
| switch the plan and enforce those limits.
*/

/** Schedule a downgrade to take effect at the next renewal. */
export const scheduleDowngrade = async ({ userId, newPlan, keepCompetitorIds = [], keepPageIds = [] }) => {
  const subscription = await getSubscriptionByUserId(userId);
  if (!subscription) throw new Error("No active subscription found");

  const workspace = await Workspace.findOne({ ownerId: userId });
  const rivals = workspace
    ? await Competitor.find({ workspaceId: workspace._id, role: "Competitor" }).select("_id")
    : [];
  const rivalIds = rivals.map((c) => String(c._id));

  const competitorLimit = newPlan?.limits?.competitors ?? 0;
  const pagesLimit = newPlan?.limits?.pagesPerCompetitor ?? null;

  // Validate the keep-selection: must be real competitors and within the new limit.
  const keep = [...new Set((keepCompetitorIds || []).map(String))].filter((id) => rivalIds.includes(id));
  if (rivalIds.length > competitorLimit && keep.length > competitorLimit) {
    throw new Error(`You can keep at most ${competitorLimit} competitor(s) on the ${newPlan.displayName || newPlan.name} plan.`);
  }
  // If they're already within the limit, keep everything.
  const finalKeep = rivalIds.length <= competitorLimit ? rivalIds : keep;

  const effectiveAt = subscription.nextBilledAt || subscription.currentPeriodEnd || null;

  // Validate page keep-selection against the pages that actually exist.
  const finalKeepPages = [...new Set((keepPageIds || []).map(String))];

  subscription.pendingDowngrade = {
    planId: newPlan._id,
    priceId: newPlan.priceId,
    effectiveAt,
    keepCompetitorIds: finalKeep,
    keepPageIds: finalKeepPages,
    requestedAt: new Date(),
  };
  subscription.markModified("pendingDowngrade");
  await subscription.save();

  // Inform the user which kept competitors will be over the new page limit
  // WITHOUT a selection — those are auto-trimmed (newest kept) at the switch.
  if (pagesLimit && finalKeep.length) {
    const keptOverLimit = [];
    for (const compId of finalKeep) {
      const nonHome = await Page.find({ competitorId: compId, pendingChange: { $ne: "remove" } }).select("url");
      const overLimit = nonHome.filter((p) => !isHomepagePath(p.url)).length > pagesLimit;
      const hasSelection = finalKeepPages.length > 0; // page-level selection provided at all
      if (overLimit && !hasSelection) keptOverLimit.push(compId);
    }
    if (keptOverLimit.length) {
      await Notification.create({
        userId,
        type: "downgrade_pages",
        title: "Choose which pages to keep before your downgrade",
        body: `Some competitors have more than ${pagesLimit} pages, the ${newPlan.displayName || newPlan.name} limit. Trim them before ${effectiveAt ? new Date(effectiveAt).toLocaleDateString() : "renewal"}, or we'll automatically keep the ${pagesLimit} most recent per competitor.`,
        link: "/settings/billing",
      }).catch(() => {});
    }
  }

  return { effectiveAt, keepCompetitorIds: finalKeep };
};

/** Cancel a scheduled downgrade before it takes effect. */
export const cancelDowngrade = async (userId) => {
  const subscription = await getSubscriptionByUserId(userId);
  if (!subscription) throw new Error("No active subscription found");
  subscription.pendingDowngrade = {
    planId: null, priceId: null, effectiveAt: null, keepCompetitorIds: [], keepPageIds: [], requestedAt: null,
  };
  subscription.markModified("pendingDowngrade");
  await subscription.save();
  return { cancelled: true };
};

/** Daily sweep: apply downgrades whose effective date has arrived. */
export const applyDueDowngrades = async () => {
  const now = new Date();
  const due = await Subscription.find({
    "pendingDowngrade.planId": { $ne: null },
    "pendingDowngrade.effectiveAt": { $lte: now },
  });

  for (const subscription of due) {
    try {
      await applyDowngrade(subscription);
    } catch (err) {
      console.error("Downgrade apply failed for", String(subscription._id), err.message);
    }
  }
  return { applied: due.length };
};

async function applyDowngrade(subscription) {
  const pd = subscription.pendingDowngrade || {};
  const newPlan = await getPlanById(pd.planId).catch(() => null);
  if (!newPlan) throw new Error("Target plan not found");

  const userId = subscription.userId;
  const workspace = await Workspace.findOne({ ownerId: userId });

  // 1) Switch billing at Paddle (best-effort — never block the local switch).
  if (subscription.subscriptionId && pd.priceId) {
    await updateSubscriptionPlan(subscription.subscriptionId, pd.priceId, "prorated_immediately")
      .catch((e) => console.error("Paddle downgrade switch failed (continuing):", e.message));
  }

  // 2) Enforce the new limits on the workspace's competitors/pages.
  if (workspace) {
    const keep = new Set((pd.keepCompetitorIds || []).map(String));
    const rivals = await Competitor.find({ workspaceId: workspace._id, role: "Competitor" }).select("_id");
    const toRemove = rivals.filter((c) => !keep.has(String(c._id))).map((c) => c._id);

    if (toRemove.length) {
      await Page.deleteMany({ competitorId: { $in: toRemove } });
      await ChangeReport.deleteMany({ competitorId: { $in: toRemove } });
      await MetricSnapshot.deleteMany({ competitorId: { $in: toRemove } });
      // Analysis.competitors is a single { ownerId, competitorId } object — delete
      // the comparison docs, don't $pull (which fails on a non-array field).
      await Analysis.deleteMany({
        workspaceId: workspace._id,
        "competitors.competitorId": { $in: toRemove },
      });
      await Competitor.deleteMany({ _id: { $in: toRemove } });
    }

    // Trim each remaining competitor's pages to the new per-competitor limit.
    // Homepage is always kept. Pages the user explicitly chose to keep come
    // first; if that's still under the limit we fill with the oldest remaining;
    // anything over the limit is removed. No selection → keep newest N.
    const pagesLimit = newPlan?.limits?.pagesPerCompetitor ?? null;
    const keepPageSet = new Set((pd.keepPageIds || []).map(String));
    if (pagesLimit) {
      const remaining = await Competitor.find({ workspaceId: workspace._id }).select("_id role");
      for (const comp of remaining) {
        const pages = await Page.find({ competitorId: comp._id }).sort({ createdAt: -1 }); // newest first
        const nonHome = pages.filter((p) => !isHomepagePath(p.url));
        if (nonHome.length <= pagesLimit) continue;

        const chosen = nonHome.filter((p) => keepPageSet.has(String(p._id)));
        const rest = nonHome.filter((p) => !keepPageSet.has(String(p._id)));
        const keptIds = new Set([...chosen, ...rest].slice(0, pagesLimit).map((p) => String(p._id)));
        const toDelete = nonHome.filter((p) => !keptIds.has(String(p._id)));
        if (toDelete.length) {
          await Page.deleteMany({ _id: { $in: toDelete.map((p) => p._id) } });
        }
      }
    }
  }

  // 3) Switch the local plan + user, re-align cadence, clear the schedule.
  subscription.planId = newPlan._id;
  subscription.priceId = pd.priceId || subscription.priceId;
  subscription.pendingDowngrade = {
    planId: null, priceId: null, effectiveAt: null, keepCompetitorIds: [], keepPageIds: [], requestedAt: null,
  };
  subscription.markModified("pendingDowngrade");
  await subscription.save();

  await User.findByIdAndUpdate(userId, { plan: newPlan.name }).catch(() => {});
  await recomputeNextScanForOwner(userId, newPlan?.planReportingFrequency).catch((e) =>
    console.error("nextScan recompute after downgrade failed:", e.message)
  );
}
