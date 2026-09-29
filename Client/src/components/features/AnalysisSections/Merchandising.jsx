import React from 'react';
import { pickSource, Card, SimpleTable, DomainTag, getMerchandisingRows, getDomains } from './_helpers';

/* Merchandising & shopping UX — filtering/sorting on collection pages and how much
   the homepage merchandises. Crawled already; wasn't shown anywhere. */

export default function Merchandising(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const rows = getMerchandisingRows(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  if (!rows.length) return null;
  const enriched = rows.map((r) => ({
    ...r,
    filterRate: r.collectionCount ? (r.collectionsWithFilters || 0) / r.collectionCount : null,
    sortRate: r.collectionCount ? (r.collectionsWithSort || 0) / r.collectionCount : null,
  }));

  return <div className="space-y-5">
    <Card
      title="Merchandising & shopping UX"
      subtitle="How each store helps shoppers browse — filtering/sorting on collection pages, and how much the homepage merchandises. Strong filtering and homepage merchandising usually lift conversion."
    ><SimpleTable exportName="merchandising" columns={[
      {key:'domain',label:'Store',render:(v)=><DomainTag user={v===domains.user}>{v}</DomainTag>},
      {key:'collectionCount',label:'Collections'},
      {key:'collectionsWithFilters',label:'With filters'},
      {key:'filterRate',label:'Filter coverage',format:'pct'},
      {key:'collectionsWithSort',label:'With sort'},
      {key:'sortRate',label:'Sort coverage',format:'pct'},
      {key:'homepageFeaturedCollections',label:'Homepage collections'},
      {key:'homepageFeaturedProducts',label:'Homepage products'},
    ]} rows={enriched}/></Card>
  </div>;
}
