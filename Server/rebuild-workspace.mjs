/*
 * Re-generate the workspace-level analysis report for the stuck Nike workspace.
 * The competitor pages are already scraped — this only re-runs the comparison +
 * AI report step (which failed before) and saves the Analysis record, which is
 * what the UI waits for to leave the /intro screen.
 *
 * PREREQ: restart the Node server FIRST (so the running worker has the fixes:
 * bigger max_tokens + the failure guards), THEN run this:
 *   node rebuild-workspace.mjs
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";
import workspaceQueue from "./app/queues/workspace.queue.js";

const WORKSPACE_ID = "6a745216f27d0952fcf89bc5"; // Nike
const USER_ID = "6a6b200d227cda751a9f7e34";

const run = async () => {
  await mongoose.connect(process.env.MONGO_URI);

  const competitors = await mongoose.connection
    .collection("competitors")
    .find({
      workspaceId: new mongoose.Types.ObjectId(WORKSPACE_ID),
      role: "Competitor",
    })
    .toArray();

  const competitorIds = competitors.map((c) => c._id);
  console.log(
    `Enqueuing rebuild for ${competitorIds.length} competitor(s):`,
    competitors.map((c) => c.name).join(", ")
  );

  await workspaceQueue.add(
    "rebuildWorkspaceAnalysis",
    { workspaceId: WORKSPACE_ID, userId: USER_ID, competitorIds },
    { jobId: `workspace-${WORKSPACE_ID}-manual-${Date.now()}`, removeOnComplete: true }
  );

  console.log(
    "✅ Enqueued. Watch the Node server logs for '🔄 Workspace processing' → " +
    "'✅ Analysis completed for: Bombshellsportswear'. If it fails, the log will " +
    "now say exactly why (truncated JSON / AI error). Then hard-refresh the browser."
  );

  await mongoose.disconnect();
  await workspaceQueue.close();
  process.exit(0);
};

run().catch((e) => {
  console.error("❌", e.message);
  process.exit(1);
});
