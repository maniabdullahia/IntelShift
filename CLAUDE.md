# IntelShift AI — project guide (for Claude Code)

Competitor-intelligence SaaS for e-commerce stores: track competitors' catalog,
pricing, promotions and site changes, with AI insights and alerts.

## Architecture (3 services + a static site)

- **`Client/`** — React 19 + Vite SPA. Tailwind utility classes + CSS variables,
  React Router (loaders + route guards), Zustand stores (`auth.store`,
  `workspace.store`). ES modules, `.jsx`.
- **`Server/`** — Node/Express API, **ES modules** (`"type":"module"`). BullMQ
  workers (recon, competitor, analysis, workspace, alert) on **Redis**, data in
  **MongoDB** (Mongoose), realtime via **socket.io** + Redis pub/sub. Entry:
  `Server/index.js`.
- **`python/`** — FastAPI gateway `compintel_api.py` orchestrating the analyzers
  (`website_analyzer_app`, `competitor_merger_app`, `comparison_app`,
  `change_detection_app`). Uses **Playwright** + cloudscraper to render/read
  stores. Runs on port **8000**; the Node server calls it over HTTP.
- **`Admin/`** — admin React app (worked on last; leave unless asked).
- **`static/`** — marketing site (branding/colors are final; don't restyle).

Data flow: Client → Server (Express) → Python analyzers (per-page analyze →
merge → compare) → results stored in Mongo → surfaced to Client. Capture-first
onboarding: URLs only → recon captures each store's catalog → user picks/maps
pages (or Pro auto-selects) → deep analysis.

## Running locally

Each service needs its own `.env` (NOT committed — see Security). Required infra:
**MongoDB**, **Redis** (port 6379), **Python 3 + Playwright browsers**, and valid
**OpenAI/Anthropic** keys. `AI_PROVIDER=openai|claude` selects the model provider.

- Server: `cd Server && npm install && npm run dev` (nodemon `index.js`).
- Client: `cd Client && npm install && npm run dev` (Vite).
- Python: `cd python && pip install -r requirements.txt && python -m playwright install && uvicorn compintel_api:app --reload --port 8000`.

If Redis is down you'll see `[redis] connection error` and realtime updates pause,
but the process no longer hard-crashes (see `Server/app/config/redis.js`).

## Testing & quality — IMPORTANT guardrails

- **Never run tests, seeders, or cleanup scripts against the production database.**
  Use a separate **test** `MONGO_URI`. Scripts like `reseed-plans.js`,
  `backfill-trial-end.js`, `set-trial-end.js`, `reset-analysis.js`,
  `diagnose-state.mjs` mutate data — treat them as operational tools, not tests.
- Python analyzers have `pytest` suites under `python/**/tests/` and golden
  fixtures under `python/website_analyzer_app/tools/golden_fixtures/` — those are
  **test assets, do not delete**.
- Server unit tests: `cd Server && npm test` (Node's built-in `node --test`, files in
  `Server/test/*.test.js`, no DB needed). Python: `python -m pytest -q` inside each
  `python/*_app/` folder. Golden replay: `python tools/golden_check.py verify` in
  `website_analyzer_app` (12 known failures need live network — see `CHANGE_REPORT.md`).
- Client: `npm run build` and `npx eslint .` (≈200 pre-existing style findings, mostly
  unused vars / React-compiler hints). For quick server sanity: `node --check <file>`.
- End-to-end analysis needs the full runtime (Mongo + Redis + Python + Playwright +
  keys). Without it, only static checks / unit tests / harness-writing are possible.

## Conventions

- Server is ES modules — `import`/`export`, not `require`.
- Fail-open on best-effort enrichment: a probe/AI/scale step that errors should log
  and degrade, never crash the request or empty a result (see the per-page safety
  net in `python/website_analyzer_app/main.py :: analyze_url`).
- Keep branding/colors from `static/` consistent across apps.
- Prefer small, reviewable changes. For file cleanup: work on a **branch**, and
  **propose deletions for review** rather than auto-deleting — this repo has
  intentional one-off scripts that look like clutter but aren't.

## Security (read before cloning/pushing)

- `.env` files historically contained **live** secrets and are now git-ignored.
  Before pushing anywhere, verify `git ls-files | grep .env` returns **nothing**.
- Rotate any key that was ever committed (Paddle, OpenAI, Anthropic, Mongo, Auth0).
- Provide secrets to local/cloud runs via the environment, never by committing them.
- Lock down VPS MongoDB: bind to localhost or a private network, enable auth, never
  expose it openly.

## Onboarding store profile (Steps 1–4)

`python/website_analyzer_app/level1_detector/site_validator.py` (journey + market +
language signals) → `Server/utils/taxonomy.js` (Industry → Category → Subcategory)
→ `level1_detector/business_type.py` (Types 1–5; 1–2 = Enterprise) via
`/api/v1/scale-check`. Assembled in `Server/app/services/siteReadiness.service.js`,
stored on `Competitor.storeProfile` / `accessStatus`. English-only stores.
Product pairing for Growth/Pro is AI-driven (`comparison_engine/ai_product_match.py`).

## Project docs

- `LAUNCH_CHECKLIST.md` — pre-launch blockers + the go/no-go gate.
- `CHANGE_REPORT.md` — Oct 2026 review + implementation report (security, Steps 1–4,
  AI product matching, deployment), with what still needs live verification.
- `FEATURE_focus_categories.md`, `FEATURE_competitor_similarity.md` — feature specs.
