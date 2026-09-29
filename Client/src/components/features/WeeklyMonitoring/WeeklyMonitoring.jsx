import React, { useMemo, useState, useEffect } from 'react';
import Dashboard from '../Dashboard/Dashboard';
import ChangeDetails from '../ChangeDetails/ChangeDetails';
import { fetchMonitoringStatus } from './changeDetection.api';

/* ─────────────────────────────────────────────────────────────
   WeeklyMonitoring — container for the monitoring home. Fetches one status
   payload and routes the Dashboard <-> ChangeDetails.

   The Dashboard is analysis + changes, so this container does NOT hard-gate
   the whole screen by plan. Trial/one-time users still see the Dashboard
   (their competitor analysis strip); only the changes SECTION shows an
   upsell. Package -> cadence and monitoringEnabled come from the backend.

   Status payload (from Node):
     {
       monitoringEnabled, package, cadencePerWeek,
       lastMonitoredAt, nextMonitoredAt, periodStart, periodEnd,
       overallFinding?,                 // executiveSummary.overallFinding
       competitors: [{ domain, scoreVsYou, threatLevel, lastAnalyzedAt,
                       analysisUrl, unreadChanges }],   // analysis summaries
       reports:     change_detection_v1[],              // [] until first run
       aiByDomain?: { [domain]: aiInterpretation }
     }

   Props:
     workspaceId      which workspace to load status for.
     initialStatus    optional pre-loaded status payload (skips fetch).
     onOpenAnalysis   optional (domain) => void — open a competitor's full
                      analysis page. Falls back to card analysisUrl if absent.
──────────────────────────────────────────────────────────────── */

function LoadingState() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-16 text-center text-(--text-light)">
      Loading your dashboard…
    </div>
  );
}

export default function WeeklyMonitoring({ workspaceId, initialStatus, onOpenAnalysis }) {
  const [view, setView] = useState('dashboard');
  const [status, setStatus] = useState(initialStatus || null);
  const [loading, setLoading] = useState(!initialStatus);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (initialStatus || !workspaceId) { setLoading(false); return; }
    let alive = true;
    setLoading(true);
    fetchMonitoringStatus({ workspaceId })
      .then((res) => alive && setStatus(res))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [initialStatus, workspaceId]);

  const reports = status?.reports || [];
  const activeDomain = view.startsWith('detail:') ? view.slice('detail:'.length) : null;
  const activeReport = useMemo(
    () => reports.find((r) => r.domain === activeDomain) || null,
    [reports, activeDomain],
  );

  if (loading) return <LoadingState />;
  if (error) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-16 text-center text-(--accent)">
        Couldn't load your dashboard: {error}
      </div>
    );
  }
  if (!status) return <LoadingState />;

  const schedule = {
    lastMonitoredAt: status.lastMonitoredAt,
    nextMonitoredAt: status.nextMonitoredAt,
    cadencePerWeek: status.cadencePerWeek,
  };

  // Detail view for one competitor. ChangeDetails renders its own
  // "no report yet" / "no changes" states, so activeReport may be null.
  if (activeDomain) {
    return (
      <div>
        <div className="mx-auto w-full max-w-6xl px-4 pt-6 sm:px-6">
          <button type="button" onClick={() => setView('dashboard')}
            className="inline-flex items-center gap-1.5 rounded-lg border border-(--border) bg-white px-3 py-1.5 text-sm font-semibold text-(--text-light) transition hover:border-(--accent) hover:text-(--accent)">
            Back to dashboard
          </button>
        </div>
        <ChangeDetails
          changeReport={activeReport}
          aiInterpretation={(status.aiByDomain || {})[activeDomain]}
          {...schedule}
        />
      </div>
    );
  }

  return (
    <Dashboard
      competitors={status.competitors}
      reports={reports}
      aiByDomain={status.aiByDomain}
      monitoringEnabled={status.monitoringEnabled}
      overallFinding={status.overallFinding}
      periodStart={status.periodStart}
      periodEnd={status.periodEnd}
      {...schedule}
      onOpenChange={(domain) => setView(`detail:${domain}`)}
      onOpenAnalysis={onOpenAnalysis}
    />
  );
}
