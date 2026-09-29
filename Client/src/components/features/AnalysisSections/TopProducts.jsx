import React from 'react';
import { pickSource, Card, SimpleTable, DomainTag, getPriceRows, getDomains, cleanProductName, arr } from './_helpers';

// This component used to re-export ProductComparison, which caused duplicate
// matched product tables/cards when the dashboard also rendered ProductComparison.
// It now shows only price-anchor products, so product matching appears once only.
export default function TopProducts(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const rows = getPriceRows(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const anchors = arr(rows).flatMap((site) => {
    const lowest = arr(site.lowestPricedProducts).slice(0, 3).map((p) => ({
      domain: site.domain,
      anchorType: 'Lowest price',
      product: cleanProductName(p.name),
      price: p.price,
      url: p.url,
    }));
    const highest = arr(site.highestPricedProducts).slice(0, 3).map((p) => ({
      domain: site.domain,
      anchorType: 'Highest price',
      product: cleanProductName(p.name),
      price: p.price,
      url: p.url,
    }));
    return [...lowest, ...highest];
  });

  if (!anchors.length) return null;

  return (
    <Card
      title="Cheapest & most expensive items"
      subtitle="The price extremes each store presents on the analyzed pages — the entry price a shopper sees first, and the premium ceiling."
    >
      <SimpleTable
        exportName="price-extremes"
        columns={[
          { key: 'domain', label: 'Store', render: (v) => <DomainTag user={v === domains.user}>{v}</DomainTag> },
          { key: 'anchorType', label: 'Extreme' },
          { key: 'product', label: 'Product' },
          { key: 'price', label: 'Price', format: 'money' },
          { key: 'url', label: 'URL' },
        ]}
        rows={anchors}
      />
    </Card>
  );
}
