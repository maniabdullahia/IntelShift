import React from 'react';
import { pickSource, Card, getDomains, getMatchups, getInventoryRows, getPriceRows, getCurrency, arr, pct, money } from './_helpers';

export default function SwotAnalysis(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const domains = getDomains(ai, comparison, aiPayload);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const inventory = getInventoryRows(ai, comparison, aiPayload);
  const price = getPriceRows(ai, comparison, aiPayload);
  const actions = arr(ai?.recommendedActions || ai?.actionsBackedByEvidence);
  const userInv = inventory.find(r=>r.domain===domains.user)||{}; const compInv=inventory.find(r=>r.domain===domains.competitor)||{};
  const userPrice=price.find(r=>r.domain===domains.user)||{}; const compPrice=price.find(r=>r.domain===domains.competitor)||{};
  const has = matchups.length || inventory.length || price.length || actions.length;
  if(!has) return null;
  const currency=props.currency||getCurrency(ai,comparison,aiPayload);
  const strengths=[userInv.inStockRate!==undefined?`Stronger availability: ${pct(userInv.inStockRate)} in stock vs competitor ${pct(compInv.inStockRate)}`:null, userPrice.averagePrice&&compPrice.averagePrice&&userPrice.averagePrice>compPrice.averagePrice?`Higher premium ceiling / average price: ${money(userPrice.averagePrice,userPrice.currency||currency)}`:null].filter(Boolean);
  const weaknesses=matchups.filter(m=>m.assortmentGap?.direction==='competitor_broader').map(m=>`${m.category}: competitor broader by ${Math.abs(m.assortmentGap?.difference||0)} items`);
  const opportunities=actions.map(a=>a.recommendation||a.successMetric).filter(Boolean).slice(0,4);
  const threats=matchups.flatMap(m=>arr(m.topProductMatches).filter(x=>x.priceGap?.direction==='competitor_lower').map(x=>`${m.category}: competitor lower on matched items`)).slice(0,4);
  return <Card title="SWOT summary" subtitle="Auto-generated from available comparison signals."><div className="grid gap-4 md:grid-cols-2"><Box title="Strengths" items={strengths}/><Box title="Weaknesses" items={weaknesses}/><Box title="Opportunities" items={opportunities}/><Box title="Threats" items={[...new Set(threats)]}/></div></Card>;
}
function Box({title,items}){ return <div className="rounded-xl border border-slate-200 p-4"><p className="font-semibold text-slate-900">{title}</p>{items.length?<ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">{items.map((x,i)=><li key={i}>{x}</li>)}</ul>:<p className="mt-2 text-sm text-slate-500">No strong signal captured.</p>}</div> }
