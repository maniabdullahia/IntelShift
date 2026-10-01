# IntelShift — Review & Implementation Report (Oct 2026)

**Branch:** `claude/upbeat-thompson-dtvibe` (based on `5a9328e`) · **Scope:** `Server/`, `python/`, `Client/`.
`static/` (marketing site) and `Admin/` were intentionally not touched.

This report is written so another person or agent (e.g. Claude Cowork) can pick the work up cold:
what changed, why, how it was verified, what must be configured before deploying, and what is
still open.

---

## 1. Before you deploy — required configuration

These are **operational steps**. Without them, some of the new protections stay inactive or the app
won't reach the Python service.

| Where | Setting | Why |
|---|---|---|
| Python service env | `COMPINTEL_SERVICE_KEYS=<long random secret>` | Turns on API-key auth for the Python API (it was fully open). |
| `Server/.env` | `PYTHON_API_KEY=<same secret>` | Node sends it as `X-API-Key`. Service keys are never rate-limited. |
| `Server/.env` | `PYTHON_SERVER_URL=http://127.0.0.1:8000/api` | **Must include `/api`**. The old `.env.example` and PM2 config had wrong values (`…:8000` / `/python`). |
| `Server/.env` | `TRUST_PROXY=1` (behind nginx) | So per-user/IP rate limits see the real client IP. |
| `Server/.env` | `REDIS_HOST / REDIS_PORT / REDIS_PASSWORD` | Redis is now env-driven. Use a password in production. |
| Python env | `MAX_BROWSERS=3` (tune to RAM: ~200 MB each) | Caps concurrent Chromium instances. |
| PM2 | `pm2 delete all && pm2 start ecosystem.config.cjs --env production` | The config now includes the **recon worker** (it was missing, so onboarding would hang in "recon"). |
| Network | Keep the Python API on localhost / private network only | Auth is now on, but it should still not be public. |

Optional: `BUSINESS_TYPE_ALLOWLIST=gymshark,khaadi` releases stores wrongly routed to Enterprise ·
`ENABLE_DEBUG_ROUTES=1` re-enables the admin-only `/api/debug-fetch` · `LOG_REQUEST_BODIES=1` logs
**redacted** bodies (local debugging only) · rate limits: `CRAWL_/HEAVY_/MATCH_/AUTH_RATE_LIMIT_PER_MIN`.
All are documented in `Server/.env.example` and `python/website_analyzer_app/.env.example`.

No data migration is needed. New Mongo fields (`Competitor.storeProfile`, `Competitor.accessStatus`,
`Workspace.productMatchDecisions`) are optional and default to empty.

---

## 2. What changed

### 2.1 Security & logging (all fixed)

| Issue | Fix | Files |
|---|---|---|
| Every request body (incl. **passwords**) was logged | Bodies never logged by default; opt-in logging is redacted + truncated | `Server/index.js`, `Server/utils/redact.js` |
| Other sensitive logs: social-login payloads, decoded JWTs, full user docs, full Paddle payloads, Playwright headers with `cf_clearance` cookies / storefront tokens | Reduced to ids/statuses | `auth.service.js`, `social.middleware.js`, `workspace.controller.js`, `webhooks/paddle/*`, `fetcher.py` |
| Crawler/AI routes had no auth: `/url-tree`, `/collection-count`, `/validate-url`, `/detect-stores`, `/suggest-competitors`, `/validate-site` | Require login + per-user rate limits | `Server/app/routes/routes.js`, `middleware/rateLimit.middleware.js` |
| `/debug-fetch` returned raw HTML of any URL, publicly | Admin-only and off unless `ENABLE_DEBUG_ROUTES=1` | `routes.js` |
| **SSRF**: user URLs like `http://127.0.0.1:27017` or `169.254.169.254` were fetched | Guard in Node (all mutating requests) and Python (API boundary + every fetcher, re-checked after redirects) | `Server/utils/urlGuard.js`, `python/.../level1_detector/net_guard.py`, `compintel_api.py` |
| Python API auth was commented out | Enabled; Node sends the service key | `compintel_api.py`, `api_security.py`, `Server/api/python.api.js` |
| Login/register/reset had no brute-force limit | 10/min per IP | `routes.js` |
| Unbounded Chromium launches (OOM risk) | `MAX_BROWSERS` semaphore around all 6 launch sites | `net_guard.py`, `fetcher.py`, `catalog_enrich.py` |

A bug found during integration testing: `compintel_api.py` was silently importing an **older copy** of
`api_security.py` from `comparison_app/` because of `sys.path` order. That copy has no service keys and a
10/min per-IP heavy limit, which would have throttled the backend. It now loads the root module by path.

### 2.2 Deployment & reliability

- `ecosystem.config.cjs` rewritten: adds `recon-worker`, one absolute `PYTHON_SERVER_URL` for every process,
  `node` interpreter (`tsx` is dev-only), restart backoff. The stale `deploy` block (pointed at another repo
  and `ecosystem.config.js`) was removed.
- `npm start` → `node bootstrap.js`; `npm test` → `node --test test/*.test.js`.
- Competitors stuck in `Processing` (API restarted mid-scan) are reset after `STALE_SCAN_MINUTES` (180).
  Before this, the scheduler skipped that workspace **forever**.
- Rescan wrote `scanStatus: 'pending'` (lowercase, not in the enum) to *all* pages, including pages queued
  for removal. Now `"Pending"`, and only on the pages being queued.
- Add competitor: plan-limit + duplicate checks run **before** the multi-minute readiness check, and
  duplicates are detected by domain (`www.x.com` = `x.com`).
- Route loader for `/onboarding` no longer shows the router's raw error page when the API is unreachable.

### 2.3 Step 1 — Website accessibility check

`python/website_analyzer_app/level1_detector/site_validator.py`

- Critical stages (unchanged gate): **homepage → collection → product**. Failing any of them means the
  store can't be analysed ("Unable to Analyse"), as before.
- New journey stages (fast HTTP, run in parallel): **search** (form/link, or Shopify/Woo search URL),
  **cart** (cart link → `/cart` → Shopify `/cart.js`), **checkout** (`/checkout` reachable; an empty-cart
  redirect to `/cart` counts as reachable — we never place orders).
- Result `accessStatus`: `complete` | `incomplete` (search/cart/checkout **blocked or erroring**; "not
  available" search doesn't count) | `unverified` (the check itself timed out; the competitor is added but
  flagged, instead of silently passing as before).
- Product-page check tightened: a price alone no longer counts when the URL is shaped like a listing
  (`/collections/x`, `/product-category/x`, `/shop/x`).
- Removed the leftover `currencyDebug` block (it doubled Shopify requests on every validation).
- Fixed `_host()` using `.lstrip("www.")`, which stripped any leading `w`/`.` characters
  (`wearwild.com` → `earwild.com`).

### 2.4 Step 2 — Business type (Types 1–5)

`python/website_analyzer_app/level1_detector/business_type.py` (single source of truth;
`marketplace_gate.classify_scale` now delegates to it).

| Type | Label | Rule (first match wins) | Outcome |
|---|---|---|---|
| — | allowlisted | `BUSINESS_TYPE_ALLOWLIST` | skips 1–2 |
| 1 | Large Marketplace | known marketplace domain (Amazon, Daraz, eBay, Noon, Sephora…) · strong seller-structure marker ("become a seller", "seller center"…) **with** a ≥20k or uncountable catalog · ≥250k products | **Enterprise** |
| 2 | Global / Multinational Brand | known multinational (Nike, Adidas, Zara, H&M…) · ≥30 hreflang regional storefronts **and** ≥5k or uncountable catalog | **Enterprise** |
| 3 | General Marketplace | multi-brand (≥5 vendors or AI "multi_brand") **and** ≥3 industries · small multi-vendor shop with seller sign-up | continue |
| 4 | Niche / Category Marketplace | multi-brand, 1–2 industries | continue |
| 5 | Single-Brand Store | otherwise | continue |

Fixes compared with the old gate: Nike/Adidas/Zara were self-serve (now Enterprise, per your spec and
`LAUNCH_CHECKLIST.md` §4). Multi-brand stores with ≥40 vendors were blocked (now Types 3/4, continue).
The generic `"marketplace"` / `"/sellers/"` substrings no longer block brand stores. Generic labels like
`target.pk` / `jd…` no longer match on the label alone.

Competitor suggestions now exclude the **same** marketplace/multinational lists (fetched from Python via
`GET /api/v1/business-type/lists`) and use the owner's type: Types 3/4 compete with multi-brand stores,
Type 5 with brands.

### 2.5 Step 3 — Market & location (English only)

`python/website_analyzer_app/level1_detector/store_profile.py` + `site_validator._build_profile`

You asked whether there are other ways to find where a store actually serves. These are the signals now
used, strongest first:

- **Home country:** Shopify `/meta.json` (the store's own settings) → JSON-LD `Organization.address` →
  ccTLD (vanity TLDs like `.co/.io/.ai` ignored) → single-country currency → phone dialling code.
- **Delivery scope** (`domestic` / `selected` / `worldwide`): shipping-policy wording (`/policies/shipping-policy`,
  `/pages/shipping`, …, e.g. "we only ship within Pakistan", "we ship worldwide") → the **Shopify Markets
  country selector** (the countries the store actually sells to) → JSON-LD `shippingDestination` →
  hreflang regions.
- Output `store_market_v1`: `{ country, countryName, scope, shipsTo[], currency, confidence, signals[], evidence }`.
- **English only:** `<html lang>` plus an English stop-word ratio on visible text (lang attributes are often
  wrong). Non-English stores are rejected early (before slow renders) with `UNSUPPORTED_LANGUAGE`. If the
  store has an English hreflang alternate, the message points to it.
- Competitor suggestions use the detected home country ahead of the currency guess (a Pakistani store priced
  in USD is still searched as Pakistan).

### 2.6 Step 4 — Industry → Category → Subcategory

`Server/utils/taxonomy.js`

- A fixed taxonomy: 13 industries, 87 subcategories (Fashion, Beauty, Electronics, Home & Living,
  Appliances, Health, Sports, Baby & Kids, Food, Pets, Books, Automotive, Gifts).
- The AI picks a path **from the list only**, using categories, product types, titles and vendors. Its answer
  is validated and falls back to a deterministic keyword scorer. The same call returns `industries[]`
  (breadth, used for Type 3 vs 4) and `brandModel` (single vs multi-brand, used for Type 4/5 when vendors are
  unreadable).
- Competitor suggestions: the taxonomy path anchors the search phrase, adds a 15% "same category" weight to
  similarity ranking, and **drops candidates confidently in a different industry** (falls back if that would
  leave nothing).

The **store profile** (Steps 1–4 combined) is stored on `Competitor.storeProfile` and `accessStatus`.
That covers both the owner store (role `Owner`) and competitors. It is built in
`Server/app/services/siteReadiness.service.js` and cached for 6h by domain
(`storeProfile.service.js`). If the API restarted between validation and creation, the recon worker
rebuilds it in the background.

### 2.7 AI product matching (Growth & Pro)

The old fuzzy matcher stays **off** (it was unreliable). Pairing is now AI-driven:

- `python/comparison_app/comparison_engine/ai_product_match.py`: within each mapped collection pair, cheap
  scoring only **shortlists** about 6 candidates per product (including name-disjoint ones via price
  proximity). The AI then picks the like-for-like match or `null`, with a short reason. Enforced 1:1,
  confidence ≥ 0.6, ids outside the shortlist rejected, results cached by product-set hash (unchanged
  collections don't re-bill daily). No AI key or an AI error leaves products unmatched; it never falls back
  to fuzzy pairs.
- Runs automatically in the analysis worker for plans with `pairingScope` `collections_products` (Growth) or
  `complete_site` (Pro), before the insights payload is built. Matches land in the existing `productMatching`
  slots, so the UI and the AI report use them unchanged. Capped by `AI_MATCH_MAX_PAIRS` (12) per competitor.
- `POST /api/product-matches` (the manual "Suggest matches" card) is plan-gated **on the server** (it was
  UI-only) and AI-first. Accept/reject decisions are saved: `GET/POST /api/product-matches/decisions`.
- Model: the existing cheap-model helper (`ai_assist.py`: `gpt-4o-mini` / `claude-haiku-4-5`, per `AI_PROVIDER`).

### 2.8 Python execution review — improvements for different site types

How it works today: `fetch_html` tries requests → cloudscraper → Playwright, then platform detection routes to
the Shopify / WordPress / Wix / Unknown analyzers. Retries kick in for JS platforms and missing prices. This is
solid for Shopify/Woo. The weak spot was the **Unknown** analyzer (custom, headless, Next/Nuxt, Magento,
BigCommerce, Squarespace), which only read the DOM.

Changes:
- **Structured-data recovery** in the Unknown collection analyzer (`analyzers/unknown/structured_products.py`):
  JSON-LD `ItemList`/`Product` (exact price + currency) and hydration state (`__NEXT_DATA__`, `__NUXT__`,
  `__INITIAL_STATE__`, Apollo, JSON scripts). It fills missing prices/images on DOM products by URL and adds
  products the DOM missed. Recorded in `source.structuredData`.
- **"Fail loud" report gate**: `comparison.dataQuality.status` = `ok` | `partial` | `insufficient` per side
  (no pages, no products, price coverage < 85%, failed pages), plus each store's Step 1 access status. The
  analysis page shows a banner, and the AI report already receives `dataQuality`.
- Browser concurrency cap and SSRF guard (above).

Recommended next steps (not done):
1. Platform JSON adapters for **Squarespace** (`?format=json` on collection URLs, public) and **Magento 2**
   (public GraphQL `products(filter:{category_uid…})`).
2. Reuse one browser per worker with a fresh context per site, instead of launching Chromium for every
   fetch. This is faster and still isolates cookies (checklist §3).
3. Replace the ~250 `print()` calls with `logging` and levels.
4. Make golden replay truly offline (see §3).

### 2.9 Client

- Onboarding uses the server's verdict:
  - The Enterprise modal distinguishes "global brand" from "marketplace".
  - Non-English stores get a clear message.
  - The Focus step shows **"Here's how we read your store"**: type, market & delivery scope, category path,
    and access.
  - A toast appears when a competitor's journey is incomplete.
- The analysis page has a **read-quality banner** for partial/insufficient data.
- Suggested matches: AI-first, shows the AI's reason, decisions saved, and an upgrade message on 403.
  AI reasons are labelled in comparisons.
- **Code splitting:** main bundle 1,125 kB → 538 kB (159 kB gzipped).
- Sidebar inner components hoisted to module level (they were re-created every render, causing
  remounts/favicon flicker).

---

## 3. Verification performed

The container's network policy blocks outbound requests to stores, so **no live store was crawled**.
Everything else was run:

| Check | Result |
|---|---|
| Python pytest (4 suites) | **88 passed** (comparison 20, merger 13, analyzer 44, change-detection 11). New: `test_store_profile.py` (incl. an end-to-end `validate_site` against a stubbed Shopify store), `test_structured_products.py`, `test_ai_product_match.py`. The 2 previously failing comparison tests now opt into the fuzzy matcher explicitly. |
| Server `npm test` | **13 passed**: taxonomy, SSRF guard, redaction, rate limiter, AI-match injection. |
| Live Node → Python integration (local uvicorn) | Types 2/4/5 over HTTP, allowlist, SSRF 400, shared lists, AI-match no-key path, **API key auth** (no key/wrong key → 401, service key → 200, `/health` exempt, loopback unthrottled in dev). |
| Golden fixtures (`tools/golden_check.py verify`) | Fixtures 11, fields 137, failed 12. **Identical on the original commit**, so no regressions. 10 are Sivanna fixtures whose replay calls the live `products.json` (blocked here); 2 are a `WordPress / WooCommerce` label expectation drift. |
| Client | `npm run build` OK; ESLint 208 findings (was 207; all pre-existing style/compiler hints); headless Chromium smoke test of `/login`, `/register` and protected routes: correct redirects, **0 page errors**. |
| Server modules | `node --check` on all files; routes + workers import cleanly (stop only at the missing Mongo URI). |

---

## 4. Needs live verification (on a machine with Mongo + Redis + Python + keys)

1. Onboarding with 3–5 real stores per type: a Shopify brand (Type 5), a Pakistani multi-brand beauty store
   (Type 4), a general store (Type 3), nike.com (Type 2 → Enterprise modal), daraz.pk (Type 1).
2. Check the Focus-step profile card: country, delivery scope and category path look right.
3. A store with a blocked checkout shows "incomplete" (toast + report banner).
4. A Growth/Pro analysis logs `🤝 AI product matching: N pairs`; matches look like-for-like; decisions persist
   across reload.
5. `pm2 ls` shows 6 processes incl. `recon-worker`; a restart mid-scan recovers after `STALE_SCAN_MINUTES`.
6. Rate limits don't trip during a normal onboarding (tune the `*_RATE_LIMIT_PER_MIN` vars if they do).
7. Re-record the Sivanna golden fixtures with network so replay is fully offline.
8. Then run the golden-store suite in `LAUNCH_CHECKLIST.md` §2/§10. That is still the real go/no-go gate.

---

## 5. Open decisions & proposals (not changed)

- **Bot-protection wording vs tooling.** The app says IntelShift "respects bot protection and doesn't bypass
  it", but the fetcher uses `cloudscraper`, `playwright-stealth` and `--disable-blink-features=AutomationControlled`,
  and doesn't check robots.txt `Disallow`. Either soften the copy or remove the evasion and add robots
  checks. This is a legal/trust call, so it was left for you.
- **Proposed deletions** (per `CLAUDE.md`, proposed rather than deleted): `catalog_debug.json` (root debug
  dump); Stripe leftovers (`Server/app/controllers/subscription.controller.js` Stripe path,
  `Client/src/services/stripe.js`, `stripe` deps) if Paddle is the only billing; the four outdated
  `python/*_app/api_security.py` copies (only the root one is used by the unified API).
- Rate limiter is in-memory (fine for one API process; move to Redis if the API is scaled out).
- Node-side helper fetches (`getStoreProductTotal`, category reads) follow redirects without re-checking the
  target. Low risk because the entry URL is guarded and Python re-checks, but worth tightening.
- Lint backlog (~200, mostly unused vars) is cosmetic; clean up gradually.
- The taxonomy and the marketplace/multinational lists are curated. Extend them as real stores show gaps
  (`business_type.py`, `Server/utils/taxonomy.js`).

---

## 6. `LAUNCH_CHECKLIST.md` mapping

| Checklist item | Status after this work |
|---|---|
| §1 Rotate secrets / untrack `.env` | You've rotated keys; `git ls-files` shows no `.env`. |
| §2 Fail loud (extraction-quality gate) | **Implemented** (dataQuality status + banner); verify live. |
| §3 Cross-site cookie isolation | Each Playwright fetch already uses a fresh browser; unchanged. |
| §3 Competitor suggestion quality | Improved (business type, taxonomy filter, market country); verify live. |
| §4 Plan limits enforced | Competitor limit now checked first; product matching now server-enforced. |
| §4 Enterprise "contact us" path | **Implemented** for Types 1–2 (Nike/Daraz → modal). |
| §7 A failed page doesn't sink the run / observability | Stale-scan recovery, fail-open AI matching, safer logs. Uptime alerting still open. |

## 7. Commits

```
51531dd Fix Python API auth shadowing; forward store-profile signals to scale-check
46fddb3 Review fixes: realistic rate limits, conservative regional-storefront rule
988cd6a Client: store profile in onboarding, report read-quality banner, AI match UX, code splitting
a7e14ec Analyzer: structured-data recovery for custom/JS stores, report data-quality verdict, safe fetch logs
715b131 AI product matching for Growth/Pro
1d44aec Onboarding steps 1-4: journey check, Type 1-5 business type, market, English-only, taxonomy
87117e9 Deploy & reliability: PM2 recon worker, absolute Python URL, env-driven Redis, stale-scan recovery
eb7e3e4 Security: stop logging secrets, auth+rate-limit crawler routes, SSRF guard, Python API auth, browser cap
```
