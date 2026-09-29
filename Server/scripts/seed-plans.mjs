/*
 * Force-seed the plan tiers and print what's now in the DB, so you can verify the
 * live values without booting the whole server. (The `npm run seed` script is a
 * no-op — seeder.js only exports seedAll and never connects/runs.)
 *
 * Usage (from the Server directory):
 *   node scripts/seed-plans.mjs
 */
import dotenv from "dotenv";
import mongoose from "mongoose";

dotenv.config();

import seedPlans from "../app/seeder/plan.seeder.js";
import Plan from "../app/models/plan.js";

const main = async () => {
  if (!process.env.MONGO_URI) throw new Error("MONGO_URI missing in .env");
  await mongoose.connect(process.env.MONGO_URI);
  console.log(`✅ Connected to ${mongoose.connection.name}`);

  await seedPlans();

  const plans = await Plan.find({}).sort({ price: 1 }).lean();
  console.log("\n📋 Plan tiers now in the database:");
  for (const p of plans) {
    const l = p.limits || {};
    console.log(
      `  ${(p.displayName || p.name).padEnd(12)} $${p.price}  ` +
      `competitors=${l.competitors}  pages=${l.pagesPerCompetitor}  cadence=${l.reportFrequency}`
    );
  }

  await mongoose.disconnect();
  process.exit(0);
};

main().catch(async (err) => {
  console.error("❌ Seed failed:", err.message);
  try { await mongoose.disconnect(); } catch {}
  process.exit(1);
});
