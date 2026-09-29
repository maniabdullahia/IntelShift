/* ─────────────────────────────────────────────────────────────
   Client for the monitoring status the change-tracking screens consume.

   IMPORTANT (from UNIFIED_API_README.md): do NOT call the Python API
   directly from the browser with the API key — it would be exposed in the
   bundle. Route through your own Node backend:

       React → Node (/api/monitoring/...) → Python (/api/v1/diff-snapshots)

   Node owns package → cadence, snapshot storage, the scheduled runs, and
   holds COMPINTEL_API_KEY server-side. React just reads status.

   We go through the shared axios `api` instance so requests carry the base
   URL, the Bearer token, and the 401 → refresh-token retry flow.
──────────────────────────────────────────────────────────────── */

import api from "../../../api/api";

/* Single call that powers the whole feature. Returns:
   {
     monitoringEnabled, package, cadencePerWeek,
     lastMonitoredAt, nextMonitoredAt, periodStart, periodEnd,
     overallFinding?,
     competitors: [{ domain, scoreVsYou, threatLevel, lastAnalyzedAt,
                     analysisUrl, unreadChanges }],
     reports: change_detection_v1[],   // [] until the first run
     aiByDomain?: { [domain]: aiInterpretation }
   }
*/
export async function fetchMonitoringStatus({ workspaceId } = {}) {
  if (!workspaceId) throw new Error("workspaceId is required to load monitoring status");
  const res = await api.get(`/monitoring/status/${encodeURIComponent(workspaceId)}`);
  return res.data;
}
