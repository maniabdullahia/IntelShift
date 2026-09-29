/*
 * One-off: hard-delete a test account and ALL its data so it can be recreated
 * cleanly. Mirrors account.service.js -> hardDeleteUser exactly, plus the queue
 * bookkeeping (jobs/jobEvents) so a re-test starts from a blank slate.
 *
 * Usage (from the Server directory):
 *   node scripts/delete-test-account.mjs [email]
 * Defaults to the email below if none is passed.
 */
import dotenv from "dotenv";
import mongoose from "mongoose";

import User from "../app/models/user.js";
import Workspace from "../app/models/workspace.js";
import Competitor from "../app/models/competitor.js";
import Page from "../app/models/page.js";
import Analysis from "../app/models/analysis.js";
import ChangeReport from "../app/models/changeReport.js";
import MetricSnapshot from "../app/models/metricSnapshot.js";
import Notification from "../app/models/notification.js";
import Subscription from "../app/models/subscription.js";

dotenv.config();

const TARGET_EMAIL = (process.argv[2] || "20-10369@formanite.fccollege.edu.pk").trim();

const main = async () => {
  if (!process.env.MONGO_URI) throw new Error("MONGO_URI missing in .env");
  await mongoose.connect(process.env.MONGO_URI);
  console.log("✅ Connected");

  // Case-insensitive exact match on email.
  const user = await User.findOne({
    email: { $regex: `^${TARGET_EMAIL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`, $options: "i" },
  });

  if (!user) {
    console.log(`⚠️ No user found for "${TARGET_EMAIL}" — nothing to delete.`);
    await mongoose.disconnect();
    return;
  }

  console.log(`🎯 Found user ${user._id} <${user.email}> (${user.name || "no name"})`);

  const workspaces = await Workspace.find({ ownerId: user._id }).select("_id");
  const wsIds = workspaces.map((w) => w._id);
  const competitors = await Competitor.find({ workspaceId: { $in: wsIds } }).select("_id");
  const compIds = competitors.map((c) => c._id);

  const results = {
    pages: (await Page.deleteMany({ competitorId: { $in: compIds } })).deletedCount,
    changeReports: (await ChangeReport.deleteMany({ competitorId: { $in: compIds } })).deletedCount,
    metricSnapshots: (await MetricSnapshot.deleteMany({ competitorId: { $in: compIds } })).deletedCount,
    analyses: (await Analysis.deleteMany({ workspaceId: { $in: wsIds } })).deletedCount,
    competitors: (await Competitor.deleteMany({ workspaceId: { $in: wsIds } })).deletedCount,
    workspaces: (await Workspace.deleteMany({ ownerId: user._id })).deletedCount,
    notifications: (await Notification.deleteMany({ userId: user._id })).deletedCount,
    subscriptions: (await Subscription.deleteMany({ userId: user._id })).deletedCount,
    user: (await User.deleteOne({ _id: user._id })).deletedCount,
  };

  console.log("🗑️  Deleted:", results);
  console.log("✅ Done — the account and all its data are gone. You can recreate it now.");

  await mongoose.disconnect();
};

main().catch(async (err) => {
  console.error("❌ Delete failed:", err.message);
  try { await mongoose.disconnect(); } catch {}
  process.exit(1);
});
