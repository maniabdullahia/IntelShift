import { test } from "node:test";
import assert from "node:assert/strict";
import { applyAiProductMatches, planAllowsProductPairing } from "../app/services/productMatch.service.js";

const prod = (name, price) => ({ name, priceValue: price, currency: "PKR", productUrl: `https://x/${name}` });

const comparison = () => ({
    oneToOneComparison: {
        competitors: [{
            catalogWideProductMatching: { matchedProductCount: 0 },
            collectionMatchups: [
                { category: "kitchen", userCollection: { url: "u/kitchen" }, competitorCollection: { url: "c/kitchen" },
                  productMatching: { matches: [], userUnmatchedProducts: [prod("Air Fryer 5L", 25000)], competitorUnmatchedProducts: [prod("Digital Fryer 5 Litre", 24000)] } },
                { category: "empty", userCollection: { url: "u/e" }, competitorCollection: { url: "c/e" },
                  productMatching: { matches: [], userUnmatchedProducts: [], competitorUnmatchedProducts: [prod("x", 1)] } },
            ],
        }],
    },
});

test("plan gate: only Growth / Pro scopes pair products", () => {
    assert.equal(planAllowsProductPairing({ limits: { pairingScope: "collections" } }), false);
    assert.equal(planAllowsProductPairing({ limits: { pairingScope: "collections_products" } }), true);
    assert.equal(planAllowsProductPairing({ limits: { pairingScope: "complete_site" } }), true);
    assert.equal(planAllowsProductPairing(null), false);
});

test("AI matches are injected into productMatching and the summary", async () => {
    const c = comparison();
    let sent;
    const post = async (url, body) => {
        sent = body;
        return { data: { results: [{ key: body.pairs[0].key, productMatching: {
            source: "ai", matchedProductCount: 1,
            matches: [{ confidence: 0.9, priceGap: { percentVsUser: -4 }, userProduct: prod("Air Fryer 5L", 25000), competitorProduct: prod("Digital Fryer 5 Litre", 24000) }],
            userUnmatchedProducts: [], competitorUnmatchedProducts: [],
        } }] } };
    };
    const out = await applyAiProductMatches(c, { post });
    assert.equal(sent.pairs.length, 1); // empty-side pair skipped
    assert.deepEqual(out, { pairs: 1, matched: 1 });
    const block = c.oneToOneComparison.competitors[0];
    assert.equal(block.collectionMatchups[0].productMatching.matchingMethod, "ai");
    assert.equal(block.catalogWideProductMatching.matchedProductCount, 1);
    assert.equal(block.catalogWideProductMatching.medianPriceGapPercentVsUser, -4);
});

test("Python failure leaves the comparison untouched", async () => {
    const c = comparison();
    const before = JSON.stringify(c);
    const out = await applyAiProductMatches(c, { post: async () => { throw new Error("down"); } });
    assert.equal(out.error, true);
    assert.equal(JSON.stringify(c), before);
});
