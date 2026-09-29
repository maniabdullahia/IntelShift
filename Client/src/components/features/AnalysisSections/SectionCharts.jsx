import React, { useEffect, useRef } from 'react';
import { Card, Verdict, arr, compactNum, money, pct, titleCase, limitText } from './_helpers';

/* Brand palette (theme/brand.css). Convention across all charts:
   dataset 0 = user (teal / "you"), dataset 1 = competitor (coral / threat). */
export const BRAND_COLORS = ['#4ecdc4', '#ff6b6b', '#1a1a2e', '#fed330', '#26de81', '#636e72'];
const withAlpha = (hex, a) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};
export function applyBrandTheme(config) {
  if (!config?.data?.datasets) return config;
  const isRadar = config.type === 'radar';
  const isDoughnut = config.type === 'doughnut' || config.type === 'pie';
  config.data.datasets.forEach((ds, i) => {
    if (ds.backgroundColor || ds.borderColor) return; // respect explicit colors
    if (isDoughnut) {
      ds.backgroundColor = ds.data.map((_, j) => BRAND_COLORS[j % BRAND_COLORS.length]);
      ds.borderColor = '#ffffff';
    } else {
      const c = BRAND_COLORS[i % BRAND_COLORS.length];
      ds.borderColor = c;
      ds.backgroundColor = isRadar ? withAlpha(c, 0.18) : withAlpha(c, 0.75);
      if (isRadar) { ds.pointBackgroundColor = c; ds.borderWidth = 2; }
      else { ds.borderWidth = 0; ds.borderRadius = 6; }
    }
  });
  return config;
}

export const baseChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' },
    tooltip: { mode: 'index', intersect: false },
  },
  scales: {
    x: { grid: { display: false } },
    y: { beginAtZero: true },
  },
};

export function useChart(canvasRef, config) {
  useEffect(() => {
    let chart;
    let cancelled = false;
    async function run() {
      if (!canvasRef.current || !config) return;
      try {
        const mod = await import('chart.js/auto');
        if (cancelled) return;
        const Chart = mod.default;
        if (Chart?.defaults) { Chart.defaults.font.family = "'Inter', system-ui, sans-serif"; Chart.defaults.color = '#636e72'; }
        chart = new Chart(canvasRef.current, applyBrandTheme(config));
      } catch (e) {
        // Chart.js is optional. Fallback bars/tables still render if not installed.
      }
    }
    run();
    return () => {
      cancelled = true;
      if (chart) chart.destroy();
    };
  }, [canvasRef, config]);
}

export function ChartBox({ title, subtitle, config, fallback, verdict, verdictTone, className = '', height = 'h-64' }) {
  const ref = useRef(null);
  useChart(ref, config);
  if (!config && !fallback) return null;
  return (
    <Card title={title} subtitle={subtitle} className={className}>
      {config ? (
        <div className={`${height} w-full`}>
          <canvas ref={ref} />
        </div>
      ) : null}
      {fallback ? <div className={config ? 'mt-4' : ''}>{fallback}</div> : null}
      {verdict ? <Verdict tone={verdictTone}>{verdict}</Verdict> : null}
    </Card>
  );
}

export function BarFallback({ rows, valueKey, labelKey = 'domain', formatter = compactNum }) {
  const max = Math.max(...arr(rows).map((r) => Number(r[valueKey]) || 0), 1);
  return (
    <div className="space-y-3">
      {arr(rows).map((r, i) => {
        const value = Number(r[valueKey]) || 0;
        return (
          <div key={i}>
            <div className="mb-1 flex justify-between text-xs text-slate-600">
              <span className="font-medium">{r[labelKey]}</span>
              <span>{formatter(value, r)}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-slate-800" style={{ width: `${Math.max(3, (value / max) * 100)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function priceRangeChart(priceRows) {
  if (!arr(priceRows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: priceRows.map((r) => r.domain),
      datasets: [
        { label: 'Minimum price', data: priceRows.map((r) => Number(r.priceMin) || 0) },
        { label: 'Average price', data: priceRows.map((r) => Number(r.averagePrice) || 0) },
        { label: 'Maximum price', data: priceRows.map((r) => Number(r.priceMax) || 0) },
      ],
    },
    options: baseChartOptions,
  };
}

export function inventoryChart(inventoryRows) {
  if (!arr(inventoryRows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: inventoryRows.map((r) => r.domain),
      datasets: [
        { label: 'In stock', data: inventoryRows.map((r) => Number(r.inStockCount) || 0) },
        { label: 'Out of stock', data: inventoryRows.map((r) => Number(r.outOfStockCount) || 0) },
      ],
    },
    options: baseChartOptions,
  };
}

export function catalogChart(catalogRows) {
  if (!arr(catalogRows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: catalogRows.map((r) => r.domain),
      datasets: [
        { label: 'Products detected', data: catalogRows.map((r) => Number(r.uniqueProducts || r.productsDetected || r.productsWithPrice) || 0) },
        { label: 'Priced products', data: catalogRows.map((r) => Number(r.productsWithPrice || r.pricedProducts || r.uniqueProducts) || 0) },
      ],
    },
    options: baseChartOptions,
  };
}

export function toCollectionChartRows(matchups) {
  return arr(matchups).map((m) => ({
    category: m.category,
    label: m.userCollection?.title || m.competitorCollection?.title
      || (m.category && String(m.category).toLowerCase() !== 'unknown' ? titleCase(m.category) : 'Collection'),
    userLabel: m.userCollection?.title || '',
    competitorLabel: m.competitorCollection?.title || '',
    userProducts: Number(m.userCollection?.productCount ?? m.userCollectionProductCount ?? m.assortmentGap?.userProductCount ?? 0),
    competitorProducts: Number(m.competitorCollection?.productCount ?? m.competitorCollectionProductCount ?? m.assortmentGap?.competitorProductCount ?? 0),
    userInStock: Number(m.userCollection?.inStockRate ?? 0),
    competitorInStock: Number(m.competitorCollection?.inStockRate ?? 0),
    userAveragePrice: Number(m.priceStats?.user?.average ?? m.userCollection?.averagePrice ?? 0),
    competitorAveragePrice: Number(m.priceStats?.competitor?.average ?? m.competitorCollection?.averagePrice ?? 0),
  }));
}

export function assortmentChart(collectionRows) {
  if (!arr(collectionRows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: collectionRows.map((m) => m.label || m.category),
      datasets: [
        { label: 'User products', data: collectionRows.map((m) => m.userProducts) },
        { label: 'Competitor products', data: collectionRows.map((m) => m.competitorProducts) },
      ],
    },
    options: baseChartOptions,
  };
}

export function collectionStockChart(collectionRows) {
  if (!arr(collectionRows).length) return null;
  // Full "your collection vs their collection" titles, surfaced on hover so the
  // x-axis can stay a clean compact marker instead of long SEO collection names.
  const titles = collectionRows.map((m) => {
    const u = m.userLabel || m.label || 'Your collection';
    const c = m.competitorLabel || 'Their collection';
    return `${u}  vs  ${c}`;
  });
  return {
    type: 'bar',
    data: {
      labels: collectionRows.map((_, i) => `#${i + 1}`),
      datasets: [
        { label: 'User in-stock %', data: collectionRows.map((m) => Math.round(m.userInStock * 1000) / 10) },
        { label: 'Competitor in-stock %', data: collectionRows.map((m) => Math.round(m.competitorInStock * 1000) / 10) },
      ],
    },
    options: {
      ...baseChartOptions,
      scales: { ...baseChartOptions.scales, y: { beginAtZero: true, max: 100 } },
      plugins: {
        ...baseChartOptions.plugins,
        tooltip: {
          ...baseChartOptions.plugins.tooltip,
          callbacks: { title: (items) => (items && items.length ? titles[items[0].dataIndex] || '' : '') },
        },
      },
    },
  };
}

export function collectionAveragePriceChart(collectionRows) {
  if (!arr(collectionRows).some((m) => m.userAveragePrice || m.competitorAveragePrice)) return null;
  return {
    type: 'bar',
    data: {
      labels: collectionRows.map((m) => m.label || m.category),
      datasets: [
        { label: 'User avg price', data: collectionRows.map((m) => m.userAveragePrice) },
        { label: 'Competitor avg price', data: collectionRows.map((m) => m.competitorAveragePrice) },
      ],
    },
    options: baseChartOptions,
  };
}

export function cleanAvailability(v) {
  // availability can be bool, string, or an OBJECT ({status, inStock}) —
  // the object form rendered "[object Object]" with real pipeline data.
  if (v === true) return 'In stock';
  if (v === false) return 'Out of stock';
  if (v && typeof v === 'object' && !Array.isArray(v)) {
    if (v.inStock === true) return 'In stock';
    if (v.inStock === false) return 'Out of stock';
    return cleanAvailability(v.status);
  }
  const s = String(v || '');
  if (s.includes('out_of_stock') || s.toLowerCase().includes('out of stock')) return 'Out of stock';
  if (s.includes('in_stock') || s.toLowerCase().includes('in stock')) return 'In stock';
  return s || '—';
}

export function collectMatchedProducts(matchups) {
  return arr(matchups).flatMap((m) =>
    arr(m.topProductMatches).map((p) => ({
      category: m.category,
      user: p.userProduct || {},
      competitor: p.competitorProduct || {},
      userName: p.userProduct?.name,
      competitorName: p.competitorProduct?.name,
      matchReasons: p.matchReasons || [],
      matchTier: p.matchTier,
      gap: Number(p.priceGap?.absolute ?? (Number(p.competitorProduct?.priceValue) - Number(p.userProduct?.priceValue))),
      gapPct: Number(p.priceGap?.percentVsUser),
      direction: p.priceGap?.direction,
      confidence: Number(p.confidence),
      competitorStock: cleanAvailability(p.competitorProduct?.availability),
      userStock: cleanAvailability(p.userProduct?.availability),
    }))
  );
}

function shortName(s, max = 22) {
  const t = String(s || '').replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

export function priceGapChart(matchedProducts, limit = 16) {
  if (!arr(matchedProducts).length) return null;
  return {
    type: 'bar',
    data: {
      // Real product names — "skincare 1 / foundation 2" told users nothing.
      labels: matchedProducts.slice(0, limit).map((r, i) => shortName(r.userName) || `${r.category || 'match'} ${i + 1}`),
      datasets: [{ label: 'Price gap % (negative = competitor cheaper)', data: matchedProducts.slice(0, limit).map((r) => r.gapPct) }],
    },
    options: baseChartOptions,
  };
}

// Product counts per analyzed page — user (teal) vs competitor (coral).
export function perPageCatalogChart(rows, userLabel = 'You', competitorLabel = 'Competitor') {
  if (!arr(rows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: rows.map((r) => r.page),
      datasets: [
        { label: userLabel, data: rows.map((r) => r.user) },
        { label: competitorLabel, data: rows.map((r) => r.competitor) },
      ],
    },
    options: baseChartOptions,
  };
}

export function priceDirectionChart(matchedProducts) {
  if (!arr(matchedProducts).length) return null;
  const competitorLower = matchedProducts.filter((p) => String(p.direction).includes('competitor_lower')).length;
  const userLower = matchedProducts.filter((p) => String(p.direction).includes('competitor_higher')).length;
  return {
    type: 'doughnut',
    data: {
      labels: ['Competitor cheaper', 'User cheaper / competitor higher'],
      datasets: [{ label: 'Matched products', data: [competitorLower, userLower] }],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
  };
}

export function matchedStockChart(matchedProducts) {
  if (!arr(matchedProducts).length) return null;
  const inStock = matchedProducts.filter((p) => String(p.competitorStock).toLowerCase().includes('in stock')).length;
  const out = matchedProducts.filter((p) => String(p.competitorStock).toLowerCase().includes('out')).length;
  return {
    type: 'doughnut',
    data: {
      labels: ['Competitor matched in stock', 'Competitor matched out of stock'],
      datasets: [{ label: 'Matched products', data: [inStock, out] }],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } },
  };
}

export function seoChart(seoRows) {
  if (!arr(seoRows).length) return null;
  const rows = seoRows.map((r) => ({
    domain: r.domain,
    missingMeta: Number(r.pagesWithMissingMetaDescription || 0),
    missingH1: Number(r.pagesWithMissingH1 || 0),
    pages: Number(r.pagesAnalyzed || arr(r.seoRows || r.collectionPages || r.examples).length || 0),
  })).map((r) => ({ ...r, complete: Math.max(0, r.pages * 2 - r.missingMeta - r.missingH1) }));
  return {
    type: 'bar',
    data: {
      labels: rows.map((r) => r.domain),
      datasets: [
        { label: 'Missing meta descriptions', data: rows.map((r) => r.missingMeta) },
        { label: 'Missing H1', data: rows.map((r) => r.missingH1) },
        { label: 'Complete SEO checks', data: rows.map((r) => r.complete) },
      ],
    },
    options: baseChartOptions,
  };
}

export function trustChart(trustRows) {
  if (!arr(trustRows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: trustRows.map((r) => r.domain),
      datasets: [
        { label: 'Trust signal', data: trustRows.map((r) => (r.hasHomepageTrustSignals ? 1 : 0)) },
        { label: 'Newsletter', data: trustRows.map((r) => (r.newsletterDetected ? 1 : 0)) },
        { label: 'Discount message', data: trustRows.map((r) => (r.discountMessagingDetected ? 1 : 0)) },
      ],
    },
    options: { ...baseChartOptions, scales: { ...baseChartOptions.scales, y: { beginAtZero: true, max: 1, ticks: { stepSize: 1 } } } },
  };
}

export { money, pct };

export function clampScore(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, Math.round(v)));
}

/* Radar dimension weights per business type. Dimension order matches
   buildCompetitiveScores labels:
   [Catalog depth, Price access, Stock health, SEO hygiene, Trust/conversion,
    Collection breadth, Content depth, Promotions, Navigation] */
export const RADAR_WEIGHTS = {
  ecommerce: [25, 10, 20, 15, 15, 15, 15, 10,  8],
  saas:      [10, 25,  5, 30, 20, 10, 15,  3,  8],
  services:  [10, 15,  5, 30, 25, 15, 12,  3,  8],
  website:   [15, 15, 10, 25, 20, 15, 12,  6, 10],
};
export function weightedScore(values = [], businessType = 'ecommerce', activeMask = null) {
  const weights = RADAR_WEIGHTS[businessType] || RADAR_WEIGHTS.website;
  // A dimension with no data for either store shouldn't dilute the composite:
  // drop its weight from the denominator entirely.
  const eff = weights.map((w, i) => (activeMask && activeMask[i] === false ? 0 : w));
  const total = eff.reduce((a, b) => a + b, 0) || 1;
  return clampScore(values.reduce((sum, v, i) => sum + (Number(v) || 0) * (eff[i] || 0), 0) / total);
}

// A rate that may arrive as 0–1 or 0–100 → always 0–100.
function asPct(v) {
  const n = Number(v);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return n <= 1 ? n * 100 : n;
}

export function buildCompetitiveScores({ catalogRows = [], inventoryRows = [], priceRows = [], seoRows = [], trustRows = [], collectionRows = [], contentDepthRows = [], saleRows = [], navigation = null } = {}) {
  const userCatalog = arr(catalogRows)[0] || {};
  const compCatalog = arr(catalogRows)[1] || {};
  const userInventory = arr(inventoryRows)[0] || {};
  const compInventory = arr(inventoryRows)[1] || {};
  const userPrice = arr(priceRows)[0] || {};
  const compPrice = arr(priceRows)[1] || {};
  const userSeo = arr(seoRows)[0] || {};
  const compSeo = arr(seoRows)[1] || {};
  const userTrust = arr(trustRows)[0] || {};
  const compTrust = arr(trustRows)[1] || {};

  const userProducts = Number(userCatalog.uniqueProducts || userCatalog.productsDetected || userCatalog.productsWithPrice || 0);
  const compProducts = Number(compCatalog.uniqueProducts || compCatalog.productsDetected || compCatalog.productsWithPrice || 0);
  const maxProducts = Math.max(userProducts, compProducts, 1);

  const userAvg = Number(userPrice.averagePrice || 0);
  const compAvg = Number(compPrice.averagePrice || 0);
  const maxAvg = Math.max(userAvg, compAvg, 1);
  const minEntry = Math.min(Number(userPrice.priceMin || 0) || maxAvg, Number(compPrice.priceMin || 0) || maxAvg, maxAvg);

  const userSeoPages = Number(userSeo.pagesAnalyzed || arr(userSeo.seoRows).length || 0);
  const compSeoPages = Number(compSeo.pagesAnalyzed || arr(compSeo.seoRows).length || 0);
  const seoScore = (r) => {
    const pages = Math.max(Number(r.pagesAnalyzed || arr(r.seoRows).length || 0), 1);
    const missing = Number(r.pagesWithMissingMetaDescription || 0) + Number(r.pagesWithMissingH1 || 0);
    return clampScore(((pages * 2 - missing) / (pages * 2)) * 100);
  };
  const trustScore = (r) => clampScore([
    r.hasHomepageTrustSignals,
    r.newsletterDetected,
    r.discountMessagingDetected,
    Number(r.trustSectionCount || 0) > 0,
  ].filter(Boolean).length * 25);

  const userCollectionAvg = arr(collectionRows).length
    ? arr(collectionRows).reduce((sum, r) => sum + Number(r.userProducts || 0), 0) / arr(collectionRows).length
    : 0;
  const compCollectionAvg = arr(collectionRows).length
    ? arr(collectionRows).reduce((sum, r) => sum + Number(r.competitorProducts || 0), 0) / arr(collectionRows).length
    : 0;
  const maxCollectionAvg = Math.max(userCollectionAvg, compCollectionAvg, 1);

  // Content depth — blend of variant richness (relative) and how completely each
  // store fills out its product pages (descriptions + images, absolute coverage).
  const userDepth = arr(contentDepthRows)[0] || {};
  const compDepth = arr(contentDepthRows)[1] || {};
  const maxAvgVariants = Math.max(Number(userDepth.averageVariants || 0), Number(compDepth.averageVariants || 0), 1);
  const depthScore = (r, avgVariants) => {
    if (!r || (r.productsAnalyzed == null && r.descriptionCoverageRate == null && r.averageVariants == null)) return 0;
    const variantRel = (Number(r.averageVariants || 0) / maxAvgVariants) * 100;
    const coverage = (asPct(r.descriptionCoverageRate) + asPct(r.imageCoverageRate) + asPct(r.variantCoverageRate)) / 3;
    return clampScore(variantRel * 0.4 + coverage * 0.6);
  };

  // Promotions — how actively each store discounts. One magnitude combining breadth
  // (on-sale rate) and depth (average discount), then scored relative to the leader.
  const userSale = arr(saleRows)[0] || {};
  const compSale = arr(saleRows)[1] || {};
  const promoMagnitude = (r) => (asPct(r.onSaleRate) / 100) * (1 + Number(r.averageDiscountPercent || 0) / 100);
  const userPromoRaw = promoMagnitude(userSale);
  const compPromoRaw = promoMagnitude(compSale);
  const maxPromoRaw = Math.max(userPromoRaw, compPromoRaw, 0.0001);

  // Navigation breadth — how many categories/page-types each store surfaces in nav,
  // relative to the leader.
  const navBlocks = arr(navigation?.competitors);
  const navBlock = navBlocks[0] || {};
  const userNavLinks = Number(navBlock.userNavLinkCount || 0);
  const compNavLinks = Number(navBlock.competitorNavLinkCount || 0);
  const maxNavLinks = Math.max(userNavLinks, compNavLinks, 1);

  const userVals = [
    clampScore((userProducts / maxProducts) * 100),
    clampScore((1 - ((Number(userPrice.priceMin || maxAvg) - minEntry) / maxAvg)) * 100),
    clampScore(Number(userInventory.inStockRate || 0) * 100),
    userSeoPages ? seoScore(userSeo) : 0,
    trustScore(userTrust),
    clampScore((userCollectionAvg / maxCollectionAvg) * 100),
    depthScore(userDepth),
    clampScore((userPromoRaw / maxPromoRaw) * 100),
    clampScore((userNavLinks / maxNavLinks) * 100),
  ];
  const compVals = [
    clampScore((compProducts / maxProducts) * 100),
    clampScore((1 - ((Number(compPrice.priceMin || maxAvg) - minEntry) / maxAvg)) * 100),
    clampScore(Number(compInventory.inStockRate || 0) * 100),
    compSeoPages ? seoScore(compSeo) : 0,
    trustScore(compTrust),
    clampScore((compCollectionAvg / maxCollectionAvg) * 100),
    depthScore(compDepth),
    clampScore((compPromoRaw / maxPromoRaw) * 100),
    clampScore((compNavLinks / maxNavLinks) * 100),
  ];
  // Data presence per dimension — the last three (content, promotions, nav) can be
  // absent; mark a dimension inactive when neither store has any signal for it.
  const hasContent = arr(contentDepthRows).length > 0;
  const hasPromo = arr(saleRows).length > 0 && (userPromoRaw > 0 || compPromoRaw > 0);
  const hasNav = navBlocks.length > 0 && (userNavLinks > 0 || compNavLinks > 0);
  const activeMask = [true, true, true, true, true, true, hasContent, hasPromo, hasNav];

  return {
    labels: ['Catalog depth', 'Price access', 'Stock health', 'SEO hygiene', 'Trust/conversion', 'Collection breadth', 'Content depth', 'Promotions', 'Navigation'],
    activeMask,
    user: userVals,
    competitor: compVals,
  };
}

export function competitiveRadarChart(scoreData, userLabel = 'User', competitorLabel = 'Competitor') {
  if (!scoreData || !arr(scoreData.labels).length) return null;
  return {
    type: 'radar',
    data: {
      labels: scoreData.labels,
      datasets: [
        { label: userLabel, data: scoreData.user || [] },
        { label: competitorLabel, data: scoreData.competitor || [] },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom' } },
      scales: { r: { beginAtZero: true, max: 100, ticks: { stepSize: 20 } } },
    },
  };
}

export function buildSignalCounts(matchups) {
  const counts = new Map();
  arr(matchups).forEach((m) => {
    arr(m.topProductMatches).forEach((p) => {
      const sig = p.positioningComparisonSignals || {};
      arr(sig.sharedSignals).forEach((x) => counts.set(x, { ...(counts.get(x) || {}), shared: ((counts.get(x)||{}).shared || 0) + 1 }));
      arr(sig.userOnlySignals).forEach((x) => counts.set(x, { ...(counts.get(x) || {}), user: ((counts.get(x)||{}).user || 0) + 1 }));
      arr(sig.competitorOnlySignals).forEach((x) => counts.set(x, { ...(counts.get(x) || {}), competitor: ((counts.get(x)||{}).competitor || 0) + 1 }));
    });
  });
  return [...counts.entries()]
    .map(([signal, v]) => ({ signal, shared: v.shared || 0, user: v.user || 0, competitor: v.competitor || 0, total: (v.shared || 0) + (v.user || 0) + (v.competitor || 0) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 10);
}

export function positioningSignalChart(signalRows) {
  if (!arr(signalRows).length) return null;
  return {
    type: 'bar',
    data: {
      labels: signalRows.map((r) => r.signal),
      datasets: [
        { label: 'Shared', data: signalRows.map((r) => r.shared) },
        { label: 'User-only', data: signalRows.map((r) => r.user) },
        { label: 'Competitor-only', data: signalRows.map((r) => r.competitor) },
      ],
    },
    options: { ...baseChartOptions, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } } },
  };
}

function matrixTone(item) {
  const s = String(item.priority || item.severity || item.impact || '').toLowerCase();
  if (s.includes('p1') || s.includes('urgent') || s.includes('high')) return 'bg-(--accent) text-white border-(--accent-dark)';
  if (s.includes('p2') || s.includes('medium')) return 'bg-(--warning) text-(--primary) border-[#e5bd2b]';
  return 'bg-(--secondary) text-white border-(--secondary-dark)';
}

export function OpportunityMatrix({ items = [], title = 'Opportunity matrix', subtitle = 'Impact vs effort view for prioritizing next actions.' }) {
  const rows = arr(items).slice(0, 8).map((r, i) => {
    const priority = String(r.priority || r.severity || '').toLowerCase();
    const importance = Number(r.importanceScore || r.impactScore || 0);
    const actionText = r.recommendation || r.action || r.title || r.successMetric || '';
    const impact = priority.includes('p1') || priority.includes('high') || priority.includes('urgent') ? 86 : priority.includes('p2') || priority.includes('medium') ? 68 : importance || 48;
    const effort = String(r.area || r.relatedArea || actionText).toLowerCase().includes('seo') ? 32 : String(actionText).length > 140 ? 68 : String(actionText).length > 90 ? 54 : 40;
    const bubble = priority.includes('p1') || priority.includes('high') ? 46 : priority.includes('p2') || priority.includes('medium') ? 40 : 34;
    return { ...r, x: clampScore(impact), y: clampScore(effort), bubble, index: i + 1, actionText };
  });
  if (!rows.length) return null;
  return (
    <Card title={title} subtitle={subtitle}>
      <div className="relative h-80 overflow-hidden rounded-2xl border border-slate-200 bg-linear-to-br from-emerald-50 via-white to-sky-50 p-4">
        <div className="absolute left-4 top-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-500">Higher effort</div>
        <div className="absolute bottom-4 right-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-500">Higher impact</div>
        <div className="absolute bottom-4 left-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-400">Lower impact</div>
        <div className="absolute right-4 top-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-400">Quick wins</div>
        <div className="absolute inset-x-8 top-1/2 border-t border-dashed border-slate-300" />
        <div className="absolute inset-y-8 left-1/2 border-l border-dashed border-slate-300" />
        {rows.map((r) => (
          <div
            key={r.index}
            className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border text-xs font-bold shadow-md ${matrixTone(r)}`}
            style={{ left: `${Math.max(9, Math.min(91, r.x))}%`, top: `${100 - Math.max(12, Math.min(88, r.y))}%`, width: r.bubble, height: r.bubble }}
            title={r.actionText}
          >
            {r.index}
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {rows.map((r) => <div key={r.index} className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><b>{r.index}.</b> {limitText(r.actionText, 120)}</div>)}
      </div>
    </Card>
  );
}

export function AssortmentGapHeatmap({ rows = [] }) {
  const data = arr(rows).map((r) => ({
    category: r.category,
    label: r.label || (r.category && String(r.category).toLowerCase() !== 'unknown' ? titleCase(r.category) : 'Collection'),
    userLabel: r.userLabel || '',
    competitorLabel: r.competitorLabel || '',
    user: Number(r.userProducts || 0),
    competitor: Number(r.competitorProducts || 0),
    gap: Number(r.competitorProducts || 0) - Number(r.userProducts || 0),
    userStock: Number(r.userInStock || 0),
    competitorStock: Number(r.competitorInStock || 0),
  }));
  if (!data.length) return null;
  return (
    <Card title="Assortment gap heatmap" subtitle="Each bar splits the matched category by product count — teal is you, coral is the competitor.">
      <div className="grid gap-3">
        {data.map((r, i) => {
          const competitorBroader = r.gap > 0;
          const total = r.user + r.competitor;
          const userPct = total ? (r.user / total) * 100 : 0;
          const compPct = total ? (r.competitor / total) * 100 : 0;
          return (
            <div key={r.label + i} className="grid items-center gap-3 rounded-xl border border-slate-200 p-3 md:grid-cols-[1fr_2fr_7rem]">
              <div className="min-w-0">
                <p className="line-clamp-2 text-xs font-semibold leading-snug" title={`${r.userLabel || '—'} vs ${r.competitorLabel || '—'}`}>
                  <span className="text-slate-900">{r.userLabel || '—'}</span>
                  <span className="text-slate-400"> vs </span>
                  <span className="text-slate-900">{r.competitorLabel || '—'}</span>
                </p>
                <p className="mt-0.5 text-[11px] text-slate-500">User {r.user} vs competitor {r.competitor}</p>
              </div>
              {/* Stacked share bar: teal = your products, coral = the competitor's. */}
              <div className="flex h-7 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full bg-[rgba(78,205,196,0.6)]" style={{ width: `${userPct}%` }} title={`You: ${r.user}`} />
                <div className="h-full bg-[rgba(255,107,107,0.55)]" style={{ width: `${compPct}%` }} title={`Competitor: ${r.competitor}`} />
              </div>
              <div className="whitespace-nowrap text-right text-sm font-semibold text-slate-700">{competitorBroader ? `Competitor +${r.gap}` : `User +${Math.abs(r.gap)}`}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function ProductOpportunityQuadrant({ products = [] }) {
  const rows = arr(products).slice(0, 14).map((p, i) => {
    const price = Number(p.price || p.priceValue || 0);
    const inStock = String(p.availability || p.stock || '').toLowerCase().includes('in stock') || String(p.availability || '').includes('in_stock');
    const band = String(p.priceBand || '').toLowerCase();
    const x = band.includes('low') ? 30 : band.includes('premium') || band.includes('high') ? 76 : price ? 55 : 45;
    const y = inStock ? 76 : 34;
    const bubble = inStock && (band.includes('high') || band.includes('premium')) ? 42 : inStock ? 36 : 30;
    return { ...p, index: i + 1, x, y, bubble, inStock };
  });
  if (!rows.length) return null;
  return (
    <Card title="Product opportunity quadrant" subtitle="Competitor-only products grouped by price band and availability.">
      <div className="relative h-80 overflow-hidden rounded-2xl border border-slate-200 bg-linear-to-br from-slate-50 via-white to-amber-50 p-4">
        <div className="absolute left-4 top-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-500">In stock / available</div>
        <div className="absolute bottom-4 right-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-500">Higher price band</div>
        <div className="absolute bottom-4 left-4 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-400">Lower price band</div>
        <div className="absolute inset-x-8 top-1/2 border-t border-dashed border-slate-300" />
        <div className="absolute inset-y-8 left-1/2 border-l border-dashed border-slate-300" />
        {rows.map((p) => (
          <div key={p.index} className={`absolute flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border text-xs font-bold shadow-md ${p.inStock ? 'border-emerald-500 bg-emerald-400 text-white' : 'border-slate-300 bg-white text-slate-700'}`} style={{ left: `${p.x}%`, top: `${100 - p.y}%`, width: p.bubble, height: p.bubble }} title={p.name || p.product}>{p.index}</div>
        ))}
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2">
        {rows.slice(0, 8).map((p) => <div key={p.index} className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><b>{p.index}.</b> {limitText(p.name || p.product, 90)} <span className="text-slate-500">({money(p.price || p.priceValue, p.currency || '')})</span></div>)}
      </div>
    </Card>
  );
}
