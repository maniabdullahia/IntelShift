import jwt from "jsonwebtoken";

import User from "../models/user.js";
import Workspace from "../models/workspace.js";
import Competitor from "../models/competitor.js";
import Page from "../models/page.js";
import Analysis from "../models/analysis.js";
import ChangeReport from "../models/changeReport.js";
import MetricSnapshot from "../models/metricSnapshot.js";
import Notification from "../models/notification.js";
import Subscription from "../models/subscription.js";

import paddle from "./paddle.service.js";
import { getSubscriptionByUserId } from "./subscription.service.js";
import {
  sendDeletionVerificationMail,
  sendDeletionScheduledMail,
  sendDeletionReminderMail,
  sendAccountDeactivatedMail,
  sendAccountDeletedMail,
  sendReactivatedMail,
} from "./email.service.js";

const GRACE_DAYS = 14; // days after access ends before permanent deletion
const TOKEN_TYPE = "account-deletion";

const addDays = (date, days) => {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
};

/* Step 1 — user requests closure; we email a confirmation link (nothing changes yet). */
export const requestAccountDeletion = async (userId) => {
  const user = await User.findById(userId);
  if (!user) throw new Error("User not found");

  const token = jwt.sign(
    { userId: String(user._id), type: TOKEN_TYPE },
    process.env.ACCESS_TOKEN_SECRET,
    { expiresIn: "3d" }
  );

  user.deletion = { status: "requested", requestedAt: new Date(), remindersSent: [] };
  user.markModified("deletion");
  await user.save();

  const link = `${process.env.CLIENT_URL || ""}/account/confirm-deletion/${token}`;
  await sendDeletionVerificationMail(user.email, user.name, link);
  return { requested: true };
};

/* Step 2 — user confirms via email link: cancel subscription at period end, keep
   access until then, schedule deletion after a grace period. */
export const confirmAccountDeletion = async (token) => {
  let decoded;
  try {
    decoded = jwt.verify(token, process.env.ACCESS_TOKEN_SECRET);
  } catch {
    throw new Error("This confirmation link is invalid or has expired.");
  }
  if (decoded?.type !== TOKEN_TYPE) throw new Error("Invalid confirmation link.");

  const user = await User.findById(decoded.userId);
  if (!user) throw new Error("User not found");

  const subscription = await getSubscriptionByUserId(user._id);
  const periodEnd = subscription?.nextBilledAt || subscription?.currentPeriodEnd || null;
  const accessEndsAt = periodEnd ? new Date(periodEnd) : addDays(new Date(), 30);
  const deleteAt = addDays(accessEndsAt, GRACE_DAYS);

  user.deletion = {
    status: "scheduled",
    requestedAt: user.deletion?.requestedAt || new Date(),
    confirmedAt: new Date(),
    accessEndsAt,
    deleteAt,
    remindersSent: [],
  };
  user.markModified("deletion");
  await user.save();

  // Best-effort: stop future charges by cancelling at the next billing period.
  await cancelPaddleSubscription(subscription).catch((e) =>
    console.error("Paddle cancel failed (continuing):", e.message)
  );

  await sendDeletionScheduledMail(user.email, user.name, accessEndsAt, deleteAt);
  return { accessEndsAt, deleteAt };
};

/* Undo — reactivate before the access period ends (or during the grace window). */
export const reactivateAccount = async (userId) => {
  const user = await User.findById(userId);
  if (!user) throw new Error("User not found");
  if (!user.deletion || user.deletion.status === "none") return { reactivated: true };

  user.deletion = { status: "none", requestedAt: null, confirmedAt: null, accessEndsAt: null, deleteAt: null, remindersSent: [] };
  if (user.accountStatus === "deactivated") user.accountStatus = "active";
  user.markModified("deletion");
  await user.save();

  await sendReactivatedMail(user.email, user.name);
  return { reactivated: true };
};

async function cancelPaddleSubscription(subscription) {
  if (!subscription?.subscriptionId) return;
  // Paddle Node SDK — cancel at the next billing period. Adjust to your SDK version if needed.
  if (paddle?.subscriptions?.cancel) {
    await paddle.subscriptions.cancel(subscription.subscriptionId, { effectiveFrom: "next_billing_period" });
  }
}

/* Daily cron — reminders, deactivation at period end, hard delete after grace. */
export const processScheduledDeletions = async () => {
  const now = new Date();

  // 1) Reminder emails (7 days / 1 day before access ends)
  const scheduled = await User.find({ "deletion.status": "scheduled" });
  for (const user of scheduled) {
    const ends = user.deletion?.accessEndsAt;
    if (!ends) continue;
    const days = Math.ceil((new Date(ends) - now) / 86400000);
    const sent = user.deletion.remindersSent || [];
    let kind = null;
    if (days <= 1 && days > 0 && !sent.includes("1d")) kind = "1d";
    else if (days <= 7 && days > 1 && !sent.includes("7d")) kind = "7d";
    if (kind) {
      await sendDeletionReminderMail(user.email, user.name, ends, kind).catch(() => {});
      user.deletion.remindersSent = [...sent, kind];
      user.markModified("deletion");
      await user.save();
    }
  }

  // 2) Deactivate accounts whose paid period has ended
  const toDeactivate = await User.find({ "deletion.status": "scheduled", "deletion.accessEndsAt": { $lte: now } });
  for (const user of toDeactivate) {
    user.accountStatus = "deactivated";
    user.deletion.status = "deactivated";
    user.markModified("deletion");
    await user.save();
    await sendAccountDeactivatedMail(user.email, user.name, user.deletion.deleteAt).catch(() => {});
  }

  // 3) Hard delete after the grace period
  const toDelete = await User.find({ "deletion.status": "deactivated", "deletion.deleteAt": { $lte: now } });
  for (const user of toDelete) {
    try {
      const email = user.email;
      const name = user.name;
      await hardDeleteUser(user);
      await sendAccountDeletedMail(email, name).catch(() => {});
    } catch (e) {
      console.error("Hard delete failed for", String(user._id), e.message);
    }
  }
};

async function hardDeleteUser(user) {
  const workspaces = await Workspace.find({ ownerId: user._id }).select("_id");
  const wsIds = workspaces.map((w) => w._id);
  const competitors = await Competitor.find({ workspaceId: { $in: wsIds } }).select("_id");
  const compIds = competitors.map((c) => c._id);

  await Page.deleteMany({ competitorId: { $in: compIds } });
  await ChangeReport.deleteMany({ competitorId: { $in: compIds } });
  await MetricSnapshot.deleteMany({ competitorId: { $in: compIds } });
  await Analysis.deleteMany({ workspaceId: { $in: wsIds } });
  await Competitor.deleteMany({ workspaceId: { $in: wsIds } });
  await Workspace.deleteMany({ ownerId: user._id });
  await Notification.deleteMany({ userId: user._id });
  await Subscription.deleteMany({ userId: user._id });
  await User.deleteOne({ _id: user._id });
}
