import { useState, useEffect } from 'react';
import { Clock3 } from 'lucide-react';

import { useNavigate, useSearchParams } from 'react-router-dom';

import Button from '../../../components/ui/Button'
import CreateCompetitor from '../../../components/features/Competitor/CreateCompetitor';
import CompetitorCard from '../../../components/features/Competitor/CompetitorCard';
import NoCompetetiorFallback from '../../../components/features/Competitor/NoCompetetiorFallback';

import Alert from '../../../components/shared/Alert';

import useWorkspaceStore from '../../../store/workspace.store'
import useAuthStore from '../../../store/auth.store';


function Competitors() {

  const [createCompetitorProcessSarted, setCreateCompetitorProcessStarted] = useState(false)

  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const workspace = useWorkspaceStore((state) => state.workspace);
  const workspaceCompetitors = workspace?.competitors?.filter((c) => c.role === "Competitor") || [];
  const competitorLimit = useAuthStore((state) => state?.user?.subscription?.planId?.limits?.competitors) || 0;
  const pagesPerCompetitor = useAuthStore((state) => state?.user?.subscription?.planId?.limits?.pagesPerCompetitor) || 0;
  const cadence = useAuthStore((state) => state?.user?.subscription?.planId?.planReportingFrequency);

  const removing = workspaceCompetitors.filter((c) => c.pendingChange === "remove");
  const removingCount = removing.length;
  // Display counts STILL include a competitor staged for removal — it's monitored
  // until the next run applies. (A staged-add competitor isn't monitored yet.)
  const monitoredCompetitors = workspaceCompetitors.filter((c) => c.pendingChange !== "add");
  const totalCompetitors = monitoredCompetitors.length;
  // For the ADD gate, a staged removal frees a slot so a replacement can go in now.
  const effectiveCount = workspaceCompetitors.filter((c) => c.pendingChange !== "remove").length;

  // ── Summary stats ─────────────────────────────────────────────────────────
  const isHomepageUrl = (raw) => {
    try {
      const s = String(raw || "").trim();
      if (!s) return false;
      const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
      return u.pathname === "" || u.pathname === "/";
    } catch {
      return false;
    }
  };
  const competitorsLeft = Math.max(0, competitorLimit - effectiveCount);
  // Pages actively monitored — excludes the homepage and pages staged to ADD (not
  // monitored until the next run). Pages staged to REMOVE are STILL monitored until
  // that run applies, so they stay in the count.
  const trackedPages = (c) =>
    (c.pages || []).filter((p) => p.pendingChange !== "add" && !isHomepageUrl(p.url)).length;
  const totalTracked = monitoredCompetitors.reduce((sum, c) => sum + trackedPages(c), 0);
  const pageCapacity = pagesPerCompetitor * competitorLimit;
  const totalRecentChanges = monitoredCompetitors.reduce((sum, c) => sum + (c.recentChanges || 0), 0);
  const nextScanAt = workspace?.nextScanAt;
  const CADENCE_LABEL = { daily: "Daily", "2d": "Every 2 days", "3d": "Every 3 days", weekly: "Weekly", monthly: "Monthly", once: "One-time" };
  const cadenceLabel = CADENCE_LABEL[String(cadence || "").toLowerCase()] || "—";
  const fmtDate = (d) => (d ? new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—");

  const stats = [
    { label: "Competitors", value: `${totalCompetitors}/${competitorLimit || "—"}`, sub: removingCount > 0 ? `${removingCount} removing · frees next run` : `${competitorsLeft} slot${competitorsLeft === 1 ? "" : "s"} left` },
    { label: "Pages monitored", value: pageCapacity ? `${totalTracked}/${pageCapacity}` : String(totalTracked), sub: "across all competitors" },
    { label: "Recent changes", value: String(totalRecentChanges), sub: "at last monitoring run" },
    { label: "Monitoring", value: cadenceLabel, sub: nextScanAt ? `Next: ${fmtDate(nextScanAt)}` : "Not scheduled" },
  ];


  const handleAddCompetitorCancellation = () => {
    setCreateCompetitorProcessStarted(false);
  }

  const handleAddCompetitor = () => {
    if (effectiveCount >= competitorLimit) {
      Alert.fire({
        icon: 'warning',
        title: 'Limit Reached',
        text: `Your current plan allows monitoring up to ${competitorLimit} ${competitorLimit === 1 ? 'competitor' : 'competitors'}. Please remove an existing competitor or upgrade your plan to add more.`,
      }).then((result) => {
        if (result.isConfirmed) {
          // Redirect to pricing page or open upgrade modal
          // console.log('Redirecting to pricing page...');
          // setcurrentScreen("billing_usage");
          navigate('/settings/billing');
        }});
      return;
    }
    setCreateCompetitorProcessStarted(true);
  }

  // Deep-link from the header usage pill ("+ Add competitor") opens the flow.
  useEffect(() => {
    if (searchParams.get('add') === '1') {
      handleAddCompetitor();
      searchParams.delete('add');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      {createCompetitorProcessSarted ? (
        <CreateCompetitor onCancel={handleAddCompetitorCancellation} />
      ) : (
        <div className="min-h-screen px-4 py-6 sm:px-6 sm:py-10">
          <div className="mx-auto w-full max-w-6xl">


            {workspaceCompetitors.length === 0 ? (
              <NoCompetetiorFallback onCreateCompetitor={() => setCreateCompetitorProcessStarted(true)} />
            ) : (
              <>
                {/* Header */}
                <div className="mb-6">
                  <h1 className="font-[Inter] tracking-tight text-3xl font-bold sm:text-4xl">Competitors</h1>
                  {workspaceCompetitors.length > 0 && (
                    <p className="text-(--text-light) text-sm my-2">Currently monitoring {totalCompetitors} {totalCompetitors === 1 ? 'competitor' : 'competitors'}</p>
                  )}
                </div>

                {/* Staged-removal note */}
                {removingCount > 0 && (
                  <div className="mb-6 flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm" style={{ borderColor: "#fcd34d", background: "#fffbeb", color: "#92400e" }}>
                    <Clock3 size={16} className="mt-0.5 shrink-0" />
                    <p>
                      {removingCount === 1
                        ? <><strong>{removing[0]?.name || "A competitor"}</strong> is staged for removal.</>
                        : <><strong>{removingCount} competitors</strong> are staged for removal.</>}
                      {" "}{removingCount === 1 ? "It" : "They"} will be removed on your next monitoring run{nextScanAt ? ` (around ${fmtDate(nextScanAt)})` : ""}. Add a replacement or undo the removal before then.
                    </p>
                  </div>
                )}

                {/* Summary stats */}
                <div className="mb-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
                  {stats.map((s) => (
                    <div key={s.label} className="rounded-2xl border border-(--border) bg-white p-4 shadow-sm">
                      <p className="text-xs font-semibold uppercase tracking-wide text-(--text-light)">{s.label}</p>
                      <p className="mt-1 text-2xl font-bold text-(--primary)">{s.value}</p>
                      <p className="mt-0.5 text-xs text-(--text-light)">{s.sub}</p>
                    </div>
                  ))}
                </div>

                <Button title='+ Add more Competitors' onClick={handleAddCompetitor}></Button>

                <div className="mt-10 overflow-x-auto rounded-2xl bg-white shadow">
                  <table className="w-full min-w-170">
                    <thead className="text-left text-sm text-(--text-light) uppercase">
                      <tr className='border-none'>
                        <th className="px-4 py-3">Competitor</th>
                        <th className="px-4 py-3">Pages Monitored</th>
                        <th className="px-4 py-3">Recent Changes</th>
                        <th className="px-4 py-3">Last Updated</th>
                      </tr>
                    </thead>

                    <tbody>
                      {workspaceCompetitors?.map((comp, index) => (
                        <CompetitorCard key={index} competitor={comp} pagesLimit={pagesPerCompetitor} />
                      ))}
                    </tbody>
                  </table>
                </div>

              </>
            )}
          </div >
        </div >
      )
      }
    </>
  )
}

export default Competitors
