import React, { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

import ChangeDetails from "./ChangeDetails";
import useMonitoringStatus from "../../../hooks/useMonitoringStatus";
import usePageNav from "../../../store/pageNav.store";

/* Data container for ChangeDetails. Picks the report for the :domain route
   param (or the first available report when the route is /change_detail with
   no domain). When no report exists yet, <ChangeDetails/> renders its own
   "monitoring set up — no report yet" / "no changes" states, so we always
   pass the schedule info through. */
function StateBlock({ children }) {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-16 text-center text-(--text-light)">
      {children}
    </div>
  );
}

export default function ChangeDetailsScreen() {
  const { domain: domainParam } = useParams();
  const navigate = useNavigate();
  const { status, loading, error, refetch } = useMonitoringStatus();

  const setNav = usePageNav((s) => s.setNav);
  const clearNav = usePageNav((s) => s.clearNav);

  // Competitor switcher in the header — jump between competitors' change reports.
  const switcherCompetitors = status?.competitors || [];
  const activeDomain = domainParam ? decodeURIComponent(domainParam) : (status?.reports?.[0]?.domain || null);
  const switcherKey = switcherCompetitors.map((c) => c.domain).join("|");
  useEffect(() => {
    if (switcherCompetitors.length > 1) {
      setNav(
        { items: switcherCompetitors.map((c) => ({ key: c.domain, label: c.domain })), activeKey: activeDomain },
        (d) => navigate(`/change_detail/${encodeURIComponent(d)}`)
      );
    } else {
      clearNav();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [switcherKey, activeDomain]);
  useEffect(() => () => clearNav(), [clearNav]);

  if (loading) return <StateBlock>Loading changes…</StateBlock>;

  if (error) {
    return (
      <StateBlock>
        <p className="text-(--accent) font-semibold">Couldn't load changes</p>
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
  const reports = s.reports || [];
  const competitors = s.competitors || [];

  const domain = domainParam
    ? decodeURIComponent(domainParam)
    : reports[0]?.domain || null;

  const report = reports.find((r) => r.domain === domain) || null;
  const ai = (s.aiByDomain || {})[domain] || null;
  const competitor = competitors.find((c) => c.domain === domain) || null;

  return (
    <ChangeDetails
      changeReport={report}
      aiInterpretation={ai}
      analysisUrl={competitor?.analysisUrl}
      lastMonitoredAt={s.lastMonitoredAt}
      nextMonitoredAt={s.nextMonitoredAt}
      cadencePerWeek={s.cadencePerWeek}
      monitoringEnabled={s.monitoringEnabled}
      monitoringPaused={s.monitoringPaused}
      trialExpired={s.trialExpired}
      onUpgrade={() => navigate("/settings/billing")}
    />
  );
}
