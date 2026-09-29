// competitor.worker.js

import dotenv from "dotenv";
dotenv.config();

import { Worker } from "bullmq";
import mongoose from "mongoose";

import connection from "../config/redis.js";
import Page from "../models/page.js";

import { mergeJson } from "../../api/python/merger.js";
import { detectSnapshotChanges } from "../../api/python/changeDetector.js";
import { analyzeUrl, discoverPolicyPages } from "../../api/python/analyzer.js";

import Competitor from "../models/competitor.js";
import ChangeReport from "../models/changeReport.js";
import MetricSnapshot from "../models/metricSnapshot.js";



/*
|--------------------------------------------------------------------------
| DB CONNECTION
|--------------------------------------------------------------------------
*/
async function connectDB() {
  if (!process.env.MONGO_URI) {
    throw new Error("MONGO_URI is missing in environment");
  }

  if (mongoose.connection.readyState === 0) {
    await mongoose.connect(process.env.MONGO_URI);
  }
}

/*
|--------------------------------------------------------------------------
| WORKER START
|--------------------------------------------------------------------------
*/
async function startWorker() {
  try {
    await connectDB();

    const competitorWorker = new Worker(
      "competitor",

      async (job) => {
        const { competitorId, workspaceId, userId } = job.data;

        /*
        |--------------------------------------------------------------------------
        | FETCH PAGES
        |--------------------------------------------------------------------------
        */
        const pages = await Page.find(
          {
            competitorId,
            scanStatus: "Completed",
          },
          {
            analysisData: 1,
          }
        ).lean();

        if (!pages.length) {
          console.log("⚠️ No completed pages found");

          return {
            competitorId,
            workspaceId,
            userId,
            snapshot: null,
            totalPages: 0,
          };
        }

        /*
        |--------------------------------------------------------------------------
        | EXTRACT DATA
        |--------------------------------------------------------------------------
        */
        const analysisDataList = pages
          .map((p) => p.analysisData?.raw)
          .filter((data) => data && Object.keys(data).length > 0);

        /*
        |--------------------------------------------------------------------------
        | AUTO-TRACK POLICY / SHIPPING / CHECKOUT PAGES (ecommerce, hidden)
        |--------------------------------------------------------------------------
        | Nobody selects these, but they carry high-signal intel (free-ship
        | thresholds, COD, bank-deposit offers, delivery times). For ecommerce
        | sites we discover them from the homepage's footer/nav links and analyze
        | them with the SAME per-page analyzer whose output the merge consumes, so
        | they fold into the snapshot with zero shape risk. Fully best-effort: any
        | failure leaves the tracked-page analysis untouched.
        */
        try {
          // Runs for EVERY site (owner + each competitor). The owner needs its
          // policy pages folded in just as much as the rival, so the Shipping &
          // Payment comparison has both sides.
          const isEcom = analysisDataList.some(
            (d) => Array.isArray(d?.products) && d.products.length > 0
          );

          // Reliable base URL: the competitor doc's own store URL is authoritative
          // (the homepage raw can be missing its URL after a Playwright render).
          const selfDoc = await Competitor.findById(competitorId)
            .select("storeUrl websiteUrl domain role")
            .lean();
          const homeRaw =
            analysisDataList.find(
              (d) => (d?.page?.pageType || d?.pageType) === "homepage"
            ) || analysisDataList[0] || {};
          const nav = homeRaw?.navigation || {};
          const baseUrl =
            selfDoc?.storeUrl ||
            selfDoc?.websiteUrl ||
            homeRaw?.page?.url ||
            homeRaw?.technical?.finalUrl ||
            homeRaw?.url ||
            (selfDoc?.domain ? `https://${selfDoc.domain}` : "");
          const label = selfDoc?.role === "Owner" ? "owner" : "competitor";

          if (isEcom && baseUrl) {
            const already = new Set(
              analysisDataList
                .map((d) => (d?.page?.url || d?.url || "").replace(/\/+$/, ""))
                .filter(Boolean)
            );

            const policy = await discoverPolicyPages({
              url: baseUrl,
              footerLinks: nav.footerLinks || [],
              navLinks: nav.links || [],
              platform: homeRaw?.platform || homeRaw?.level1?.platform || selfDoc?.platform || "",
            });

            const toFetch = policy
              .map((p) => p.url)
              .filter((u) => u && !already.has(u.replace(/\/+$/, "")));

            console.log(
              `📄 [policy] ${label} ${baseUrl}: isEcom=${isEcom} discovered=${policy.length} toFetch=${toFetch.length}`
            );

            if (toFetch.length) {
              const results = await Promise.allSettled(toFetch.map((u) => analyzeUrl(u)));
              let added = 0;
              results.forEach((r, i) => {
                if (r.status !== "fulfilled") {
                  console.warn(`📄 [policy] ${toFetch[i]} failed: ${r.reason?.message || r.reason}`);
                  return;
                }
                const data = r.value;
                if (!data || data.status === 404 || data.success === false || data.status === "website_blocked") {
                  console.log(`📄 [policy] ${toFetch[i]} skipped (status=${data?.status} success=${data?.success})`);
                  return;
                }
                analysisDataList.push(data);
                added += 1;
              });
              console.log(`📄 [policy] ${label} ${baseUrl}: folded ${added}/${toFetch.length} policy pages`);
            }
          } else {
            console.log(`📄 [policy] ${label} skipped: isEcom=${isEcom} baseUrl=${baseUrl || "none"}`);
          }
        } catch (policyErr) {
          console.warn("policy-page auto-track skipped (continuing):", policyErr?.message || policyErr);
        }

        /*
        |--------------------------------------------------------------------------
        | MERGE JSON (PYTHON API)
        |--------------------------------------------------------------------------
        */
        let mergedData = {};

        try {
          mergedData = await mergeJson(...analysisDataList);
        } catch (err) {
          console.error("❌ mergeJson failed, fallback to raw structure", err);

          // fallback (important for stability)
          mergedData = analysisDataList;
        }

        /*
        |--------------------------------------------------------------------------
        | METRIC SNAPSHOT (per cycle) — powers advanced/Pro historical trends
        |--------------------------------------------------------------------------
        | Read straight from the snapshot's pre-computed site.catalog aggregates.
        | Captured every cycle (including the first) so the trend is complete.
        */
        try {
          const site = mergedData?.site;
          const cat = site?.catalog;
          if (site && cat) {
            await MetricSnapshot.create({
              competitorId,
              workspaceId,
              capturedAt: new Date(),
              totalProducts: cat.totalUniqueProducts ?? site.totalUniqueProducts ?? null,
              productsWithPrice: cat.productsWithPrice ?? site.productsWithPrice ?? null,
              avgPrice: cat.priceRange?.average ?? null,
              minPrice: cat.priceRange?.min ?? null,
              maxPrice: cat.priceRange?.max ?? null,
              currency: cat.currency ?? null,
              inStockCount: cat.inStockCount ?? null,
              onSaleCount: cat.onSaleCount ?? null,
              collectionsCount: Array.isArray(site.collections) ? site.collections.length : null,
              categoriesCount: Array.isArray(cat.categoriesDetected) ? cat.categoriesDetected.length : null,
            });
          }
        } catch (err) {
          console.error("MetricSnapshot capture failed (continuing):", err.message);
        }

        /*
        |--------------------------------------------------------------------------
        | SNAPSHOT BUILD
        |--------------------------------------------------------------------------
        */

        const previousSnapshot = await Competitor.findById(competitorId, { analysisData: 1, domain: 1, role: 1 }).lean();
        console.log("🔄 Previous snapshot:", previousSnapshot);

        // The fetcher follows redirects (allow_redirects=True), so an apex domain
        // that 301s to a different host — e.g. ayeshashoaibmalik.com → .us — makes
        // the analyzer record the POST-redirect host as site.domain. That flipped
        // the competitor's identity across the whole analysis/comparison UI, which
        // reads site.domain. The domain the user actually entered (stored on the
        // Competitor) is authoritative, so stamp it back onto the snapshot before
        // it's compared and saved. Works on the first run too — the Competitor doc
        // always carries the entered domain, even when analysisData is still empty.
        const authoritativeDomain = previousSnapshot?.domain;
        if (authoritativeDomain && mergedData?.site && typeof mergedData.site === "object") {
          mergedData.site.domain = authoritativeDomain;
        }
        // Normalize the previous snapshot's domain the same way, so a value that
        // differs only because of a redirect isn't mis-detected as a real change.
        if (authoritativeDomain && previousSnapshot?.analysisData?.data?.site && typeof previousSnapshot.analysisData.data.site === "object") {
          previousSnapshot.analysisData.data.site.domain = authoritativeDomain;
        }

        // When a previous snapshot exists, diff it against the new one and persist
        // a ChangeReport. Skip this for the owner's OWN site (role Owner) — we only
        // track changes for competitors. We deliberately DO NOT early-return: the
        // new snapshot must still be returned below so analysisData advances and the
        // job completes (otherwise it would stay stuck in "Processing" forever).
        if (previousSnapshot?.analysisData?.data && previousSnapshot.role !== "Owner") {
          console.log("🔄 Comparing with previous snapshot");
          try {
            const report = await detectSnapshotChanges(
              previousSnapshot.analysisData.data,
              mergedData
            );

            if (report) {
              const prevAt = previousSnapshot.analysisData?._meta?.lastRebuiltAt;
              const periodStart = prevAt
                ? new Date(prevAt)
                : report.previousGeneratedAt
                  ? new Date(report.previousGeneratedAt)
                  : new Date();
              const periodEnd = new Date();
              const totalChanges = report.summary?.totalChanges ?? 0;

              // Stamp the competitor's authoritative domain so the report always
              // maps to the right competitor card, even if the snapshot's
              // site.domain was missing or inconsistent.
              if (previousSnapshot.domain) report.domain = previousSnapshot.domain;

              // Upsert on the unique (competitorId, periodStart, periodEnd) key so a
              // retried job doesn't throw a duplicate-key error.
              await ChangeReport.findOneAndUpdate(
                { competitorId, periodStart, periodEnd },
                {
                  workspaceId,
                  competitorId,
                  periodStart,
                  periodEnd,
                  monitoredAt: new Date(),
                  report,
                  changeScore: report.changeScore ?? 0,
                  overallSeverity: report.overallSeverity ?? "low",
                  totalChanges,
                  // A "nothing changed" report is not a pending notification.
                  read: totalChanges === 0,
                },
                { upsert: true, new: true, setDefaultsOnInsert: true }
              );

              console.log(
                `📝 ChangeReport saved for competitor ${competitorId} ` +
                `(${totalChanges} changes, severity ${report.overallSeverity})`
              );
            }
          } catch (err) {
            // Never fail the whole scan because change detection had a problem —
            // the snapshot below still advances the monitoring baseline.
            console.error("❌ Change detection / ChangeReport save failed (continuing):", err.message);
          }
        }

        const snapshot = {
          data: mergedData,
          _meta: {
            totalPages: pages.length,
            lastRebuiltAt: new Date().toISOString(),
          },
        };

        console.log(`✅ Snapshot built (${pages.length} pages)`);

        return {
          competitorId,
          workspaceId,
          userId,
          snapshot,
        };
      },

      {
        connection: connection.duplicate(),
        concurrency: 1,

        // stability settings
        lockDuration: 60000,
        stalledInterval: 30000,
        maxStalledCount: 3,
      }
    );

    /*
    |--------------------------------------------------------------------------
    | EVENTS
    |--------------------------------------------------------------------------
    */

    competitorWorker.on("completed", (job) => {
      console.log("🎉 Competitor Job completed:", job.id);
    });

    competitorWorker.on("failed", (job, err) => {
      console.error("🔥 Competitor Job failed:", job?.id, err);
    });

    competitorWorker.on("stalled", (jobId) => {
      console.warn("⚠️ Competitor Job stalled:", jobId);
    });

    console.log("✅ Competitor Worker started");
  } catch (err) {
    console.error("❌ Competitor Worker startup failed:", err);
    process.exit(1);
  }
}

startWorker();