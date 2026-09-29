/**
 * reset-analysis.js — wipe analysis data so you can re-run from scratch
 * WITHOUT creating a new account.
 *
 * It deletes the cached page snapshots (Page — the thing that makes re-runs
 * reuse stale data), competitors, analyses, change reports, metric snapshots,
 * jobs and job events. Your User account (and Plans/Subscriptions) are kept.
 *
 * Usage (run from the Server/ folder):
 *   node reset-analysis.js your@email.com        # reset just this account
 *   node reset-analysis.js --all                 # reset EVERY workspace (keeps all users)
 *   node reset-analysis.js your@email.com --keep-workspace
 *        # keep the workspace + competitor rows, only clear pages/analyses so a
 *        # rescan re-fetches everything (you don't have to re-add competitors)
 *
 * After running: restart the Python analyzer + Node workers, then run onboarding
 * (or a rescan if you used --keep-workspace).
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";

import User from "./app/models/user.js";
import Workspace from "./app/models/workspace.js";
import Competitor from "./app/models/competitor.js";
import Page from "./app/models/page.js";
import Analysis from "./app/models/analysis.js";
import ChangeReport from "./app/models/changeReport.js";
import MetricSnapshot from "./app/models/metricSnapshot.js";
import Job from "./app/models/job.js";
import JobEvent from "./app/models/jobEvent.js";
import Notification from "./app/models/notification.js";
import AIUsage from "./app/models/aiUsage.js";

const args = process.argv.slice(2);
const ALL = args.includes("--all");
const KEEP_WORKSPACE = args.includes("--keep-workspace");
const email = args.find((a) => !a.startsWith("--"));

if (!ALL && !email) {
  console.error(
    "\nRefusing to run without a target.\n" +
      "  node reset-analysis.js your@email.com          (reset one account)\n" +
      "  node reset-analysis.js --all                   (reset everything)\n"
  );
  process.exit(1);
}

const MONGO_URI = process.env.MONGO_URI;
if (!MONGO_URI) {
  console.error("MONGO_URI not found in environment (.env).");
  process.exit(1);
}

async function main() {
  await mongoose.connect(MONGO_URI);
  console.log(`Connected to MongoDB: ${mongoose.connection.name}\n`);

  // Resolve which workspaces we're clearing.
  let workspaceIds = [];
  let userIds = [];

  if (ALL) {
    workspaceIds = (await Workspace.find({}, "_id")).map((w) => w._id);
    userIds = (await User.find({}, "_id")).map((u) => u._id);
    console.log(`Target: ALL (${workspaceIds.length} workspaces)\n`);
  } else {
    const user = await User.findOne({ email });
    if (!user) {
      console.error(`No user found with email: ${email}`);
      await mongoose.disconnect();
      process.exit(1);
    }
    userIds = [user._id];
    workspaceIds = (await Workspace.find({ ownerId: user._id }, "_id")).map(
      (w) => w._id
    );
    console.log(
      `Target: ${email} (userId ${user._id}, ${workspaceIds.length} workspaces)\n`
    );
  }

  const byWs = { workspaceId: { $in: workspaceIds } };

  // Collect job ids first so we can clear their events.
  const jobIds = (await Job.find(byWs, "_id")).map((j) => j._id);

  const results = {};
  results.analyses = (await Analysis.deleteMany(byWs)).deletedCount;
  results.changeReports = (await ChangeReport.deleteMany(byWs)).deletedCount;
  results.metricSnapshots = (await MetricSnapshot.deleteMany(byWs)).deletedCount;
  results.jobEvents = (
    await JobEvent.deleteMany({ jobId: { $in: jobIds } })
  ).deletedCount;
  results.jobs = (await Job.deleteMany(byWs)).deletedCount;
  results.notifications = (
    await Notification.deleteMany({ userId: { $in: userIds } })
  ).deletedCount;
  results.aiUsage = (
    await AIUsage.deleteMany({ userId: { $in: userIds } })
  ).deletedCount;

  if (KEEP_WORKSPACE) {
    // Keep workspace + competitor + page rows (pages hold the tracked URLs),
    // but reset their status to 'pending' so a rescan re-fetches every page
    // from scratch and overwrites the cached snapshot data.
    results.pages = 0;
    results.competitors = 0;
    results.workspaces = 0;
    const p = await Page.updateMany(byWs, { $set: { scanStatus: "pending" } });
    results.pagesReset = p.modifiedCount ?? p.nModified ?? 0;
    await Competitor.updateMany(byWs, { $set: { scanStatus: "pending" } });
    await Workspace.updateMany(
      { _id: { $in: workspaceIds } },
      { $set: { scanStatus: "pending" } }
    );
    console.log(
      "Kept workspace/competitor/page rows; reset scanStatus to 'pending'.\n"
    );
  } else {
    results.pages = (await Page.deleteMany(byWs)).deletedCount;
    results.competitors = (await Competitor.deleteMany(byWs)).deletedCount;
    results.workspaces = (
      await Workspace.deleteMany({ _id: { $in: workspaceIds } })
    ).deletedCount;
  }

  console.log("Deleted:");
  for (const [k, v] of Object.entries(results)) {
    console.log(`  ${k.padEnd(16)} ${v}`);
  }
  console.log("\nKept: User account(s), Plans, Subscriptions.");
  console.log(
    KEEP_WORKSPACE
      ? "\nNext: restart Python + Node workers, then RESCAN (re-fetches all pages)."
      : "\nNext: restart Python + Node workers, then run ONBOARDING again (same login)."
  );

  await mongoose.disconnect();
  process.exit(0);
}

main().catch(async (e) => {
  console.error(e);
  await mongoose.disconnect();
  process.exit(1);
});
