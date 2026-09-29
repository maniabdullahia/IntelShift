import React from 'react';
import { pickSource, Card, Pill, getRankedInsights, humanizeSlugsInText, arr, limitText, titleCase } from './_helpers';

export default function KeyInsights(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const raw = getRankedInsights(ai, comparison, aiPayload)
    // "No data detected" pseudo-insights say nothing actionable — drop them.
    .filter(x => !/no .*detected|not detected|no high-importance/i.test(String(x.finding || x.title || '')));
  // The AI returns risks/opportunities as plain STRINGS (or sometimes objects).
  const norm = (x) => (typeof x === 'string' ? { title: x } : x || {});
  const risks = arr(ai?.executiveSummary?.topRisksForUser).map(norm);
  const opps = arr(ai?.executiveSummary?.topOpportunitiesForUser).map(norm);
  const insights = [
    ...raw.map(x => ({ title: x.finding || x.title || x.type, body: x.detail || x.shortText, severity: x.severity || x.workspacePriority, type: x.type || 'finding', action: x.recommendedAction })),
    ...opps.map(x => ({ title: x.opportunity || x.title, body: x.reason || x.businessImpact, severity: x.severity || x.priority, type: 'opportunity', action: x.recommendation })),
  ].filter(x => x.title).filter((x, i, list) => {
    const key = String(x.title).toLowerCase().replace(/\s+/g, ' ').trim();
    return list.findIndex((y) => String(y.title).toLowerCase().replace(/\s+/g, ' ').trim() === key) === i;
  });

  return <div className="space-y-5">
    {insights.length ? <Card title="Key insights" subtitle="Every finding from this analysis, ranked by severity.">
      <div className="divide-y divide-(--border)">
        {insights.slice(0, 12).map((x, i) => (
          <div key={i} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
            <div className="w-20 shrink-0 pt-0.5"><Pill tone={x.severity}>{x.severity || 'note'}</Pill></div>
            <div className="min-w-0">
              <p className="text-sm font-semibold leading-snug text-(--primary)">
                {humanizeSlugsInText(x.title)}
                <span className="ml-2 align-middle text-[10px] font-bold uppercase tracking-wide text-(--text-light)">{titleCase(String(x.type))}</span>
              </p>
              {x.body && <p className="mt-0.5 text-xs leading-relaxed text-(--text-light)">{humanizeSlugsInText(limitText(x.body, 160))}</p>}
            </div>
          </div>
        ))}
      </div>
    </Card> : null}

    {risks.length ? <Card title="Risks to review">
      <ul className="space-y-2">
        {risks.map((r, i) => (
          <li key={i} className="flex items-start gap-2.5 text-sm leading-relaxed text-(--text)">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-(--accent)" />
            <span>{humanizeSlugsInText(r.risk || r.title)}</span>
          </li>
        ))}
      </ul>
    </Card> : null}
  </div>;
}
