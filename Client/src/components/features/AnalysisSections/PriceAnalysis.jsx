import React from 'react';
import { pickSource, Card, Stat, Verdict, Pill, getPriceRows, getMatchups, getDomains, getCurrency, hasPromoGap, arr, money, confidenceTier, humanizeMatchReasons, cleanProductName, conceptLabel, getEvidenceProductMap } from './_helpers';
import { ChartBox, BarFallback, priceRangeChart, priceGapChart, collectMatchedProducts } from './SectionCharts';

/* Pricing tab, scope-aware:
   1. MATCHED PRODUCTS first (like-for-like — the numbers that matter)
   2. Promo posture note (competitor runs sales, you don't) when detected
   3. Whole-snapshot price ranges last, clearly labeled as such */

function medianGapPct(matched) {
  const gaps = matched.map((p) => Number(p.gapPct)).filter(Number.isFinite).sort((a, b) => a - b);
  if (!gaps.length) return null;
  return Math.round(gaps[Math.floor(gaps.length / 2)]);
}

export default function PriceAnalysis(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const rows = getPriceRows(ai, comparison, aiPayload);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const currency = props.currency || getCurrency(ai, comparison, aiPayload);
  const matchedProducts = collectMatchedProducts(matchups);
  const evidenceMap = getEvidenceProductMap(ai, comparison, aiPayload);
  const promoGap = hasPromoGap(ai, comparison, aiPayload);
  // True when the engine scoped price aggregates to the user's mapped collections
  // (same categories both sides) — so we can say so instead of implying full catalogs.
  const priceScoped = [comparison, aiPayload, ai].some((s) => s?.priceComparison?.scopedToMappedCollections);
  if (!rows.length && !matchedProducts.length) return null;

  const median = medianGapPct(matchedProducts);
  const cheaperCount = matchedProducts.filter((p) => String(p.direction).includes('competitor_lower')).length;
  const positionText = median === null ? null
    : median < -3 ? `You are priced ~${Math.abs(median)}% ABOVE ${domains.competitor || 'the competitor'} on comparable products`
    : median > 3 ? `You are priced ~${median}% BELOW ${domains.competitor || 'the competitor'} on comparable products`
    : 'You are priced at par with the competitor on comparable products';

  const norm = (u) => String(u || '').trim().replace(/\/+$/, '').toLowerCase();

  // Per-variant breakdown (option name → price → stock) for a product page,
  // joined from the evidence pack. Only shown when there's more than one
  // variant — and flagged when prices actually differ between them.
  const VariantBreakdown = ({ ev }) => {
    const variants = arr(ev?.variants).filter((v) => v && (v.option1 || v.title));
    if (variants.length < 2) return null;
    const prices = variants.map((v) => Number(v.price)).filter(Number.isFinite);
    const pricesDiffer = new Set(prices).size > 1;
    const shown = variants.slice(0, 8);
    return (
      <div className="mt-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-(--text-light)">
          Variants ({variants.length}){pricesDiffer ? ' · prices vary' : ''}
        </p>
        <div className="mt-1 divide-y divide-(--border) overflow-hidden rounded-lg border border-(--border) bg-(--card)">
          {shown.map((v, i) => (
            <div key={i} className="flex items-center justify-between gap-2 px-2.5 py-1.5 text-xs">
              <span className="min-w-0 truncate text-(--text)">{v.option1 || v.title || `Variant ${i + 1}`}</span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-(--text-light)">{Number.isFinite(Number(v.price)) ? money(Number(v.price), currency) : '—'}</span>
                <span className={v.available ? 'text-(--success)' : 'text-(--text-light)'}>{v.available ? 'In stock' : 'Out'}</span>
              </span>
            </div>
          ))}
          {variants.length > shown.length ? (
            <div className="px-2.5 py-1.5 text-xs text-(--text-light)">+{variants.length - shown.length} more variants</div>
          ) : null}
        </div>
      </div>
    );
  };

  // Colour swatches — the actual colours a product comes in (label + hex).
  const Swatches = ({ p }) => {
    const sw = arr(p?.swatches).filter((s) => s && (s.label || s.value));
    if (!sw.length) return null;
    const shown = sw.slice(0, 12);
    return (
      <div className="mt-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-(--text-light)">Colours ({sw.length})</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {shown.map((s, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-full border border-(--border) px-1.5 py-0.5 text-[11px] text-(--text)">
              {s.colorHex ? <span className="inline-block h-2.5 w-2.5 rounded-full border border-black/10" style={{ background: s.colorHex }} /> : null}
              <span className="max-w-[90px] truncate">{s.label || s.value}</span>
            </span>
          ))}
          {sw.length > shown.length ? <span className="text-[11px] text-(--text-light)">+{sw.length - shown.length} more</span> : null}
        </div>
      </div>
    );
  };

  // Extra product-page detail we already capture but never showed: how many
  // variants, what the variant options are, the product type, and sale pricing.
  const ProductMeta = ({ p }) => {
    if (!p) return null;
    const vc = Number(p.variantCount);
    const opts = arr(p.variantOptions);
    // The engine stores the strike-through price as `priceCompareAt`; older/other
    // shapes use `compareAtPrice` — accept either so the discount always shows.
    const compareAt = p.priceCompareAt ?? p.compareAtPrice;
    return (
      <>
        {Number.isFinite(vc) && vc > 1 ? (
          <p className="mt-1 text-xs text-(--text-light)">
            <span className="font-semibold text-(--text)">{vc} variants</span>
            {opts.length ? `: ${opts.slice(0, 6).join(', ')}${opts.length > 6 ? '…' : ''}` : ''}
          </p>
        ) : null}
        {p.productType ? <p className="mt-0.5 text-xs text-(--text-light)">Type: {p.productType}</p> : null}
        {p.isOnSale && compareAt != null ? (
          <p className="mt-0.5 text-xs">
            <span className="text-(--text-light) line-through">{money(compareAt, currency)}</span>
            {p.discountPercent ? <span className="ml-1 font-semibold text-(--accent)">-{Math.round(p.discountPercent)}%</span> : null}
            {!p.discountPercent ? <span className="ml-1 font-semibold text-(--accent)">on sale</span> : null}
          </p>
        ) : null}
      </>
    );
  };

  return <div className="space-y-5">
    {matchedProducts.length ? <Card
      title="Price position on matched products"
      subtitle={`Like-for-like comparison across ${matchedProducts.length} matched product${matchedProducts.length > 1 ? 's' : ''} in matched collections.`}
    >
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <Stat label="Median price gap" value={median !== null ? `${median > 0 ? '+' : ''}${median}%` : undefined} hint="Competitor vs your price" />
        <Stat label="Competitor cheaper on" value={`${cheaperCount} of ${matchedProducts.length}`} hint="Matched products" />
        <Stat label="Matched products" value={matchedProducts.length} hint="Across matched collections" />
      </div>
      {positionText && <Verdict tone={median !== null && median < -3 ? 'risk' : median !== null && median > 3 ? 'good' : 'info'}>{positionText}.</Verdict>}
    </Card> : null}

    {matchedProducts.length ? <Card
      title="Matched products — like for like"
      subtitle="Each of your products paired with its closest competitor match — why they were paired, and how they compare."
    >
      <div className="space-y-3">
        {matchedProducts.map((r, i) => {
          const uPrice = r.user?.price ?? r.user?.priceValue;
          const cPrice = r.competitor?.price ?? r.competitor?.priceValue;
          const pctVal = Number.isFinite(r.confidence)
            ? (r.confidence <= 1 ? Math.round(r.confidence * 100) : Math.round(r.confidence))
            : null;
          const dir = String(r.direction || '');
          const cheaper = dir.includes('competitor_lower')
            ? `${domains.competitor || 'Competitor'} cheaper`
            : dir.includes('user_lower')
              ? 'You cheaper'
              : 'Similar price';
          const cheaperTone = dir.includes('competitor_lower') ? 'high' : dir.includes('user_lower') ? 'low' : 'medium';
          const why = humanizeMatchReasons(r.matchReasons).replace(/^Matched because:\s*/i, '');
          return (
            <div key={i} className="rounded-2xl border border-(--border) bg-(--card) p-4">
              {/* header: category · match confidence · price verdict */}
              <div className="mb-3 flex flex-wrap items-center gap-2">
                {r.category && <Pill tone="low">{conceptLabel(r.category)}</Pill>}
                {pctVal !== null && <Pill tone="medium">{confidenceTier(r.confidence) || 'Match'} · {pctVal}%</Pill>}
                <Pill tone={cheaperTone}>
                  {cheaper}
                  {Number.isFinite(r.gapPct) ? ` · ${r.gapPct > 0 ? '+' : ''}${Math.round(r.gapPct)}%` : ''}
                </Pill>
              </div>

              {/* the two products, side by side */}
              <div className="grid items-stretch gap-3 sm:grid-cols-[1fr_auto_1fr]">
                <div
                  className="rounded-xl border p-3"
                  style={{ borderColor: 'color-mix(in srgb, var(--secondary) 45%, transparent)', background: 'color-mix(in srgb, var(--secondary) 5%, transparent)' }}
                >
                  <p className="text-[11px] font-bold uppercase tracking-wide text-(--secondary)">You</p>
                  <p className="mt-1 font-semibold text-(--primary) break-words">{cleanProductName(r.userName) || '—'}</p>
                  <p className="mt-1 text-sm text-(--text-light)">{money(uPrice, currency)}{r.userStock ? ` · ${r.userStock}` : ''}</p>
                  <ProductMeta p={r.user} />
                  <Swatches p={r.user} />
                  <VariantBreakdown ev={evidenceMap[norm(r.user?.productUrl || r.user?.url)]} />
                </div>

                <div className="flex items-center justify-center text-xs font-semibold text-(--text-light)">vs</div>

                <div
                  className="rounded-xl border p-3"
                  style={{ borderColor: 'color-mix(in srgb, var(--accent) 45%, transparent)', background: 'color-mix(in srgb, var(--accent) 5%, transparent)' }}
                >
                  <p className="text-[11px] font-bold uppercase tracking-wide text-(--accent)">{domains.competitor || 'Competitor'}</p>
                  <p className="mt-1 font-semibold text-(--primary) break-words">{cleanProductName(r.competitorName) || '—'}</p>
                  <p className="mt-1 text-sm text-(--text-light)">{money(cPrice, currency)}{r.competitorStock ? ` · ${r.competitorStock}` : ''}</p>
                  <ProductMeta p={r.competitor} />
                  <Swatches p={r.competitor} />
                  <VariantBreakdown ev={evidenceMap[norm(r.competitor?.productUrl || r.competitor?.url)]} />
                </div>
              </div>

              {why && (
                <p className="mt-3 text-xs text-(--text-light)">
                  <span className="font-semibold text-(--text)">Why matched:</span> {why}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card> : null}

    {promoGap ? <Card title="Promotional posture">
      <Verdict tone="risk">{domains.competitor || 'The competitor'} shows visible sale and discount offers on their analyzed pages — yours don't. Price-sensitive shoppers see them discounting.</Verdict>
    </Card> : null}

    {/* Raw "Price table — analyzed pages" removed: it repeated this chart's data
        as numbers, and store-level price stats already live in the Overview
        tiles + Assortment "Catalog & stock" table. The range chart stays — it
        shows the min/avg/max spread, which the tiles don't. */}
    {rows.length ? <ChartBox
      title="Price ranges across analyzed pages"
      subtitle={priceScoped
        ? "The min–average–max spread over the collections you mapped — the same categories on both sides, so the averages are like-for-like. Use the matched-product numbers above for pricing decisions."
        : "The min–average–max spread each store shows on the analyzed pages. Use the matched-product numbers above for pricing decisions."}
      config={priceRangeChart(rows)}
      fallback={<BarFallback rows={rows} valueKey="averagePrice" formatter={(v, r) => money(v, r.currency || currency)} />}
    /> : null}
  </div>;
}
