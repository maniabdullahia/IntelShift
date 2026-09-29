import React from 'react';
import { pickSource, Card, SimpleTable, DomainTag, getCatalogRows, getInventoryRows, getPriceRows, getDomains } from './_helpers';

/* Store-level catalog totals. Per-collection breadth/stock visuals live in
   CollectionData (heatmap + stock-health chart); this owns the one-row-per-store
   "Catalog & stock" table so the same numbers aren't charted twice. */

export default function QuantitativeSignals(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const catalog = getCatalogRows(ai, comparison, aiPayload);
  const inventory = getInventoryRows(ai, comparison, aiPayload);
  const price = getPriceRows(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  if (!catalog.length && !inventory.length && !price.length) return null;

  // Merge the catalog (all-pages) and inventory (collection-only) rows into one
  // row per store so users see a single table instead of two with different
  // denominators. Stock columns naturally stay blank for stores with no
  // analyzed collection.
  const byDomain = {};
  catalog.forEach((r) => { byDomain[r.domain] = { ...(byDomain[r.domain] || {}), ...r }; });
  inventory.forEach((r) => { byDomain[r.domain] = { ...(byDomain[r.domain] || {}), ...r }; });
  const combined = Object.values(byDomain);

  return <div className="space-y-5">
    {/* Per-page products chart and per-collection stock chart removed here —
        they duplicated CollectionData's assortment-gap heatmap and stock-health
        chart. This section now owns only the store-level catalog totals. */}
    {combined.length ? <Card
      title="Catalog & stock"
      subtitle="One row per store, counting each product once. 'Products found' is every unique product across the pages analyzed — homepage-only 'featured' items are excluded, since they just re-showcase catalog products. 'In collections' is the unique products that sit inside a collection you track; 'Not in collections' is the rest — products found on standalone product pages or in collections you don't track — and the two add up to 'Products found'. 'On homepage' is how many of those catalog products are also featured on the homepage — an overlay that can overlap with 'In collections' or 'Not in collections', so it's not part of the sum. Stock is only measurable inside collections, so those columns cover the 'In collections' subset. Note: a product can belong to several collections, so per-collection lists elsewhere may show the same item more than once."
    ><SimpleTable exportName="catalog-stock" columns={[
      {key:'domain',label:'Store',render:(v)=><DomainTag user={v===domains.user}>{v}</DomainTag>},
      {key:'platform',label:'Platform'},
      {key:'uniqueProducts',label:'Products found'},
      {key:'collectionProductCount',label:'In collections'},
      {key:'notInCollections',label:'Not in collections'},
      {key:'onHomepageCount',label:'On homepage'},
      {key:'inStockCount',label:'In stock'},
      {key:'outOfStockCount',label:'Out of stock'},
      {key:'inStockRate',label:'In-stock rate',format:'pct'},
      {key:'priceCoverageRate',label:'Price coverage',format:'pct'},
    ]} rows={combined}/></Card> : null}
  </div>;
}
