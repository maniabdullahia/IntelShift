# Competitor Comparison App v5

A deterministic, vertical-agnostic competitor comparison engine for your React SaaS.

## What it does

- Compares user website vs one or more competitors (merged `site_snapshot_v2` JSONs from the merger app)
- Works across ALL ecommerce verticals (cosmetics, appliances, sports, clothing, electronics, home, toys, ...) via a broad category taxonomy with plural stemming
- Like-for-like matching only: products are gated by inferred category (a blusher can never match a lipstick), marketing adjectives ("matte", "premium", "waterproof") never drive matches, and each site's brand tokens are detected dynamically and excluded
- Prices compared relatively (log-ratio, same currency only) - no absolute thresholds; cross-currency comparisons are flagged and suppressed
- Also supports SaaS (pricing pages) and services/business sites via page-intent matching

## Key output modules (comparison_engine_v5)

- `rankedInsights` - deterministic, evidence-backed insights (price positioning on matched products, assortment gaps, category gaps, promo pressure, content depth, trust, SEO)
- `categoryCoverageComparison` - canonical category x site matrix with counts + price stats; `userGapCategories` / `userExclusiveCategories`
- `oneToOneComparison` - matched collections + matched product pairs (with confidence tiers, price gaps, positioning signals) + catalog-wide matching
- `saleAndDiscountComparison` - promo intensity per site (on-sale rate, discount depth)
- `contentDepthComparison` - description/image/variant coverage per site
- `priceComparison` - with `sameCurrency` guard and warning
- homepage / navigation / page-match / SEO / merchandising / trust modules
- `aiAnalysisInput` + `openAiEvidencePack` - AI-ready packs (computed once, shared)

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Docs: http://127.0.0.1:8000/docs

## API

```txt
POST /api/compare        { "userWebsite": {...}, "competitors": [{...}], "options": {...} }
POST /api/compare-one    { "userWebsite": {...}, "competitorWebsite": {...} }
```

## Tests

```bash
python tests/test_comparison_engine.py     # or python -m pytest tests/ -q
```

Sample output from real data: `output/comparison_v5_sivanna_vs_gabrini.json`.
