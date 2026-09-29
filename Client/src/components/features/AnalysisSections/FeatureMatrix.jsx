import React from 'react';
import { pickSource, Card, Stat, SimpleTable, firstAvailable, arr, inferBusinessType } from './_helpers';

export default function FeatureMatrix(props) {
  const { comparison, aiPayload } = pickSource(props);
  // Pricing-page detection, service pages and generic page matches are SaaS /
  // services concepts. For an e-commerce store they're noise (and a product
  // page can slip in mislabelled), so this whole section is hidden there.
  if (inferBusinessType(comparison, aiPayload) === 'ecommerce') return null;
  const pricing = firstAvailable(arr(comparison?.pricingPageComparison?.competitors), arr(aiPayload?.modules?.pricingPages?.competitors), arr(aiPayload?.pricingPageComparison?.competitors)) || [];
  const services = firstAvailable(arr(comparison?.servicesComparison?.competitors), arr(aiPayload?.modules?.services?.competitors), arr(aiPayload?.servicesComparison?.competitors)) || [];
  const pageMatches = firstAvailable(arr(comparison?.pageMatchComparison?.competitors?.[0]?.matches), arr(aiPayload?.matchEvidence?.pageMatchSummary?.[0]?.matches), arr(aiPayload?.pageMatchSummary?.[0]?.matches)) || [];
  const pricingDetected = pricing.some(p => p.userPricingPageDetected || p.competitorPricingPageDetected || arr(p.userPricingSignals).length || arr(p.competitorPricingSignals).length);
  const servicesDetected = services.some(s => (s.userServicePageCount||0)>0 || (s.competitorServicePageCount||0)>0 || arr(s.userServiceSignals).length || arr(s.competitorServiceSignals).length);
  const usefulPageMatches = pageMatches.filter(m => !['product','collection','homepage'].includes(String(m.pageIntent||'')));
  if (!pricingDetected && !servicesDetected && !usefulPageMatches.length) return null;
  return <div className="space-y-5">
    {pricingDetected ? <Card title="Pricing page comparison"><SimpleTable columns={[{key:'competitorDomain',label:'Competitor'},{key:'userPricingPageDetected',label:'User pricing page'},{key:'competitorPricingPageDetected',label:'Competitor pricing page'},{key:'sharedPlanNames',label:'Shared plans'},{key:'competitorOnlyPlanNames',label:'Competitor-only plans'}]} rows={pricing}/></Card> : null}
    {servicesDetected ? <Card title="Service page comparison"><SimpleTable columns={[{key:'competitorDomain',label:'Competitor'},{key:'userServicePageCount',label:'User service pages'},{key:'competitorServicePageCount',label:'Competitor service pages'},{key:'sharedServiceConcepts',label:'Shared services'},{key:'competitorOnlyServiceConcepts',label:'Competitor-only services'}]} rows={services}/></Card> : null}
    {usefulPageMatches.length ? <Card title="Matched generic pages"><SimpleTable columns={[{key:'pageIntent',label:'Intent'},{key:'confidence',label:'Confidence'},{key:'userPage.title',label:'User page'},{key:'competitorPage.title',label:'Competitor page'}]} rows={usefulPageMatches}/></Card> : null}
  </div>;
}
