/**
 * backfill-trial-end.js — stamp trialStart/trialEnd on existing "trialing"
 * subscriptions that predate the 14-day-trial change, so the dashboard trial
 * banner (and the monitoring cap) work for current testers. Run from Server/:
 *
 *   node backfill-trial-end.js
 *
 * Safe & idempotent: only touches trialing subs that are missing trialEnd, and
 * anchors the 14 days on the existing trialStart / createdAt so the countdown is
 * accurate rather than resetting the clock.
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";
import Subscription from "./app/models/subscription.js";

const TRIAL_DAYS = Number(process.env.TRIAL_DAYS) || 14;
const DAY = 24 * 60 * 60 * 1000;

async function main() {
  if (!process.env.MONGO_URI) {
    console.error("MONGO_URI is not set in Server/.env");
    process.exit(1);
  }
  await mongoose.connect(process.env.MONGO_URI);

  const subs = await Subscription.find({
    status: "trialing",
    $or: [{ trialEnd: null }, { trialEnd: { $exists: false } }],
  });

  if (!subs.length) {
    console.log("No trialing subscriptions need backfilling.");
    await mongoose.disconnect();
    process.exit(0);
  }

  let updated = 0;
  for (const s of subs) {
    const start = s.trialStart || s.currentPeriodStart || s.createdAt || new Date();
    const end = new Date(new Date(start).getTime() + TRIAL_DAYS * DAY);
    s.trialStart = start;
    s.trialEnd = end;
    if (!s.currentPeriodEnd) s.currentPeriodEnd = end;
    await s.save();
    updated += 1;
    const daysLeft = Math.max(0, Math.ceil((end.getTime() - Date.now()) / DAY));
    console.log(`user ${s.userId}: trialEnd=${end.toISOString().slice(0, 10)} (${daysLeft} days left)`);
  }

  console.log(`\nBackfilled ${updated} trial subscription(s).`);
  console.log("Refresh the app (or log out/in) so the client re-fetches the subscription and shows the banner.");
  await mongoose.disconnect();
  process.exit(0);
}

main().catch(async (e) => {
  console.error("Backfill failed:", e?.message || e);
  try { await mongoose.disconnect(); } catch {}
  process.exit(1);
});
