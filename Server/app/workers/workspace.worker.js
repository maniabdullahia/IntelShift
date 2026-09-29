import { Worker } from "bullmq";
import mongoose from "mongoose";
import connection from "../config/redis.js";

import Workspace from "../models/workspace.js";
import Competitor from "../models/competitor.js";
import Page from "../models/page.js";

import { compareAnalysis } from "../../utils/Analyzer.js";
import { generateAiStats } from "../../utils/aiStats.js";

import { compareSite } from "../../api/python/siteComparison.js";
import { buildAiPayload, buildOpenAiInsights } from "../../api/python/payload.ai.js";
import { mergeJson } from "../../api/python/merger.js";

import { createAnalysis } from "../services/analysis.service.js";

mongoose.set("bufferCommands", false);

import dotenv from "dotenv";
dotenv.config();

/*
|--------------------------------------------------------------------------
| DB CONNECT
|--------------------------------------------------------------------------
*/

async function connectDB() {
  try {
    if (mongoose.connection.readyState === 0) {
      await mongoose.connect(process.env.MONGO_URI);

      console.log("✅ Workspace Worker MongoDB connected");
    }
  } catch (error) {
    console.error("❌ MongoDB connection failed:", error.message);

    process.exit(1);
  }
}

await connectDB();

/*
|--------------------------------------------------------------------------
| WORKER (COMPUTE ONLY)
|--------------------------------------------------------------------------
*/

const workspaceWorker = new Worker(
  "workspace",
  async (job) => {
    try {
      const { workspaceId, userId, competitorIds } = job.data;

      console.log("🔄 Workspace processing:", workspaceId);

      /*
      |--------------------------------------------------------------------------
      | Fetch data
      |--------------------------------------------------------------------------
      */

      const workspace = await Workspace.findById(workspaceId).lean();

      if (!workspace) {
        throw new Error(`Workspace not found: ${workspaceId}`);
      }

      const owner = await Competitor.findOne({
        workspaceId,
        role: "Owner",
      }).lean();

      // When the trigger passed a specific set (only the changed / new
      // competitors), rebuild just those; otherwise rebuild all.
      const competitorFilter = { workspaceId, role: "Competitor" };
      if (Array.isArray(competitorIds) && competitorIds.length) {
        competitorFilter._id = { $in: competitorIds };
      }

      const competitors = await Competitor.find(competitorFilter).lean();

      if (!owner?.analysisData || !competitors.length) {
        console.warn(
          `⚠️ Skipping workspace ${workspaceId} - Missing owner analysis or competitors`
        );

        return {
          workspaceId,
          userId,
          analysis: [],
          skipped: true,
          analysesCreated: 0,
          competitorsTotal: competitors.length,
        };
      }

      /*
      |--------------------------------------------------------------------------
      | Process comparisons
      |--------------------------------------------------------------------------
      */

      const analysisResults = [];
      // Track how many reports actually persisted, so the workspace status can be
      // reported truthfully (0 → Failed) instead of a misleading "Completed" that
      // traps the UI on the intro/loading screen forever.
      let analysesCreated = 0;

      // Owner pages that went offline (404) — any mapping onto one of these is
      // skipped so a dead owner page can't drag a competitor's comparison.
      const offlineOwner = await Page.find({ competitorId: owner._id, offline: true }).select("url").lean();
      const offlineOwnerUrls = new Set(offlineOwner.map((p) => String(p.url || "").trim().replace(/\/+$/, "")));

      for (const comp of competitors) {
        try {
          if (!comp.analysisData) {
            console.warn(
              `⚠️ Missing analysis data for competitor: ${comp.name}`
            );

            continue;
          }

          // Respect the user's EXPLICIT collection mapping from onboarding. The
          // comparison engine otherwise pairs collections by name similarity
          // alone, so deliberately-mapped collections with different names (e.g.
          // parizad "luxury-pret" ↔ ayeshashoaibmalik "collection-noya") never
          // match and the Catalog comes up empty. We pass the competitor→owner
          // page pairs so those collections are force-matched.
          const compData = comp.analysisData?.data;
          let mappings = [];
          try {
            const mappedPages = await Page.find({
              competitorId: comp._id,
              mapStatus: "matched",
              mappedOwnerUrl: { $nin: [null, ""] },
              offline: { $ne: true }, // skip the pair if the competitor page is offline
            }).select("url mappedOwnerUrl").lean();

            mappings = mappedPages
              .filter((p) => p.url && p.mappedOwnerUrl)
              // ...and skip the pair if the OWNER side is offline.
              .filter((p) => !offlineOwnerUrls.has(String(p.mappedOwnerUrl).trim().replace(/\/+$/, "")))
              .map((p) => ({ competitorUrl: p.url, ownerUrl: p.mappedOwnerUrl }));

            if (compData && typeof compData === "object" && mappings.length) {
              compData._userCollectionMappings = mappings;
            }
          } catch (mapErr) {
            console.warn("Collection mapping lookup failed (continuing):", mapErr.message);
          }

          // Scope the OWNER snapshot to ONLY the pages mapped to THIS competitor.
          // The owner is one shared site whose analysisData is merged from every
          // page it maps to (across all competitors), so comparing that full blob
          // would count owner pages that belong to other competitors. We re-merge
          // just this competitor's mapped owner pages here. Owner pages are still
          // crawled once — this only scopes the comparison. Falls back to the full
          // snapshot if scoping yields nothing (safety).
          let ownerDataForComp = owner.analysisData?.data;
          try {
            const ownerUrls = [...new Set(mappings.map((m) => m.ownerUrl).filter(Boolean))];
            if (ownerUrls.length) {
              const ownerPages = await Page.find({
                competitorId: owner._id,
                url: { $in: ownerUrls },
                scanStatus: "Completed",
              }).select("analysisData").lean();

              const ownerRaw = ownerPages
                .map((p) => p.analysisData?.raw)
                .filter((d) => d && Object.keys(d).length > 0);

              if (ownerRaw.length === 1) {
                ownerDataForComp = ownerRaw[0];
              } else if (ownerRaw.length > 1) {
                ownerDataForComp = await mergeJson(...ownerRaw);
              }
              console.log(`🔎 [${comp.name}] owner scope — ${ownerRaw.length}/${ownerUrls.length} mapped owner pages`);
            }
          } catch (scopeErr) {
            console.warn(`Owner scope merge failed for ${comp.name} (using full owner snapshot):`, scopeErr.message);
            ownerDataForComp = owner.analysisData?.data;
          }

          // Timing + payload-size instrumentation, so we can see exactly which
          // step is slow and how big the snapshots are for a given store.
          const kb = (obj) => {
            try { return Math.round(Buffer.byteLength(JSON.stringify(obj)) / 1024); }
            catch { return -1; }
          };
          console.log(
            `📦 [${comp.name}] snapshot sizes — owner ${kb(ownerDataForComp)}KB (scoped), competitor ${kb(compData)}KB`
          );

          const tCompare = Date.now();
          const comparison = await compareSite(
            ownerDataForComp,
            compData
          );
          console.log(`⏱️ [${comp.name}] compareSite (Python /compare-one) took ${((Date.now() - tCompare) / 1000).toFixed(1)}s`);

          // Give the AI business context: the user's industry and the full
          // competitor set they deliberately chose. Frames relevance without
          // overriding the evidence-only rules on the Python side.
          if (comparison && typeof comparison === "object") {
            comparison.businessContext = {
              industry: workspace?.industry || null,
              userDomain: owner?.domain || null,
              competitorDomain: comp?.domain || null,
              competitorSet: competitors.map((c) => c.domain).filter(Boolean),
            };
          }

          const tInsights = Date.now();
          const aiInsights = await buildOpenAiInsights(comparison);
          console.log(`⏱️ [${comp.name}] buildOpenAiInsights took ${((Date.now() - tInsights) / 1000).toFixed(1)}s — evidence ${kb(aiInsights)}KB`);

          const tReport = Date.now();
          const result = await compareAnalysis(aiInsights);
          console.log(`⏱️ [${comp.name}] compareAnalysis (AI) took ${((Date.now() - tReport) / 1000).toFixed(1)}s`);

          // Surface WHY a report failed instead of crashing on JSON.parse(undefined)
          // — a failed AI call returns { error, message }, and a truncated response
          // returns invalid JSON. Either way, skip this competitor with a clear log
          // rather than a cryptic parse error that silently drops the analysis.
          if (!result || result.error || !result.output_text) {
            console.error(
              `❌ AI report failed for ${comp.name}: ${result?.message || "empty output_text"} — skipping`
            );
            continue;
          }

          let parsedResult;
          try {
            parsedResult = JSON.parse(result.output_text);
          } catch (parseErr) {
            console.error(
              `❌ AI report for ${comp.name} was not valid JSON (likely truncated): ${parseErr.message} — skipping`
            );
            continue;
          }

          const competitorData = {
            ownerId: owner._id,
            competitorId: comp._id,
          }

          const analysisData = {
            comparison,
            payload: aiInsights,
            result: parsedResult,
          }

          try {
            await createAnalysis(workspaceId, competitorData, analysisData);
            analysesCreated += 1;
          } catch (error) {
            console.error(
              `❌ Error creating analysis for competitor ${comp.name}:`,
              error.message
            );
          }


          try {
            await generateAiStats(userId, result);
          } catch (statsError) {
            console.error(
              `❌ Failed to generate AI stats for competitor ${comp.name}:`,
              statsError.message
            );
          }


          console.log(`✅ Analysis completed for: ${comp.name}`);

        } catch (compError) {
          console.error(
            `❌ Error processing competitor ${comp.name}:`,
            compError.message
          );
        }
      }

      // Capture-first: once at least one report exists, the setup is complete —
      // advance a "analyzing" workspace to "ready" so the UI leaves the setup flow.
      // Guarded to setupStage: "analyzing" so it never disturbs legacy workspaces.
      if (analysesCreated > 0) {
        try {
          await Workspace.findOneAndUpdate(
            { _id: workspaceId, setupStage: "analyzing" },
            { $set: { setupStage: "ready" } }
          );
        } catch (stageErr) {
          console.warn("setupStage → ready update failed (continuing):", stageErr.message);
        }
      }

      /*
      |--------------------------------------------------------------------------
      | RETURN ONLY
      |--------------------------------------------------------------------------
      */

      return {
        workspaceId,
        userId,
        analysesCreated,
        competitorsTotal: competitors.length,
      };
    } catch (error) {
      console.error("❌ Workspace worker failed:", {
        jobId: job.id,
        workspaceId: job.data?.workspaceId,
        error: error.message,
        stack: error.stack,
      });

      throw error;
    }
  },
  {
    connection,
    concurrency: 1,
  }
);

/*
|--------------------------------------------------------------------------
| WORKER EVENTS
|--------------------------------------------------------------------------
*/

workspaceWorker.on("completed", (job) => {
  console.log(`✅ Job completed: ${job.id}`);
});

workspaceWorker.on("failed", (job, err) => {
  console.error(`❌ Job failed: ${job?.id}`, err.message);
});

workspaceWorker.on("error", (err) => {
  console.error("❌ Worker error:", err.message);
});

export default workspaceWorker;