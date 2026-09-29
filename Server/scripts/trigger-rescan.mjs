/*
 * One-off: kick off a fresh analysis run for an existing workspace WITHOUT
 * re-onboarding. Use this after `reset-analysis.js --keep-workspace`, which
 * resets page status to "pending" but does NOT enqueue anything — so the intro
 * screen sits at 0%. This re-enqueues every live page (→ competitor rebuild →
 * report), exactly like the "Retry analysis" button.
 *
 * Usage (from the Server directory, with Node workers + Redis running):
 *   node scripts/trigger-rescan.mjs <workspaceId | ownerEmail>
 * Defaults to the workspace id from the recent logs if none is passed.
 */
import dotenv from "dotenv";
import mongoose from "mongoose";

dotenv.config();

import Workspace from "../app/models/workspace.js";
import User from "../app/models/user.js";
import { rescanWorkspace } from "../app/services/workspace.service.js";

const ARG = (process.argv[2] || "6a75e8ffe375c45e4de4176c").trim();

const main = async () => {
  if (!process.env.MONGO_URI) throw new Error("MONGO_URI missing in .env");
  await mongoose.connect(process.env.MONGO_URI);

  let workspaceId = ARG;

  if (ARG.includes("@")) {
    const user = await User.findOne({
      email: { $regex: `^${ARG.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`, $options: "i" },
    });
    if (!user) throw new Error(`No user for ${ARG}`);
    const ws = await Workspace.findOne({ ownerId: user._id });
    if (!ws) throw new Error(`No workspace for ${ARG}`);
    workspaceId = ws._id.toString();
  }

  console.log(`🚀 Triggering rescan for workspace ${workspaceId} …`);
  const result = await rescanWorkspace(workspaceId);
  const n = Array.isArray(result?.pages) ? result.pages.length : "?";
  console.log(`✅ Enqueued ${n} pages for analysis. Watch the worker logs; the intro screen should start moving.`);

  await mongoose.disconnect();
  process.exit(0);
};

main().catch(async (err) => {
  console.error("❌ Rescan trigger failed:", err.message);
  try { await mongoose.disconnect(); } catch {}
  process.exit(1);
});
