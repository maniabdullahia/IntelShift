/**
 * reseed-plans.js — force-update the plan documents in MongoDB from the current
 * plan.seeder.js, without waiting for a server restart. Run from the Server/ folder
 * (your machine is on the Atlas IP whitelist):
 *
 *   node reseed-plans.js
 *
 * It upserts the plans (trial/starter/growth/pro/enterprise) and then prints every
 * plan's key fields so you can confirm the DB now matches the code.
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";
import seedPlans from "./app/seeder/plan.seeder.js";
import Plan from "./app/models/plan.js";

async function main() {
  if (!process.env.MONGO_URI) {
    console.error("MONGO_URI is not set in Server/.env");
    process.exit(1);
  }
  await mongoose.connect(process.env.MONGO_URI);
  console.log("Connected. Seeding plans…\n");

  await seedPlans();

  const plans = await Plan.find({}).sort({ price: 1 }).lean();
  console.log("\n─── Plans now in the database ───");
  for (const p of plans) {
    const L = p.limits || {};
    console.log(
      `${(p.name || "").padEnd(11)} $${String(p.price).padEnd(4)} ` +
      `cadence=${p.planReportingFrequency} ` +
      `competitors=${L.competitors} pages=${L.pagesPerCompetitor} ` +
      `pairing=${L.pairingScope || "-"} completeSite=${!!L.completeSite} ` +
      `contactSales=${!!p.contactSales}`
    );
  }
  console.log("\nDone. If the numbers above are correct, restart your app so the UI reloads them.");
  await mongoose.disconnect();
  process.exit(0);
}

main().catch(async (e) => {
  console.error("Reseed failed:", e?.message || e);
  try { await mongoose.disconnect(); } catch {}
  process.exit(1);
});
