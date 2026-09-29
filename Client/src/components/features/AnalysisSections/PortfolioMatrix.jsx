import React from 'react';
import { pickSource, Card, SimpleTable, getMarketRows, getPotentialGaps, arr } from './_helpers';

export default function PortfolioMatrix(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const rows = getMarketRows(ai, comparison, aiPayload);
  const gaps = getPotentialGaps(ai, comparison, aiPayload);
  if (!rows.length && !gaps.length) return null;
  return <div className="space-y-5">
    {rows.length ? <Card title="Market / portfolio coverage" subtitle="Concept-level coverage for categories, services, navigation and positioning themes."><SimpleTable columns={[{key:'domain',label:'Domain'},{key:'role',label:'Role'},{key:'conceptCount',label:'Concepts'},{key:'concepts',label:'Detected concepts'}]} rows={rows}/></Card> : null}
    {gaps.length ? <Card title="Competitor-only opportunities"><SimpleTable columns={[{key:'concept',label:'Concept'},{key:'severity',label:'Severity'},{key:'whyImportant',label:'Why important'}]} rows={gaps}/></Card> : null}
  </div>;
}
