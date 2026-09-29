/*
 * One-time recovery: normalise stuck workspace scanStatus values.
 *
 * A bug wrote scanStatus: "completed" (lowercase) on workspace completion, which
 * doesn't match the schema enum / what the frontend waits for ("Completed"), so
 * the UI polled /api/profile forever. This flips those (and any left in
 * "Processing") back to the correct "Completed" so the screen unsticks.
 *
 * Run from the Server folder AFTER restarting the Node server:
 *   node fix-workspace-status.mjs
 */
import mongoose from "mongoose";
import dotenv from "dotenv";

dotenv.config();

const run = async () => {
  if (!process.env.MONGO_URI) {
    throw new Error("MONGO_URI is not set in Server/.env");
  }

  await mongoose.connect(process.env.MONGO_URI);
  console.log("✅ Connected to MongoDB");

  const workspaces = mongoose.connection.collection("workspaces");

  // Show current state first.
  const before = await workspaces
    .find({}, { projection: { name: 1, scanStatus: 1 } })
    .toArray();
  console.log("Current workspaces:");
  before.forEach((w) => console.log(`  - ${w.name}: "${w.scanStatus}"`));

  const result = await workspaces.updateMany(
    { scanStatus: { $in: ["completed", "processing", "Processing"] } },
    { $set: { scanStatus: "Completed", lastRebuiltAt: new Date() } }
  );

  console.log(`\n🟢 Fixed ${result.modifiedCount} workspace(s) → scanStatus "Completed"`);

  await mongoose.disconnect();
  console.log("Done. Hard-refresh the browser (Ctrl+Shift+R).");
};

run().catch((err) => {
  console.error("❌ Failed:", err.message);
  process.exit(1);
});
