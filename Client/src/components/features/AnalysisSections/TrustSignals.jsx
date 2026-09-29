import React from 'react';
import { pickSource, Card, SimpleTable, DomainTag, getTrustRows, getDomains, hasSignalRows, arr } from './_helpers';

// Compact yes/no matrix — the previous stat tiles + 0-to-1 bar chart said
// the same thing three times, loudly.
export default function TrustSignals(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const rows = getTrustRows(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const hasUseful = hasSignalRows(rows, ['hasHomepageTrustSignals','trustSectionCount','newsletterDetected','discountMessagingDetected']) || rows.some(r => arr(r.trustSections).length);
  if (!hasUseful) return null;
  const evidence = rows.flatMap(r => arr(r.trustSections).map(s => ({ domain:r.domain, ...s })));

  const METRICS = [
    { key: 'hasHomepageTrustSignals', label: 'Trust signals on homepage' },
    { key: 'newsletterDetected', label: 'Newsletter capture' },
    { key: 'discountMessagingDetected', label: 'Discount messaging' },
  ];
  const cols = [{ key: 'label', label: 'Signal' }, ...rows.map((r) => ({ key: r.domain, exportLabel: r.domain, label: <DomainTag user={r.domain === domains.user}>{r.domain}</DomainTag> }))];
  const tableRows = METRICS
    .filter((m) => rows.some((r) => r[m.key] !== undefined && r[m.key] !== null))
    .map((m) => ({ label: m.label, ...Object.fromEntries(rows.map((r) => [r.domain, r[m.key]])) }));

  return <div className="space-y-5">
    <Card title="Trust & conversion signals" subtitle="What each homepage shows shoppers.">
      <SimpleTable columns={cols} rows={tableRows} />
    </Card>
    {evidence.length ? <Card title="Detected trust evidence"><SimpleTable columns={[{key:'domain',label:'Store'},{key:'positionLabel',label:'Position'},{key:'textPreview',label:'Text'}]} rows={evidence}/></Card> : null}
  </div>;
}
