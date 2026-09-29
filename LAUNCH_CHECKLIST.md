# IntelShift AI — Pre-Launch Checklist

The goal of this list is a single, honest answer to *"are we ready?"*. Each item
has a **Done when** line — the objective test. You are ready for an open paid
launch only when every **🔴 Blocker** is checked and the **Launch gate** at the
bottom passes.

Legend: 🔴 Blocker (cannot launch without) · 🟠 Important (launch feels risky
without) · 🟢 Polish (fine to follow shortly after).

---

## 1. Security & secrets 🔴

- [ ] **Rotate every leaked secret.** The `.env` files were committed to git with
      live keys.
      **Done when:** Paddle live API key + webhook secret, OpenAI, Anthropic,
      MongoDB, and Auth0 credentials have all been regenerated and the old ones
      revoked.
- [ ] **Untrack `.env` from git.** `git rm --cached` every `.env`, add to
      `.gitignore`, and confirm they no longer appear in `git ls-files`.
      **Done when:** `git ls-files | grep .env` returns nothing.
- [ ] **Scrub git history** (or accept the risk consciously). The old keys live
      in past commits even after untracking.
      **Done when:** either history is rewritten/secrets purged, or you've decided
      the rotated keys make the old ones worthless and documented that choice.
- [ ] **Confirm production env is set server-side**, not from a committed file
      (host dashboard / secrets manager).
      **Done when:** the deployed app reads secrets from the platform, not the repo.

## 2. Core analysis reliability 🔴 — *this is the real launch gate*

- [ ] **Golden store suite defined.** Pick 10–15 *realistic* target stores —
      mid-size Shopify/WooCommerce shops like your actual customers, NOT giants
      (Gymshark/Nike/Fabletics are bot-protected + enterprise-scale and are the
      wrong bar).
      **Done when:** the list exists and is written down (add it below in §10).
- [ ] **Every golden store produces a complete, two-sided report.** Owner AND
      competitor both have pages, products, prices, and categories.
      **Done when:** for all golden stores, neither side shows "0 pages analyzed"
      or "no homepage detected," and price coverage is ≥ ~85% on both sides.
- [ ] **Fail loud, not quiet — extraction-quality gate.** If either side comes
      back near-empty or low-coverage, the app must say "we couldn't fully read
      this store" instead of rendering a confident-looking but hollow report.
      **Done when:** a deliberately-broken run shows an honest warning state, not
      a normal report with silent zeros.
- [ ] **No junk in product data.** No payment/shipping badges (Klarna, Afterpay,
      "Free Shipping…") counted as products; no impossible prices (e.g. 2.8 where
      real is 28).  *(DOM-junk filter added — verify it holds on the suite.)*
      **Done when:** spot-checking 3 reports shows product lists that a human
      would agree are real products at believable prices.
- [ ] **AI is actually on during real runs.** (Was silently disabled via
      `gpt-5-mini`; now defaulted to `gpt-4o-mini`.)
      **Done when:** a full run's logs show **zero** `[ai_assist:*] fallback`
      lines caused by model/auth errors.
- [ ] **Gymshark-class 500 fixed.** Capture the traceback (logging now added),
      fix the crash, and confirm the owner side no longer disappears.
      **Done when:** re-running the case that produced the empty owner side yields
      a full two-sided report.

## 3. Known bugs from testing to close 🟠

- [ ] **Canonical host normalization.** A regional redirect (`us.dfyne.com`) is
      being saved as the store's canonical domain.
      **Done when:** adding `dfyne.com` stores it as `dfyne.com`, and policy/FAQ
      fetches use that host.
- [ ] **Cross-site cookie isolation.** Geo cookies from one store were bleeding
      into another's fetch (`us.checkout.gymshark.com`), corrupting the render.
      **Done when:** each site's fetch uses a fresh browser context; no foreign
      geo/localization cookies appear in a store's fetch logs.
- [ ] **Dashboard "Recent Changes" + ChangeDetails respect trial-ended state.**
      *(Fixed this session — verify end to end.)*
      **Done when:** an expired-trial account shows "monitoring paused," never a
      phantom "next check in N days."
- [ ] **Competitor suggestion quality.** *(Wide-catalog single-brand fix landed.)*
      **Done when:** a single-brand store (e.g. an activewear shop) returns
      same-vertical brands, not random marketplaces or noise.

## 4. Billing & plans (Paddle) 🔴

- [ ] **Live checkout completes** for each paid tier (Starter, Growth, Pro) with a
      real card.
      **Done when:** each tier can be purchased and the subscription appears active.
- [ ] **Webhooks update the account.** Payment success/failure, cancellation, and
      renewal flip the subscription state correctly.
      **Done when:** a test purchase and a cancellation both reflect in-app within
      the expected window.
- [ ] **Plan limits enforced** (competitor count, pages per site, cadence).
      **Done when:** exceeding a limit is blocked with the right message, not a crash.
- [ ] **Enterprise "contact us" path** works (no self-serve checkout for giants).
      **Done when:** a Nike/Daraz-scale URL routes to the contact flow, not analysis.

## 5. Trial & entitlement 🟠

- [ ] **New signup gets a clean 14-day trial** with the banner + days-left.
- [ ] **Trial end → read-only** across workspace, competitors, alerts, and pages;
      monitoring stops.
      **Done when:** an expired account cannot mutate anything and sees the paused
      messaging everywhere change info appears.
- [ ] **Upgrade from expired trial restores full access** immediately.

## 6. Monitoring & change detection 🟠

- [ ] **A scheduled run actually fires** and produces a change report on the next
      cadence (not just the initial analysis).
      **Done when:** at least one real week-over-week change report has been
      generated end to end.
- [ ] **Change reports read correctly** — no false "everything changed" from
      extraction wobble between snapshots.

## 7. Observability & ops 🟠

- [ ] **Errors are visible.** Server logs surface tracebacks (analyze-page done —
      extend to merge/compare/worker paths).
      **Done when:** a forced failure shows a real stack trace, not a bare 500.
- [ ] **A failed page doesn't sink the whole run.** One page 500 should degrade
      gracefully, not empty an entire side.
- [ ] **Basic uptime + error alerting** on the API, workers, and Python service.
- [ ] **Stable, committed build.** No more testing on uncommitted changes or
      hand-edited DB state.
      **Done when:** `git status` is clean and the deployed build matches `main`.

## 8. Legal & trust 🟢→🟠

- [ ] Terms, Privacy, Refund pages live and linked (login + footer). *(Links added.)*
- [ ] **Robots/blocker respect messaging** is honest and consistent. *(Reworded
      this session.)*
- [ ] Support/contact path exists for when something goes wrong.

## 9. UX polish 🟢

- [ ] Onboarding copy is ecommerce-only and consistent. *(Reviewed this session.)*
- [ ] Empty/loading/error states exist for every main screen (no blank panels).
- [ ] The "This can take a few minutes" long-operation waits have clear feedback.

---

## 10. Golden store suite (fill this in)

| # | Store | Platform | Owner-side clean? | Competitor-side clean? | Notes |
|---|-------|----------|-------------------|------------------------|-------|
| 1 |       |          | ☐                 | ☐                      |       |
| 2 |       |          | ☐                 | ☐                      |       |
| 3 |       |          | ☐                 | ☐                      |       |
| … |       |          | ☐                 | ☐                      |       |

---

## ✅ Launch gate (the one honest test)

You are ready for an **open, self-serve, paid launch** only when:

1. Every 🔴 Blocker above is checked, **and**
2. All 10–15 golden stores produce complete, correct, two-sided reports with AI
   on and no junk data, **and**
3. You can run a full flow — signup → trial → analysis → upgrade → paid → a
   scheduled change report — without touching the database or code by hand.

Before that, the right move is a **controlled beta**: a handful of invited users
on hand-picked stores, with you watching every run. That's reachable much sooner
than the full gate, and it's how you find the real-world breakage safely.
