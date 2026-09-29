import React from 'react';
import { pickSource, Card, Pill, getRecommendations, humanizeSlugsInText, limitText } from './_helpers';

// Raw metric expressions ("pagesWithMissingMetaDescription = 0") read like
// code — soften to plain words where possible.
function humanizeMetric(s = '') {
  return String(s)
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .replace(/\s*=\s*/g, ' reaches ')
    .replace(/\s*>=\s*/g, ' reaches at least ')
    .replace(/\s*>\s*/g, ' exceeds ')
    .toLowerCase();
}

export default function Recommendation(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const recs = getRecommendations(ai, comparison, aiPayload);
  if (!recs.length) return null;
  return <div className="space-y-5">
    <Card title="Recommended actions" subtitle="Prioritized next steps.">
    <div className="divide-y divide-(--border)">{recs.map((r,i)=><div key={i} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0"><div className="flex w-20 shrink-0 flex-col items-start gap-1 pt-0.5"><Pill tone={r.priority || r.severity}>{r.priority || 'action'}</Pill>{r.impact&&<span className="text-[10px] font-bold uppercase tracking-wide text-(--text-light)">{r.impact} impact</span>}</div><div className="min-w-0"><p className="text-sm font-semibold leading-snug text-(--primary)">{humanizeSlugsInText(r.recommendation || r.action)}</p>{r.reason&&<p className="mt-0.5 text-xs leading-relaxed text-(--text-light)">{humanizeSlugsInText(r.reason)}</p>}{r.successMetric&&<p className="mt-1 text-[11px] text-(--secondary-dark)">Done when: {limitText(humanizeMetric(r.successMetric),140)}</p>}</div></div>)}</div>
  </Card>
  </div>;
}
