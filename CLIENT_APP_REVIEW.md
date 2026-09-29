# IntelShift — Client App Review & Execution Plan

_Scope: the React/Node client-side workspace (Client + the Server routes it depends on, and the Python bridge for change detection). Design/branding intentionally left for later. Focus: Dashboard, Change Details, and the bugs around them._

---

## 1. The single most important finding

**Dashboard and Change Details don't work because they have no data container wiring them to the backend.**

Both `Dashboard.jsx` and `ChangeDetails.jsx` are well-built **presentational** components — they take *all* their data through props (`competitors`, `reports`, `aiByDomain`, `changeReport`, schedule info, etc.) and render nothing but empty/placeholder states when those props are missing.

But in `Router.jsx` they are rendered **bare, with no props**:

```jsx
{ path: "/dashboard",     element: <Dashboard /> }
{ path: "/change_detail", element: <ChangeDetails /> }
```

So:
- Dashboard always falls into its "Run your first analysis to get started" empty state (because `competitors` and `reports` are `undefined`).
- ChangeDetails always falls into its "Monitoring is set up — no report yet" empty state (because `changeReport` is `undefined`).

There **is** a container built for exactly this job — `components/features/WeeklyMonitoring/WeeklyMonitoring.jsx` — which fetches monitoring status and passes props to both screens. But it is:
1. **Never imported by the router** (dead code today), and
2. **Broken**: it imports `'../Dashboard/Dashboard'` and `'../ChangeDetails/ChangeDetails'`, paths that don't exist. The real files live in `screens/Main/Core/`.

**Conclusion:** the screens themselves are basically fine. The missing piece is the container + data plumbing. That is the bulk of the work.

---

## 2. What is working well

- **Auth / token flow** (`api/api.js`): clean axios instance with request interceptor (Bearer) and a proper 401 → refresh-token → retry queue. Solid.
- **Analysis screen** (`screens/Main/Core/Analysis.jsx`): this is the pattern that works — reads `:analysisId` from the URL, calls `getAnalysis(id)`, renders `<AnalysisPage>`. This is the template to copy for Dashboard/ChangeDetails.
- **Workspace store** (`store/workspace.store.js`): well-structured zustand + immer + persist store with sync, CRUD, and socket-driven status updates.
- **The presentational components themselves** (`Dashboard.jsx`, `ChangeDetails.jsx`): genuinely good. Severity grouping, filters, before/after diffs, CSV export, AI-interpretation block, empty/never-run/no-changes states are all handled. They just need to be fed.
- **`changeReportUtils.js`**: rollup/severity/date helpers are complete and shared correctly.
- **Server change-report data model** (`models/changeReport.js`): schema is designed correctly for Python `/diff-snapshots` output. The plumbing to fill it is what's missing.

---

## 3. What needs completion (functionality gaps)

### A. Client data container for the monitoring home
Wire Dashboard + ChangeDetails to real data. Two viable approaches:
- **Fix and adopt `WeeklyMonitoring.jsx`** (fix the two import paths, mount it at `/dashboard`, let it own the Dashboard↔ChangeDetails view switching via internal state), **or**
- **Add react-router loaders** (mirroring `plan.loader`) that fetch monitoring status and feed the screens, with a `/change_detail/:domain` route param for the detail view.

Recommend the container approach — it already handles the domain selection and back-navigation that the bare routes lack.

### B. The monitoring API call is broken end-to-end
`components/features/WeeklyMonitoring/changeDetection.api.js` → `fetchMonitoringStatus`:
- Uses **raw `fetch('/api/monitoring/status?workspaceId=…')`** — a relative URL. There is **no Vite proxy** (`vite.config.js` has none), so this hits the dev server origin, not the API (`localhost:3000/api`). It will 404.
- It does **not attach the Bearer token**, so even reaching the server it would be unauthenticated.
- It sends `workspaceId` as a **query param**, but the server route is a **path param**: `GET /monitoring/status/:workspaceId`.

**Fix:** route this through the shared axios `api` instance (gets baseURL + auth + refresh for free) and call `/monitoring/status/${workspaceId}`.

### C. Server `/monitoring/status` returns placeholder data
`controllers/monitoring.controller.js`:
- Returns **`reports: null`** and **`aiByDomain: null`** *always* — it never queries the `ChangeReport` collection. So the "changes" half of the Dashboard and all of ChangeDetails will always be empty even after the client is wired.
- **Field-name mismatches with what the client expects:**
  - returns `reportingFrequency` → client wants **`cadencePerWeek`**
  - returns `overallFindings` (plural) → client wants **`overallFinding`** (singular)
- `overallFindings` is hardcoded to `"##### OVERALL FINDINGS #####"`.
- `scoreVsYou: null` hardcoded → Dashboard's headline score card never shows.
- `unreadChanges: 3` hardcoded.
- `periodStart`/`periodEnd` are set to `lastRebuiltAt`/`nextScanAt`, which isn't really the comparison window.

**Fix:** query `ChangeReport` for the workspace, shape it into `reports: change_detection_v1[]` + `aiByDomain`, and rename the fields to match the client contract.

### D. The change-detection pipeline never persists a report
This is the deeper backend gap feeding C:
- `api/python/changeDetector.js` → `detectSnapshotChanges()` calls Python `/v1/diff-snapshots` **but never returns `response`** (missing `return`), so callers always get `undefined`.
- `workers/competitor.worker.js` (~line 111) calls it, `console.log`s the (undefined) result, then `return;` — **it never creates a `ChangeReport`.** The model is imported nowhere that writes it.

**Fix:** return the Python response from the bridge; in the worker, persist a `ChangeReport` (report JSON + denormalized `changeScore`/`overallSeverity`/`totalChanges`) whenever a previous snapshot existed.

### E. Optional AI interpretation of changes
`aiByDomain` is part of the contract but nothing generates it. Lower priority — the screens degrade gracefully without it ("AI interpretation is pending / below threshold"). Wire after D works.

---

## 4. Bugs found (independent of the big wiring gap)

1. **Sidebar analysis sub-links go nowhere.** In `Sidebar.jsx`, the "Competitor Analysis" children are built as `{ id: item.analysisId, name }` — **no `path`** — then rendered as `<Link to={child.path}>` (i.e. `to={undefined}`). Clicking an analysis does nothing. Also `setCurrentScreen(child.id)` is called with an analysisId, which fails `isValidScreen` and logs a warning. **Fix:** `to={`/analysis/${child.id}`}` and drop the `setCurrentScreen` call for children.

2. **Two competing navigation systems.** `Router.jsx` uses real routes (`/dashboard`, `/change_detail`, …) rendering components directly, **while** `MainWindow.jsx` switches screens off `window.store.currentScreen`, and `Sidebar` fires **both** `<Link to>` *and* `setCurrentScreen()` on every click. `MainWindow` (the currentScreen switch) is only mounted at `/`, so the whole `window.store` screen machine is effectively dead/contradictory. **Decide on one** (recommend react-router routes; retire `MainWindow` + `currentScreen`, or vice-versa) — keeping both guarantees drift and confusion.

3. **`detectSnapshotChanges` / `detectComparisonChanges` return nothing** (missing `return response` — both functions in `changeDetector.js`).

4. **`Analysis.jsx` reads a nonexistent store field:** `useWindowController((state) => state.currentWorkspace)` — `window.store` has no `currentWorkspace`. Currently harmless (used only as an effect dependency) but it's dead/misleading code.

5. **`page.api.js` GET helpers send a body on GET requests** (`getPages`, `getPage`, `getPageAnalytics` pass `{ data: {...} }`). Axios drops GET bodies in the browser and the server can't read them. And `getPageAnalytics` targets `/page/analytics`, a route that **isn't registered** in `routes.js` (the file's own comment admits this). Convert to query params and add the route if that feature is needed.

6. **Env inconsistency:** `api.js` fallback base is `localhost:5000/api`; `.env.development` uses `localhost:3000`; `.env` (prod) uses `api.intelshift.ai`. Make sure the dev server actually runs on the port `.env.development` points to. Minor, but a classic "why is nothing loading" trap.

7. **Reports / Alert Settings routes exist but are commented out of the sidebar.** `Reports.jsx`, `AlertSettings.jsx` are routed but unreachable from nav. Confirm whether they're in-scope or should be removed to reduce dead surface.

---

## 5. Functionality opportunities (once the above works)

- **Per-competitor change detail routing** with a real `domain`/id param, so links are shareable and refresh-safe (rather than only internal container state).
- **Unread-changes badges** driven by `ChangeReport.read` (the model already has the `read` flag) instead of the hardcoded `unreadChanges: 3`.
- **`scoreVsYou`**: compute a real competitive score from the analysis payload so the Dashboard score cards mean something.
- **"Rescan now" / manual monitoring trigger** from the Dashboard (a `workspace-rescan/:workspaceId` route already exists server-side).
- **AI interpretation of change reports** (`aiByDomain`) to power the "Recommended Actions" block that's already built into the Dashboard.
- **Empty-state → onboarding nudges** consolidated once navigation is unified.

---

## 6. Proposed execution plan (ordered)

**Phase 0 — Decide navigation model** (blocks clean work on everything else)
- Pick react-router routes as the single source of truth; retire `MainWindow`/`currentScreen` (or consciously keep it and delete the routes). Fix Sidebar to emit one kind of navigation.

**Phase 1 — Make the backend return real monitoring data**
1. `changeDetector.js`: add `return response` (both functions).
2. `competitor.worker.js`: persist a `ChangeReport` after a diff when a previous snapshot exists.
3. `monitoring.controller.js`: query `ChangeReport`, build `reports[]` + `aiByDomain`, rename `reportingFrequency→cadencePerWeek` and `overallFindings→overallFinding`, drop hardcoded values.

**Phase 2 — Wire the client container**
4. Fix `WeeklyMonitoring.jsx` import paths; mount it at `/dashboard` (and route `/change_detail` through it or add `/change_detail/:domain`).
5. Rewrite `fetchMonitoringStatus` to use the shared axios `api` instance and the `/monitoring/status/:workspaceId` path.
6. Feed real `workspaceId` from the workspace store.

**Phase 3 — Fix the surrounding bugs**
7. Sidebar analysis sub-links (`/analysis/:id`).
8. `Analysis.jsx` dead store read; `page.api.js` GET bodies; env/port sanity.

**Phase 4 — Verify**
9. Manual pass per screen: fresh account (no analysis) → empty states; one analysis, no monitoring → competitor strip only; monitoring with a real ChangeReport → changes + detail view + CSV export. Confirm severity counts and filters. Check auth/refresh still holds across these calls.

**Phase 5 — Enhancements** (§5, as time allows): real `scoreVsYou`, unread badges, manual rescan, AI interpretation.

---

### Suggested starting point
Phase 1 first — until the server returns real `reports`, the client has nothing to render even once wired. Phase 0 (navigation) can run in parallel since it's isolated to the client shell. I'd tackle **Phase 1 → Phase 2** as the first executable milestone that makes Dashboard + Change Details actually light up.
