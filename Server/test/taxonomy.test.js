import { test } from "node:test";
import assert from "node:assert/strict";
import { taxonomyFromKeywords, classifyTaxonomy, isValidPath, taxonomySimilarity, allPaths } from "../utils/taxonomy.js";

test("keyword fallback: cosmetics store → Beauty → Makeup", () => {
    const t = taxonomyFromKeywords({
        categories: ["Lipsticks", "Mascara", "Foundation", "Eyeliner", "Blush"],
        titles: ["Matte Lipstick Ruby", "Volume Mascara Black", "HD Foundation 30ml"],
    });
    assert.equal(t.industry, "Beauty");
    assert.equal(t.category, "Makeup");
    assert.equal(t.industryCount, 1);
});

test("keyword fallback: footwear store", () => {
    const t = taxonomyFromKeywords({ categories: ["Sneakers", "Running Shoes", "Trainers"], titles: ["Air Runner Sneaker"] });
    assert.equal(t.industry, "Fashion");
    assert.equal(t.category, "Footwear");
    assert.equal(t.subcategory, "Athletic Shoes");
});

test("keyword fallback: general store spans several industries", () => {
    const t = taxonomyFromKeywords({
        categories: ["Lipstick", "Mascara", "Air Fryer", "Blender", "Laptop", "Headphones", "Dresses", "Sofa", "Toys"],
    });
    assert.ok(t.industryCount >= 3, `got ${t.industries}`);
});

test("no signals → empty low-confidence profile", () => {
    const t = taxonomyFromKeywords({});
    assert.equal(t.industry, null);
    assert.equal(t.confidence, "low");
});

test("AI answer is validated against the fixed taxonomy", async () => {
    const good = await classifyTaxonomy({
        domain: "x.pk", categories: ["Gaming Laptops"],
        llm: async () => JSON.stringify({ primary: { industry: "Electronics", category: "Computing", subcategory: "Gaming PCs" }, industries: ["Electronics", "Made Up"], brandModel: "multi_brand" }),
    });
    assert.equal(good.source, "ai");
    assert.equal(good.path, "Electronics → Computing → Gaming PCs");
    assert.deepEqual(good.industries, ["Electronics"]); // invented industry dropped
    assert.equal(good.brandModel, "multi_brand");

    const bad = await classifyTaxonomy({
        domain: "x.pk", categories: ["Lipsticks", "Mascara"],
        llm: async () => JSON.stringify({ primary: { industry: "Beauty", category: "Cosmetics", subcategory: "Stuff" } }),
    });
    assert.equal(bad.source, "keywords"); // invalid path → fallback
    assert.equal(bad.industry, "Beauty");

    const thrown = await classifyTaxonomy({ domain: "x", categories: ["Sofa"], llm: async () => { throw new Error("down"); } });
    assert.equal(thrown.source, "keywords");
});

test("every path is valid and similarity is ordered", () => {
    for (const [i, c, s] of allPaths()) assert.ok(isValidPath(i, c, s));
    const a = { industry: "Beauty", category: "Makeup", subcategory: "Lips", industries: ["Beauty"] };
    assert.equal(taxonomySimilarity(a, a), 1);
    assert.equal(taxonomySimilarity(a, { ...a, subcategory: "Eyes" }), 0.85);
    assert.equal(taxonomySimilarity(a, { ...a, category: "Skincare" }), 0.6);
    assert.equal(taxonomySimilarity(a, { industry: "Electronics", industries: ["Electronics"] }), 0);
    assert.equal(taxonomySimilarity(a, { industry: null }), null);
});
