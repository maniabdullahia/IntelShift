import React from 'react';
import { pickSource, Card, Stat, SimpleTable, getSeoRows, DomainTag, getDomains, arr } from './_helpers';
import { ChartBox, seoChart } from './SectionCharts';

export default function SeoAnalysis(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const rows = getSeoRows(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  if (!rows.length) return null;
  const examples = rows.flatMap(r => arr(r.examples || r.collectionPages || r.seoRows).map(e => ({ domain: r.domain, ...e })));
  const hasQuality = rows.some(r => r.avgTitleLength != null || r.metaPresentRate != null);

  return <div className="space-y-5">
    <div className="grid gap-5 xl:grid-cols-2">
      <Card title="SEO health" subtitle="Meta description, H1 and canonical checks for analyzed pages.">
        <div className="grid gap-3 md:grid-cols-2">{rows.flatMap(r => [<Stat key={`${r.domain}-meta`} label={`${r.domain} missing meta`} value={r.pagesWithMissingMetaDescription ?? 0}/>, <Stat key={`${r.domain}-h1`} label={`${r.domain} missing H1`} value={r.pagesWithMissingH1 ?? 0}/>])}</div>
      </Card>
      <ChartBox title="SEO health chart" subtitle="Missing meta descriptions, missing H1s and complete checks." config={seoChart(rows)} />
    </div>

    {hasQuality ? <Card
      title="SEO quality by store"
      subtitle="Title and meta-description best-practice checks across analyzed pages. Titles read best at ~30–60 characters and meta descriptions at ~120–160; duplicate titles compete against each other in search."
    ><SimpleTable exportName="seo-quality" columns={[
      {key:'domain',label:'Store',render:(v)=><DomainTag user={v===domains.user}>{v}</DomainTag>},
      {key:'pagesAnalyzed',label:'Pages'},
      {key:'avgTitleLength',label:'Avg title (chars)'},
      {key:'titlesTooShort',label:'Titles < 30'},
      {key:'titlesTooLong',label:'Titles > 60'},
      {key:'metaPresentRate',label:'Meta present',format:'pct'},
      {key:'avgMetaLength',label:'Avg meta (chars)'},
      {key:'metaOutOfRange',label:'Meta off-length'},
      {key:'h1PresentRate',label:'H1 present',format:'pct'},
      {key:'canonicalPresentRate',label:'Canonical',format:'pct'},
      {key:'duplicateTitlePages',label:'Duplicate titles'},
    ]} rows={rows}/></Card> : null}

    {examples.length ? <Card title="SEO page details"><SimpleTable exportName="seo-page-details" columns={[{key:'domain',label:'Domain'},{key:'url',label:'URL'},{key:'pageType',label:'Type'},{key:'titleLength',label:'Title len'},{key:'metaDescriptionLength',label:'Meta len'},{key:'metaDescriptionPresent',label:'Meta'},{key:'h1Present',label:'H1'},{key:'canonicalPresent',label:'Canonical'}]} rows={examples}/></Card> : null}
  </div>;
}
