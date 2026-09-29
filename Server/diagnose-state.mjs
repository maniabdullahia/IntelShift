/*
 * Read-only diagnostic: prints why the app is stuck on the loading/intro screen.
 * Run from the Server folder:  node diagnose-state.mjs
 * (Change EMAIL below if the account differs.)
 */
import mongoose from "mongoose";
import dotenv from "dotenv";

dotenv.config();

const EMAIL = "20-10369@formanite.fccollege.edu.pk";

const run = async () => {
  await mongoose.connect(process.env.MONGO_URI);
  const db = mongoose.connection;

  const user = await db.collection("users").findOne({ email: EMAIL });
  if (!user) {
    console.log(`No user found for ${EMAIL}`);
    return mongoose.disconnect();
  }

  console.log("USER");
  console.log("  _id:", String(user._id));
  console.log("  isEmailVerified:", user.isEmailVerified);
  console.log("  workspace field (pointer):", user.workspace ? String(user.workspace) : "(none)");

  const subs = await db.collection("subscriptions").find({ userId: user._id }).toArray();
  console.log(`\nSUBSCRIPTIONS (${subs.length})`);
  subs.forEach((s) => console.log(`  _id=${s._id} status=${s.status} planId=${s.planId}`));

  const workspaces = await db.collection("workspaces").find({ ownerId: user._id }).toArray();
  console.log(`\nWORKSPACES (${workspaces.length})`);
  for (const w of workspaces) {
    const analysisCount = await db.collection("analyses").countDocuments({ workspaceId: w._id });
    const competitors = await db.collection("competitors").find({ workspaceId: w._id }).toArray();
    const compLines = competitors
      .map((c) => `${c.role}:${c.name}[${c.scanStatus}]`)
      .join(", ");
    console.log(
      `  • ${w.name}  id=${w._id}\n      scanStatus="${w.scanStatus}" introCompleted=${w.introCompleted} analyses=${analysisCount} competitors=${competitors.length}\n      ${compLines}`
    );
  }

  await mongoose.disconnect();
};

run().catch((e) => { console.error("❌", e.message); process.exit(1); });
