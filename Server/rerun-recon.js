/**
 * rerun-recon.js — re-run the onboarding "Reviewing the Sites" (recon) step for an
 * EXISTING workspace, without creating a new one. Useful after a recon-logic change
 * (e.g. the quick-catalog fallback for JS/Cloudflare stores) so a store that
 * captured 0 categories gets re-read.
 *
 * It resets each site's reconStatus, clears the stale recon blob, flips the
 * workspace back to setupStage "recon", and re-enqueues a recon job per site.
 *
 * Usage (from the Server/ folder — Redis + the recon worker must be running):
 *   node rerun-recon.js 6aad158f3e48590493f5fac8      # by workspace id
 *   node rerun-recon.js your@email.com                # your most-recent workspace
 *
 * After it prints "queued N site(s)", reload the app — the intro screen re-runs.
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";

import User from "./app/models/user.js";
import Workspace from "./app/models/workspace.js";
import Competitor from "./app/models/competitor.js";
import { enqueueWorkspaceRecon } from "./app/services/recon.service.js";

const arg = process.argv.slice(2).find((a) => !a.startsWith("--"));
if (!arg) {
  console.error("\nUsage:\n  node rerun-recon.js <workspaceId>\n  node rerun-recon.js your@email.com\n");
  process.exit(1);
}
if (!process.env.MONGO_URI) {
  console.error("MONGO_URI not found in environment (.env).");
  process.exit(1);
}

async function main() {
  await mongoose.connect(process.env.MONGO_URI);
  console.log(`Connected to MongoDB: ${mongoose.connection.name}\n`);

  // Resolve the workspace, by id or by the user's most-recent one.
  let ws = null;
  if (/^[a-f0-9]{24}$/i.test(arg)) {
    ws = await Workspace.findById(arg);
  } else {
    const user = await User.findOne({ email: arg });
    if (!user) { console.error(`No user with email: ${arg}`); await mongoose.disconnect(); process.exit(1); }
    ws = await Workspace.findOne({ ownerId: user._id }).sort({ createdAt: -1 });
  }
  if (!ws) { console.error("Workspace not found."); await mongoose.disconnect(); process.exit(1); }

  console.log(`Workspace: ${ws._id} (owner ${ws.ownerId}) — setupStage was "${ws.setupStage}"`);

  // Reset each site's recon so the UI shows "Analyzing…" and the worker re-captures.
  const reset = await Competitor.updateMany(
    { workspaceId: ws._id },
    { $set: { reconStatus: "Pending" }, $unset: { recon: "", reconCapturedAt: "" } }
  );
  console.log(`Reset reconStatus on ${reset.modifiedCount ?? reset.nModified ?? 0} site(s).`);

  // Flip the workspace back to the recon stage (the worker flips it forward again
  // to "selecting" once every site's recon completes).
  await Workspace.findByIdAndUpdate(ws._id, { $set: { setupStage: "recon" } });

  const { queued } = await enqueueWorkspaceRecon({ workspaceId: ws._id, userId: ws.ownerId });
  console.log(`\nqueued ${queued} site(s) for recon. Reload the app — the intro screen will re-run.`);

  await mongoose.disconnect();
  process.exit(0);
}

main().catch(async (e) => {
  console.error(e);
  await mongoose.disconnect();
  process.exit(1);
});
