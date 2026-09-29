import React from "react";
import { useNavigate } from "react-router-dom";

import Dashboard from "./Dashboard";
import ActionCenter from "../../../components/features/ActionCenter/ActionCenter";
import useMonitoringStatus from "../../../hooks/useMonitoringStatus";
import useDashboardAnalytics from "../../../hooks/useDashboardAnalytics";
import useEntitlement from "../../../hooks/useEntitlement";

/* Data container for the Dashboard. Fetches the monitoring status payload and
   feeds the presentational <Dashboard/>. Navigation is URL-based (Phase 0):
   - onOpenChange(domain)   -> /change_detail/:domain
   - onOpenAnalysis(domain) -> that competitor's analysis page */
function StateBlock({ children }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-16 text-center text-(--text-light)">
      {children}
    </div>
  );
}

export default function DashboardScreen() {
  const navigate = useNavigate();
  const { status, loading, error, refetch } = useMonitoringStatus();
  const { byDomain, aggregate, loading: analyticsLoading } = useDashboardAnalytics(status?.competitors);
  const { trialExpired } = useEntitlement();

  if (loading) return <StateBlock>Loading your dashboard…</StateBlock>;

  if (error) {
    return (
      <StateBlock>
        <p className="text-(--accent) font-semibold">Couldn't load your dashboard</p>
        <p className="mt-1 text-sm">{error}</p>
        <button
          type="button"
          onClick={refetch}
          className="mt-4 rounded-lg border border-(--border) bg-white px-4 py-2 text-sm font-semibold text-(--text-light) transition hover:border-(--primary) hover:text-(--primary)"
        >
          Try again
        </button>
      </StateBlock>
    );
  }

  const s = status || {};
  const competitors = s.competitors || [];

  const openAnalysis = (domain) => {
    const match = competitors.find((c) => c.domain === domain);
    if (match?.analysisUrl) navigate(match.analysisUrl);
  };

  return (
    <>
      <div className="mx-auto w-full max-w-6xl px-4 pt-6">
        <ActionCenter />
      </div>
      <Dashboard
      competitors={competitors}
      reports={s.reports}
      aiByDomain={s.aiByDomain}
      monitoringEnabled={s.monitoringEnabled}
      overallFinding={s.overallFinding}
      lastMonitoredAt={s.lastMonitoredAt}
      nextMonitoredAt={s.nextMonitoredAt}
      cadencePerWeek={s.cadencePerWeek}
      periodStart={s.periodStart}
      periodEnd={s.periodEnd}
      snapshot={aggregate}
      metricsByDomain={byDomain}
      analyticsLoading={analyticsLoading}
      trialExpired={trialExpired}
      onOpenChange={(domain) => navigate(`/change_detail/${encodeURIComponent(domain)}`)}
      onOpenAnalysis={openAnalysis}
      onUpgrade={() => navigate("/settings/billing")}
    />
    </>
  );
}
