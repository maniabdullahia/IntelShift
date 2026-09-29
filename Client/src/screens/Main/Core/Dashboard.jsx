import React, { useMemo } from 'react';
import {
  arr, num, buildRollup, changeHeadline, sevPillClass, sevTextClass,
  relativeDate, relativeFuture, fmtDate, fmtDateTime, cadenceLabel,
  monitoringState, titleCase,
} from '../../../components/features/WeeklyMonitoring/changeReportUtils';
import DashboardSnapshot from './DashboardSnapshot';
import Favicon from '../../../components/shared/Favicon';

const clampScore = (n) => Math.max(0, Math.min(100, Math.round(Number(n) || 0)));
const rate01 = (v) => (v == null ? null : v > 1 ? v / 100 : v);
const pctText = (v) => { const r = rate01(v); return r == null ? '—' : `${Math.round(r * 1000) / 10}%`; };
const moneyText = (v, c = '') => (v == null || v === '' ? '—' : `${c ? c + ' ' : ''}${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`);

/* ─────────────────────────────────────────────────────────────
   Dashboard — the monitoring home. Two independent halves:

   1. COMPETITOR STRIP (analysis-derived) — one card per competitor with the
      analysis score vs the user, last-analyzed date, and a link into that
      competitor's full analysis. This exists as soon as the first analysis
      runs, for every plan (including trial), and does NOT depend on change
      monitoring. (IMPROVEMENT_PLAN §4.)

   2. WEEKLY CHANGES (monitoring-derived) — severity stats, top changes and
      recommended actions from the Python change_detection_app. This is a
      SECTION with its own state (disabled / never-run / no-changes /
      has-changes). It never takes over the whole page.

   No sample/hardcoded data. Each half renders only what it's given.

   Props:
     competitors      analysis summaries: [{ domain, scoreVsYou, threatLevel,
                      lastAnalyzedAt, analysisUrl, unreadChanges }]. Drives the
                      strip; hidden when empty.
     reports          change_detection_v1[] — one per monitored competitor.
     aiByDomain       optional { [domain]: aiInterpretation } for actions.
     monitoringEnabled  false for plans without change tracking (e.g. trial) →
                      the changes section shows a compact upsell, analysis stays.
     lastMonitoredAt / nextMonitoredAt / cadencePerWeek / periodStart / periodEnd
                      scheduling info (backend-computed; display only).
     overallFinding   optional one-line executiveSummary headline.
     onOpenChange     (domain) => void — open ChangeDetails for a competitor.
     onOpenAnalysis   (domain) => void — open the full analysis for a competitor.
──────────────────────────────────────────────────────────────── */

function Shell({ children }) {
  return (
    <div className="bg-gray-50 px-4 py-6 sm:px-6 sm:py-8">
      <div className="mx-auto w-full max-w-6xl">{children}</div>
    </div>
  );
}

function NextRunNote({ nextMonitoredAt, cadencePerWeek }) {
  if (!nextMonitoredAt) return null;
  return (
    <span>
      Next check {relativeFuture(nextMonitoredAt)}
      {cadencePerWeek ? ` (monitoring runs ${cadenceLabel(cadencePerWeek)})` : ''}.
    </span>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <div className="text-sm text-(--text-light) uppercase tracking-wide">{label}</div>
      <div className={`text-3xl font-bold my-3 ${accent}`}>{value}</div>
      <div className="text-sm text-(--text-light)">{value === 1 ? '1 change' : `${value} changes`} this period</div>
    </div>
  );
}

/* Analysis-derived card: score vs you + link to full analysis, augmented with
   the latest change signal for that domain when monitoring exists. */
function CompetitorCard({ c, report, metrics, onOpenAnalysis, onOpenChange }) {
  const hasMetrics = !!metrics;
  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Favicon domain={c.domain} size={30} tile />
          <p className="font-semibold text-(--primary) truncate">{c.domain}</p>
        </div>
        {c.threatLevel && (
          <span className={`rounded-full border px-2 py-0.5 text-[11px] font-bold uppercase ${sevPillClass(c.threatLevel)}`}>
            {c.threatLevel}
          </span>
        )}
      </div>

      {hasMetrics ? (
        <div className="mt-3 space-y-3">
          <div>
            <div className="flex items-baseline justify-between">
              <p className={`text-3xl font-extrabold ${sevTextClass(c.threatLevel)}`}>{metrics.score?.competitor ?? '—'}</p>
              <p className="text-xs text-(--text-light)">vs you {metrics.score?.user ?? '—'}</p>
            </div>
            <p className="text-xs text-(--text-light) uppercase tracking-wide">Competitive score</p>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-(--bg)">
              <div className="h-full rounded-full bg-(--accent)" style={{ width: `${clampScore(metrics.score?.competitor)}%` }} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg bg-(--bg) px-2.5 py-1.5">
              <p className="text-(--text-light)">Their in-stock</p>
              <p className="font-bold text-(--primary)">{pctText(metrics.inStock?.competitor)}</p>
            </div>
            <div className="rounded-lg bg-(--bg) px-2.5 py-1.5">
              <p className="text-(--text-light)">Their avg price</p>
              <p className="font-bold text-(--primary)">{moneyText(metrics.price?.compAvg, metrics.price?.currency)}</p>
            </div>
          </div>
        </div>
      ) : (
        num(c.scoreVsYou) !== null && (
          <div className="mt-3">
            <p className={`text-3xl font-extrabold ${sevTextClass(c.threatLevel)}`}>{c.scoreVsYou}</p>
            <p className="text-xs text-(--text-light) uppercase tracking-wide">Competitive score vs you</p>
          </div>
        )
      )}

      <p className="mt-2 text-xs text-(--text-light)">
        {c.lastAnalyzedAt ? `Analyzed ${relativeDate(c.lastAnalyzedAt)}` : 'Analysis available'}
      </p>

      {/* change signal, only when a report exists for this domain */}
      {report && (
        <div className="mt-3 flex items-center justify-between rounded-lg bg-(--bg) px-3 py-2">
          <span className="text-xs text-(--text-light)">
            {(report.summary?.totalChanges ?? arr(report.changes).length) || 0} change
            {((report.summary?.totalChanges ?? arr(report.changes).length) || 0) === 1 ? '' : 's'} this period
          </span>
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${sevPillClass(report.overallSeverity)}`}>
            {report.overallSeverity}
          </span>
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {(onOpenAnalysis || c.analysisUrl) && (
          <button type="button"
            onClick={() => (onOpenAnalysis ? onOpenAnalysis(c.domain) : (window.location.href = c.analysisUrl))}
            className="flex-1 rounded-lg border border-(--border) px-3 py-2 text-sm font-semibold text-(--text-light) transition hover:border-(--primary) hover:text-(--primary)">
            View analysis
          </button>
        )}
        {report && onOpenChange && (
          <button type="button" onClick={() => onOpenChange(c.domain)}
            className="flex-1 rounded-lg bg-(--accent) px-3 py-2 text-sm font-bold text-white transition hover:bg-(--accent-dark)">
            View changes
          </button>
        )}
      </div>
    </div>
  );
}

function ChangeCard({ c, onOpenChange }) {
  return (
    <div className="bg-white rounded-2xl shadow p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Favicon domain={c._domain} size={30} tile className="mt-0.5" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-sm mb-2">
              <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${sevPillClass(c.severity)}`}>
                {titleCase(c.severity)} impact
              </span>
              <span className="text-(--text-light)">{relativeDate(c._date) || ''}</span>
            </div>
            <h3 className="text-lg font-semibold mb-1">{changeHeadline(c)}</h3>
            <p className="text-sm text-(--text-light)">
              {c._domain}{c.product?.category ? ` · ${c.product.category}` : ''} · {titleCase(c.type)}
            </p>
          </div>
        </div>
        {onOpenChange && (
          <button type="button" onClick={() => onOpenChange(c._domain)}
            className="shrink-0 rounded-lg border border-(--border) px-2.5 py-1 text-xs font-semibold text-(--text-light) transition hover:border-(--accent) hover:text-(--accent)">
            View details
          </button>
        )}
      </div>
      {c.whyImportant && <p className="text-(--text-light) text-sm mt-3">{c.whyImportant}</p>}
      {num(c.changePercent) !== null && (
        <p className="mt-2 text-sm">
          <span className="text-(--text-light) line-through">{c.oldValue}</span>
          <span className="text-(--text-light)"> to </span>
          <span className="font-semibold text-(--primary)">{c.newValue}</span>
          <span className={`ml-2 font-bold ${c.changePercent > 0 ? 'text-(--accent)' : 'text-(--secondary-dark)'}`}>
            {c.changePercent > 0 ? '+' : ''}{c.changePercent}%
          </span>
        </p>
      )}
    </div>
  );
}

/* Compact notice used inside the changes section only. */
function ChangesNotice({ title, body, foot, action }) {
  return (
    <div className="rounded-2xl border border-dashed border-(--border) bg-white p-6 text-center">
      <p className="font-semibold text-(--primary)">{title}</p>
      {body && <p className="mx-auto mt-1 max-w-xl text-sm text-(--text-light)">{body}</p>}
      {foot && <p className="mt-3 text-sm text-(--text-light)">{foot}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export default function Dashboard({
  competitors, reports, aiByDomain, monitoringEnabled = true,
  lastMonitoredAt, nextMonitoredAt, cadencePerWeek, periodStart, periodEnd,
  overallFinding, onOpenChange, onOpenAnalysis, onUpgrade,
  snapshot, metricsByDomain, analyticsLoading, trialExpired = false,
}) {
  const comps = arr(competitors);
  const list = arr(reports);
  const reportByDomain = useMemo(() => {
    const m = new Map();
    list.forEach((r) => m.set(r.domain, r));
    return m;
  }, [list]);

  const state = monitoringState({ monitoringEnabled, reports: list, lastMonitoredAt });
  const rollup = useMemo(() => buildRollup(list), [list]);
  const { totals, topChanges, count } = rollup;

  const actions = useMemo(() => {
    const out = [];
    Object.entries(aiByDomain || {}).forEach(([domain, ai]) => {
      arr(ai?.recommendedActions || ai?.actions).forEach((a) => {
        out.push({
          domain,
          title: a.title || a.recommendation || (typeof a === 'string' ? a : ''),
          detail: a.detail || '',
          priority: a.priority,
        });
      });
    });
    const rank = { high: 3, medium: 2, low: 1, p1: 3, p2: 2, p3: 1 };
    return out.sort((x, y) => (rank[String(y.priority).toLowerCase()] || 0) - (rank[String(x.priority).toLowerCase()] || 0));
  }, [aiByDomain]);

  const period = [fmtDate(periodStart), fmtDate(periodEnd)].filter(Boolean).join(' to ');
  const stats = [
    { label: 'Critical', value: totals.critical, accent: 'text-(--primary)' },
    { label: 'High Impact', value: totals.high, accent: 'text-(--accent)' },
    { label: 'Medium Impact', value: totals.medium, accent: 'text-(--warning-dark)' },
    { label: 'Low Impact', value: totals.low, accent: 'text-(--text-light)' },
  ].filter((s) => s.value > 0);

  // Nothing at all yet (no analysis, no monitoring) — the only true full-page empty.
  if (comps.length === 0 && list.length === 0) {
    return (
      <Shell>
        <h1 className="font-[Inter] tracking-tight text-3xl font-bold sm:text-4xl">Dashboard</h1>
        <div className="mt-8 rounded-2xl border border-dashed border-(--border) bg-white p-10 text-center">
          <p className="text-lg font-semibold text-(--primary)">Run your first analysis to get started</p>
          <p className="mx-auto mt-2 max-w-xl text-sm text-(--text-light)">
            Once you analyze a competitor, this dashboard fills with your competitive position and,
            on a monitoring plan, week-over-week changes.
          </p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mb-8">
        <h1 className="font-[Inter] tracking-tight text-3xl font-bold sm:text-4xl">Competitive Overview</h1>
        <p className="text-(--text-light) mt-2 text-sm">
          {comps.length > 0 && `${comps.length} competitor${comps.length === 1 ? '' : 's'} tracked`}
          {trialExpired ? (
            <span className="ml-1 font-medium text-(--accent)">· Monitoring paused — your free trial ended.</span>
          ) : (
            <>
              {monitoringEnabled && nextMonitoredAt ? ' · ' : ''}
              {monitoringEnabled && <NextRunNote nextMonitoredAt={nextMonitoredAt} cadencePerWeek={cadencePerWeek} />}
            </>
          )}
        </p>
        <DashboardSnapshot summary={snapshot} overallFinding={overallFinding} loading={analyticsLoading} />
      </div>

      {/* ── Analysis-derived competitor strip (always, when we have analysis) ── */}
      {comps.length > 0 && (
        <>
          <h2 className="text-xl font-semibold mb-4">Your Competitors</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
            {comps.map((c) => (
              <CompetitorCard key={c.domain} c={c} report={reportByDomain.get(c.domain)}
                metrics={metricsByDomain?.[c.domain]}
                onOpenAnalysis={onOpenAnalysis} onOpenChange={onOpenChange} />
            ))}
          </div>
        </>
      )}

      {/* ── Weekly changes section (scoped state) ── */}
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-xl font-semibold">Recent Changes</h2>
        {state === 'has_changes' && (
          <span className="text-sm text-(--text-light)">{period ? `${period} · ` : ''}{totals.total} change{totals.total === 1 ? '' : 's'}</span>
        )}
      </div>

      {/* Trial ended → monitoring paused. Takes priority over the plan-based
          states below (a trial reads as a monitoring plan, so without this the
          section would wrongly show the "one-time analysis" or "next check"
          copy). */}
      {trialExpired && (
        <ChangesNotice
          title="Monitoring paused — your free trial ended"
          body="Change tracking is on hold now that your trial has ended, so no new snapshots are being taken. Upgrade to resume monitoring and start receiving change reports again."
          action={onUpgrade && (
            <button type="button" onClick={onUpgrade}
              className="inline-flex items-center gap-2 rounded-xl bg-(--primary) px-5 py-2.5 text-sm font-bold text-white transition hover:opacity-90">
              Upgrade to resume
            </button>
          )}
        />
      )}
      {!trialExpired && state === 'disabled' && (
        <ChangesNotice
          title="🔒 Change tracking is a monitoring feature"
          body="Your current plan runs a one-time analysis. Upgrade to a monitoring package to track ongoing competitor changes here."
          action={onUpgrade && (
            <button type="button" onClick={onUpgrade}
              className="inline-flex items-center gap-2 rounded-xl bg-(--accent) px-5 py-2.5 text-sm font-bold text-white transition hover:bg-(--accent-dark)">
              Upgrade plan
            </button>
          )}
        />
      )}
      {!trialExpired && state === 'never_run' && (
        <ChangesNotice
          title="Monitoring is set up — no report yet"
          body="Change tracking compares each competitor against its previous snapshot, so the first change report appears after the next scheduled run."
          foot={<NextRunNote nextMonitoredAt={nextMonitoredAt} cadencePerWeek={cadencePerWeek} />}
        />
      )}
      {!trialExpired && state === 'no_changes' && (
        <ChangesNotice
          title="No changes this period"
          body={`We checked ${count > 0 ? `${count} competitor${count === 1 ? '' : 's'}` : 'your competitors'}${period ? ` between ${period}` : ''} and found no meaningful changes.`}
          foot={<NextRunNote nextMonitoredAt={nextMonitoredAt} cadencePerWeek={cadencePerWeek} />}
        />
      )}

      {state === 'has_changes' && (
        <>
          {stats.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-4 mb-8">
              {stats.map((item) => <StatCard key={item.label} {...item} />)}
            </div>
          )}
          <div className="space-y-6">
            {topChanges.slice(0, 6).map((c, i) => <ChangeCard key={i} c={c} onOpenChange={onOpenChange} />)}
          </div>
        </>
      )}

      {/* ── Recommended actions (from AI interpretation of changes) ── */}
      {actions.length > 0 && (
        <>
          <h2 className="text-xl font-semibold mt-10 mb-4">Recommended Actions</h2>
          <div className="space-y-4">
            {actions.slice(0, 6).map((action, index) => (
              <div key={index} className="bg-white rounded-2xl shadow p-5 border-l-4 border-(--accent)">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-medium">{action.title}</h3>
                  {action.priority && (
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${sevPillClass(action.priority)}`}>{action.priority}</span>
                  )}
                  <span className="text-xs text-(--text-light)">· {action.domain}</span>
                </div>
                {action.detail && <p className="text-sm text-(--text-light) mt-1">{action.detail}</p>}
              </div>
            ))}
          </div>
        </>
      )}

      <p className="mt-10 text-center text-xs text-(--text-light)">
        IntelShift uses AI and can make mistakes. Verify important changes on the competitor's live site before acting.
      </p>
    </Shell>
  );
}
