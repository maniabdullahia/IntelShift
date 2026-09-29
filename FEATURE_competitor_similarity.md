# Feature Spec — Real-competitor discovery (similarity re-ranking + peer-set source)

## Problem
Current discovery (SearXNG web search → frequency voting → LLM classify → verify)
selects for *"a store that sells this category,"* and web search ranks by SEO
authority — so results skew to category giants and well-optimized players, not
true peers. Nothing scores whether a candidate actually **resembles** the user's
store (catalog, prices, size, market). This spec fixes both: a non-SEO discovery
source (#2) and a similarity re-rank that decides the final list (#1 + giant
exclusion). Lives in `Server/app/services/competitorSuggest.service.js`.

Out of scope: asking the user to name a competitor (they already have
category-search + manual add). Audience is approximated via price band + size +
market — no paid audience data.

---

## #1 — Similarity re-ranking (the deciding step)
After candidates are discovered + verified, score each against the user's store and
**re-rank; drop low-similarity ones even if SEO-strong.** Weighted score from
signals we can get cheaply:

| Signal | How | Data source | Weight (start) |
|--------|-----|-------------|----------------|
| **Price band overlap** | overlap of price ranges / median ratio | sample candidate `/products.json` (or Woo) first page for prices; user's from own probe/catalog | **0.35** |
| **Catalog size similarity** | ratio of product totals (penalize big mismatch) | `getStoreProductTotal` / scale gateway | 0.20 |
| **Category / focus overlap** | Jaccard of category sets, weighted by focusCategories | `getStoreCategoriesFast` on candidate; user's categories/focus | 0.20 |
| **Assortment similarity** | token/keyword overlap of product titles | product titles from the same sample | 0.15 |
| **Market/region match** | same region/currency = full, adjacent = partial | detected currency/region (already probed) | 0.10 |

- **Budget:** discover ~20 candidates, deep-probe (price/size/titles) only the top
  ~8 by cheap pre-signals (category overlap + region), then re-rank those. Keeps
  onboarding latency bounded.
- **Price band is the strongest signal** — a $40 and a $200 brand in the same
  category are not competitors. Get candidate prices from a single products.json
  page (Shopify) / Store API (Woo); skip gracefully if unavailable (down-weight,
  don't drop).
- Output: attach a `similarityScore` (0–1) + a short `whyMatch` (e.g. "similar
  price band · overlaps 3 focus categories · same market") to each suggestion, so
  the UI can show *why* it's a real competitor.

## Giant exclusion (folded in)
Extend the existing marketplace denylist + scale gateway: **demote/drop
enterprise-scale or huge-catalog domains** from suggestions — they're never peers
for a self-serve store. (Reuses `checkScale` / size backstop already built.)

## #2 — LLM peer-set discovery (non-SEO source)
Add a second candidate source alongside web search:
- Prompt the model with the user's brand + categories/focus + **price band** +
  region + catalog size: *"list direct competitors of similar size and positioning
  — not category giants."*
- Merge its domains with the web-search candidates (dedupe), then run the SAME
  verification (live/real check) and #1 re-ranking over the combined pool.
- Hallucinated/dead domains are caught by existing verification; this only widens
  the candidate net beyond whatever ranks on Google.

---

## Pipeline (after change)
1. Build queries (existing; focus-categories already feed this).
2. Candidates = web-search domains **∪** LLM peer-set domains (deduped).
3. Drop hard-excluded + giant-scale domains.
4. Cheap pre-rank (category overlap + region) → keep top ~8.
5. Deep-probe those (price band, size, titles).
6. **Similarity re-rank** → final ordered list with `similarityScore` + `whyMatch`.
7. Store on `workspace.suggestedCompetitors` (existing) — add the score + reason.

## Build order
1. Similarity scorer + candidate deep-probe (price/size/titles) — pure ranking on
   existing discovery. Biggest quality jump.
2. Giant exclusion in the candidate filter.
3. LLM peer-set source + merge.
4. Surface `whyMatch` in the suggestion UI (SelectionModal / onboarding picks).

## Guardrails
- Every added probe/LLM call is best-effort + fail-open (missing data → down-weight,
  never crash or block onboarding).
- Latency budget: cap deep-probes (~8) and total added time (~few seconds).
- Similarity is a **ranking lens** — if scoring fails entirely, fall back to today's
  frequency-vote order rather than returning nothing.
