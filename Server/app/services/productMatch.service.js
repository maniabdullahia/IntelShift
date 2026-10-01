// productMatch.service.js — AI product matching for the plans that include it.
//
// Growth ("collections_products") and Pro ("complete_site") pair PRODUCTS, not
// just collections. The pairing is done by AI (python comparison_engine/
// ai_product_match.py): within every mapped collection pair, the model picks the
// like-for-like competitor product for each of the user's products (or none).
// The AI matches are written into the comparison's existing `productMatching`
// slots, so the analysis UI and the AI insights payload use them unchanged.
//
// Fail-open throughout: any error leaves the comparison exactly as it was.

import pythonApi from "../../api/python.api.js";

const PRODUCT_PAIRING_SCOPES = new Set(["collections_products", "complete_site", "full"]);
const MAX_PAIRS = Number(process.env.AI_MATCH_MAX_PAIRS) || 12;

export const planAllowsProductPairing = (plan) =>
    PRODUCT_PAIRING_SCOPES.has(String(plan?.limits?.pairingScope || "").toLowerCase());

const pairKey = (m, i) =>
    `${m?.userCollection?.url || m?.userCollection?.title || i}|${m?.competitorCollection?.url || m?.competitorCollection?.title || i}`;

/**
 * Run AI matching over every collection matchup in a comparison and inject the
 * results in place. Returns { pairs, matched } for logging.
 */
export const applyAiProductMatches = async (comparison, { post = (url, body, cfg) => pythonApi.post(url, body, cfg) } = {}) => {
    const blocks = comparison?.oneToOneComparison?.competitors;
    if (!Array.isArray(blocks) || !blocks.length) return { pairs: 0, matched: 0 };

    const jobs = [];
    for (const block of blocks) {
        (block.collectionMatchups || []).forEach((m, i) => {
            const pm = m?.productMatching || {};
            // With local matching off, every product sits in the unmatched lists.
            const userProducts = [...(pm.matches || []).map((x) => x.userProduct), ...(pm.userUnmatchedProducts || [])];
            const competitorProducts = [...(pm.matches || []).map((x) => x.competitorProduct), ...(pm.competitorUnmatchedProducts || [])];
            if (!userProducts.length || !competitorProducts.length) return;
            jobs.push({
                block, matchup: m,
                pair: {
                    key: pairKey(m, i),
                    category: m.category || null,
                    currency: userProducts.find((p) => p?.currency)?.currency || null,
                    userProducts, competitorProducts,
                },
            });
        });
    }
    if (!jobs.length) return { pairs: 0, matched: 0 };

    // Largest overlaps first — they carry the most like-for-like signal.
    jobs.sort((a, b) => (b.pair.userProducts.length + b.pair.competitorProducts.length) - (a.pair.userProducts.length + a.pair.competitorProducts.length));
    const run = jobs.slice(0, MAX_PAIRS);

    let results = [];
    try {
        const res = await post("/v1/ai-product-matches", { pairs: run.map((j) => j.pair) }, { timeout: 600000 });
        results = res.data?.results || [];
    } catch (err) {
        console.warn("AI product matching skipped:", err?.message || err);
        return { pairs: run.length, matched: 0, error: true };
    }

    let matched = 0;
    const touched = new Set();
    run.forEach((job, idx) => {
        const pm = results[idx]?.productMatching;
        if (!pm || pm.source !== "ai") return;
        job.matchup.productMatching = { ...pm, matchingMethod: "ai" };
        matched += pm.matchedProductCount || 0;
        touched.add(job.block);
    });

    // Roll the AI pairs up into each competitor's catalog-wide summary.
    for (const block of touched) {
        const all = (block.collectionMatchups || []).flatMap((m) => (m.productMatching?.matchingMethod === "ai" ? m.productMatching.matches || [] : []));
        const gaps = all.map((m) => m.priceGap?.percentVsUser).filter((g) => typeof g === "number").sort((a, b) => a - b);
        const median = gaps.length ? (gaps.length % 2 ? gaps[(gaps.length - 1) / 2] : (gaps[gaps.length / 2 - 1] + gaps[gaps.length / 2]) / 2) : null;
        block.catalogWideProductMatching = {
            ...(block.catalogWideProductMatching || {}),
            description: "AI-matched like-for-like product pairs within your mapped collections.",
            matchingMethod: "ai",
            matchedProductCount: all.length,
            medianPriceGapPercentVsUser: median == null ? null : Math.round(median * 100) / 100,
            topMatches: [...all].sort((a, b) => b.confidence - a.confidence).slice(0, 25),
        };
    }
    return { pairs: run.length, matched };
};

export default { planAllowsProductPairing, applyAiProductMatches };
