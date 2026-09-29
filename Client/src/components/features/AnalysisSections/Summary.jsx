import React from 'react';
import { pickSource, Card, Pill, getPriceRows, getInventoryRows, getCatalogRows, getDomains, getSeoRows, getTrustRows, getMatchups, getCurrency, getWhoWinsWhere, getPriorityInsights, inferBusinessType, money, pct, limitText, getContentDepthRows, getSaleDiscountRows, getNavigation } from './_helpers';
import { ChartBox, buildCompetitiveScores, competitiveRadarChart, toCollectionChartRows } from './SectionCharts';

/* Overview = the verdict, not the warehouse:
   1. Bottom line — one synthesized sentence
   2. Three delta tiles (price / assortment / stock) with who-leads
   3. Who wins where (AI, with a deterministic fallback so it's never empty)
   4. Top findings (AI, with a deterministic fallback)
   5. Competitive radar
   Full tables live in the Pricing and Assortment tabs — Overview never repeats them. */

const num = (v) => (v === null || v === undefined || v === '' || Number.isNaN(Number(v)) ? null : Number(v));

function WhoWinsWhere({ dims, domains }) {
  if (!dims.length) return null;
  const mine = dims.filter((d) => d.winner === domains.user);
  const theirs = dims.filter((d) => d.winner === domains.competitor);
  return (
    <Card title="Who wins where" subtitle="Verdict per dimension from the analyzed pages.">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-[rgba(78,205,196,0.3)] bg-[rgba(78,205,196,0.06)] p-4">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-(--secondary-dark)">You lead</p>
          <div className="flex flex-wrap gap-2">
            {mine.length ? mine.map((d) => <span key={d.key} className="rounded-full bg-(--card) px-3 py-1 text-sm font-semibold text-(--text) shadow-(--shadow-sm)">{d.label}</span>) : <span className="text-sm text-(--text-light)">No dimension leads in this analysis</span>}
          </div>
        </div>
        <div className="rounded-xl border border-[rgba(255,107,107,0.25)] bg-[rgba(255,107,107,0.05)] p-4">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-(--accent)">{domains.competitor || 'Competitor'} leads</p>
          <div className="flex flex-wrap gap-2">
            {theirs.length ? theirs.map((d) => <span key={d.key} className="rounded-full bg-(--card) px-3 py-1 text-sm font-semibold text-(--text) shadow-(--shadow-sm)">{d.label}</span>) : <span className="text-sm text-(--text-light)">No dimension leads in this analysis</span>}
          </div>
        </div>
      </div>
    </Card>
  );
}

function DeltaTile({ label, userText, compText, note, tone }) {
  const noteColor = tone === 'good' ? 'text-(--secondary-dark)' : tone === 'risk' ? 'text-(--accent)' : 'text-(--text-light)';
  return (
    <div className="rounded-xl border border-(--border) bg-(--card) p-4">
      <p className="mb-3 text-xs font-bold uppercase tracking-wide text-(--text-light)">{label}</p>
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-(--secondary-dark)">You</p>
          <p className="text-lg font-bold text-(--text)">{userText ?? '—'}</p>
        </div>
        <div className="text-right">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-(--accent)">Them</p>
          <p className="text-lg font-bold text-(--text)">{compText ?? '—'}</p>
        </div>
      </div>
      {note ? <p className={`mt-3 text-sm font-semibold ${noteColor}`}>{note}</p> : null}
    </div>
  );
}

export default function Summary(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const domains = getDomains(ai, comparison, aiPayload);
  const price = getPriceRows(ai, comparison, aiPayload);
  const inventory = getInventoryRows(ai, comparison, aiPayload);
  const catalog = getCatalogRows(ai, comparison, aiPayload);
  const seo = getSeoRows(ai, comparison, aiPayload);
  const trust = getTrustRows(ai, comparison, aiPayload);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const businessType = inferBusinessType(comparison, aiPayload);
  const currency = getCurrency(ai, comparison, aiPayload);
  const collectionRows = toCollectionChartRows(matchups);
  const contentDepthRows = getContentDepthRows(ai, comparison, aiPayload);
  const saleRows = getSaleDiscountRows(ai, comparison, aiPayload);
  const navigation = getNavigation(ai, comparison, aiPayload);
  const scoreData = buildCompetitiveScores({ catalogRows: catalog, inventoryRows: inventory, priceRows: price, seoRows: seo, trustRows: trust, collectionRows, contentDepthRows, saleRows, navigation });

  const comp = domains.competitor || 'the competitor';
  const userPrice = price.find(r => r.domain === domains.user) || price[0] || {};
  const compPrice = price.find(r => r.domain === domains.competitor) || price[1] || {};
  const userInv = inventory.find(r => r.domain === domains.user) || inventory[0] || {};
  const compInv = inventory.find(r => r.domain === domains.competitor) || inventory[1] || {};
  const userCat = catalog.find(r => r.domain === domains.user) || catalog[0] || {};
  const compCat = catalog.find(r => r.domain === domains.competitor) || catalog[1] || {};
  const cur = userPrice.currency || currency;

  const uAvg = num(userPrice.averagePrice), cAvg = num(compPrice.averagePrice);
  const uProd = num(userCat.uniqueProducts ?? userPrice.pricedProducts), cProd = num(compCat.uniqueProducts ?? compPrice.pricedProducts);
  const uStock = num(userInv.inStockRate), cStock = num(compInv.inStockRate);

  // ── Derived deltas (drive tiles, verdict, and the deterministic fallbacks) ──
  const pricePct = (uAvg != null && cAvg != null && cAvg > 0) ? Math.round(Math.abs(1 - uAvg / cAvg) * 100) : null;
  const prodDiff = (uProd != null && cProd != null) ? Math.abs(cProd - uProd) : null;
  const stockDiff = (uStock != null && cStock != null) ? Math.abs(uStock - cStock) : null;

  const tiles = [];
  if (uAvg != null || cAvg != null) {
    let note = null, tone = 'info';
    if (pricePct != null) {
      if (pricePct < 3) { note = 'Priced on par'; tone = 'info'; }
      else if (uAvg < cAvg) { note = `You're ${pricePct}% cheaper on average`; tone = 'good'; }
      else { note = `You're ${pricePct}% more premium`; tone = 'info'; }
    }
    tiles.push(<DeltaTile key="price" label="Average price" userText={uAvg != null ? money(uAvg, cur) : null} compText={cAvg != null ? money(cAvg, compPrice.currency || cur) : null} note={note} tone={tone} />);
  }
  if (uProd != null || cProd != null) {
    let note = null, tone = 'info';
    if (prodDiff != null) {
      if (prodDiff === 0) { note = 'Same catalog depth'; tone = 'info'; }
      else if (cProd > uProd) { note = `They list ${prodDiff} more products`; tone = 'risk'; }
      else { note = `You list ${prodDiff} more products`; tone = 'good'; }
    }
    tiles.push(<DeltaTile key="assort" label="Unique products found" userText={uProd != null ? uProd : null} compText={cProd != null ? cProd : null} note={note} tone={tone} />);
  }
  if (uStock != null || cStock != null) {
    let note = null, tone = 'info';
    if (stockDiff != null) {
      if (stockDiff < 0.02) { note = 'Availability on par'; tone = 'info'; }
      else if (uStock > cStock) { note = 'Your stock is healthier'; tone = 'good'; }
      else { note = 'Their stock is healthier'; tone = 'risk'; }
    }
    tiles.push(<DeltaTile key="stock" label="In-stock rate" userText={uStock != null ? pct(uStock) : null} compText={cStock != null ? pct(cStock) : null} note={note} tone={tone} />);
  }

  // ── Who wins where: AI first, deterministic fallback so it's never empty ──
  let whoWins = getWhoWinsWhere(ai);
  if (!whoWins.length) {
    const d = [];
    if (pricePct != null && pricePct >= 3) d.push({ key: 'price', label: 'Price accessibility', winner: uAvg <= cAvg ? domains.user : domains.competitor });
    if (prodDiff != null && prodDiff !== 0) d.push({ key: 'assortment', label: 'Assortment breadth', winner: uProd > cProd ? domains.user : domains.competitor });
    if (stockDiff != null && stockDiff >= 0.02) d.push({ key: 'stock', label: 'Stock health', winner: uStock > cStock ? domains.user : domains.competitor });
    whoWins = d;
  }

  // ── Top findings: AI first, deterministic fallback from the biggest deltas ──
  let topInsights = getPriorityInsights(ai).slice(0, 3);
  if (!topInsights.length) {
    const f = [];
    if (prodDiff != null && prodDiff !== 0) f.push({ severity: cProd > uProd ? 'high' : 'low', title: cProd > uProd ? `${comp} lists ${prodDiff} more products than you in the analyzed scope` : `You list ${prodDiff} more products than ${comp}`, whyItMatters: 'Assortment breadth shapes how much shopper demand each store can capture.' });
    if (pricePct != null && pricePct >= 3) f.push({ severity: 'medium', title: uAvg < cAvg ? `Your average price is ${pricePct}% below ${comp}` : `Your average price is ${pricePct}% above ${comp}`, whyItMatters: uAvg < cAvg ? 'A lower entry price wins price-sensitive shoppers — worth checking against margin.' : 'A premium position needs differentiation to justify the gap.' });
    if (stockDiff != null && stockDiff >= 0.02) f.push({ severity: uStock > cStock ? 'low' : 'high', title: uStock > cStock ? `Your availability is stronger: ${pct(uStock)} in stock vs ${pct(cStock)}` : `${comp} has healthier stock: ${pct(cStock)} vs your ${pct(uStock)}`, whyItMatters: 'Out-of-stock items are lost sales and can signal supply problems.' });
    topInsights = f.slice(0, 3);
  }

  return <div className="space-y-5">
    {tiles.length ? <div className="grid gap-3 sm:grid-cols-3">{tiles}</div> : null}
    {matchups.length > 1 ? (
      <p className="-mt-2 text-xs text-(--text-light)">
        Blends <span className="font-semibold text-(--text)">{matchups.length} matched collections</span> — per-collection detail is in the Assortment tab.
      </p>
    ) : null}

    <WhoWinsWhere dims={whoWins} domains={domains} />

    {topInsights.length ? <Card title="Top findings" subtitle="The signals that matter most — the full list is in the Actions tab.">
      <div className="space-y-3">{topInsights.map((x, i) => (
        <div key={i} className="rounded-xl border border-(--border) p-4">
          <div className="mb-2"><Pill tone={x.severity}>{x.severity || 'finding'}</Pill></div>
          <p className="font-semibold text-(--primary)">{x.title}</p>
          {x.whyItMatters && <p className="mt-1 text-sm text-(--text-light)">{limitText(x.whyItMatters, 200)}</p>}
        </div>
      ))}</div>
    </Card> : null}

    {catalog.length || inventory.length || price.length ? <ChartBox
      title="Competitive score radar"
      subtitle={`The dimensions behind the header scores — catalog depth, price access, stock health, SEO, trust, collection breadth, content depth, promotions and navigation — weighted for ${businessType === 'saas' ? 'SaaS' : businessType} analysis. Each compares the two stores on the analyzed pages.`}
      config={competitiveRadarChart(scoreData, domains.user || 'User', domains.competitor || 'Competitor')}
    /> : null}
  </div>;
}
