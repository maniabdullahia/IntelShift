# Website Analyzer — accuracy hardening status (handoff, 2026-07-10)

Context for continuing this work in a separate chat. All changes are already
applied in this codebase.

## Scoreboard (accuracy_check runs)

| Pack | Before | After | Notes |
|---|---|---|---|
| Shopify | 0.88, 1 crash | ~0.92+, 0 crashes | 12 false-"blocked" sites recovered & restored to pack |
| WordPress | 0.856, 8 crashes | 0.898, 0 crashes | product pages 0.571 → 0.889 |
| Wix | 0.655, all fetches failing | 0.859 | products 1.0; all pages via requests now |
| Unknown | 0.717 | 0.731, 0 crashes | homepages 32/37 correct; mismatches 44 → 31 (≈6 transient rate-limit blocks, ≈4 geo-redirect artifacts, ≈21 real long-tail) |

## Fixes applied (all verified except the last two)

1. **Shopify collection crash** — products.json `options`/`images` as strings (analyzers/shopify/collection.py).
2. **website_blocked contract** — canonical `status/blockedReason/userMessage` on all blocked outcomes + 90s fallback time budget (`ANALYZER_FALLBACK_BUDGET_SECONDS`), main.py. React contract documented in `React App Code/BLOCKED_SITE_HANDLING.md`.
3. **Price retry** — now triggers on 0-product collections and <80% coverage; outcome stamped into responseHeaders (was invisible: base_analyzer copies headers at analyze() time).
4. **WP NameErrors** ×3 (`page_url=url` → `base_url`, wordpress/collection.py).
5. **WP product pages** — `result["products"]` was hardcoded `[]`; now populated (wordpress/product.py). Same fix for Wix (wix/product.py).
6. **competitive_schema crashes** — string descriptions (WP) and non-dict product entries guarded.
7. **Page-type detector** — /shop/ single-product override (needs `single-product` body class), Woo grid markup in category/family-landing bail-outs, blog equivalences in checker.
8. **False-block bug (biggest win)** — challenge markers ("cloudflare", "captcha"…) were counted inside JS bundles, classifying whole platforms (all of Wix) as blocked; now visible-text-only with size guard (fetcher.py `is_html_blocked_or_empty`).
9. **Hydration-shell heuristic** — >15KB HTML with <1200 chars visible text forces Playwright (fetcher.py `should_force_playwright`).
10. **Unknown analyzer blog stomp** — general extractor hardcoded pageType "general", erasing detected "blog" (unknown/general.py, two shadowed definitions of `analyze_unknown_general` — dead code worth cleaning).
11. **bs4 decompose crash** — unknown/product.py `extract_product_region` iterating decomposed elements.
12. **Homepage locale roots** — `is_homepage_path` now accepts `/eu_en`, `/eg/en/`, `/us-en/home.html` etc. (unit-tested, 13 cases). **Retest pending.**

## URL packs (training/)

- Cleaned of dead URLs, wrong-platform sites (gooddyeyoung/snoot/orangeamps/magnatiles/indiansummer moved to Shopify pack), and same-site/same-type duplicates.
- Blocked regression set kept intentionally: colourpop, kylie, bombas, onlymine, puravida.
- claude.ai replaced with anthropic.com (redirects to login).
- `tools/debug_page_type.py` — prints decision rule + full signals for any URL; use `--expected <type>`.
- Accuracy checker now records tracebacks (8 lines), `status`/`blockedReason` per row.

## Next steps

1. ~~Unknown pack retest~~ DONE (2026-07-10 15:06): 0 errors, 0.731, homepages 32/37.
2. Accepted/backlog: SPA hydration waits (chipotle, dominos, gymshark/mejuri prices), geo-redirect sites (louboutin, coca-cola subpages), custom-platform collection detection long tail (paulsmith, mollybracken, bleu-de-chauffe, sonos /shop), genuine bot walls (spotify, asus support). hp/lenovo "blocked" rows in the last run are rate-limiting from repeated same-day testing — they pass when fresh.
3. ~~Website Analyzer accuracy pass is COMPLETE. Next: Analysis Merger app → Competitor Comparison app → Change Detection app (same treatment).~~ DONE (2026-07-10):

## Downstream pipeline pass (merger → comparison → change detection)

- **`pipeline_check.py`** (project root) — the accuracy_check equivalent for the
  downstream apps. Feed it a folder of analyzer outputs:
  `python pipeline_check.py <folder>` (or `--fuzz-only`). Stages: merge (with
  snapshot invariants: schema, counts, price shapes, sourcePages, no _html /
  responseHeaders leakage) → pairwise compare (schema, currency guard,
  category-gate invariant on every matched pair) → self-diff (must be 0
  changes) → AI payload/OpenAI request build → 10 hostile fuzz cases.
- **Result: 852/852 checks passed** on a 35-output / 18-domain real corpus
  (ecommerce + SaaS + services + blocked sites). Zero crashes anywhere.
- **website_blocked contract propagated through the merger**: page summaries
  carry `status`/`blockedReason`/`userMessage`; all-pages-blocked snapshots get
  top-level `status: "website_blocked"` + `userMessage` (same React contract as
  the analyzer); mixed snapshots get `status: "partial_blocked"` +
  `quality.coverage.blockedPages`.
- **Domain normalization**: `www2.`/`www3.` prefixes now stripped like `www.`
  (www2.hm.com == hm.com — matters for same-site change detection).
- Merger tests: 13 passed (blocked-contract + www-variant tests added).

Run `pipeline_check.py` after any merger/comparison/detector change, with the
analyzer accuracy packs' outputs as corpus when available.

## Scorecard calibration (2026-07-10, after unknown retest)

- Unknown pack rescored 0.731 → **0.851** (confirmed by rerun): pack-aware
  platform checks (custom pack accepts Unknown + framework labels; named packs
  verify platform MATCHES), empty-collection price checks no longer scored,
  `expectBlocked` bucket supported in packs.
- HubSpot detector precision fix: forms/tracking embeds (hs-scripts, hsforms)
  no longer classify a site as HubSpot CMS (anthropic.com case); CMS markers
  required. Weak HubSpot/Squarespace/BigCommerce winners resolve to Unknown.
- **`tools/known_issues.json`**: triaged/accepted failures (rate-limits, bot
  walls, geo-redirects, custom-collection long tail) are marked KNOWN in
  reports and no longer fail the exit code - only NEW regressions gate.
  Seeded from the triage above; add entries as new accepted items appear.
- Remaining pack hygiene: move to matching packs: news.airbnb.com,
  monin.com (Shopify), paulsmith/templespa (Magento), visiofactory (Woo),
  toasttab (Shopify), nerdwallet (WordPress). Detector false positive to
  investigate someday: linear.app -> WooCommerce (JS-bundle signal strings).


## Ground-truth value verification (2026-07-10)

The scorecard verifies STRUCTURE (a price exists); it does not prove the
extracted VALUES match the real page. New harness closes that gap:

- **`tools/golden_check.py`** - golden fixture harness.
  `record <url>` freezes the page HTML + pre-fills expected.json from the
  extraction; a HUMAN then confirms each value against the live page (that
  pass is what makes it ground truth). `verify` replays every fixture's
  frozen HTML through the current extraction code offline and fails on any
  value mismatch (exit 1). Deterministic - no network, no price drift.
- Seeded: `tools/golden_fixtures/sivanna-com-pk-foundation-product/`
  (255KB frozen HTML; values hand-verified: Liquid Foundation, 2750 PKR,
  2 variants, vendor Sivanna Colors).
- TODO (needs the user's PC - sandbox copies of recently-edited analyzer
  modules are sync-stale): run `python tools/golden_check.py verify` to
  confirm the seeded fixture passes, then `record` ~10-15 fixtures covering
  each platform x page type (2 collections + 1 product + 1 homepage per
  platform, 2 SaaS pricing pages) and human-confirm their expected.json.
  Add `verify` next to accuracy_check in the release gate.


## Deterministic plan-card parser (2026-07-10, driven by golden fixtures)

First golden-fixture recordings caught two real issues:
1. WPBakery changed its pricing lineup (now Regular $82 / 5 Sites $299 /
   10 Sites $592, lifetime) - old expected values were stale.
2. Plan extraction was LLM-dependent: the deterministic extractor returned
   ZERO plans from WPBakery's cleanly-marked-up HTML (requests path; the
   earlier plans came via Jina+LLM).

Fix: **`extractors/plan_parser.py`** - generic DOM plan-card parser (card
classes plan/pricing/tier/package, split currency/amount spans, strikethrough
compare-at with must-be-higher guard, /mo|/year|/lifetime periods, li
features). Wired as fallback in `wordpress/general.py` extract_pricing_data
and BOTH copies of the corePlans block in `unknown/general.py` (the shadowed
duplicate defs - still worth cleaning). Verified against frozen fixtures:
wpbakery 3/3 plans with compare-at; elementor unaffected (text path already
finds its 6 plans).

Fixture updated: wpbakery expected.json now holds the verified current values.
User TODO: `py tools\golden_check.py verify` should now pass 3 fixtures; keep
recording (~12 total). Elementor fixture: user reported 2 plans renamed +
prices off vs live page - likely the annual/monthly toggle or geo-serving;
compare expected.json against the FROZEN page.html (not the live site) and
correct expected.json to match page.html.


## Nike product-price bug (2026-07-10, caught by golden fixture)

Nike product page extracted $50 instead of $130. Root causes, both fixed in
analyzers/unknown/product.py:
1. JSON-LD `ProductGroup` (nike.com) was filtered out - the sellable Products
   with offers live in `hasVariant`. flatten_jsonld now descends into it
   (verified: 5 variant Products found, offer price 130 USD).
2. DOM fallback took the FIRST dollar amount in the whole page text ($50
   banner). New tier 4a: price-DESIGNATED nodes first
   ([data-testid*=price], [itemprop=price], product-price/current-price
   classes) - independently yields $130 on the frozen HTML.
Fixture updated to the verified values (name/vendor/handle were already
correct). User TODO: `py tools\golden_check.py verify` (4 fixtures now).
Note: expected.json name contains the (R) sign - if verify fails only on the
name, check the exact character against the extraction and adjust.


## Gymshark null-price bug (2026-07-10, caught by golden fixture)

Headless-Shopify product page (gymshark everyday seamless shorts) extracted
name/handle fine but price=null, although the frozen HTML contains it
(JSON-LD ProductGroup variant offer: 28 USD; visible $28). Two gates fixed in
analyzers/shopify/product.py's headless fallback block:
1. Trigger was `if not product.get("name")` only - Gymshark gets the name
   from DOM, so price-only recovery never ran. Now triggers on missing name
   OR missing price.current (with a guard so an existing DOM name is never
   overwritten).
2. Its JSON-LD loop only accepted @type=Product - now also ProductGroup with
   hasVariant descent (same pattern as the unknown-analyzer Nike fix).
Verified against frozen fixtures: gymshark -> 28 USD, nike (same logic) ->
130 USD. Fixture expected.json updated. User TODO: `golden_check.py verify`
(5 fixtures).

RULE OF THUMB for missing/wrong fixture values (user asked): if the value IS
in the frozen page.html but extraction misses it -> extractor bug, report/fix
(never hand-edit expected.json to what the extractor can't produce, except
deliberately keeping a red fixture as a tracked TODO). If the value is NOT in
the frozen HTML at all -> fetch-side limitation; delete that field from
expected.json (the fixture can't test what the crawler never received).


## ProductGroup name-vs-offers split (2026-07-10, second verify run: 135/137)

The golden suite grew to 11 fixtures (added: clare.pro Woo collection+product,
claude.com/pricing, copperandbrass Wix product, vivietmargot Wix collection -
all pass, incl. per-seat plan parsing on claude.com). The 2 failures were name
regressions from the ProductGroup fixes: variant nodes carry per-colour/size
names ("... - Size XS"), the canonical product name lives on the GROUP.

Fixed rule: name from group, offers from variant.
- unknown/product.py extract_jsonld_products: ProductGroup now emits a MERGED
  product (group name/description/brand/image + first variant incl. offers)
  first in the list.
- shopify/product.py headless fallback: jl_name prefers group name; and when
  the OG title CONTAINS the jl name and is longer, OG wins (richer form:
  "Gymshark Everyday Seamless Shorts - Black" vs "everyday seamless shorts").
Verified on frozen fixtures: nike name=group name + 130 USD; gymshark
name=OG form + 28 USD. Expect verify 137/137.
