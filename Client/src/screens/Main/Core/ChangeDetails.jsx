import React, { useMemo, useState } from 'react';
import { relativeFuture, fmtDateTime, cadenceLabel } from '../../../components/features/WeeklyMonitoring/changeReportUtils';

/* ─────────────────────────────────────────────────────────────
   ChangeDetails — data-driven view over the Python change_detection_app
   report (detector.py schema) plus an optional AI interpretation.

   Props:
     changeReport     detector output: { domain, overallSeverity, changeScore,
                      summary, changes[], warnings, extractionStable, ... }
     aiInterpretation optional AI JSON: { strategicIntent, impactScore,
                      whyThisMatters[], recommendedActions[] }
     analysisUrl      optional link to the competitor's full analysis page
     nextMonitoredAt  ISO | null — when the next comparison is scheduled.
     cadencePerWeek   number — plan cadence, display only.
     lastMonitoredAt  ISO | null — null ⇒ never monitored yet.

   No sample/hardcoded data. When there is no report for this competitor yet
   it shows when monitoring will next run; when a run happened but nothing
   changed it says so and shows the next run. Real changes render as before.
──────────────────────────────────────────────────────────────── */

const arr = (v) => (Array.isArray(v) ? v : []);
const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);

const GROUPS = [
  { key: 'pricing', label: 'Pricing & Promotions', types: ['price_change', 'sale_started', 'sale_ended', 'plan_price_change', 'pricing_plan_added', 'pricing_plan_removed'] },
  { key: 'catalog', label: 'Catalog & Products', types: ['new_product', 'product_removed', 'removed_product', 'variant_count_change', 'categories_added', 'categories_removed'] },
  { key: 'availability', label: 'Availability', types: ['out_of_stock', 'back_in_stock'] },
  { key: 'merchandising', label: 'Merchandising', types: ['rank_change'] },
  { key: 'messaging', label: 'Messaging & Positioning', types: ['name_change', 'description_change', 'hero_change', 'headline_change', 'feature_change'] },
  { key: 'site', label: 'Site & Navigation', types: ['navigation_change', 'platform_change', 'siteType_change', 'category_change'] },
];
const groupOf = (type = '') => GROUPS.find((g) => g.types.includes(type))?.key
  || (/(price|plan|sale|discount)/.test(type) ? 'pricing'
    : /(product|categor|variant)/.test(type) ? 'catalog'
    : /(stock)/.test(type) ? 'availability'
    : /(nav|platform|site)/.test(type) ? 'site'
    : /(name|desc|hero|headline|feature|messag)/.test(type) ? 'messaging' : 'other');

const SEV_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };
const sevClass = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return 'bg-(--primary) text-white border-(--primary)';
  if (s === 'high') return 'bg-[rgba(255,107,107,0.10)] text-(--accent) border-[rgba(255,107,107,0.25)]';
  if (s === 'medium') return 'bg-[rgba(254,211,48,0.16)] text-(--warning-dark) border-[rgba(254,211,48,0.4)]';
  return 'bg-(--bg) text-(--text-light) border-(--border)';
};
const Pill = ({ children, sev = 'low', className = '' }) => (
  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.05em] ${sevClass(sev)} ${className}`}>{children}</span>
);
const titleCase = (s = '') => String(s).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const fmtDate = (iso) => { if (!iso) return null; try { return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return String(iso).slice(0, 10); } };
const fmtVal = (v, type = '') => {
  if (v === true) return /stock/.test(type) ? 'In stock' : 'Yes';
  if (v === false) return /stock/.test(type) ? 'Out of stock' : 'No';
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v);
};

function changeHeadline(c) {
  const name = c.product?.name || c.plan?.name;
  switch (c.type) {
    case 'price_change': return `${name}: price ${c.direction === 'decrease' ? 'dropped' : 'increased'} ${Math.abs(num(c.changePercent) ?? 0)}%`;
    case 'plan_price_change': return `Plan "${name}": price changed ${num(c.changePercent) !== null ? `${c.changePercent > 0 ? '+' : ''}${c.changePercent}%` : ''}`;
    case 'pricing_plan_added': return `New pricing plan: "${name}"${c.plan?.priceRaw ? ` at ${c.plan.priceRaw}` : ''}`;
    case 'pricing_plan_removed': return `Pricing plan removed: "${name}"`;
    case 'sale_started': return `${name}: promotion started${num(c.discountPercent) !== null ? ` (${c.discountPercent}% off)` : ''}`;
    case 'sale_ended': return `${name}: promotion ended`;
    case 'new_product': return `New product: ${name}`;
    case 'product_removed': case 'removed_product': return `Product removed: ${name}`;
    case 'out_of_stock': return `${name}: went out of stock`;
    case 'back_in_stock': return `${name}: back in stock`;
    case 'rank_change': return `${name}: moved ${Math.abs(num(c.positionsMoved) ?? 0)} positions ${num(c.positionsMoved) > 0 ? 'up' : 'down'} (${c.oldRank} → ${c.newRank})`;
    case 'name_change': return `Product renamed`;
    case 'variant_count_change': return `${name}: variants ${c.oldValue} → ${c.newValue}`;
    case 'navigation_change': return 'Main navigation changed';
    case 'categories_added': return `New categories: ${arr(c.categories).join(', ')}`;
    case 'categories_removed': return `Categories removed: ${arr(c.categories).join(', ')}`;
    default: return `${titleCase(c.type)}${name ? `: ${name}` : ''}`;
  }
}

function BeforeAfter({ c }) {
  const hasOldNew = c.oldValue !== undefined || c.newValue !== undefined;
  const chips = [
    ...arr(c.addedLabels).map((l) => ({ l, add: true })),
    ...arr(c.removedLabels).map((l) => ({ l, add: false })),
    ...arr(c.categories).map((l) => ({ l, add: c.type !== 'categories_removed' })),
  ];
  if (!hasOldNew && !chips.length) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {hasOldNew && (
        <div className="flex items-center gap-2 rounded-lg bg-(--bg) px-3 py-2 text-sm">
          <span className="text-(--text-light) line-through decoration-[rgba(255,107,107,0.6)]">{fmtVal(c.oldValue, c.type)}</span>
          <span className="text-(--text-light)">→</span>
          <span className="font-semibold text-(--primary)">{fmtVal(c.newValue, c.type)}</span>
          {num(c.changePercent) !== null && (
            <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${c.changePercent > 0 ? 'bg-[rgba(255,107,107,0.12)] text-(--accent)' : 'bg-[rgba(78,205,196,0.15)] text-(--secondary-dark)'}`}>
              {c.changePercent > 0 ? '+' : ''}{c.changePercent}%
            </span>
          )}
        </div>
      )}
      {chips.map((x, i) => (
        <span key={i} className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${x.add ? 'border-[rgba(38,222,129,0.35)] bg-[rgba(38,222,129,0.1)] text-(--success-dark)' : 'border-(--border) bg-(--bg) text-(--text-light) line-through'}`}>
          {x.add ? '+ ' : '− '}{x.l}
        </span>
      ))}
    </div>
  );
}

function ChangeRow({ c }) {
  return (
    <div className="rounded-xl border border-(--border) bg-(--card) p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Pill sev={c.severity}>{c.severity}</Pill>
        <span className="text-xs font-semibold uppercase tracking-wide text-(--text-light)">{titleCase(c.type)}</span>
        {c.product?.category && <span className="rounded-full bg-(--bg) px-2 py-0.5 text-xs text-(--text-light)">{c.product.category}</span>}
      </div>
      <p className="mt-2 font-semibold text-(--primary)">
        {c.product?.productUrl
          ? <a href={c.product.productUrl} target="_blank" rel="noreferrer" className="hover:text-(--accent) hover:underline">{changeHeadline(c)}</a>
          : changeHeadline(c)}
      </p>
      {c.whyImportant && <p className="mt-1 text-sm text-(--text-light)">{c.whyImportant}</p>}
      <BeforeAfter c={c} />
    </div>
  );
}

function SummaryStat({ label, value, accentClass = 'text-(--primary)' }) {
  return (
    <div className="rounded-2xl border border-(--border) bg-(--card) p-4 text-center shadow-(--shadow-sm)">
      <p className={`text-3xl font-extrabold ${accentClass}`}>{value ?? 0}</p>
      <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-(--text-light)">{label}</p>
    </div>
  );
}

/* Shared empty-state shell for the "not monitored yet" / "no changes" / "locked" views. */
function MonitoringNotice({ domain, title, body, nextMonitoredAt, cadencePerWeek, analysisUrl, action }) {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <div className="rounded-3xl border border-(--border) bg-(--card) p-8 text-center sm:p-12">
        {domain && <p className="text-sm font-semibold uppercase tracking-wide text-(--text-light)">{domain}</p>}
        <h1 className="mt-2 text-2xl font-extrabold tracking-[-0.02em] text-(--primary) sm:text-3xl">{title}</h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-(--text-light)">{body}</p>
        {nextMonitoredAt && (
          <p className="mt-5 inline-block rounded-full border border-(--border) bg-(--bg) px-4 py-2 text-sm text-(--text)">
            Next check <strong className="text-(--primary)">{relativeFuture(nextMonitoredAt)}</strong>
            {cadencePerWeek ? ` · runs ${cadenceLabel(cadencePerWeek)}` : ''}
            {' '}({fmtDateTime(nextMonitoredAt)})
          </p>
        )}
        {action && <div className="mt-6">{action}</div>}
        {analysisUrl && (
          <div className="mt-6">
            <a href={analysisUrl} className="inline-flex items-center gap-2 rounded-xl bg-(--accent) px-5 py-3 text-sm font-bold text-white transition hover:bg-(--accent-dark)">
              View full competitor analysis →
            </a>
          </div>
        )}
      </div>
    </section>
  );
}

export default function ChangeDetails({ changeReport, report, data, aiInterpretation, aiResult, analysisUrl, nextMonitoredAt, cadencePerWeek, lastMonitoredAt, monitoringEnabled = true, monitoringPaused = false, trialExpired = false, onUpgrade }) {
  const provided = changeReport || report || (data && Array.isArray(data.changes) ? data : null);
  const r = provided || {};

  const [sevFilter, setSevFilter] = useState('all');
  const changes = useMemo(() => {
    const list = arr(r.changes).filter((c) => sevFilter === 'all' || String(c.severity).toLowerCase() === sevFilter);
    return [...list].sort((a, b) => (SEV_ORDER[b.severity] || 0) - (SEV_ORDER[a.severity] || 0));
  }, [r.changes, sevFilter]);

  const grouped = useMemo(() => {
    const map = new Map();
    changes.forEach((c) => {
      const g = groupOf(c.type);
      if (!map.has(g)) map.set(g, []);
      map.get(g).push(c);
    });
    return [...GROUPS.map((g) => g.key), 'other']
      .filter((k) => map.has(k))
      .map((k) => ({ key: k, label: GROUPS.find((g) => g.key === k)?.label || 'Other', items: map.get(k) }));
  }, [changes]);

  const s = r.summary || {};
  const sevCounts = [
    { key: 'critical', label: 'Critical', value: s.criticalChanges, cls: 'text-(--primary)' },
    { key: 'high', label: 'High', value: s.highChanges, cls: 'text-(--accent)' },
    { key: 'medium', label: 'Medium', value: s.mediumChanges, cls: 'text-(--warning-dark)' },
    { key: 'low', label: 'Low', value: s.lowChanges, cls: 'text-(--text-light)' },
  ];
  const score = num(r.changeScore) ?? 0;
  const period = [fmtDate(r.previousGeneratedAt), fmtDate(r.currentGeneratedAt)].filter(Boolean).join(' → ');

  const downloadChangesCsv = () => {
    const cols = ['group', 'type', 'severity', 'change', 'item', 'url', 'oldValue', 'newValue', 'changePercent', 'whyImportant'];
    const esc = (v) => { const s = v === null || v === undefined ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const lines = arr(r.changes).map((c) => [
      groupOf(c.type), c.type, c.severity, changeHeadline(c),
      c.product?.name || c.plan?.name || '', c.product?.productUrl || '',
      fmtVal(c.oldValue, c.type), fmtVal(c.newValue, c.type),
      c.changePercent ?? '', c.whyImportant || '',
    ].map(esc).join(','));
    const blob = new Blob(['﻿' + cols.join(',') + '\n' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `changes-${r.domain || 'site'}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  };

  // ── Trial ended → monitoring paused (read-only) ─────────────────────────
  // Takes priority over the plan-based states below: a trial carries a
  // monitoring cadence, so without this an ended trial would fall through to
  // "monitoring set up — next check in N days" (see monitoring.controller).
  if (monitoringPaused && !provided) {
    return (
      <MonitoringNotice
        title="Monitoring paused — your free trial ended"
        body="Change tracking is on hold now that your trial has ended, so no new snapshots are being taken. Upgrade to resume monitoring and start receiving change reports again."
        analysisUrl={analysisUrl}
        action={onUpgrade && (
          <button type="button" onClick={onUpgrade}
            className="inline-flex items-center gap-2 rounded-xl bg-(--primary) px-5 py-3 text-sm font-bold text-white transition hover:opacity-90">
            Upgrade to resume
          </button>
        )}
      />
    );
  }

  // ── Monitoring not included on this plan (free / one-time) ──────────────
  if (!monitoringEnabled && !provided) {
    return (
      <MonitoringNotice
        title="🔒 Monitoring isn't included on your plan"
        body="Your current plan runs a one-time analysis. Upgrade to a monitoring package to track competitor changes over time."
        analysisUrl={analysisUrl}
        action={onUpgrade && (
          <button type="button" onClick={onUpgrade}
            className="inline-flex items-center gap-2 rounded-xl bg-(--primary) px-5 py-3 text-sm font-bold text-white transition hover:opacity-90">
            Upgrade plan
          </button>
        )}
      />
    );
  }

  // ── No report for this competitor yet ──────────────────────────────────
  if (!provided) {
    const everRan = !!lastMonitoredAt;
    return (
      <MonitoringNotice
        title={everRan ? 'No change report for this competitor yet' : 'Monitoring is set up — no report yet'}
        body={
          everRan
            ? 'The next comparison will produce this competitor’s first change report.'
            : 'Change tracking compares each competitor against its previous snapshot. Your first change report appears after the next scheduled run.'
        }
        nextMonitoredAt={nextMonitoredAt}
        cadencePerWeek={cadencePerWeek}
        analysisUrl={analysisUrl}
      />
    );
  }

  // ── A run happened, but nothing changed for this competitor ─────────────
  if (arr(r.changes).length === 0) {
    return (
      <MonitoringNotice
        domain={r.domain}
        title="No changes this period"
        body={`We compared ${r.domain || 'this site'}${period ? ` (${period})` : ''} against the previous snapshot and found no meaningful changes.`}
        nextMonitoredAt={nextMonitoredAt}
        cadencePerWeek={cadencePerWeek}
        analysisUrl={analysisUrl}
      />
    );
  }

  return (
    <section className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      {/* ─── Header ─── */}
      <div className="mb-6 overflow-hidden rounded-3xl bg-(--primary) p-6 text-white sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Pill sev={r.overallSeverity} className="!border-white/20">{r.overallSeverity} impact</Pill>
              {r.changesTruncated && <span className="text-xs text-white/50">List truncated</span>}
            </div>
            <h1 className="mt-3 text-2xl font-extrabold tracking-[-0.02em] sm:text-3xl">
              Changes on <em className="font-['Fraunces',Georgia,serif] font-light italic text-(--secondary)">{r.domain}</em>
            </h1>
            {period && <p className="mt-2 text-sm text-white/60">Compared snapshots: {period}</p>}
            {nextMonitoredAt && <p className="mt-1 text-sm text-white/60">Next check {relativeFuture(nextMonitoredAt)} ({fmtDateTime(nextMonitoredAt)})</p>}
            {monitoringPaused && (
              <p className="mt-2 inline-flex items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-sm text-white/80">
                Monitoring paused — your free trial ended. This is the last report; {onUpgrade
                  ? <button type="button" onClick={onUpgrade} className="font-semibold underline underline-offset-2 hover:opacity-80">upgrade to resume</button>
                  : "upgrade to resume"}.
              </p>
            )}
            {r.extractionStable === false && (
              <p className="mt-3 rounded-lg border border-(--warning) bg-[rgba(254,211,48,0.12)] px-3 py-2 text-sm text-(--warning)">
                ⚠ Extraction was unstable between snapshots — some changes below may be scraping artifacts rather than real site changes.
              </p>
            )}
            {arr(r.warnings).map((w, i) => <p key={i} className="mt-2 text-xs text-(--warning)">⚠ {w}</p>)}
          </div>
          <div className="min-w-[150px] rounded-2xl border border-white/15 bg-white/[0.04] px-5 py-4 text-center">
            <p className="text-4xl font-extrabold text-(--secondary)">{score}</p>
            <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-white/55">Change score / 100</p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-(--secondary)" style={{ width: `${score}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* ─── Severity summary + filter ─── */}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        <SummaryStat label="Total changes" value={s.totalChanges ?? arr(r.changes).length} />
        {sevCounts.map((x) => (
          <button key={x.key} type="button" onClick={() => setSevFilter(sevFilter === x.key ? 'all' : x.key)}
            className={`rounded-2xl border p-4 text-center shadow-(--shadow-sm) transition ${sevFilter === x.key ? 'border-(--primary) bg-[rgba(26,26,46,0.03)] ring-1 ring-(--primary)' : 'border-(--border) bg-(--card) hover:border-(--text-light)'}`}>
            <p className={`text-3xl font-extrabold ${x.cls}`}>{x.value ?? 0}</p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-(--text-light)">{x.label}{sevFilter === x.key ? ' ✕' : ''}</p>
          </button>
        ))}
      </div>

      {/* ─── Grouped change list ─── */}
      {arr(r.changes).length > 0 && (
        <div className="mb-3 flex justify-end">
          <button type="button" onClick={downloadChangesCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border border-(--border) bg-(--card) px-2.5 py-1 text-xs font-semibold text-(--text-light) transition hover:border-(--secondary) hover:text-(--secondary-dark)">
            ↓ Download all changes (CSV)
          </button>
        </div>
      )}
      {grouped.length === 0 && (
        <div className="rounded-2xl border border-dashed border-(--border) bg-(--bg) p-8 text-center text-(--text-light)">
          {sevFilter !== 'all' ? `No ${sevFilter} changes in this report.` : 'No changes detected between these snapshots.'}
        </div>
      )}
      <div className="space-y-6">
        {grouped.map((g) => (
          <div key={g.key}>
            <h2 className="mb-3 text-lg font-bold tracking-[-0.01em] text-(--primary)">
              {g.label} <span className="ml-1 rounded-full bg-(--border) px-2 py-0.5 align-middle text-xs font-bold text-(--text-light)">{g.items.length}</span>
            </h2>
            <div className="space-y-3">{g.items.map((c, i) => <ChangeRow key={i} c={c} />)}</div>
          </div>
        ))}
      </div>

      {/* ─── Cross-link to full analysis ─── */}
      {analysisUrl && (
        <div className="mt-8">
          <a href={analysisUrl} className="inline-flex items-center gap-2 rounded-xl bg-(--accent) px-5 py-3 text-sm font-bold text-white shadow-(--shadow-sm) transition hover:bg-(--accent-dark)">
            View full competitor analysis →
          </a>
        </div>
      )}

      <p className="mt-8 text-center text-xs text-(--text-light)">
        IntelShift uses AI and can make mistakes. Verify important changes on the competitor's live site before acting.
      </p>
    </section>
  );
}
