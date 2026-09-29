import { Worker } from "bullmq";
import mongoose from "mongoose";
import connection from "../config/redis.js";

import { AnalyzeURL } from "../../utils/Analyzer.js";
import { generateAiStats } from "../../utils/aiStats.js";

import { analyzeUrl } from "../../api/python/analyzer.js";

mongoose.set("bufferCommands", false);

import dotenv from "dotenv";
dotenv.config();




async function startWorker() {
  try {
    await mongoose.connect(process.env.MONGO_URI);

    const analysisWorker = new Worker(
      "analysis",
      async (job) => {

        const {
          userId,
          pageId,
          url,
          competitorId,
          workspaceId
        } = job.data;

        console.log(job.data);


        /*
        |--------------------------------------------------------------------------
        | Validate input
        |--------------------------------------------------------------------------
        */

        if (!pageId || !mongoose.Types.ObjectId.isValid(pageId)) {
          throw new Error("Invalid pageId");
        }

        await job.updateProgress(10);

        /*
        |--------------------------------------------------------------------------
        | AI Analysis
        |--------------------------------------------------------------------------
        */

        let result = await analyzeUrl(url);
        const httpStatus = result?.status;
        // Definitive 404 → the page is gone/renamed. Signal offline so the completed
        // handler marks it, skips its mapped pair, and notifies the user. (Other
        // non-200s stay a normal failure — they're usually transient.)
        if (httpStatus === 404) {
          await job.updateProgress(100);
          return { pageId, competitorId, workspaceId, userId, url, offline: true, httpStatus: 404 };
        }
        if (httpStatus == 200) {
          result = await AnalyzeURL(url);
          await generateAiStats(userId, result);

        }

        await job.updateProgress(60);

        /*
        |--------------------------------------------------------------------------
        | AI Stats tracking (kept here for performance)
        |--------------------------------------------------------------------------
        */


        await job.updateProgress(85);

        /*
        |--------------------------------------------------------------------------
        | Safe parsing
        |--------------------------------------------------------------------------
        */

        let parsed;

        try {
          parsed = JSON.parse(result.output_text);
        } catch {
          parsed = { raw: result };
        }

        await job.updateProgress(100);

        /*
        |--------------------------------------------------------------------------
        | RETURN ONLY (IMPORTANT)
        |--------------------------------------------------------------------------
        */

        return {
          pageId,
          competitorId,
          workspaceId,
          userId,
          url,
          analysis: parsed,
        };
      },
      {
        connection,
        concurrency: 3,
      }
    );

    analysisWorker.on("failed", (job, err) => {
      console.error("🔥 Job failed:", job?.id, err.message);
    });

    analysisWorker.on("completed", (job) => {
      console.log("🎉 Job completed:", job.id);
    });

  } catch (err) {
    console.error("❌ Worker startup failed:", err);
    process.exit(1);
  }
}

startWorker();