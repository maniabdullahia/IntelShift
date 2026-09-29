# Competitor Comparison Engine API v4

This version is designed for a React app: **JSON input, JSON output**. No JSON file upload is required.

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

```txt
http://127.0.0.1:8000/docs
```

## Main endpoint

```txt
POST /api/compare
Content-Type: application/json
```

### Request body

```json
{
  "userWebsite": { "schemaVersion": "site_snapshot_v1", "site": {}, "pagesAnalyzed": [], "products": [] },
  "competitors": [
    { "schemaVersion": "site_snapshot_v1", "site": {}, "pagesAnalyzed": [], "products": [] }
  ],
  "options": {
    "includeOpenAiEvidencePack": true,
    "includeProductDetails": true,
    "includePageContent": true,
    "includeSectionDetails": true,
    "includeOneToOneComparison": true,
    "maxProductsPerSite": null,
    "maxSectionsPerSite": null
  }
}
```

### Response body

Returns JSON directly:

```json
{
  "schemaVersion": "comparison_engine_v3",
  "summary": {},
  "sites": [],
  "catalogComparison": {},
  "productDetailComparison": {},
  "oneToOneComparison": {},
  "openAiEvidencePack": {}
}
```

## 1-vs-1 endpoint

For one competitor only:

```txt
POST /api/compare-one
```

```json
{
  "userWebsite": {},
  "competitorWebsite": {},
  "options": {}
}
```

## React fetch example

```js
export async function compareWebsites(userWebsite, competitors) {
  const res = await fetch("http://127.0.0.1:8000/api/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      userWebsite,
      competitors,
      options: {
        includeOpenAiEvidencePack: true,
        includeProductDetails: true,
        includePageContent: true,
        includeSectionDetails: true,
        includeOneToOneComparison: true
      }
    })
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return await res.json();
}
```

## Smaller dashboard response

For dashboard only, reduce response size:

```json
{
  "userWebsite": {},
  "competitors": [],
  "options": {
    "includeOpenAiEvidencePack": false,
    "includeProductDetails": false,
    "includePageContent": true,
    "includeSectionDetails": true,
    "includeOneToOneComparison": true,
    "maxProductsPerSite": 20,
    "maxSectionsPerSite": 15
  }
}
```

## Recommended app flow

```txt
React app has merged JSONs
↓
POST /api/compare
↓
Receive deterministic comparison JSON
↓
Show selected dashboard sections
↓
Send openAiEvidencePack to OpenAI for narrative insights if needed
```
