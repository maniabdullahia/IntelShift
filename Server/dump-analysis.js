/**
 * dump-analysis.js — write a single analysis document to analysis_dump.json so it
 * can be reviewed offline. Run from the Server/ folder (your machine is on the
 * Atlas IP whitelist):
 *
 *   node dump-analysis.js 6ab12c301dd421b343ce7230
 *
 * Produces Server/analysis_dump.json with { comparison, payload, result } and meta.
 */
import dotenv from "dotenv";
dotenv.config();

import mongoose from "mongoose";
import fs from "fs";
import Analysis from "./app/models/analysis.js";
import Competitor from "./app/models/competitor.js";

const id = process.argv[2];
if (!id) {
  console.error("Usage: node dump-analysis.js <analysisId>");
  process.exit(1);
}

async function main() {
  await mongoose.connect(process.env.MONGO_URI);
  const doc = await Analysis.findById(id).lean();
  if (!doc) {
    console.error(`Analysis ${id} not found.`);
    await mongoose.disconnect();
    process.exit(1);
  }
  // Attach the competitor names/urls for context.
  const owner = doc.competitors?.ownerId
    ? await Competitor.findById(doc.competitors.ownerId).select("name domain storeUrl websiteUrl role currency").lean()
    : null;
  const rival = doc.competitors?.competitorId
    ? await Competitor.findById(doc.competitors.competitorId).select("name domain storeUrl websiteUrl role currency").lean()
    : null;

  const out = {
    _id: String(doc._id),
    createdAt: doc.createdAt,
    owner,
    competitor: rival,
    comparison: doc.data?.comparison || null,
    payload: doc.data?.payload || null,
    result: doc.data?.result || null,
  };

  fs.writeFileSync("analysis_dump.json", JSON.stringify(out, null, 2));
  console.log(`Wrote Server/analysis_dump.json — ${JSON.stringify(out).length} bytes`);
  await mongoose.disconnect();
  process.exit(0);
}

main().catch(async (e) => {
  console.error(e);
  await mongoose.disconnect();
  process.exit(1);
});
