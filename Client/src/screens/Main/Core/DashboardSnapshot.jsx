import React, { useState } from "react";

/* ─────────────────────────────────────────────────────────────
   DashboardSnapshot — the visual "Competitive Overview" panel. Rolls the
   per-competitor analysis metrics up into ONE summary across all tracked
   competitors (you = teal / --secondary, competitors = coral / --accent):
   competitive standing, price position, availability, plus a short
   "where you stand" highlight list. The AI executive summary is kept as a
   collapsible "Analyst summary".

   Degrades gracefully: with no derived metrics it just shows the summary text,
   so it never renders worse than the old paragraph.

   Props:
     summary         aggregated metrics across all competitors (or null)
     overallFinding  the AI executiveSummary text (string | null)
     loading         true while competitor analyses are still being fetched
──────────────────────────────────────────────────────────────── */

const pctText = (v) => (v == null ? "—" : `${Math.round((v > 1 ? v / 100 : v) * 1000) / 10}%`);
const barPct = (v) => (v == null ? 0 : Math.max(0, Math.min(100, (v > 1 ? v / 100 : v) * 100)));

function Badge({ tone = "neutral", children }) {
  const cls =
    tone === "win"
      ? "bg-[rgba(38,222,129,0.14)] text-(--success-dark)"
      : tone === "risk"
        ? "bg-[rgba(255,107,107,0.12)] text-(--accent)"
        : tone === "warn"
          ? "bg-[rgba(254,211,48,0.18)] text-(--warning-dark)"
          : "bg-(--bg) text-(--text-light)";
  return <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-bold ${cls}`}>{children}</span>;
}

function Kpi({ label, value, sub }) {
  return (
    <div className="bg-white rounded-2xl border border-(--border) shadow-(--shadow-sm) p-5">
      <p className="text-[11px] font-bold uppercase tracking-wide text-(--text-light)">{label}</p>
      <p className="mt-2 text-2xl font-extrabold text-(--primary) leading-tight">{value}</p>
      {sub && <p className="mt-2 text-xs text-(--text-light) leading-snug">{sub}</p>}
    </div>
  );
}

export default function DashboardSnapshot({ summary, overallFinding, loading }) {
  const [open, setOpen] = useState(false);

  // Fallback: no metrics yet — show the summary text (styled), never worse than before.
  if (!summary) {
    if (!overallFinding && !loading) return null;
    return (
      <div className="mt-4 rounded-2xl border border-(--border) bg-white p-5 shadow-(--shadow-sm)">
        {loading ? (
          <p className="text-sm text-(--text-light)">Building your competitive snapshot…</p>
        ) : (
          <p className="text-(--text) leading-relaxed">{overallFinding}</p>
        )}
      </div>
    );
  }

  const n = summary.competitorCount || 0;
  const cLabel = `${n} competitor${n === 1 ? "" : "s"}`;
  const score = summary.score || {};
  const price = summary.price || {};
  const inStock = summary.inStock || {};
  const products = summary.products || {};

  const scoreWin = (score.leadCount ?? 0) * 2 >= n;
  const stockWin = inStock.user != null && inStock.competitorAvg != null && inStock.user >= inStock.competitorAvg;

  // Price KPI — count-led so it can't contradict itself. "Priced below N of M"
  // is the headline; the average gap % is only a secondary descriptor and is
  // shown as "roughly matched" when it's within a point either way.
  const rated = price.ratedCount || 0;
  const lead = price.leadCount || 0;
  let priceValue = "—";
  let priceSub = <>Across {cLabel}</>;
  if (rated) {
    const majority = lead * 2 >= rated;
    priceValue = lead === rated ? `Below all ${rated}` : `Below ${lead} of ${rated}`;
    const g = price.avgGapPct;
    const gapPhrase =
      g != null && Math.abs(g) >= 1
        ? `~${Math.abs(Math.round(g))}% ${g > 0 ? "below" : "above"} competitor median`
        : "roughly matched on price";
    priceSub = (
      <>
        <Badge tone={majority ? "win" : "risk"}>{majority ? "You lead" : "At risk"}</Badge> Competitors you're priced below · {gapPhrase}
      </>
    );
  }

  // "Where you stand" highlights across all competitors.
  const highlights = [];
  if (price.ratedCount) {
    highlights.push(
      price.leadCount >= price.ratedCount - price.leadCount
        ? { tone: "win", text: `Priced below ${price.leadCount} of ${price.ratedCount} competitors` }
        : { tone: "risk", text: `Priced above ${price.ratedCount - price.leadCount} of ${price.ratedCount} competitors` }
    );
  }
  if (products.user != null && products.competitorAvg != null) {
    highlights.push(
      products.user >= products.competitorAvg
        ? { tone: "win", text: `Broader catalog than average (${products.user} vs ${products.competitorAvg} avg)` }
        : { tone: "risk", text: `Narrower catalog than average (${products.user} vs ${products.competitorAvg} avg)` }
    );
  }
  if (inStock.trailingCount > 0) {
    highlights.push({ tone: "risk", text: `Availability trails ${inStock.trailingCount} of ${n} competitors` });
  } else if (stockWin && inStock.user != null) {
    highlights.push({ tone: "win", text: `Availability leads across analyzed competitors` });
  }
  if (summary.promoGapCount > 0) {
    highlights.push({ tone: "warn", text: `${summary.promoGapCount} competitor${summary.promoGapCount === 1 ? "" : "s"} run homepage discount messaging — you don't` });
  }

  return (
    <div className="mt-5 space-y-5">
      {/* Aggregate KPI cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Kpi
          label="Competitive standing"
          value={<span>Ahead of {score.leadCount ?? 0}<span className="text-base font-semibold text-(--text-light)"> of {n}</span></span>}
          sub={<><Badge tone={scoreWin ? "win" : "risk"}>{scoreWin ? "Leading" : "Behind"}</Badge> Avg score {score.user ?? "—"} vs {score.competitorAvg ?? "—"} across {cLabel}</>}
        />
        <Kpi label="Price position" value={priceValue} sub={priceSub || `Across ${cLabel}`} />
        <Kpi
          label="Availability"
          value={
            <span>
              <span className={!stockWin && inStock.user != null ? "text-(--accent)" : "text-(--secondary-dark)"}>{pctText(inStock.user)}</span>
              <span className="text-base font-semibold text-(--text-light)"> vs {pctText(inStock.competitorAvg)}</span>
            </span>
          }
          sub={<><Badge tone={stockWin ? "win" : "risk"}>{stockWin ? "You lead" : "At risk"}</Badge> Your in-stock rate vs competitor average</>}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Availability comparison */}
        {(inStock.user != null || inStock.competitorAvg != null) && (
          <div className="rounded-2xl border border-(--border) bg-white p-5 shadow-(--shadow-sm)">
            <h3 className="text-base font-bold text-(--primary)">Availability</h3>
            <p className="mt-0.5 text-sm text-(--text-light)">In-stock rate — you vs competitor average</p>
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-2">
                <span className="w-28 shrink-0 text-xs font-semibold text-(--text)">You</span>
                <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-(--bg)"><span className="block h-full rounded-full bg-(--secondary)" style={{ width: `${barPct(inStock.user)}%` }} /></div>
                <span className="w-14 shrink-0 text-right text-xs font-bold text-(--secondary-dark)">{pctText(inStock.user)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-28 shrink-0 text-xs font-semibold text-(--text)">Competitor avg</span>
                <div className="h-3.5 flex-1 overflow-hidden rounded-full bg-(--bg)"><span className="block h-full rounded-full bg-(--accent)" style={{ width: `${barPct(inStock.competitorAvg)}%` }} /></div>
                <span className="w-14 shrink-0 text-right text-xs font-bold text-(--accent)">{pctText(inStock.competitorAvg)}</span>
              </div>
            </div>
          </div>
        )}

        {/* Where you stand */}
        {highlights.length > 0 && (
          <div className="rounded-2xl border border-(--border) bg-white p-5 shadow-(--shadow-sm)">
            <h3 className="text-base font-bold text-(--primary)">Where you stand</h3>
            <p className="mt-0.5 text-sm text-(--text-light)">Summary across {cLabel}</p>
            <ul className="mt-4 space-y-2.5">
              {highlights.map((h, i) => (
                <li key={i} className="flex items-start gap-2.5 text-sm text-(--text)">
                  <span className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${h.tone === "win" ? "bg-(--secondary)" : h.tone === "warn" ? "bg-(--warning)" : "bg-(--accent)"}`} />
                  <span>{h.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Collapsible analyst summary (the original AI text) */}
      {overallFinding && (
        <div className="rounded-2xl border border-(--border) bg-white shadow-(--shadow-sm)">
          <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-5 py-3.5 text-left">
            <span className="text-xs font-bold uppercase tracking-wide text-(--primary)">Analyst summary</span>
            <span className={`text-(--text-light) transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
          </button>
          {open && <p className="border-t border-(--border) px-5 py-4 text-sm leading-relaxed text-(--text-light)">{overallFinding}</p>}
        </div>
      )}
    </div>
  );
}
