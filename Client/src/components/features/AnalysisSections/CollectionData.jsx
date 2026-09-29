import React from 'react';
import { ExternalLink } from 'lucide-react';
import { pickSource, Card, Stat, Pill, SimpleTable, DomainTag, getMatchups, getDomains, conceptLabel, confidenceTier, humanizeMatchReasons, money, pct } from './_helpers';
import { ChartBox, toCollectionChartRows, collectionStockChart, AssortmentGapHeatmap } from './SectionCharts';

/* NOTE: the category-coverage matrix was removed on purpose — with only a
   few analyzed pages, category inference overstated "gaps" and showed
   categories the competitor sells site-wide but weren't actually analyzed.
   Revisit if/when the Python side produces reliable per-page categories. */

export default function CollectionData(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const collectionRows = toCollectionChartRows(matchups);
  if (!matchups.length) return null;

  return <div className="space-y-5">
    <Card title={`Matched collections (${matchups.length} total matched)`} subtitle="Each paired collection, shown side by side. A product can sit in more than one collection.">
      <div className="space-y-6">{matchups.map((m,i)=><CollectionCard key={i} matchup={m} currency={props.currency} domains={domains}/>)}</div>
    </Card>

    {collectionRows.length ? <AssortmentGapHeatmap rows={collectionRows} /> : null}

    {collectionRows.some(r => r.userInStock || r.competitorInStock) ? <ChartBox
      title="Stock health by matched collection"
      subtitle="In-stock rate inside each matched category."
      config={collectionStockChart(collectionRows)}
    /> : null}
  </div>;
}

function CollectionCard({matchup:m,currency:fallbackCurrency='',domains={}}){
  const u=m.userCollection||{}; const c=m.competitorCollection||{}; const currency=u.currency||c.currency||fallbackCurrency;
  const isUserMapped = Array.isArray(m.matchReasons) && m.matchReasons.includes('user_mapped');
  const hasCategory = m.category && String(m.category).toLowerCase() !== 'unknown';
  const tier = confidenceTier(m.confidence);
  const reasons = humanizeMatchReasons(m.matchReasons);
  // Use the LIVE collection product counts (the same source as the table + heatmap:
  // what's actually on each collection page) for the cards, the gap, and the
  // direction — NOT the catalog-matched unmatched counts, which come from a
  // different, looser product set and disagreed with the table.
  const uCount = u.productCount ?? m.userCollectionProductCount ?? 0;
  const cCount = c.productCount ?? m.competitorCollectionProductCount ?? 0;
  const gap = Math.abs(cCount - uCount);
  const dirIsComp = cCount > uCount;
  const dir = cCount === uCount ? '' : (dirIsComp ? 'competitor_broader' : 'user_broader');
  // The broader side's CATEGORY label gets a solid dark chip + white text so it
  // stands out from the tint pills.
  const broaderStyle = { color: '#fff', background: 'var(--primary)', borderColor: 'var(--primary)' };
  const rows=[
    {side:'you',store:domains.user||'You',title:u.title,url:u.url||u.link||u.href||'',products:u.productCount ?? m.userCollectionProductCount,price:`${money(u.priceMin,currency)} – ${money(u.priceMax,currency)}`,avg:u.averagePrice?money(u.averagePrice,currency):null,stock:u.inStockRate!==undefined?pct(u.inStockRate):null},
    {side:'them',store:domains.competitor||'Competitor',title:c.title,url:c.url||c.link||c.href||'',products:c.productCount ?? m.competitorCollectionProductCount,price:`${money(c.priceMin,currency)} – ${money(c.priceMax,currency)}`,avg:c.averagePrice?money(c.averagePrice,currency):null,stock:c.inStockRate!==undefined?pct(c.inStockRate):null},
  ];
  return <div className="rounded-xl border border-(--border) bg-(--bg) p-5 shadow-(--shadow-sm)">
    <div className="mb-4 flex flex-wrap items-center gap-2">{hasCategory?(dir?<span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.05em]" style={broaderStyle}>{conceptLabel(m.category)}</span>:<Pill tone="low">{conceptLabel(m.category)}</Pill>):null}{!isUserMapped&&tier?<Pill tone="medium">{tier}</Pill>:null}{dir&&<Pill tone={dirIsComp?'high':'teal'}>{dir.replace(/_/g,' ')}</Pill>}</div>
    <div className="mb-4 grid gap-3 sm:grid-cols-3"><Stat label="Your Products" value={uCount} tone="user"/><Stat label="Their Products" value={cCount} tone="competitor"/><Stat label="Assortment gap" value={gap} tone="plain"/></div>
    <SimpleTable columns={[
      {key:'store',label:'Store',render:(v,r)=><DomainTag user={r.side==='you'}>{v}</DomainTag>},
      {key:'title',label:'Collection Name',render:(v,r)=> r.url ? <a href={r.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-(--text) hover:underline" title={`Open ${v||'collection'} in a new tab`}><ExternalLink className="w-3.5 h-3.5 shrink-0 opacity-70"/>{v}</a> : v},{key:'products',label:'Products'},{key:'price',label:'Price range'},{key:'avg',label:'Avg price'},{key:'stock',label:'In stock'},
    ]} rows={rows} headerClass="bg-(--card)"/>
    {!isUserMapped && reasons ? <p className="mt-2 text-xs text-(--text-light)">{reasons}</p> : null}
  </div>
}
