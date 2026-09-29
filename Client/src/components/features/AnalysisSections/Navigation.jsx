import React from 'react';
import { pickSource, Card, Stat, Pill, getDomains, conceptLabel, prettyIntent, arr } from './_helpers';

/* Navigation & page structure — what each store surfaces in its main menu. We
   already crawl the nav; this shows the category/page-intent overlap and gaps. */

const ChipRow = ({ title, items, tone = 'low', hint }) => {
  if (!items.length) return null;
  return (
    <div className="mt-4">
      <p className="text-[11px] font-bold uppercase tracking-wide text-(--text-light)">{title}{hint ? <span className="ml-1 font-normal normal-case">· {hint}</span> : null}</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {items.slice(0, 24).map((x, i) => <Pill key={i} tone={tone}>{x}</Pill>)}
        {items.length > 24 ? <span className="text-xs text-(--text-light)">+{items.length - 24} more</span> : null}
      </div>
    </div>
  );
};

export default function Navigation(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const nav = getNavigationSafe(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const blocks = arr(nav?.competitors);
  const block = blocks.find((b) => b.competitorDomain === domains.competitor) || blocks[0];
  if (!block) return null;

  const shared = arr(block.sharedConcepts).map(conceptLabel);
  const onlyThem = arr(block.competitorOnlyConcepts).map(conceptLabel);
  const onlyYou = arr(block.userOnlyConcepts).map(conceptLabel);
  const dropIntent = (x) => x && !['unknown', 'other', 'home', 'homepage'].includes(String(x).toLowerCase());
  const missingIntents = arr(block.missingUserPageIntents).filter(dropIntent).map(prettyIntent);

  return <div className="space-y-5">
    <Card
      title="Navigation & page structure"
      subtitle="What each store surfaces in its main menu — the categories and page types it wants shoppers to find. Items only in their nav are potential gaps; items only in yours are differentiation."
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={`${domains.user || 'Your'} nav links`} value={block.userNavLinkCount ?? '—'} tone="user" />
        <Stat label={`${domains.competitor || 'Their'} nav links`} value={block.competitorNavLinkCount ?? '—'} tone="competitor" />
        <Stat label="Shared categories" value={shared.length} tone="plain" />
      </div>

      <ChipRow title={`In ${domains.competitor || 'their'} nav, not yours`} items={onlyThem} tone="high" hint="potential gaps" />
      <ChipRow title="Only in your nav" items={onlyYou} tone="teal" hint="your differentiation" />
      <ChipRow title="Page types they link that you don't" items={missingIntents} tone="medium" />
    </Card>
  </div>;
}

// Local safe getter (avoids importing an extra symbol churn if helper name changes).
function getNavigationSafe(ai, comparison, aiPayload) {
  return comparison?.navigationComparison || aiPayload?.deterministicSignals?.navigationComparison || aiPayload?.navigationComparison || null;
}
