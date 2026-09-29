# Weekly Monitoring — setup across the 3 layers

Change tracking (Dashboard + ChangeDetails) is package-gated and fully
data-driven. No sample data, no hardcoded cadence. This is exactly what to do
in each of the three parts of the system.

---

## 1) React — what to add / replace / delete

**Add (new folder `WeeklyMonitoring/`):**

| File | Role |
|------|------|
| `WeeklyMonitoring/WeeklyMonitoring.jsx` | Container. Gates by plan, fetches monitoring status, routes Dashboard <-> ChangeDetails. **Mount this in your route.** |
| `WeeklyMonitoring/changeReportUtils.js` | Shared helpers (rollup, headlines, severity styles, `monitoringState`, schedule formatting). |
| `WeeklyMonitoring/changeDetection.api.js` | `fetchMonitoringStatus(workspaceId)` — calls your Node backend. |

**Replace:**

| File | Change |
|------|--------|
| `Dashboard/Dashboard.jsx` | Now data-driven with three states (never-run / no-changes / has-changes). No mock data. |
| `ChangeDetails/ChangeDetails.jsx` | Sample fallback removed; adds "next monitoring" + "no changes" states. Logic otherwise unchanged. |

**Delete (no longer used):**

- `ChangeDetails/sampleChangeReport.js`
- `WeeklyMonitoring/sampleWeeklyRollup.js` *(removed)*
- any `WeeklyMonitoring/fixtures/` sample JSON *(removed)*

**Mount it:**

```jsx
import WeeklyMonitoring from './WeeklyMonitoring/WeeklyMonitoring';

<Route path="/monitoring" element={<WeeklyMonitoring workspaceId={workspace.id} />} />
```

That's the whole React integration. `WeeklyMonitoring` handles loading, the
plan gate, empty states and the drill-down. It reads one payload from your
backend (below) and passes it down — React never computes the schedule or
knows package names.

**Import-path note:** these files assume `Dashboard/` and `WeeklyMonitoring/`
are siblings and `ChangeDetails/` is a sibling too (`../ChangeDetails/...`,
`../WeeklyMonitoring/...`). Adjust the relative paths if your tree differs.

---

## 2) Node (backend + database) — what your developer sets up

This is where the real new work is. Python and React are ready; Node is the
glue that stores snapshots, runs the schedule per package, and serves one
status payload.

### The one payload React needs

```http
GET /api/monitoring/status?workspaceId=...
```

```json
{
  "monitoringEnabled": true,          // false for free trial (1-time only)
  "package": "starter",               // 'starter' | 'growth' | 'pro' | 'trial'
  "cadencePerWeek": 1,                // starter 1, growth 2, pro 3, trial 0
  "lastMonitoredAt": "2026-07-15T07:00:00Z",  // null if never run
  "nextMonitoredAt": "2026-07-22T07:00:00Z",  // Node computes from cadence
  "periodStart": "2026-07-08T07:00:00Z",
  "periodEnd":   "2026-07-15T07:00:00Z",
  "reports": [ /* change_detection_v1 per competitor; [] until first run */ ],
  "aiByDomain": { /* optional: { "domain": aiInterpretation } */ }
}
```

React's three states come straight from this: `monitoringEnabled=false` ->
upsell; `reports=[]` & `lastMonitoredAt=null` -> "first run scheduled";
reports present with zero total changes -> "no changes this period"; otherwise
the rollup. So getting these fields right is all React needs.

### Package -> cadence config (lives here, NOT in React)

```js
const CADENCE_PER_WEEK = { trial: 0, starter: 1, growth: 2, pro: 3 };
// monitoringEnabled = CADENCE_PER_WEEK[plan] > 0
// nextMonitoredAt   = lastRun + (7 / cadence) days  (or first slot for new users)
```

### Database (minimum)

- `monitoring_config` — per workspace: `plan`, `competitors[]`, `userSite`, `enabled`.
- `snapshots` — `workspaceId`, `domain`, `capturedAt`, `snapshotJson` (site_snapshot_v2). Keep at least the last 2 per domain.
- `change_reports` — `workspaceId`, `domain`, `runAt`, `periodStart/End`, `reportJson` (change_detection_v1).
- `monitoring_runs` — `workspaceId`, `runAt`, `nextRunAt`, `status`.

### Scheduled job (per cadence)

For each workspace whose `nextRunAt` is due:
1. For each competitor: analyze its pages -> merge -> **current** `site_snapshot_v2` (Python `/api/v1/analyze-pages` + `/api/v1/merge-site`).
2. Load that competitor's **previous** snapshot from `snapshots`.
3. `POST /api/v1/diff-snapshots { previousSnapshot, currentSnapshot, settings }` -> store the `change_detection_v1` report.
4. Save the new snapshot as the latest; compute `nextRunAt` from cadence.
5. (Optional) if a report's `shouldSendToAI` is true, generate `aiByDomain[domain]`.

A weekly/2x/3x cron (or a scheduled task) triggers this.

### Security proxy

Never call Python from the browser with the API key. Node holds
`COMPINTEL_API_KEY` and proxies. `changeDetection.api.js` already targets
`/api/monitoring/...` for this reason.

---

## 3) Python — no changes required

Verified against your app:

- `POST /api/v1/diff-snapshots` already returns the exact `change_detection_v1`
  schema both screens consume.
- The **no-changes** case works out of the box: diffing identical/near-identical
  snapshots returns `changeScore 0`, `overallSeverity "low"`, empty `changes[]`,
  `shouldSendToAI false`, while still carrying `domain` + both timestamps — which
  is what the "no changes this period" state reads.

**Optional only:** if you want AI narrative text (`aiByDomain`) on the change
screens, add a small endpoint that feeds a report's `changes[]` to OpenAI and
returns `{ strategicIntent, whyThisMatters[], recommendedActions[] }`. Both
screens work fully without it — they degrade to deterministic detail.

---

## Testing a new user/competitor set

Because nothing is hardcoded, a new case works as soon as Node returns its
status payload. To test the diff engine directly on any pair of snapshots:

```bash
cd "Python app v2/change_detection_app"
python main.py <competitorX_week1>.json <competitorX_week2>.json -o report.json
```

`<...week1/2>.json` is the `data` field of a `competitor.json` (a
`site_snapshot_v2`). The resulting `report.json` is exactly one element of the
`reports[]` array your backend returns.
