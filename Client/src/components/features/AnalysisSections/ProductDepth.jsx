import React from 'react';
import { pickSource, Card, SimpleTable, DomainTag, getContentDepthRows, getSaleDiscountRows, getDomains } from './_helpers';

/* Product-level detail we already capture but weren't surfacing: how many variants
   (sizes/shades) each store carries, product-page content depth, and promotional
   posture (how much of the catalog is discounted and how deep). One row per store,
   over the unique products analyzed. */

const pctOrDash = (v) => (v === null || v === undefined || v === '' ? '—' : `${Math.round((Number(v) > 1 ? Number(v) : Number(v) * 100) * 10) / 10}%`);
const discountPct = (v) => (v === null || v === undefined || v === '' ? '—' : `${Math.round(Number(v) * 10) / 10}%`);

export default function ProductDepth(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const depth = getContentDepthRows(ai, comparison, aiPayload);
  const promo = getSaleDiscountRows(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  if (!depth.length && !promo.length) return null;

  return <div className="space-y-5">
    {depth.length ? <Card
      title="Variants & content depth"
      subtitle="Per store, over the unique products analyzed: how many variants (sizes/shades) they carry, and how complete their product pages are (descriptions, images)."
    ><SimpleTable exportName="product-depth" columns={[
      {key:'domain',label:'Store',render:(v)=><DomainTag user={v===domains.user}>{v}</DomainTag>},
      {key:'productsAnalyzed',label:'Unique products'},
      {key:'totalVariants',label:'Total variants'},
      {key:'averageVariants',label:'Avg / product'},
      {key:'variantCoverageRate',label:'Have variants',render:(v)=>pctOrDash(v)},
      {key:'descriptionCoverageRate',label:'Have description',render:(v)=>pctOrDash(v)},
      {key:'averageDescriptionLength',label:'Avg description (chars)'},
      {key:'imageCoverageRate',label:'Have image',render:(v)=>pctOrDash(v)},
      {key:'averageImageCount',label:'Avg images'},
    ]} rows={depth}/></Card> : null}

    {promo.length ? <Card
      title="Discounts & promotions"
      subtitle="Promotional posture — how much of each catalog is on sale and how deep the discounts go. Heavy competitor discounting is a pricing-pressure signal."
    ><SimpleTable exportName="discounts" columns={[
      {key:'domain',label:'Store',render:(v)=><DomainTag user={v===domains.user}>{v}</DomainTag>},
      {key:'onSaleCount',label:'On sale'},
      {key:'onSaleRate',label:'On-sale rate',render:(v)=>pctOrDash(v)},
      {key:'averageDiscountPercent',label:'Avg discount',render:(v)=>discountPct(v)},
      {key:'maxDiscountPercent',label:'Deepest discount',render:(v)=>discountPct(v)},
      {key:'deepestDiscounts',label:'Most-discounted item',render:(v)=>{ const t=Array.isArray(v)&&v[0]; return t? (t.productUrl ? <a href={t.productUrl} target="_blank" rel="noreferrer" className="text-(--text) hover:underline">{t.name}{t.discountPercent?` · ${discountPct(t.discountPercent)}`:''}</a> : `${t.name||''}${t.discountPercent?` · ${discountPct(t.discountPercent)}`:''}`) : '—'; }},
    ]} rows={promo}/></Card> : null}
  </div>;
}
