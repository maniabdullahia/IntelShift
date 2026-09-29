/**
 * set-trial-end.js — move a user's trialEnd for TESTING the trial banner states.
 * Run from Server/:
 *
 *   node set-trial-end.js <email|userId> <daysFromNow>
 *
 * Examples:
 *   node set-trial-end.js you@example.com 5     -> "5 days left" banner
 *   node set-trial-end.js you@example.com 1     -> "1 day left"
 *   node set-trial-end.js you@example.com -1    -> "Your free trial has ended"
 *
 * Only touches trialStart/trialEnd/status="trialing" — safe to run repeatedly.
 * After running, LOG OUT/IN (or hard-refresh) so the client re-fetches the sub.
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";
import Subscription from "./app/models/subscription.js";
import User from "./app/models/user.js";

const DAY = 24 * 60 * 60 * 1000;

async function main() {
  const who = process.argv[2];
  const days = Number(process.argv[3]);
  if (!who || Number.isNaN(days)) {
    console.error("Usage: node set-trial-end.js <email|userId> <daysFromNow>");
    process.exit(1);
  }
  await mongoose.connect(process.env.MONGO_URI);

  let userId = who;
  if (who.includes("@")) {
    const u = await User.findOne({ email: who }).select("_id").lean();
    if (!u) { console.error(`No user with email ${who}`); process.exit(1); }
    userId = u._id;
  }

  const sub = await Subscription.findOne({ userId });
  if (!sub) { console.error(`No subscription for user ${userId}`); process.exit(1); }

  const end = new Date(Date.now() + days * DAY);
  sub.status = "trialing";
  if (!sub.trialStart) sub.trialStart = new Date(Date.now() - 14 * DAY);
  sub.trialEnd = end;
  await sub.save();

  const state = days > 0 ? `${days} day(s) left` : "ENDED";
  console.log(`Set trialEnd=${end.toISOString()} for user ${userId} → banner should show: ${state}`);
  console.log("Log out/in (or hard-refresh) to see it.");
  await mongoose.disconnect();
  process.exit(0);
}

main().catch(async (e) => {
  console.error("Failed:", e?.message || e);
  try { await mongoose.disconnect(); } catch {}
  process.exit(1);
});
