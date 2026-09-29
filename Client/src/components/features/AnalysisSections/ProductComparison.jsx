import React, { useMemo, useState } from 'react';
import { pickSource, Card, Pill, SimpleTable, DomainTag, getMatchups, getDomains, getCurrency, conceptLabel, arr, money, limitText, availabilityLabel, cleanProductName, confidenceTier, humanizeMatchReasons } from './_helpers';

const cleanAvailability = availabilityLabel;

// Price stats over a set of products (matched + unmatched), ignoring items
// without a numeric price so the average reflects real priced products only.
function priceStats(products) {
  const prices = arr(products)
    .map((p) => Number(p?.priceValue ?? p?.price))
    .filter((n) => Number.isFinite(n) && n > 0);
  if (!prices.length) return { count: arr(products).length, avg: null, min: null, max: null };
  const sum = prices.reduce((a, b) => a + b, 0);
  return { count: arr(products).length, avg: sum / prices.length, min: Math.min(...prices), max: Math.max(...prices) };
}

// Per-matched-collection product count + price range for each side, so a single
// blended average in the Overview doesn't hide the mix (e.g. one luxury
// collection pulling the average up).
function toCollectionStats(matchups) {
  return arr(matchups)
    .map((m) => {
      const userProducts = [
        ...arr(m.topProductMatches).map((x) => x.userProduct).filter(Boolean),
        ...arr(m.userUnmatchedProducts),
      ];
      const compProducts = [
        ...arr(m.topProductMatches).map((x) => x.competitorProduct).filter(Boolean),
        ...arr(m.competitorUnmatchedProducts),
      ];
      return {
        label: m.userCollection?.title || m.competitorCollection?.title || (m.category && String(m.category).toLowerCase() !== 'unknown' ? conceptLabel(m.category) : '') || 'Collection',
        user: priceStats(userProducts),
        competitor: priceStats(compProducts),
      };
    })
    .filter((r) => r.user.count || r.competitor.count);
}

function toProductRows(matchups) {
  return arr(matchups).flatMap((m) =>
    arr(m.topProductMatches).map((x) => ({
      category: m.category,
      confidence: x.confidence,
      userUrl: x.userProduct?.productUrl || x.userProduct?.url,
      competitorUrl: x.competitorProduct?.productUrl || x.competitorProduct?.url,
      userProduct: cleanProductName(x.userProduct?.name),
      userPrice: x.userProduct?.price ?? x.userProduct?.priceValue,
      userStock: cleanAvailability(x.userProduct?.availability),
      competitorProduct: cleanProductName(x.competitorProduct?.name),
      competitorPrice: x.competitorProduct?.price ?? x.competitorProduct?.priceValue,
      competitorStock: cleanAvailability(x.competitorProduct?.availability),
      priceGap: x.priceGap?.absolute,
      priceGapPercent: x.priceGap?.percentVsUser,
      direction: x.priceGap?.direction,
      whyMatched: humanizeMatchReasons(x.matchReasons).replace(/^Matched because: /, ''),
      sharedSignals: arr(x.positioningComparisonSignals?.sharedSignals).join(', '),
    }))
  );
}

function toCompetitorOnlyRows(matchups) {
  const seen = new Set();
  return arr(matchups).flatMap((m) =>
    arr(m.competitorUnmatchedProducts).map((p) => ({
      category: m.category || p.category,
      product: cleanProductName(p.name),
      price: p.price ?? p.priceValue,
      stock: cleanAvailability(p.availability),
      type: p.productType,
      band: p.priceBand,
      url: p.url || p.productUrl,
      reason: p.productType && p.productType !== m.category ? `Detected as ${p.productType}` : 'Competitor-only item in matched category',
    }))
  ).filter((r) => {
    const key = `${r.category}|${r.product}|${r.price}|${r.url || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function toUserOnlyRows(matchups) {
  const seen = new Set();
  return arr(matchups).flatMap((m) =>
    arr(m.userUnmatchedProducts).map((p) => ({
      category: m.category || p.category,
      product: cleanProductName(p.name),
      price: p.price ?? p.priceValue,
      stock: cleanAvailability(p.availability),
      type: p.productType,
      band: p.priceBand,
      url: p.url || p.productUrl,
      reason: 'User-only item in matched category',
    }))
  ).filter((r) => {
    const key = `${r.category}|${r.product}|${r.price}|${r.url || ''}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// Everything fetched for one side: matched products + that side's unmatched
// items, across all matched collections. (Homepage-featured items arrive as
// counts only from the pipeline, so this covers analyzed collections.)
function toAllProductsRows(matchups, side) {
  const seen = new Set();
  const out = [];
  arr(matchups).forEach((m) => {
    const collection = (side === 'user' ? m.userCollection : m.competitorCollection) || {};
    const sourcePage = collection.title || conceptLabel(m.category);
    const push = (p, matchStatus) => {
      if (!p || !p.name) return;
      const key = `${p.name}|${p.productUrl || p.url || ''}`;
      if (seen.has(key)) return;
      seen.add(key);
      // Prefer colour swatch labels; fall back to raw variant option values.
      const swatchLabels = arr(p.swatches).map((s) => (typeof s === 'string' ? s : s?.label)).filter(Boolean);
      const vOpts = swatchLabels.length ? swatchLabels : arr(p.variantOptions);
      const vCount = Number(p.variantCount) || 0;
      out.push({
        sourcePage,
        category: m.category || p.category,
        product: cleanProductName(p.name),
        price: p.priceValue ?? p.price,
        stock: availabilityLabel(p.availability),
        url: p.productUrl || p.url,
        inMatch: matchStatus,
        variants: vCount
          ? `${vCount} variant${vCount === 1 ? '' : 's'}${vOpts.length ? ' · ' + vOpts.slice(0, 6).join(', ') : ''}`
          : (vOpts.length ? vOpts.slice(0, 6).join(', ') : ''),
      });
    };
    arr(m.topProductMatches).forEach((x) => {
      push(side === 'user' ? x.userProduct : x.competitorProduct, 'Matched');
    });
    arr(side === 'user' ? m.userUnmatchedProducts : m.competitorUnmatchedProducts).forEach((p) => {
      push(p, 'Unmatched');
    });
  });
  return out;
}

// Page pills inside the "All …" tabs: All pages · <each collection>. Homepage is
// intentionally excluded — the catalog + all analysis cover only products found on
// collection pages, never the homepage showcase.
function PageFilterPills({ rows, active, onSelect, counts = {} }) {
  const pages = [...new Set(arr(rows).map((r) => r.sourcePage).filter(Boolean))];
  if (!pages.length) return null;
  // Distinct products across every page — a product listed in two collections counts
  // once here, so this is the unique-products total (matches "View all N unique products").
  const uniqueCount = new Set(arr(rows).map((r) => String(r.url || r.product || '').toLowerCase()).filter(Boolean)).size;
  const pillCls = (on) => `rounded-full border px-3 py-1 text-xs font-semibold transition ${on ? 'border-(--primary) bg-(--primary) text-white' : 'border-(--border) bg-(--card) text-(--text-light) hover:text-(--primary)'}`;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button type="button" className={pillCls(active === 'all')} onClick={() => onSelect('all')}>All pages ({uniqueCount})</button>
      {pages.map((p) => {
        // Prefer the live collection count; fall back to captured rows if unknown.
        const n = counts[p] != null ? counts[p] : rows.filter((r) => r.sourcePage === p).length;
        return <button key={p} type="button" className={pillCls(active === p)} onClick={() => onSelect(p)}>{p} ({n})</button>;
      })}
    </div>
  );
}

function ProductMatchCard({ row }) {
  const cheaper = String(row.direction).includes('competitor_lower') ? 'competitor lower' : String(row.direction).includes('competitor_higher') ? 'competitor higher' : 'price neutral';
  return <div className="rounded-2xl border border-slate-200 p-4">
    <div className="mb-3 flex flex-wrap gap-2">{row.category && String(row.category).toLowerCase() !== 'unknown' ? <Pill tone="low">{row.category}</Pill> : null}{confidenceTier(row.confidence) ? <Pill tone="medium">{confidenceTier(row.confidence)}</Pill> : null}<Pill tone={cheaper.includes('lower') ? 'high' : 'low'}>{cheaper}</Pill></div>
    <div className="grid gap-3 md:grid-cols-2">
      <div className="rounded-xl border border-[rgba(78,205,196,0.3)] bg-[rgba(78,205,196,0.07)] p-3"><p className="text-xs font-semibold uppercase tracking-wide text-(--secondary-dark)">Your product</p><p className="mt-1 font-semibold text-(--primary)">{row.userUrl ? <a href={row.userUrl} target="_blank" rel="noreferrer" className="hover:underline">{limitText(row.userProduct, 80)} ↗</a> : limitText(row.userProduct, 80)}</p><p className="mt-1 text-sm text-(--text-light)">{money(row.userPrice)} · {row.userStock}</p></div>
      <div className="rounded-xl border border-[rgba(255,107,107,0.25)] bg-[rgba(255,107,107,0.06)] p-3"><p className="text-xs font-semibold uppercase tracking-wide text-(--accent)">Their product</p><p className="mt-1 font-semibold text-(--primary)">{row.competitorUrl ? <a href={row.competitorUrl} target="_blank" rel="noreferrer" className="hover:underline">{limitText(row.competitorProduct, 80)} ↗</a> : limitText(row.competitorProduct, 80)}</p><p className="mt-1 text-sm text-(--text-light)">{money(row.competitorPrice)} · {row.competitorStock}</p></div>
    </div>
    <p className="mt-3 text-sm text-slate-600">Price gap: <b>{money(row.priceGap)}</b>{row.priceGapPercent !== undefined ? ` (${row.priceGapPercent}%)` : ''}</p>
    {row.whyMatched && <p className="mt-1 text-xs text-(--text-light)">Matched because: {row.whyMatched}</p>}
  </div>;
}

export default function ProductComparison(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const currency = getCurrency(ai, comparison, aiPayload);
  const collectionStats = useMemo(() => toCollectionStats(matchups), [matchups]);
  const matchedRows = useMemo(() => toProductRows(matchups), [matchups]);
  const competitorOnly = useMemo(() => toCompetitorOnlyRows(matchups), [matchups]);
  const userOnly = useMemo(() => toUserOnlyRows(matchups), [matchups]);
  const allUser = useMemo(() => toAllProductsRows(matchups, 'user'), [matchups]);
  const allCompetitor = useMemo(() => toAllProductsRows(matchups, 'competitor'), [matchups]);
  // LIVE per-collection product counts (same source as the Matched-collections card:
  // the collection page's reported count). The crawler can under-capture individual
  // product cards on a page, so the itemized list may be shorter than the true
  // count — we key the Catalog's page counts + totals off the live number so they
  // match the card and the live site, not the captured subset. Map: page title → count.
  const liveCounts = useMemo(() => {
    const user = {}, competitor = {};
    arr(matchups).forEach((m) => {
      const ut = m.userCollection?.title;
      if (ut) user[ut] = Number(m.userCollection?.productCount ?? m.userCollectionProductCount ?? 0);
      const ct = m.competitorCollection?.title;
      if (ct) competitor[ct] = Number(m.competitorCollection?.productCount ?? m.competitorCollectionProductCount ?? 0);
    });
    return { user, competitor };
  }, [matchups]);
  const liveTotal = (side) => Object.values(liveCounts[side]).reduce((a, b) => a + Number(b || 0), 0);
  const [activeTab, setActiveTab] = useState('matched');
  const [pageFilter, setPageFilter] = useState({ allUser: 'all', allCompetitor: 'all' });
  const [expanded, setExpanded] = useState({ matched: false, competitor: false, user: false, cards: false, allUser: false, allCompetitor: false });
  const filteredAllUser = pageFilter.allUser === 'all' ? allUser : allUser.filter((r) => r.sourcePage === pageFilter.allUser);
  const filteredAllCompetitor = pageFilter.allCompetitor === 'all' ? allCompetitor : allCompetitor.filter((r) => r.sourcePage === pageFilter.allCompetitor);

  if (!matchedRows.length && !allUser.length && !allCompetitor.length && !collectionStats.length) return null;

  const rng = (s) => (s.min != null ? `${money(s.min, currency)} – ${money(s.max, currency)}` : '—');
  const collectionStatRows = collectionStats.map((r) => ({
    collection: r.label,
    yourProducts: r.user.count || '—',
    yourAvg: r.user.avg != null ? money(r.user.avg, currency) : '—',
    yourRange: rng(r.user),
    theirProducts: r.competitor.count || '—',
    theirAvg: r.competitor.avg != null ? money(r.competitor.avg, currency) : '—',
    theirRange: rng(r.competitor),
  }));

  const tabs = [
    { key: 'matched', label: 'Matched products', count: matchedRows.length, showCount: true },
    { key: 'allUser', label: `${domains.user || 'yours'}`, count: liveTotal('user') || allUser.length },
    { key: 'allCompetitor', label: `${domains.competitor || 'theirs'}`, count: liveTotal('competitor') || allCompetitor.length },
  ].filter((x) => x.count > 0);
  const currentTab = tabs.some((t) => t.key === activeTab) ? activeTab : (tabs[0]?.key || '');

  const matchedLimit = expanded.matched ? matchedRows.length : 10;
  const competitorLimit = expanded.competitor ? competitorOnly.length : 12;
  const userLimit = expanded.user ? userOnly.length : 10;
  const allUserLimit = expanded.allUser ? allUser.length : 12;
  const allCompetitorLimit = expanded.allCompetitor ? allCompetitor.length : 12;

  const allProductColumns = (user, showPage) => ([
    ...(showPage ? [{ key: 'sourcePage', label: 'Page' }] : []),
    { key: 'product', label: 'Product', render: (v, r) => r.url ? <a href={r.url} target="_blank" rel="noreferrer" className={user ? 'text-(--secondary-dark) hover:underline' : 'text-(--accent) hover:underline'}>{v}</a> : v },
    { key: 'price', label: 'Price', format: 'money' },
    { key: 'stock', label: 'Stock' },
    { key: 'variants', label: 'Variants', render: (v) => v ? <span className="text-xs text-(--text-light)">{v}</span> : <span className="text-(--text-light)">—</span> },
  ]);

  return (
    <div className="space-y-5">
      {/* "By collection" card removed — the per-collection side-by-side lives in
          CollectionData's richer "Matched collections" card (products, price
          range, stock, matched/gap), so this was duplicate. */}
      {tabs.length ? (
        <Card
          title="Catalog"
          subtitle="Every product we fetched from each side of the comparison."
        >
          <div className="mb-4 flex flex-wrap gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`rounded-full border px-3 py-1.5 text-sm font-medium transition ${currentTab === tab.key ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}
              >
                {tab.label}{tab.showCount ? <span className="ml-1 opacity-70">{tab.count}</span> : null}
              </button>
            ))}
          </div>

          {currentTab === 'matched' && matchedRows.length ? (
            <div className="space-y-3">
              <p className="text-xs text-(--text-light)">Product pairs you mapped during setup, with the price gap for each.</p>
              <div className="grid gap-3 md:grid-cols-2">
                {matchedRows.slice(0, matchedLimit).map((row, i) => <ProductMatchCard key={i} row={row} />)}
              </div>
              {matchedRows.length > 10 ? <button type="button" onClick={() => setExpanded((x) => ({ ...x, matched: !x.matched }))} className="text-sm font-medium text-slate-700 underline">{expanded.matched ? 'Show fewer matched products' : `View all ${matchedRows.length} matched products`}</button> : null}
            </div>
          ) : null}

          {currentTab === 'allUser' && allUser.length ? (
            <div className="space-y-3">
              <p className="text-xs text-(--text-light)">Everything fetched from <span className="font-semibold text-(--secondary-dark)">{domains.user}</span>, grouped by the page it was found on.</p>
              <PageFilterPills
                rows={allUser}
                active={pageFilter.allUser}
                onSelect={(p) => setPageFilter((s) => ({ ...s, allUser: p }))}
                counts={liveCounts.user}
              />
              <SimpleTable
                columns={allProductColumns(true, pageFilter.allUser === 'all')}
                rows={filteredAllUser.slice(0, allUserLimit)}
                exportName={`all-products-${domains.user || 'user'}`}
                exportRows={allUser}
              />
              {filteredAllUser.length > 12 ? <button type="button" onClick={() => setExpanded((x) => ({ ...x, allUser: !x.allUser }))} className="text-sm font-medium text-slate-700 underline">{expanded.allUser ? 'Show fewer' : `View all ${filteredAllUser.length} unique products`}</button> : null}
            </div>
          ) : null}

          {currentTab === 'allCompetitor' && allCompetitor.length ? (
            <div className="space-y-3">
              <p className="text-xs text-(--text-light)">Everything fetched from <span className="font-semibold text-(--accent)">{domains.competitor}</span>, grouped by the page it was found on.</p>
              <PageFilterPills
                rows={allCompetitor}
                active={pageFilter.allCompetitor}
                onSelect={(p) => setPageFilter((s) => ({ ...s, allCompetitor: p }))}
                counts={liveCounts.competitor}
              />
              <SimpleTable
                columns={allProductColumns(false, pageFilter.allCompetitor === 'all')}
                rows={filteredAllCompetitor.slice(0, allCompetitorLimit)}
                exportName={`all-products-${domains.competitor || 'competitor'}`}
                exportRows={allCompetitor}
              />
              {filteredAllCompetitor.length > 12 ? <button type="button" onClick={() => setExpanded((x) => ({ ...x, allCompetitor: !x.allCompetitor }))} className="text-sm font-medium text-slate-700 underline">{expanded.allCompetitor ? 'Show fewer' : `View all ${filteredAllCompetitor.length} unique products`}</button> : null}
            </div>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
