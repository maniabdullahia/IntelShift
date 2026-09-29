# Competitor Intelligence JSON Merger (site_snapshot_v2)

Merges page-analysis JSONs from the Website Analyzer into one clean, OpenAI-ready
`site_snapshot` per site (your site or a competitor). The snapshot is the input
for the Competitor Comparison app.

Works for any site type (ecommerce, SaaS, business, content) and any page type
(homepage, collection, product, blog, service, general).

## What the merger does

- Dedupes products across pages by productUrl → handle → productId → name; when the
  same product appears on several pages, the richer page type wins (product > collection > homepage)
- Normalizes every product into one canonical schema, including legacy homepage-card
  shape (`title/url/image/currentPrice/comparePrice`) → `price{currency, current, compareAt, isOnSale, discountPercent}`
- Preserves the analyzer's page-type summaries (`homepage`, `collectionSummary`, …) as
  `pagesAnalyzed[].summary`, plus `features`, `metrics`, and `warnings`
- Builds `site` intelligence: siteName, siteType, businessCategory, positioning,
  `catalog` (price range, coverage, on-sale, stock, categories, vendors),
  `collections`, `navigation`, `homepageFeatures`/`homepageMetrics`
- Strips internal/heavy keys (`_html`, `_raw_product`, `responseHeaders`, any `_`-prefixed key),
  converts description HTML to text, truncates long text
- Warns on mixed domains, duplicate page URLs, and failed pages (`quality.warnings`);
  reports page coverage (`quality.coverage`)

## Snapshot layout

```json
{
  "schemaVersion": "site_snapshot_v2",
  "generatedAt": "...",
  "site": { "domain": "...", "siteName": "...", "platform": "...", "siteType": "ecommerce", "catalog": {}, "collections": [], "navigation": {} },
  "pagesAnalyzed": [ { "url": "...", "pageType": "...", "seo": {}, "content": {}, "ecommerce": {}, "summary": {}, "features": {}, "metrics": {} } ],
  "products": [ { "name": "...", "productUrl": "...", "price": {}, "availability": {}, "sourcePages": [] } ],
  "quality": { "warnings": [], "coverage": {}, "openAIReady": true }
}
```

## CLI usage

```bash
python main.py "path/to/json-folder" -o site_snapshot.json
python main.py homepage.json collection.json product.json -o site_snapshot.json
```

## API usage

```bash
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

Preferred SaaS endpoint (JSON body in, JSON out):

```http
POST /merge
{ "pages": [ { ...page analysis JSON... }, { ... } ] }
```

Legacy/testing endpoint (multipart file upload, form field `files`):

```http
POST /merge-files
```

## Tests

```bash
python -m pytest tests/ -q
```

Sample inputs live in `input/` (Rivaj + Sivanna analyzer outputs); a sample merged
snapshot is in `output/sivanna_snapshot_v2.json`.
