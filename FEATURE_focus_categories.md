# Feature Spec — Focus Categories (onboarding)

## Summary
After the user's store URL passes the readiness check (and before the competitor
step), add a **required** step where the user picks the categories they care most
about — **1 to 5, in priority order** — from the categories we detected. This
becomes a stored, reusable signal that sharpens competitor suggestions, page
pairing, Pro auto-select, competitor fit scoring, and page-budget selection on
small plans.

"All" (or an empty selection) means **no focus lens → the system behaves exactly
as it does today.** No special downstream logic for the "all" case.

---

## Data model (workspace)
- `focusCategories: string[]` — ordered; index 0 = highest priority. Empty `[]`
  means "all / no focus."
- `focusMode: "all" | "selected"` — `"all"` when the user chose All or skipped;
  `"selected"` when 1–5 were picked. (Redundant with the array being empty, but
  explicit for clarity/analytics.)

Values are the detected category **names/handles** (same identifiers the competitor
suggester and pairing already use), so they join cleanly to existing logic.

---

## Onboarding step — rules
- **Placement:** immediately after the user's store URL passes readiness, before
  the competitor URL step.
- **Source list:** the categories detected from the store (readiness/quick-catalog
  output), shown with product counts, ordered by count desc.
- **Selection:** multi-select, **min 1, max 5**. Selection **order = priority**
  (first picked ranks highest). Show the rank number on each chosen chip.
- **"All" option:** a distinct option. Selecting **All disables the individual
  categories** (mutually exclusive); deselecting All re-enables them.
- **Skip path (required-but-not-blocking):** if the user clicks Next with nothing
  selected, show a confirm dialog:
  *"You haven't picked any focus categories. We'll analyze all of them. Continue,
  or pick your focus?"* → **Analyze all** sets `focusMode:"all"`; **Pick focus**
  returns to the step.
- **Empty-detection edge case:** if we detected **zero** categories, do NOT show an
  empty picker. Auto-set `focusMode:"all"` and show an honest note:
  *"We couldn't pull specific categories from your store, so we'll analyze
  everything."* (Also a useful early signal that extraction under-read the store.)
- **Add-your-own (optional, recommended):** a free-text box to add a category we
  didn't detect. Counts toward the max of 5. Doubles as an extraction-correction
  signal.

---

## Engine hooks (only when `focusMode === "selected"`)
1. **Competitor suggestion** — build the region-localised search queries from the
   focus categories (in priority order) instead of the auto-detected breadth
   sample. Aligns with the existing ~6-query cap (5 focus + umbrella).
2. **Competitor fit scoring** — score/badge competitors by how many of the user's
   **focus** categories they cover ("covers 4 of your 5 focus categories"),
   weighted by priority, rather than raw overall overlap.
3. **Page pairing / mapping** — surface and pre-select focus-category collection
   pairs first; use priority to order suggestions.
4. **Pro complete-site auto-select** — pass focus categories (ordered) as the
   prioritisation steer to the auto-select/auto-pair logic.
5. **Small-plan page budget (Free/Starter)** — when the tracked-page limit is
   tight, spend it on the focus categories first.

**Guardrail:** focus is a **lens for ranking/targeting, never a filter that
discards catalog breadth.** Growth/Pro still crawl and track the full catalog;
focus only re-orders and targets.

When `focusMode === "all"`: skip all of the above — every engine runs exactly as
it does today.

---

## Out of scope
- Competitors are **not** asked for focus categories (they're measured against the
  user's focus).
- No change to the "all categories vs live-on-site" report toggle — unrelated.

## Build order (suggested)
1. Data model + persist from onboarding (no engine hooks yet).
2. Onboarding UI step (selection, order, All, skip-confirm, empty-detection).
3. Wire hook #1 (competitor suggestion) — biggest, most visible win.
4. Wire hooks #2–#5.
