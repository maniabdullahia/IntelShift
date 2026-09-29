# Website Analyzer API Guide

This project now supports both:

1. CLI usage through `main.py`
2. API usage through `api.py`

## Install

```bash
pip install -r requirements.txt
```

If Playwright is used by your crawler, also run:

```bash
playwright install
```

## Run API Locally

```bash
uvicorn api:app --reload --port 8001
```

## Test Health Endpoint

Open:

```text
http://localhost:8001/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "website-analyzer-api"
}
```

## Analyze One URL

Endpoint:

```text
POST http://localhost:8001/analyze
```

Body:

```json
{
  "url": "https://example.com"
}
```

## Analyze Multiple URLs

Endpoint:

```text
POST http://localhost:8001/analyze/batch
```

Body:

```json
{
  "urls": [
    "https://example.com",
    "https://example.com/products/product-name",
    "https://example.com/collections/category-name"
  ],
  "continue_on_error": true
}
```

## React Example

```js
const res = await fetch("http://localhost:8001/analyze", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    url: "https://example.com",
  }),
});

const data = await res.json();
console.log(data);
```

## Recommended Local Setup

```text
React frontend: http://localhost:3000
Website Analyzer API: http://localhost:8001
Merger API: http://localhost:8000
```
