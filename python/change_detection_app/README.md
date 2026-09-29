# Same-Site Change Detection (change_detection_v1)

The 4th sub-app: compares two merged snapshots (`site_snapshot_v2`) of the
SAME site taken at different times (e.g. weekly) and reports meaningful
changes with severity scoring - so your pipeline only spends AI tokens when
something actually happened.

## What it detects

- Catalog: products added / removed
- Products: price changes (threshold-based), sales started/ended, stock
  in/out, listing-rank moves, renames, description changes, variant counts
- Collections: assortment size and price-floor shifts
- SaaS: pricing plans added/removed, plan price changes (critical severity)
- Site: platform / business-model change, navigation labels, categories
- Homepage: hero-message changes, feature toggles

## Output

```json
{
  "schemaVersion": "change_detection_v1",
  "domain": "shop.pk",
  "overallSeverity": "high",
  "changeScore": 72,
  "shouldSendToAI": true,
  "summary": { "totalChanges": 9, "changesByType": {"price_change": 4} },
  "changes": [ { "type": "price_change", "severity": "high", "product": {}, "oldValue": 1000, "newValue": 1200, "changePercent": 20 } ]
}
```

## Weekly workflow

1. Analyze the same pages weekly (analyzer outputs are auto-named and never overwritten)
2. Merge each week's pages: `python competitor_merger_app/main.py <files> -o week25.json`
3. Diff: `python main.py week24.json week25.json`
4. If `shouldSendToAI` is true, feed `changes` + the current comparison to OpenAI via `openai_insights.py`

## CLI

```bash
python main.py previous_snapshot.json current_snapshot.json [-o changes.json] [--price-threshold 5] [--min-severity-ai medium]
```

## API

```bash
uvicorn api:app --reload --port 8003
POST /diff-snapshots  { "previousSnapshot": {...}, "currentSnapshot": {...}, "settings": {...} }
```

Also available on the unified API: `POST /api/v1/diff-snapshots`.
(The older `POST /api/v1/diff-comparisons` still diffs two comparison outputs.)

## Settings

`priceChangeThresholdPercent` (5), `bigPriceChangePercent` (15),
`rankChangeThreshold` (3), `textSimilarityThreshold` (0.75),
`ignoreLowChanges` (false), `minimumSeverityForAI` ("medium").

## Tests

```bash
python tests/test_detector.py
```
