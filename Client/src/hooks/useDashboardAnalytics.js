import { useEffect, useState } from "react";

import api from "../api/api";
import {
  getDomains,
  getPriceRows,
  getInventoryRows,
  getCatalogRows,
  getSeoRows,
  getTrustRows,
  getMatchups,
  inferBusinessType,
} from "../components/features/AnalysisSections/_helpers";
import {
  buildCompetitiveScores,
  weightedScore,
  toCollectionChartRows,
  collectMatchedProducts,
} from "../components/features/AnalysisSections/SectionCharts";

/* ─────────────────────────────────────────────────────────────
   useDashboardAnalytics — fetches each tracked competitor's full analysis
   (silently, in parallel) and derives the metrics the Dashboard visualises.
   All extraction reuses the tested AnalysisSections helpers so it stays
   consistent with the full analysis screen.

   Returns { byDomain, aggregate, loading }:
     byDomain[domain] = per-competitor metrics (for the competitor cards)
     aggregate        = one summary rolled up across ALL competitors (snapshot)
──────────────────────────────────────────────────────────────── */

const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);

const median = (nums) => {
  const s = nums.filter((n) => Number.isFinite(n)).sort((a, b) => a - b);
  if (!s.length) return null;
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
};

const rate01 = (v) => (v == null ? null : v > 1 ? v / 100 : v);
const mean = (nums) => {
  const s = nums.filter((n) => Number.isFinite(n));
  return s.length ? s.reduce((a, b) => a + b, 0) / s.length : null;
};
const round = (v) => (v == null ? null : Math.round(v));

/* Roll the per-competitor metrics up into one all-competitors summary. */
function aggregateMetrics(list) {
  if (!list.length) return null;
  const userScores = list.map((m) => m.score?.user);
  const compScores = list.map((m) => m.score?.competitor);
  const priceGaps = list.map((m) => m.price?.medianGapPct).filter((n) => Number.isFinite(n));
  return {
    competitorCount: list.length,
    score: {
      user: round(mean(userScores)),
      competitorAvg: round(mean(compScores)),
      leadCount: list.filter((m) => (m.score?.user ?? 0) >= (m.score?.competitor ?? 0)).length,
    },
    inStock: {
      user: mean(list.map((m) => rate01(m.inStock?.user)).filter((n) => n != null)),
      competitorAvg: mean(list.map((m) => rate01(m.inStock?.competitor)).filter((n) => n != null)),
      trailingCount: list.filter((m) => {
        const u = rate01(m.inStock?.user);
        const c = rate01(m.inStock?.competitor);
        return u != null && c != null && u < c;
      }).length,
    },
    price: {
      leadCount: list.filter((m) => Number.isFinite(m.price?.medianGapPct) && m.price.medianGapPct > 0).length,
      ratedCount: priceGaps.length,
      avgGapPct: mean(priceGaps),
    },
    products: {
      user: round(mean(list.map((m) => m.products?.user).filter((n) => Number.isFinite(n)))),
      competitorAvg: round(mean(list.map((m) => m.products?.competitor).filter((n) => Number.isFinite(n)))),
    },
    promoGapCount: list.filter((m) => m.promoGap).length,
  };
}

const analysisIdFrom = (analysisUrl) =>
  String(analysisUrl || "").split("/").filter(Boolean).pop();

function deriveMetrics(analysis) {
  const ai = analysis?.data?.result;
  const comparison = analysis?.data?.comparison;
  const aiPayload = analysis?.data?.payload;
  if (!ai && !comparison && !aiPayload) return null;

  const domains = getDomains(ai, comparison, aiPayload);
  const priceRows = getPriceRows(ai, comparison, aiPayload);
  const inventoryRows = getInventoryRows(ai, comparison, aiPayload);
  const catalogRows = getCatalogRows(ai, comparison, aiPayload);
  const seoRows = getSeoRows(ai, comparison, aiPayload);
  const trustRows = getTrustRows(ai, comparison, aiPayload);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const businessType = inferBusinessType(comparison, aiPayload);
  const collectionRows = toCollectionChartRows(matchups);

  const scores = buildCompetitiveScores({
    catalogRows,
    inventoryRows,
    priceRows,
    seoRows,
    trustRows,
    collectionRows,
  });
  const userScore = weightedScore(scores.user, businessType);
  const competitorScore = weightedScore(scores.competitor, businessType);

  const pick = (rows, domain, idx) =>
    rows.find((r) => r.domain === domain) || rows[idx] || {};
  const userPrice = pick(priceRows, domains.user, 0);
  const compPrice = pick(priceRows, domains.competitor, 1);
  const userInv = pick(inventoryRows, domains.user, 0);
  const compInv = pick(inventoryRows, domains.competitor, 1);
  const userCat = pick(catalogRows, domains.user, 0);
  const compCat = pick(catalogRows, domains.competitor, 1);
  const userTrust = pick(trustRows, domains.user, 0);
  const compTrust = pick(trustRows, domains.competitor, 1);

  const matched = collectMatchedProducts(matchups);
  const medianGapPct = median(matched.map((m) => num(m.gapPct)).filter((n) => n !== null));

  const assortment = collectionRows
    .map((r) => ({
      category: r.category,
      user: num(r.userProducts) ?? 0,
      competitor: num(r.competitorProducts) ?? 0,
      gap: (num(r.competitorProducts) ?? 0) - (num(r.userProducts) ?? 0),
    }))
    .filter((r) => r.user || r.competitor)
    .sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap))
    .slice(0, 5);

  return {
    userDomain: domains.user || null,
    competitorDomain: domains.competitor || null,
    score: { user: userScore, competitor: competitorScore },
    price: {
      userAvg: num(userPrice.averagePrice),
      compAvg: num(compPrice.averagePrice),
      currency: userPrice.currency || compPrice.currency || "",
      matchedCount: matched.length,
      medianGapPct,
    },
    inStock: {
      user: num(userInv.inStockRate),
      competitor: num(compInv.inStockRate),
      userCount: num(userInv.inStockCount),
      userTotal: (num(userInv.inStockCount) ?? 0) + (num(userInv.outOfStockCount) ?? 0) || null,
      compCount: num(compInv.inStockCount),
      compTotal: (num(compInv.inStockCount) ?? 0) + (num(compInv.outOfStockCount) ?? 0) || null,
    },
    products: {
      user: num(userCat.uniqueProducts ?? userCat.productsDetected ?? userPrice.pricedProducts),
      competitor: num(compCat.uniqueProducts ?? compCat.productsDetected ?? compPrice.pricedProducts),
    },
    promoGap: !!(compTrust.discountMessagingDetected && !userTrust.discountMessagingDetected),
    assortment,
  };
}

export default function useDashboardAnalytics(competitors) {
  const [state, setState] = useState({ byDomain: {}, aggregate: null, loading: true });

  // Stable dependency: the set of analysis URLs we'd fetch.
  const key = (competitors || [])
    .map((c) => `${c.domain}:${c.analysisUrl || ""}`)
    .join("|");

  useEffect(() => {
    const list = (competitors || []).filter((c) => c.analysisUrl);
    if (!list.length) {
      setState({ byDomain: {}, aggregate: null, loading: false });
      return;
    }

    let alive = true;
    setState((s) => ({ ...s, loading: true }));

    Promise.all(
      list.map(async (c) => {
        try {
          const id = analysisIdFrom(c.analysisUrl);
          const res = await api.get(`/analysis/${id}`);
          const analysis = res.data?.analysis || res.data;
          return [c.domain, deriveMetrics(analysis)];
        } catch {
          return [c.domain, null];
        }
      })
    ).then((entries) => {
      if (!alive) return;
      const byDomain = {};
      entries.forEach(([domain, metrics]) => {
        if (metrics) byDomain[domain] = metrics;
      });
      const aggregate = aggregateMetrics(Object.values(byDomain));
      setState({ byDomain, aggregate, loading: false });
    });

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}
