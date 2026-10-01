import React from 'react';
import { pickSource, Card, getSites, inferBusinessType, arr, titleCase } from './_helpers';

export default function AnalysisIdentity(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const sites = getSites(ai, comparison, aiPayload);
  const businessType = inferBusinessType(comparison, aiPayload);
  const heading = businessType === 'ecommerce' ? 'Sites & collections analyzed' : 'Sites analyzed';
  // Show the user-facing tech label; never surface the internal "Unknown"
  // analyzer-routing key.
  const friendlyPlatform = (s) => {
    const raw = s.displayPlatform || s.platform;
    if (!raw || String(raw).trim().toLowerCase() === 'unknown') return 'Custom / Undetected';
    return raw;
  };
  const rows = sites.map((s, i) => ({
    role: i === 0 || s.key === 'user' ? 'User' : 'Competitor',
    domain: s.domain,
    platform: friendlyPlatform(s),
    collections: s.collectionCount,
    products: s.uniqueProducts,
    pages: s.pagesAnalyzedCount,
    types: Object.keys(s.pageTypesAnalyzed || {}).join(', '),
  }));
  // Domains, site count and business type already live in the page header —
  // repeating them as stat tiles doubled the same facts at 2xl font size.
  return <Card title={heading} subtitle="What was analyzed in this run — all findings are scoped to these pages.">
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50"><tr>{['Role','Domain','Platform', businessType==='ecommerce'?'Collections':'Pages','Unique products','Page types'].map(h=><th className="px-4 py-3 text-left font-semibold text-slate-600" key={h}>{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-100 bg-white">{rows.map((r,i)=><tr key={i}><td className="px-4 py-3">{r.role}</td><td className="px-4 py-3 font-medium">{r.domain}</td><td className="px-4 py-3">{r.platform || '—'}</td><td className="px-4 py-3">{businessType==='ecommerce' ? (r.collections ?? '—') : (r.pages ?? '—')}</td><td className="px-4 py-3">{r.products ?? '—'}</td><td className="px-4 py-3">{r.types || '—'}</td></tr>)}</tbody>
      </table>
    </div>
  </Card>;
}
