import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCompetitorHistory } from "../../../api/history.api";

const fmtDate = (iso) => {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  catch { return String(iso).slice(0, 10); }
};
const titleCase = (s = "") => String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const sevPill = (s) => {
  const v = String(s || "").toLowerCase();
  if (v === "critical") return "bg-(--primary) text-white";
  if (v === "high") return "bg-[rgba(255,107,107,0.12)] text-(--accent)";
  if (v === "medium") return "bg-[rgba(254,211,48,0.16)] text-(--warning-dark)";
  return "bg-(--bg) text-(--text-light)";
};

/* Small SVG trend of change activity (advanced / Pro only). */
function TrendChart({ trend }) {
  const pts = trend.filter((t) => t && t.date);
  if (pts.length < 2) return null;
  const w = 640, h = 120, pad = 8;
  const max = Math.max(...pts.map((p) => p.changeScore || 0), 10);
  const bw = (w - pad * 2) / pts.length;
  return (
    <div className="rounded-2xl border border-(--border) bg-white p-5 shadow-(--shadow-sm)">
      <h3 className="text-base font-bold text-(--primary)">Change activity over time</h3>
      <p className="mt-0.5 text-sm text-(--text-light)">Change score per monitoring run</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-4 w-full" preserveAspectRatio="none" role="img" aria-label="Change activity trend">
        {pts.map((p, i) => {
          const bh = Math.max(2, ((p.changeScore || 0) / max) * (h - pad * 2));
          const x = pad + i * bw;
          const color = (p.changeScore || 0) >= 70 ? "var(--accent)" : (p.changeScore || 0) >= 35 ? "var(--warning)" : "var(--secondary)";
          return <rect key={i} x={x + bw * 0.15} y={h - pad - bh} width={bw * 0.7} height={bh} rx="2" fill={color} />;
        })}
      </svg>
      <div className="mt-2 flex justify-between text-[11px] text-(--text-light)">
        <span>{fmtDate(pts[0].date)}</span>
        <span>{fmtDate(pts[pts.length - 1].date)}</span>
      </div>
    </div>
  );
}

/* Compact SVG line trend for a single metric over time (advanced / Pro). */
function LineTrend({ points, accessor, label, sub, format }) {
  const data = points.map((p) => ({ date: p.date, v: Number(accessor(p)) })).filter((d) => Number.isFinite(d.v));
  if (data.length < 2) return null;
  const w = 320, h = 84, pad = 8;
  const vals = data.map((d) => d.v);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const x = (i) => pad + i * ((w - pad * 2) / (data.length - 1));
  const y = (v) => h - pad - ((v - min) / range) * (h - pad * 2);
  const path = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.v).toFixed(1)}`).join(" ");
  const last = data[data.length - 1].v, first = data[0].v;
  const delta = last - first;
  return (
    <div className="rounded-2xl border border-(--border) bg-white p-4 shadow-(--shadow-sm)">
      <div className="flex items-baseline justify-between">
        <h4 className="text-sm font-bold text-(--primary)">{label}</h4>
        <span className="text-sm font-extrabold text-(--secondary-dark)">{format(last)}</span>
      </div>
      <p className="text-xs text-(--text-light)">
        {sub}
        {delta !== 0 && (
          <span className={`ml-1 font-semibold ${delta > 0 ? "text-(--accent)" : "text-(--secondary-dark)"}`}>
            {delta > 0 ? "▲" : "▼"} {format(Math.abs(delta))}
          </span>
        )}
      </p>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 w-full" preserveAspectRatio="none" role="img" aria-label={`${label} trend`}>
        <path d={path} fill="none" stroke="var(--secondary)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="flex justify-between text-[11px] text-(--text-light)"><span>{fmtDate(data[0].date)}</span><span>{fmtDate(data[data.length - 1].date)}</span></div>
    </div>
  );
}

function LockedUpsell({ onUpgrade }) {
  return (
    <div className="rounded-2xl border border-dashed border-(--border) bg-white p-10 text-center">
      <p className="text-lg font-semibold text-(--primary)">🔒 Historical tracking is a Growth feature</p>
      <p className="mx-auto mt-2 max-w-xl text-sm text-(--text-light)">
        See how this competitor has changed over time — a full timeline of price moves, new products and messaging updates across every monitoring run. Upgrade to Growth for the historical timeline, or Pro for advanced trends and export.
      </p>
      <button type="button" onClick={onUpgrade}
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-(--accent) px-5 py-2.5 text-sm font-bold text-white transition hover:bg-(--accent-dark)">
        Upgrade plan
      </button>
    </div>
  );
}

export default function CompetitorHistory({ competitorId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (!competitorId) { setLoading(false); return; }
    let alive = true;
    setLoading(true);
    getCompetitorHistory(competitorId)
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [competitorId]);

  if (loading) return <div className="rounded-2xl border border-(--border) bg-white p-8 text-center text-sm text-(--text-light)">Loading history…</div>;
  if (!data) return <div className="rounded-2xl border border-(--border) bg-white p-8 text-center text-sm text-(--text-light)">Couldn't load history.</div>;
  if (data.locked) return <LockedUpsell onUpgrade={() => navigate("/settings/billing")} />;

  const { timeline = [], trend = [], metrics = [], advanced } = data;
  const currency = metrics.find((m) => m.currency)?.currency || "";

  const exportCsv = () => {
    const esc = (v) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const rows = [["date", "severity", "totalChanges", "changeScore", "changeType", "detail"]];
    timeline.forEach((e) => {
      if (!e.changes.length) rows.push([fmtDate(e.monitoredAt), e.overallSeverity, e.totalChanges, e.changeScore, "", ""]);
      e.changes.forEach((c) => rows.push([fmtDate(e.monitoredAt), e.overallSeverity, e.totalChanges, e.changeScore, c.type, c.whyImportant || ""]));
    });
    const blob = new Blob(["﻿" + rows.map((r) => r.map(esc).join(",")).join("\n")], { type: "text/csv;charset=utf-8;" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `history-${data.domain || "competitor"}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-(--primary)">History</h2>
          <p className="text-sm text-(--text-light)">
            {data.totalCycles || 0} monitoring run{(data.totalCycles || 0) === 1 ? "" : "s"} tracked
            {advanced ? " · advanced tracking" : ""}
          </p>
        </div>
        {advanced && timeline.length > 0 && (
          <button type="button" onClick={exportCsv}
            className="inline-flex items-center gap-1.5 rounded-lg border border-(--border) bg-white px-3 py-1.5 text-xs font-semibold text-(--text-light) transition hover:border-(--secondary) hover:text-(--secondary-dark)">
            ↓ Export CSV
          </button>
        )}
      </div>

      {advanced && metrics.length >= 2 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <LineTrend points={metrics} accessor={(p) => p.avgPrice} label="Average price"
            sub={currency ? `In ${currency}` : "Average price"} format={(v) => (v == null ? "—" : Math.round(v).toLocaleString())} />
          <LineTrend points={metrics} accessor={(p) => p.totalProducts} label="Catalog size"
            sub="Unique products" format={(v) => (v == null ? "—" : Math.round(v))} />
          <LineTrend points={metrics} accessor={(p) => p.inStockCount} label="In stock"
            sub="Products in stock" format={(v) => (v == null ? "—" : Math.round(v))} />
        </div>
      )}

      {advanced && <TrendChart trend={trend} />}

      {timeline.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-(--border) bg-white p-10 text-center">
          <p className="font-semibold text-(--primary)">No changes recorded yet</p>
          <p className="mx-auto mt-1 max-w-xl text-sm text-(--text-light)">Once monitoring detects changes for this competitor, they'll build up here as a timeline.</p>
        </div>
      ) : (
        <div className="relative space-y-4 border-l-2 border-(--border) pl-6">
          {timeline.map((entry) => (
            <div key={entry.id} className="relative">
              <span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-white bg-(--accent)" />
              <div className="rounded-2xl border border-(--border) bg-white p-5 shadow-(--shadow-sm)">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${sevPill(entry.overallSeverity)}`}>{entry.overallSeverity}</span>
                  <span className="text-sm font-semibold text-(--primary)">{fmtDate(entry.monitoredAt)}</span>
                  <span className="text-xs text-(--text-light)">· {entry.totalChanges} change{entry.totalChanges === 1 ? "" : "s"} · score {entry.changeScore}</span>
                </div>
                <ul className="mt-3 space-y-1.5">
                  {entry.changes.slice(0, 6).map((c, i) => (
                    <li key={i} className="text-sm text-(--text)">
                      <span className="font-semibold text-(--primary)">{titleCase(c.type)}</span>
                      {c.product ? <span className="text-(--text-light)"> · {c.product}</span> : null}
                      {c.changePercent != null ? <span className={`ml-2 font-bold ${c.changePercent > 0 ? "text-(--accent)" : "text-(--secondary-dark)"}`}>{c.changePercent > 0 ? "+" : ""}{c.changePercent}%</span> : null}
                      {c.whyImportant ? <span className="block text-xs text-(--text-light)">{c.whyImportant}</span> : null}
                    </li>
                  ))}
                  {entry.changes.length > 6 && <li className="text-xs text-(--text-light)">+{entry.changes.length - 6} more</li>}
                </ul>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
