import React, { useMemo, useState } from 'react';
import Favicon from '../../shared/Favicon';

export const isObj = (v) => v && typeof v === 'object' && !Array.isArray(v);
export const arr = (v) => Array.isArray(v) ? v : [];
export const obj = (v) => isObj(v) ? v : {};
export const hasValue = (v) => !(v === null || v === undefined || v === '' || (Array.isArray(v) && !v.length) || (isObj(v) && !Object.keys(v).length));
export const hasRows = (rows) => arr(rows).length > 0;
export function safe(v, fallback = '—') { if (v === null || v === undefined || v === '') return fallback; if (typeof v === 'boolean') return v ? 'Yes' : 'No'; return v; }
export function pct(v) { if (v === null || v === undefined || v === '') return '—'; const n=Number(v); if(!Number.isFinite(n)) return String(v); return `${Math.round((n > 1 ? n : n * 100) * 10) / 10}%`; }
// Currency intentionally has NO hardcoded default. Pass the currency detected
// from the data (see getCurrency). With no currency we show the plain number.
export function money(v, currency='') { if (v === null || v === undefined || v === '') return '—'; const n=Number(v); if(!Number.isFinite(n)) return String(v); return `${currency ? currency + ' ' : ''}${n.toLocaleString(undefined,{maximumFractionDigits:2})}`; }
export function compactNum(v){ if(v===null||v===undefined||v==='') return '—'; const n=Number(v); return Number.isFinite(n) ? n.toLocaleString(undefined,{maximumFractionDigits:2}) : String(v); }
export function limitText(s,n=180){ if(!s) return ''; const t=String(s).replace(/\s+/g,' ').trim(); return t.length>n ? `${t.slice(0,n)}…` : t; }
// Brief but COMPLETE: cut at sentence boundaries, never mid-word.
// Splits only on terminator + whitespace so "eveline.pk" / "in2it.com.pk"
// never count as sentence ends (the old regex silently dropped text
// before domain-name dots).
export function firstSentences(s, maxChars=320){
  if(!s) return '';
  const t=String(s).replace(/\s+/g,' ').trim();
  if(t.length<=maxChars) return t;
  const sentences=t.split(/(?<=[.!?])\s+/);
  let out='';
  for(const sen of sentences){
    if(out && (out+' '+sen).length>maxChars) break;
    out=out?`${out} ${sen}`:sen;
  }
  return out || t.slice(0,maxChars);
}

// Replace machine slugs inside AI-written sentences:
// "bundles_sets, nutrition" → "Bundles & gift sets, Nutrition & supplements".
export function humanizeSlugsInText(s){
  if(!s) return s;
  return String(s).replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (m)=>conceptLabel(m));
}
export function titleCase(s=''){ return String(s).replace(/_/g,' ').replace(/([a-z])([A-Z])/g,'$1 $2').replace(/\b\w/g, c=>c.toUpperCase()); }
export function firstAvailable(...values){ for(const v of values){ if(hasValue(v)) return v; } return undefined; }

export function getBundle(props={}){
  const candidate = props.analysis || props.result || props.data || {};
  const dataCandidate = candidate?.data && isObj(candidate.data) ? candidate.data : candidate;
  const ai = props.aiResult || props.aiAnalysis || candidate.aiResult || candidate.aiAnalysis || dataCandidate.aiResult || dataCandidate.aiAnalysis || (dataCandidate.schemaVersion && String(dataCandidate.schemaVersion).includes('ci_analysis') ? dataCandidate : null) || null;
  const comparison = props.comparison || props.comparisonData || candidate.comparison || dataCandidate.comparison || (dataCandidate.schemaVersion && String(dataCandidate.schemaVersion).includes('comparison_engine') ? dataCandidate : null) || null;
  const aiPayload = props.aiPayload || candidate.aiPayload || dataCandidate.aiPayload || (dataCandidate.schemaVersion && String(dataCandidate.schemaVersion).includes('ai_payload') ? dataCandidate : null) || null;
  return { ai: obj(ai), comparison: obj(comparison), aiPayload: obj(aiPayload) };
}
export const pickSource = getBundle;

/* ─── Brand-aligned UI primitives (tokens from theme/brand.css) ─── */

export function severityClass(sev='medium'){
  const s=String(sev||'').toLowerCase();
  if(['critical','urgent','p0','p1','high'].includes(s)) return 'bg-[rgba(255,107,107,0.10)] text-(--accent) border-[rgba(255,107,107,0.25)]';
  if(['medium','p2'].includes(s)) return 'bg-[rgba(254,211,48,0.16)] text-(--warning-dark) border-[rgba(254,211,48,0.4)]';
  if(['low','p3','p4'].includes(s)) return 'bg-(--bg) text-(--text-light) border-(--border)';
  return 'bg-[rgba(78,205,196,0.12)] text-(--secondary-dark) border-[rgba(78,205,196,0.25)]';
}
export function Pill({children,tone='medium'}){ return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.05em] ${severityClass(tone)}`}>{children}</span>; }
export function Card({title,subtitle,children,right,className=''}){ if(children===null) return null; return <section className={`rounded-2xl border border-(--border) bg-(--card) p-5 shadow-(--shadow-sm) ${className}`}>{(title||subtitle||right)&&<div className="mb-4 flex items-start justify-between gap-4"><div>{title&&<h3 className="text-base font-bold tracking-[-0.01em] text-(--primary)">{title}</h3>}{subtitle&&<p className="mt-1 text-sm text-(--text-light)">{subtitle}</p>}</div>{right}</div>}{children}</section>; }
// Value type-set adapts to content: big for numbers/short values, smaller for
// text (domains, phrases) — long values at text-2xl overwhelmed the cards.
export function Stat({label,value,hint,tone}){
  const v = safe(value);
  const len = String(v).length;
  // Keep short/medium values (incl. prices like "PKR 1,994.57") at one size so
  // paired cards match; only very long strings step down.
  const sizeCls = len <= 14 ? 'text-2xl' : len <= 22 ? 'text-lg' : 'text-sm leading-snug';
  // Colour-code the card border by side: teal = you, coral = the competitor.
  const toneStyle = tone === 'user'
    ? { borderColor: 'color-mix(in srgb, var(--secondary) 50%, transparent)', background: 'color-mix(in srgb, var(--secondary) 6%, var(--bg))' }
    : tone === 'competitor'
      ? { borderColor: 'color-mix(in srgb, var(--accent) 50%, transparent)', background: 'color-mix(in srgb, var(--accent) 6%, var(--bg))' }
      : tone === 'plain'
        ? { background: 'var(--card)' } // white surface — stands out on a tinted card
        : undefined;
  return <div className="rounded-xl border border-(--border) bg-(--bg) p-4" style={toneStyle}><p className="text-xs font-semibold uppercase tracking-wide text-(--text-light)">{label}</p><p className={`mt-1 font-bold text-(--primary) break-words ${sizeCls}`}>{v}</p>{hint&&<p className="mt-1 text-xs text-(--text-light)">{hint}</p>}</div>;
}

/* ─── Real-data presentation helpers (Phase 4) ─── */

// Human labels for canonical concept/category slugs coming from the
// comparison engine. Fallback: titleCase of the slug.
const CONCEPT_LABELS = {
  bundles_sets: 'Bundles & gift sets', sale_offers: 'Sale & discount offers',
  lip_products: 'Lip products', lip_color: 'Lip color', face_powder: 'Face powder',
  primer_fixer: 'Primer & setting', nutrition: 'Nutrition & supplements',
  suncare: 'Sun care', skincare: 'Skincare', eyeliner: 'Eyeliner',
};
export function conceptLabel(slug=''){ return CONCEPT_LABELS[slug] || titleCase(slug); }
// Site concepts that are NOT sellable categories — showing them as "category
// gaps" is noise. sale_offers is meaningful but belongs in Pricing (promo
// posture), not in category coverage.
export const NON_CATEGORY_CONCEPTS = new Set(['marketing', 'pricing']);
export const PROMO_CONCEPTS = new Set(['sale_offers']);

// Consistent side colors across the whole analysis:
// teal = the user's store, coral = the competitor (same as charts + header).
export function DomainTag({children, user=false, domain}){
  const host = domain || (typeof children === 'string' ? children : '');
  return <span className={`inline-flex items-center gap-1.5 font-semibold ${user ? 'text-(--secondary-dark)' : 'text-(--accent)'}`}>
    {host
      ? <Favicon domain={host} size={16} />
      : <span className={`h-2 w-2 shrink-0 rounded-full ${user ? 'bg-(--secondary)' : 'bg-(--accent)'}`} />}
    {children}
  </span>;
}

// Deterministic match evidence → plain words.
const MATCH_REASON_LABELS = {
  core_name_overlap: 'similar names',
  name_similarity: 'similar names',
  price_proximity: 'similar price',
  description_overlap: 'similar descriptions',
  keyword_overlap: 'overlapping keywords',
  same_category: 'same category',
  same_vendor: 'same brand',
};
export function humanizeMatchReasons(reasons){
  const parts = arr(reasons).map(r => {
    const s = String(r).toLowerCase();
    if (s.startsWith('same_product_type:')) return `both are ${s.split(':')[1].replace(/_/g,' ')}`;
    if (s.startsWith('same_inferred_category:')) return `same category (${s.split(':')[1].replace(/_/g,' ')})`;
    return MATCH_REASON_LABELS[s] || titleCase(s).toLowerCase();
  });
  return parts.length ? `Matched because: ${[...new Set(parts)].join(' · ')}` : '';
}

export function confidenceTier(v){
  const n=Number(v);
  if(!Number.isFinite(n)) return null;
  if(n>=0.85) return 'Strong match';
  if(n>=0.65) return 'Good match';
  if(n>=0.45) return 'Moderate match';
  return 'Weak match';
}

// "SPF 50+ SUNSCREEN - IN2IT CICA GLOW SUNSCREEN SPF50+ PA++++" → readable.
export function cleanProductName(s, max=64){
  if(!s) return '';
  let t=String(s).replace(/\s+/g,' ').trim();
  const letters=t.replace(/[^a-zA-Z]/g,'');
  const upperRatio=letters.length?letters.replace(/[^A-Z]/g,'').length/letters.length:0;
  if(upperRatio>0.7){ t=t.toLowerCase().replace(/(^|[\s\-–(])([a-z])/g,(m,a,b)=>a+b.toUpperCase()); }
  return t.length>max?`${t.slice(0,max)}…`:t;
}

// availability arrives as bool, string OR object ({status,inStock}) — the
// object form rendered "[object Object]" with real data.
export function availabilityLabel(v){
  if(v===true) return 'In stock';
  if(v===false) return 'Out of stock';
  if(isObj(v)){
    if(v.inStock===true) return 'In stock';
    if(v.inStock===false) return 'Out of stock';
    return availabilityLabel(v.status);
  }
  const s=String(v||'');
  if(/out[_\s]?of[_\s]?stock/i.test(s)) return 'Out of stock';
  if(/in[_\s]?stock/i.test(s)) return 'In stock';
  return s && s.length<=40 ? titleCase(s) : (s ? 'Captured' : '—');
}

// AI executiveSummary.whoWinsWhere → [{label, winner}]
const WIN_DIMENSION_LABELS = {
  AssortmentDepth: 'Assortment depth',
  PricePositioningOnMatchedProducts: 'Price on matched products',
  SEOMetaDescriptions: 'SEO meta coverage',
  ProductContentDepth: 'Product content depth',
  InventoryInStockRateInAnalyzedCollections: 'Stock availability',
  ExclusiveCategoryDifferentiation: 'Category differentiation',
  HomepageMerchandisingVolume: 'Homepage merchandising',
};
export function getWhoWinsWhere(ai){
  const raw=obj(ai?.executiveSummary?.whoWinsWhere);
  return Object.entries(raw).map(([k,winner])=>({key:k,label:WIN_DIMENSION_LABELS[k]||titleCase(k),winner}));
}
export function getPriorityInsights(ai){ return arr(ai?.priorityInsights); }

// comparison.categoryCoverageComparison → normalized per-category rows.
export function getCategoryCoverage(comparison, aiPayload, domains){
  const cc = comparison?.categoryCoverageComparison || aiPayload?.categoryCoverageComparison;
  if(!cc) return [];
  return arr(cc.rows)
    .filter(r=>!NON_CATEGORY_CONCEPTS.has(r.category) && !PROMO_CONCEPTS.has(r.category))
    .map(r=>{
      const sites=obj(r.sites);
      const u=obj(sites[domains?.user]); const c=obj(sites[domains?.competitor]);
      return {
        category:r.category, label:conceptLabel(r.category),
        userCount:Number(u.productCount||0), compCount:Number(c.productCount||0),
        userExample:arr(u.exampleProducts)[0]?.name, compExample:arr(c.exampleProducts)[0]?.name,
      };
    })
    .filter(r=>r.userCount||r.compCount)
    .sort((a,b)=>(b.compCount-b.userCount)-(a.compCount-a.userCount));
}
export function hasPromoGap(ai,comparison,aiPayload){
  return getPotentialGaps(ai,comparison,aiPayload).some(g=>PROMO_CONCEPTS.has(g.concept));
}

// Product counts PER ANALYZED PAGE (homepage / each matched collection).
// This is a pages analysis, not a whole-site analysis — totals across pages
// misled users into reading them as full catalog sizes.
export function getPerPageProductCounts(ai,comparison,aiPayload){
  const domains=getDomains(ai,comparison,aiPayload);
  const rows=[];
  const hp=getHomepageRows(ai,comparison,aiPayload);
  const hpUser=arr(hp).find(r=>r.domain===domains.user);
  const hpComp=arr(hp).find(r=>r.domain===domains.competitor);
  if(Number(hpUser?.featuredProductCount||0)||Number(hpComp?.featuredProductCount||0)){
    rows.push({page:'Homepage (featured)', user:Number(hpUser?.featuredProductCount||0), competitor:Number(hpComp?.featuredProductCount||0)});
  }
  getMatchups(ai,comparison,aiPayload).forEach(m=>{
    const hasCat = m.category && String(m.category).toLowerCase() !== 'unknown';
    const label = m.userCollection?.title || m.competitorCollection?.title
      || (hasCat ? `${conceptLabel(m.category)} collection` : 'Collection');
    rows.push({
      page:label,
      user:Number(m.userCollection?.productCount ?? m.userCollectionProductCount ?? 0),
      competitor:Number(m.competitorCollection?.productCount ?? m.competitorCollectionProductCount ?? 0),
    });
  });
  return rows.filter(r=>r.user||r.competitor);
}
export function Empty({label='No data available for this section.'}){ return <div className="rounded-xl border border-dashed border-(--border) bg-(--bg) p-5 text-sm text-(--text-light)">{label}</div>; }

// One-sentence takeaway below charts/tables. Data people read sentences first.
export function Verdict({children,tone='info'}){
  if(!children) return null;
  const color = tone==='risk' ? 'border-(--accent)' : tone==='good' ? 'border-(--success)' : 'border-(--secondary)';
  return <p className={`mt-3 rounded-lg border-l-4 ${color} bg-(--bg) px-3 py-2 text-sm font-medium text-(--text)`}>{children}</p>;
}

/* ─── CSV export ─── */
function csvCell(v){
  if(v===null||v===undefined) return '';
  if(Array.isArray(v)) return v.join('; ');
  if(typeof v==='boolean') return v?'Yes':'No';
  if(typeof v==='object') return JSON.stringify(v);
  return String(v);
}
export function downloadCsv(filename, rows=[], columns=[]){
  const cols = columns.length ? columns : Object.keys(rows[0]||{}).map(k=>({key:k,label:k}));
  const esc = (s)=>{ const t=csvCell(s); return /[",\n]/.test(t) ? `"${t.replace(/"/g,'""')}"` : t; };
  // labels can be React nodes (colored store tags) — fall back to key for CSV
  const header = cols.map(c=>esc(typeof (c.label||c) === 'string' ? (c.label||c) : (c.exportLabel || c.key || ''))).join(',');
  const body = rows.map(r=>cols.map(c=>esc(resolvePath(r,c.key||c))).join(',')).join('\n');
  const blob = new Blob(['﻿'+header+'\n'+body], {type:'text/csv;charset=utf-8;'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith('.csv') ? filename : `${filename}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}
export function DownloadCsvButton({filename, rows=[], columns=[], label='Download CSV'}){
  if(!arr(rows).length) return null;
  return <button type="button" onClick={()=>downloadCsv(filename, rows, columns)}
    className="inline-flex items-center gap-1.5 rounded-lg border border-(--border) bg-(--card) px-2.5 py-1 text-xs font-semibold text-(--text-light) transition hover:border-(--secondary) hover:text-(--secondary-dark)">
    ↓ {label}
  </button>;
}

/* Sortable + searchable table. Backwards compatible with the old SimpleTable API.
   - Click a header to sort (auto-detects numeric columns).
   - `searchable` prop, or automatic search box when more than 8 rows.
   - `exportName="price-comparison"` adds a Download CSV button (exports ALL
     rows with raw values, not just the filtered/visible ones). */
export function SimpleTable({columns=[],rows=[],searchable,maxHeight,exportName,exportRows,headerClass='bg-(--bg)',headerTextClass='text-(--text-light) hover:text-(--primary)'}){
  const [sort,setSort]=useState(null); // {key, dir}
  const [q,setQ]=useState('');
  const showSearch = searchable ?? arr(rows).length > 8;

  const filtered = useMemo(()=>{
    if(!q) return arr(rows);
    const needle=q.toLowerCase();
    return arr(rows).filter(r=>columns.some(c=>{
      const v=resolvePath(r,c.key||c);
      return v!==null && v!==undefined && String(Array.isArray(v)?v.join(' '):typeof v==='object'?JSON.stringify(v):v).toLowerCase().includes(needle);
    }));
  },[rows,q,columns]);

  const sorted = useMemo(()=>{
    if(!sort) return filtered;
    const list=[...filtered];
    list.sort((a,b)=>{
      const va=resolvePath(a,sort.key), vb=resolvePath(b,sort.key);
      const na=Number(va), nb=Number(vb);
      const bothNum=Number.isFinite(na)&&Number.isFinite(nb);
      let cmp;
      if(bothNum) cmp=na-nb;
      else cmp=String(va??'').localeCompare(String(vb??''));
      return sort.dir==='asc'?cmp:-cmp;
    });
    return list;
  },[filtered,sort]);

  if(!hasRows(rows)) return null;
  const toggleSort=(key)=>setSort(s=>!s||s.key!==key?{key,dir:'desc'}:s.dir==='desc'?{key,dir:'asc'}:null);

  // Hide columns that are empty for every row ("—" walls add noise, not data).
  const visColumns = columns.filter(c => arr(rows).some(r => {
    const v = resolvePath(r, c.key || c);
    return v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && !v.length);
  }));

  return <div>
    {(showSearch || exportName) && <div className="mb-2 flex flex-wrap items-center gap-2">
      {showSearch && <><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Filter rows…" className="w-full max-w-xs rounded-lg border border-(--border) bg-(--card) px-3 py-1.5 text-sm text-(--text) outline-none placeholder:text-(--text-light) focus:border-(--secondary)"/>{q&&<span className="text-xs text-(--text-light)">{sorted.length} of {arr(rows).length} rows</span>}</>}
      {exportName && <span className="ml-auto"><DownloadCsvButton filename={exportName} rows={exportRows || rows} columns={columns}/></span>}
    </div>}
    <div className={`overflow-x-auto rounded-xl border border-(--border) ${maxHeight?'overflow-y-auto':''}`} style={maxHeight?{maxHeight}:undefined}>
      <table className="min-w-full divide-y divide-(--border) text-sm">
        <thead className={headerClass}><tr>{visColumns.map(c=>{
          const key=c.key||c; const active=sort?.key===key;
          return <th key={key} onClick={()=>toggleSort(key)} className={`cursor-pointer select-none whitespace-nowrap px-4 py-3 text-left font-semibold ${headerTextClass}`}>{c.label||c}{active?<span className="ml-1 text-(--secondary-dark)">{sort.dir==='desc'?'▾':'▴'}</span>:null}</th>;
        })}</tr></thead>
        <tbody className="divide-y divide-(--border) bg-(--card)">{sorted.map((r,i)=><tr key={i} className="hover:bg-(--bg)">{visColumns.map(c=><td key={c.key||c} className="px-4 py-3 text-(--text)">{renderCell(resolvePath(r,c.key||c), c, r)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  </div>;
}
function resolvePath(o,path){ if(!String(path).includes('.')) return o?.[path]; return String(path).split('.').reduce((a,k)=>a?.[k],o); }
function renderCell(v,c={},row={}){ if(c.render) return c.render(v,row); if(v===null||v===undefined||v==='') return '—'; if(c.format==='money') return money(v,c.currency); if(c.format==='pct') return pct(v); if(Array.isArray(v)) return v.length ? v.join(', ') : '—'; if(typeof v==='boolean') return v?'Yes':'No'; if(typeof v==='object') return JSON.stringify(v); return String(v); }

export function MiniBar({value,max,label,sub}){ const n=Number(value)||0; const m=Math.max(Number(max)||0,n,1); const w=Math.max(3,Math.min(100,(n/m)*100)); return <div className="space-y-1"><div className="flex justify-between text-xs"><span className="font-medium text-(--text)">{label}</span><span className="text-(--text-light)">{sub ?? compactNum(value)}</span></div><div className="h-2 overflow-hidden rounded-full bg-(--border)"><div className="h-full rounded-full bg-(--primary)" style={{width:`${w}%`}} /></div></div>; }
export function ComparisonBars({rows=[],valueKey='averagePrice',labelKey='domain',title,format='number',currency=''}){ if(!hasRows(rows)) return null; const max=Math.max(...rows.map(r=>Number(r[valueKey])||0),1); return <Card title={title}><div className="space-y-4">{rows.map((r,i)=><MiniBar key={i} label={r[labelKey]} value={r[valueKey]} max={max} sub={format==='money'?money(r[valueKey],r.currency||currency):format==='pct'?pct(r[valueKey]):compactNum(r[valueKey])}/>)}</div></Card>; }
export function RangeBar({row,minKey='priceMin',maxKey='priceMax',avgKey='averagePrice',domainKey='domain',currency=''}){ const cur=row.currency||currency; const min=Number(row[minKey])||0, max=Number(row[maxKey])||0, avg=Number(row[avgKey])||0; return <div className="rounded-xl border border-(--border) p-4"><div className="mb-2 flex justify-between"><span className="font-semibold text-(--primary)">{row[domainKey]}</span><span className="text-sm text-(--text-light)">Avg {money(avg,cur)}</span></div><div className="h-3 rounded-full bg-(--border)"><div className="h-full rounded-full bg-(--primary)" style={{width:`${Math.max(5, Math.min(100, (avg/(max||avg||1))*100))}%`}}/></div><div className="mt-2 flex justify-between text-xs text-(--text-light)"><span>{money(min,cur)}</span><span>{money(max,cur)}</span></div></div>; }
export function hasSignalRows(rows, keys=[]){ return arr(rows).some(r => keys.some(k => hasValue(r?.[k]) && r?.[k] !== false && r?.[k] !== 0)); }

/* ─── Data extraction (schema-tolerant readers over ai / comparison / ai_payload) ─── */

export function getSites(ai,comparison,aiPayload){
  return firstAvailable(arr(comparison?.sites), arr(aiPayload?.snapshotScope?.sites), arr(aiPayload?.sites), Object.entries(obj(ai?.snapshotScope?.pagesAnalyzedCount)).map(([domain,pages],idx)=>({key:idx===0?'user':`competitor_${idx}`,domain,pagesAnalyzedCount:pages,pageTypesAnalyzed:ai?.snapshotScope?.pageTypesAnalyzed?.[domain]}))) || [];
}
export function getDomains(ai,comparison,aiPayload){ const sites=getSites(ai,comparison,aiPayload); const user=firstAvailable(ai?.domains?.user, ai?.userDomain, aiPayload?.domains?.user, comparison?.summary?.userDomain, sites.find(s=>s.key==='user'||s.role==='user')?.domain, sites[0]?.domain); const competitor=firstAvailable(ai?.domains?.competitor, arr(ai?.competitorDomains)[0], arr(aiPayload?.domains?.competitors)[0], arr(comparison?.summary?.competitorDomains)[0], sites.find(s=>s.key!=='user'&&s.role!=='user')?.domain, sites[1]?.domain); return {user,competitor}; }
// IntelShift targets e-commerce. A store with products/collections is "ecommerce";
// anything else falls back to a neutral "website" (SaaS/services types were retired).
export function inferBusinessType(comparison,aiPayload){ const sites=arr(comparison?.sites).length?arr(comparison?.sites):arr(aiPayload?.snapshotScope?.sites); const hasProducts=sites.some(s=>(s.uniqueProducts||0)>0 || (s.collectionCount||0)>0); return hasProducts ? 'ecommerce' : 'website'; }

// Currency comes from the data, never hardcoded. Scans price rows, matchup
// collections and price-anchor products for the first declared currency.
export function getCurrency(ai,comparison,aiPayload){
  const priceRows=getPriceRows(ai,comparison,aiPayload);
  const fromPrice=arr(priceRows).map(r=>r.currency).find(Boolean);
  if(fromPrice) return fromPrice;
  const matchups=getMatchups(ai,comparison,aiPayload);
  const fromMatchups=arr(matchups).map(m=>m.userCollection?.currency||m.competitorCollection?.currency).find(Boolean);
  if(fromMatchups) return fromMatchups;
  const fromAnchors=arr(priceRows).flatMap(r=>[...arr(r.lowestPricedProducts),...arr(r.highestPricedProducts)]).map(p=>p.currency).find(Boolean);
  return fromAnchors || firstAvailable(comparison?.summary?.currency, aiPayload?.currency, ai?.currency) || '';
}

// Data-quality notes for the page header (pages analyzed, warnings).
export function getWarnings(ai,comparison,aiPayload){
  const out=[];
  const push=(v)=>{ if(typeof v==='string'&&v.trim()) out.push(v.trim()); else if(isObj(v)) Object.values(v).forEach(push); else if(Array.isArray(v)) v.forEach(push); };
  push(comparison?.warnings); push(aiPayload?.warnings); push(ai?.warnings);
  push(ai?.dataQualityAndScopeNotes?.notes || ai?.dataQualityAndScopeNotes?.limitations);
  return [...new Set(out)].slice(0,10);
}
export function getGeneratedAt(ai,comparison,aiPayload){ return firstAvailable(comparison?.generatedAt, aiPayload?.generatedAt, ai?.generatedAt); }

export function getCatalogRows(ai,comparison,aiPayload){ return firstAvailable(arr(comparison?.catalogComparison?.rows), arr(aiPayload?.deterministicSignals?.catalogComparison?.rows), arr(aiPayload?.catalogComparison?.rows), arr(ai?.comparisonTables?.find(t=>t.key==='catalog_comparison')?.rows)) || []; }
export function getContentDepthRows(ai,comparison,aiPayload){ return firstAvailable(arr(comparison?.contentDepthComparison?.rows), arr(aiPayload?.deterministicSignals?.contentDepth?.rows), arr(aiPayload?.contentDepth?.rows)) || []; }
export function getSaleDiscountRows(ai,comparison,aiPayload){ return firstAvailable(arr(comparison?.saleAndDiscountComparison?.rows), arr(aiPayload?.deterministicSignals?.saleAndDiscountComparison?.rows), arr(aiPayload?.saleAndDiscountComparison?.rows)) || []; }
export function getNavigation(ai,comparison,aiPayload){ return firstAvailable(comparison?.navigationComparison, aiPayload?.deterministicSignals?.navigationComparison, aiPayload?.navigationComparison) || null; }
export function getMerchandisingRows(ai,comparison,aiPayload){ return firstAvailable(arr(comparison?.merchandisingComparison?.rows), arr(aiPayload?.deterministicSignals?.merchandisingComparison?.rows), arr(aiPayload?.merchandisingComparison?.rows)) || []; }
export function prettyIntent(s){ const t=String(s||'').replace(/[_-]+/g,' ').trim(); return t ? t.charAt(0).toUpperCase()+t.slice(1) : ''; }
export function getDashboardCards(ai,comparison,aiPayload){ const cards=arr(ai?.dashboardCards); if(cards.length) return cards; return firstAvailable(arr(aiPayload?.deterministicSignals?.rankedInsights?.items), arr(comparison?.rankedInsights?.items))?.map(x=>({title:x.title||x.type, type:x.type, severity:x.severity, shortText:x.detail, recommendedAction:x.recommendation, evidencePath:x.evidencePath})) || []; }
export function getRankedInsights(ai,comparison,aiPayload){ return firstAvailable(arr(ai?.executiveSummary?.keyFindings), arr(ai?.executiveSummary?.rankedInsightsFromEvidence), arr(aiPayload?.deterministicSignals?.rankedInsights?.items), arr(comparison?.rankedInsights?.items)) || []; }
export function getRecommendations(ai,comparison,aiPayload){ return firstAvailable(arr(ai?.recommendedActions), arr(ai?.actionsBackedByEvidence), arr(ai?.prioritizedActionsFromEvidence?.recommendations), arr(aiPayload?.deterministicSignals?.recommendations?.items), arr(comparison?.recommendations?.items)) || []; }
/* Index the AI evidence pack's rich products (which carry full per-variant
   detail: option name, price, availability) by their URL, so matched-product
   cards can join to them and show the variant breakdown. */
export function getEvidenceProductMap(ai, comparison, aiPayload){
  const src = comparison || aiPayload || ai || {};
  const sites = arr(src?.openAiEvidencePack?.sites || src?.evidencePack?.sites);
  const norm = (u) => String(u || '').trim().replace(/\/+$/, '').toLowerCase();
  const map = {};
  sites.forEach((s) => arr(s.topProductsForAI).forEach((p) => {
    const k = norm(p.productUrl || p.url);
    if (k && !map[k]) map[k] = p;
  }));
  return map;
}

export function getMatchups(ai,comparison,aiPayload){
  const domains = getDomains(ai, comparison, aiPayload);

  const fromAi = arr(ai?.categoryMatchups).map(m=>({
    category:m.category,
    confidence:m.confidence,
    userCollection:Object.values(obj(m.collections))[0],
    competitorCollection:Object.values(obj(m.collections))[1],
    assortmentGap:m.assortmentGap,
    matchedProductCount:m.matchCoverage?.matchedProductCount,
    userUnmatchedCount:Object.entries(obj(m.matchCoverage)).find(([k])=>k.includes('unmatched')&&k.includes(domains.user))?.[1],
    competitorUnmatchedCount:Object.entries(obj(m.matchCoverage)).find(([k])=>k.includes('unmatched')&&k.includes(domains.competitor))?.[1],
    topProductMatches:arr(m.observedPricePositioningFromTopMatches).map(x=>({
      userProduct:{name:x.userProductName},
      competitorProduct:{name:x.competitorProductName},
      priceGap:{absolute:x.priceGapAbsolute,percentVsUser:x.priceGapPercentVsUser,direction:x.direction},
      positioningComparisonSignals:{sharedSignals:x.sharedSignals}
    }))
  }));

  const fromComparison = arr(comparison?.oneToOneComparison?.competitors).flatMap(c => arr(c.collectionMatchups));
  const fromPayload = arr(aiPayload?.matchEvidence?.oneToOneSummary).flatMap(c => arr(c.collectionMatchups));
  const fromPayloadLegacy = arr(aiPayload?.oneToOneSummary?.[0]?.collectionMatchups);

  const sources = [fromPayload, fromComparison, fromPayloadLegacy, fromAi].filter(a => a && a.length);
  if (!sources.length) return [];

  // Prefer the source that contains the richest product matching detail.
  sources.sort((a,b)=>{
    const score = (rows) => arr(rows).reduce((sum,m)=> sum + arr(m.topProductMatches).length + arr(m.productMatching?.matches).length + arr(m.competitorUnmatchedProducts).length + arr(m.productMatching?.competitorUnmatchedProducts).length + arr(m.userUnmatchedProducts).length + arr(m.productMatching?.userUnmatchedProducts).length, 0);
    return score(b) - score(a);
  });

  return sources[0].map(m => {
    const productMatching = obj(m.productMatching);
    return {
      ...m,
      matchedProductCount: m.matchedProductCount ?? productMatching.matchedProductCount,
      userUnmatchedCount: m.userUnmatchedCount ?? productMatching.userUnmatchedCount,
      competitorUnmatchedCount: m.competitorUnmatchedCount ?? productMatching.competitorUnmatchedCount,
      topProductMatches: arr(m.topProductMatches).length ? arr(m.topProductMatches) : arr(productMatching.matches),
      competitorUnmatchedProducts: arr(m.competitorUnmatchedProducts).length ? arr(m.competitorUnmatchedProducts) : arr(productMatching.competitorUnmatchedProducts),
      userUnmatchedProducts: arr(m.userUnmatchedProducts).length ? arr(m.userUnmatchedProducts) : arr(productMatching.userUnmatchedProducts),
    };
  });
}
export function getPriceRows(ai,comparison,aiPayload){ if(ai?.pricingOverview?.siteLevel) return Object.entries(ai.pricingOverview.siteLevel).map(([domain,row])=>({domain,...row})); return firstAvailable(arr(ai?.comparisonTables?.find(t=>t.key==='price_summary')?.rows), arr(comparison?.priceComparison?.rows), arr(aiPayload?.modules?.price?.rows), arr(aiPayload?.priceComparison?.rows)) || []; }
export function getInventoryRows(ai,comparison,aiPayload){ if(ai?.inventoryOverview?.siteLevel) return Object.entries(ai.inventoryOverview.siteLevel).map(([domain,row])=>({domain,...row})); return firstAvailable(arr(ai?.comparisonTables?.find(t=>t.key==='inventory_summary')?.rows), arr(comparison?.inventoryComparison?.rows), arr(aiPayload?.modules?.inventory?.rows), arr(aiPayload?.inventoryComparison?.rows)) || []; }
export function getSeoRows(ai,comparison,aiPayload){ if(ai?.seoOverview) return Object.entries(ai.seoOverview).map(([domain,row])=>({domain,...row})); return firstAvailable(arr(ai?.comparisonTables?.find(t=>t.key==='seo_collections')?.rows), arr(comparison?.seoComparison?.rows), arr(aiPayload?.modules?.seo?.rows), arr(aiPayload?.seoComparison?.rows)) || []; }
export function getHomepageRows(ai,comparison,aiPayload){ if(ai?.homepageAndConversionSignals?.homepageDetected) return Object.entries(ai.homepageAndConversionSignals.homepageDetected).map(([domain,detected])=>({domain,homepageDetected:detected,hasTrustSignals:ai.homepageAndConversionSignals.trustSignalsDetected?.[domain],newsletterDetected:ai.homepageAndConversionSignals.newsletterDetected?.[domain],discountMessagingDetected:ai.homepageAndConversionSignals.discountMessagingDetected?.[domain]})); return firstAvailable(arr(comparison?.homepageComparison?.rows), arr(aiPayload?.modules?.homepage?.rows), arr(aiPayload?.homepageComparison?.rows)) || []; }
export function hasHomepageData(rows){ return arr(rows).some(r => r.homepageDetected === true || (r.sectionCount||0)>0 || arr(r.topSections).length || r.hasHero || r.hasNewsletter || r.hasTrustSignals || r.hasDiscountMessaging); }
export function getTrustRows(ai,comparison,aiPayload){ const h=ai?.homepageAndConversionSignals; if(h?.trustSignalsDetected) return Object.entries(h.trustSignalsDetected).map(([domain,has])=>({domain,hasHomepageTrustSignals:has,newsletterDetected:h.newsletterDetected?.[domain],discountMessagingDetected:h.discountMessagingDetected?.[domain]})); return firstAvailable(arr(comparison?.trustAndConversionComparison?.rows), arr(aiPayload?.modules?.trustAndConversion?.rows), arr(aiPayload?.trustAndConversionComparison?.rows)) || []; }
export function getMarketRows(ai,comparison,aiPayload){ return firstAvailable(arr(comparison?.marketCoverageComparison?.rows), arr(aiPayload?.modules?.marketCoverage?.rows), arr(aiPayload?.marketCoverageComparison?.rows)) || []; }
export function getPotentialGaps(ai,comparison,aiPayload){ return firstAvailable(arr(ai?.navigationAndConceptCoverage?.collectionGapAnalysisPotentialUserGaps), arr(aiPayload?.modules?.collectionGapAnalysis?.competitors?.[0]?.potentialUserGaps), arr(comparison?.collectionGapAnalysis?.competitors?.[0]?.potentialUserGaps)) || []; }
export function getComparisonTables(ai){ return arr(ai?.comparisonTables); }
