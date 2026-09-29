# Unified CompIntel API

This file adds one JSON-in / JSON-out API gateway over the existing tools:

1. website_analyzer_app
2. competitor_merger_app
3. comparison_app
4. weekly comparison diff gate

It does not replace the existing CLI tools. Your CMD/local JSON file workflow can stay the same.

## Install

From inside the `CompIntel` folder:

```bash
pip install -r requirements_unified_api.txt
playwright install
```

## Run

```bash
uvicorn compintel_api:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Security (auth + rate limiting)

All endpoints (except `/health` and `/docs`) support API-key auth and per-IP
rate limiting via environment variables - no code changes needed:

```bash
set COMPINTEL_API_KEY=your-long-random-secret     # enables auth
set RATE_LIMIT_PER_MINUTE=60                      # normal endpoints (default 60)
set HEAVY_RATE_LIMIT_PER_MINUTE=10                # analyze/full-run/generate-insights (default 10)
```

Clients must send the key in a header:

```js
fetch("http://localhost:8000/api/v1/compare-sites", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": "your-long-random-secret" },
  body: JSON.stringify(payload),
})
```

If `COMPINTEL_API_KEY` is not set, auth is disabled (dev mode) and a warning
is printed at startup. Rate limiting is always active. Responses: `401` for a
bad/missing key, `429` (with `Retry-After`) when the limit is hit.

IMPORTANT: if your React app calls this API directly from the browser, the key
is visible to users in the bundle/network tab. For production, route calls
through your own backend (React -> your server -> CompIntel API) so the key
stays server-side.

## Endpoints

### Health

```http
GET /health
```

### Analyze one page

```http
POST /api/v1/analyze-page
```

Body:

```json
{
  "url": "https://eveline.pk/collections/foundations"
}
```

### Analyze multiple pages

```http
POST /api/v1/analyze-pages
```

Body:

```json
{
  "urls": [
    "https://eveline.pk/",
    "https://eveline.pk/collections/foundations",
    "https://eveline.pk/collections/eyeshadow-palettes"
  ],
  "continueOnError": true
}
```

### Merge page JSON into one site snapshot

```http
POST /api/v1/merge-site
```

Body:

```json
{
  "pages": [
    { "...": "homepage analysis JSON" },
    { "...": "collection analysis JSON" }
  ]
}
```

### Compare user site vs competitors

```http
POST /api/v1/compare-sites
```

Body:

```json
{
  "userWebsite": { "...": "merged user snapshot" },
  "competitors": [
    { "...": "merged competitor snapshot" }
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

### Compare one user site vs one competitor

```http
POST /api/v1/compare-one
```

Body:

```json
{
  "userWebsite": { "...": "merged user snapshot" },
  "competitorWebsite": { "...": "merged competitor snapshot" }
}
```

### Build OpenAI insights request (recommended for AI insights)

```http
POST /api/v1/openai-insights-request
```

Body:

```json
{
  "comparison": { "...": "full comparison JSON from /api/v1/compare-sites" },
  "options": { "model": "gpt-4o", "temperature": 0.2 }
}
```

Returns a COMPLETE OpenAI Chat Completions request: system prompt (evidence-only
rules), compact evidence payload (~85% smaller than the raw comparison), and a
STRICT `json_schema` response format (`ci_insights_v1`) so OpenAI can only return
dashboard-ready JSON (executiveSummary, competitorProfiles, insights with
evidencePath, dashboardCards, recommendedActions, dataNotes).

Send `openaiRequest` from the response directly to
`https://api.openai.com/v1/chat/completions` with your API key.

### Generate insights server-side (optional)

```http
POST /api/v1/generate-insights
```

Same body. The API server calls OpenAI itself - requires `OPENAI_API_KEY` in the
server environment and `pip install openai`. Returns parsed `ci_insights_v1`
JSON + token usage + validation result.

### Same-site change detection (weekly monitoring)

```http
POST /api/v1/diff-snapshots
```

Body:

```json
{
  "previousSnapshot": { "...": "site_snapshot_v2 from last week" },
  "currentSnapshot": { "...": "site_snapshot_v2 from this week" },
  "settings": { "priceChangeThresholdPercent": 5, "minimumSeverityForAI": "medium" }
}
```

Detects products added/removed, price + sale changes, stock, rank moves,
collection shifts, SaaS plan changes, navigation and homepage-messaging
changes. Returns `changeScore`, `overallSeverity` and `shouldSendToAI`.

### Weekly diff gate (comparison outputs)

```http
POST /api/v1/diff-comparisons
```

Body:

```json
{
  "previousComparison": { "...": "last week comparison output" },
  "currentComparison": { "...": "this week comparison output" },
  "settings": {
    "minimumSeverityForAI": "medium",
    "priceChangeThresholdPercent": 5,
    "rankChangeThreshold": 3,
    "ignoreLowChanges": true
  }
}
```

### Full end-to-end test

```http
POST /api/v1/full-run
```

Body:

```json
{
  "userPages": [
    "https://eveline.pk/",
    "https://eveline.pk/collections/foundations",
    "https://eveline.pk/collections/eyeshadow-palettes"
  ],
  "competitorPages": [
    "https://sivanna.com.pk/",
    "https://sivanna.com.pk/collections/foundation",
    "https://sivanna.com.pk/collections/eyeshadow"
  ],
  "previousComparison": null,
  "continueOnError": true
}
```

## Recommended React flow

For production, call endpoints step-by-step:

1. `/api/v1/analyze-pages` for user pages
2. `/api/v1/merge-site` for user snapshot
3. `/api/v1/analyze-pages` for competitor pages
4. `/api/v1/merge-site` for competitor snapshot
5. `/api/v1/compare-sites`
6. `/api/v1/diff-comparisons` if weekly insights are enabled

For quick local testing, use `/api/v1/full-run`.

---

## AI Payload Builder in Unified API

The unified API now includes the compact AI payload builder. This lets React send a full comparison JSON and receive a smaller OpenAI-ready JSON response.

### Build AI Payload Only

```http
POST /api/v1/build-ai-payload
```

Request:

```json
{
  "comparison": {},
  "options": {
    "includeStats": true
  }
}
```

Response:

```json
{
  "success": true,
  "data": {},
  "stats": {
    "originalApproxCharacters": 0,
    "aiPayloadApproxCharacters": 0,
    "reductionPercent": 0,
    "sourceSchemaVersion": "comparison_engine_v4",
    "aiPayloadSchemaVersion": "ai_payload_v1"
  }
}
```

Use `data` as the JSON payload to send to OpenAI.

### Compare + AI Payload

```http
POST /api/v1/compare-sites-ai-payload
POST /api/v1/compare-one-ai-payload
```

These endpoints return both:

```json
{
  "comparison": {},
  "aiPayload": {},
  "stats": {}
}
```

### Full Run + AI Payload

```http
POST /api/v1/full-run
```

Add:

```json
{
  "includeAiPayload": true,
  "aiPayloadOptions": {
    "includeStats": true
  }
}
```

The response will include:

```json
{
  "comparison": {},
  "aiPayload": {},
  "aiPayloadStats": {}
}
```
