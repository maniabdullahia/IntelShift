import React, { useCallback, useEffect, useMemo, useState } from 'react';
import usePageNav from '../../../store/pageNav.store';

/* One malformed field in a payload must never white-screen the whole
   analysis — degrade to a quiet notice and keep the other tabs working. */
class TabErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('[AnalysisPage] tab render error:', error, info); }
  componentDidUpdate(prev) { if (prev.tabKey !== this.props.tabKey && this.state.error) this.setState({ error: null }); }
  render() {
    if (this.state.error) {
      return (
        <div className="rounded-2xl border border-dashed border-(--border) bg-(--bg) p-8 text-center text-sm text-(--text-light)">
          This section couldn't be displayed for this analysis. The rest of the tabs are unaffected.
        </div>
      );
    }
    return this.props.children;
  }
}
import {
  pickSource, arr, titleCase, limitText, firstSentences,
  getDomains, getSites, inferBusinessType, getCurrency, getWarnings, getGeneratedAt,
  getPriceRows, getCatalogRows, getInventoryRows, getSeoRows, getTrustRows, getHomepageRows,
  getMatchups, getMarketRows, getPotentialGaps, getRankedInsights, getRecommendations, getDashboardCards,
  getContentDepthRows, getSaleDiscountRows, getNavigation,
} from './_helpers';
import { buildCompetitiveScores, weightedScore, toCollectionChartRows } from './SectionCharts';

import AnalysisIdentity from './AnalysisIdentity';
import Summary from './Summary';
import PriceAnalysis from './PriceAnalysis';
import TopProducts from './TopProducts';
import CollectionData from './CollectionData';
import ProductComparison from './ProductComparison';
import SuggestedMatches from './SuggestedMatches';
import ShippingPayment from './ShippingPayment';
import ProductDepth from './ProductDepth';
import Navigation from './Navigation';
import Merchandising from './Merchandising';
import Positioning from './Positioning';
import SeoAnalysis from './SeoAnalysis';
import TrustSignals from './TrustSignals';
import KeyInsights from './KeyInsights';
import Recommendation from './Recommendation';
import CompetitorHistory from '../History/CompetitorHistory';

/* "Fail loud": when either store was only partly readable (few products,
   low price coverage, failed pages, blocked cart/checkout), say so up front
   instead of letting the report look complete. Driven by
   comparison.dataQuality.status (ok | partial | insufficient). */
function ReadQualityBanner({ quality }) {
  const status = quality?.status;
  if (!status || status === 'ok') return null;
  const warnings = arr(quality.warnings).slice(0, 4);
  const insufficient = status === 'insufficient';
  return (
    <div
      role="status"
      className={`mb-5 rounded-2xl border p-4 text-sm ${insufficient
        ? 'border-[rgba(255,107,107,0.35)] bg-[rgba(255,107,107,0.08)]'
        : 'border-[rgba(254,211,48,0.45)] bg-[rgba(254,211,48,0.12)]'}`}
    >
      <p className="font-semibold text-(--text)">
        {insufficient
          ? "We couldn't fully read one of these stores — treat this report as incomplete."
          : 'Part of this comparison is based on incomplete data.'}
      </p>
      {warnings.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-(--text-light)">
          {warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}
    </div>
  );
}

/* Map finding/insight types to a tab so tab badges can show where the
   high-severity items live. */
function tabForType(type = '') {
  const t = String(type).toLowerCase();
  if (/(price|pricing|plan|discount|sale)/.test(t)) return 'pricing';
  if (/(catalog|product|assortment|collection|category|inventory|stock|variant)/.test(t)) return 'catalog';
  if (/(seo|meta|h1|canonical|trust|conversion|newsletter|homepage|position|messag|signal|brand)/.test(t)) return 'brand';
  return 'overview';
}

function readTabFromUrl() {
  try { return new URLSearchParams(window.location.search).get('tab'); } catch { return null; }
}
function writeTabToUrl(tab) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.replaceState(null, '', url.toString());
  } catch { /* non-browser environment */ }
}

const SEV_HIGH = ['critical', 'urgent', 'high', 'p0', 'p1'];

export default function AnalysisPage(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const domains = getDomains(ai, comparison, aiPayload);
  const businessType = inferBusinessType(comparison, aiPayload);
  const currency = getCurrency(ai, comparison, aiPayload);
  const warnings = getWarnings(ai, comparison, aiPayload);
  const generatedAt = getGeneratedAt(ai, comparison, aiPayload);
  const sites = getSites(ai, comparison, aiPayload);

  const priceRows = getPriceRows(ai, comparison, aiPayload);
  const catalogRows = getCatalogRows(ai, comparison, aiPayload);
  const inventoryRows = getInventoryRows(ai, comparison, aiPayload);
  const seoRows = getSeoRows(ai, comparison, aiPayload);
  const trustRows = getTrustRows(ai, comparison, aiPayload);
  const homepageRows = getHomepageRows(ai, comparison, aiPayload);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const marketRows = getMarketRows(ai, comparison, aiPayload);
  const gaps = getPotentialGaps(ai, comparison, aiPayload);
  const insights = getRankedInsights(ai, comparison, aiPayload);
  const recommendations = getRecommendations(ai, comparison, aiPayload);
  const cards = getDashboardCards(ai, comparison, aiPayload);
  const contentDepthRows = getContentDepthRows(ai, comparison, aiPayload);
  const saleRows = getSaleDiscountRows(ai, comparison, aiPayload);
  const navigation = getNavigation(ai, comparison, aiPayload);

  const scoreData = useMemo(() => buildCompetitiveScores({
    catalogRows, inventoryRows, priceRows, seoRows, trustRows,
    collectionRows: toCollectionChartRows(matchups),
    contentDepthRows, saleRows, navigation,
  }), [catalogRows, inventoryRows, priceRows, seoRows, trustRows, matchups, contentDepthRows, saleRows, navigation]);
  const userScore = weightedScore(scoreData.user, businessType, scoreData.activeMask);
  const competitorScore = weightedScore(scoreData.competitor, businessType, scoreData.activeMask);

  // High-severity counts per tab, for badges.
  const severityByTab = useMemo(() => {
    const out = {};
    [...insights, ...cards].forEach((x) => {
      const sev = String(x.severity || x.workspacePriority || '').toLowerCase();
      if (!SEV_HIGH.includes(sev)) return;
      const tab = tabForType(x.type || x.title || x.finding);
      out[tab] = (out[tab] || 0) + 1;
    });
    return out;
  }, [insights, cards]);

  // IntelShift is e-commerce only — assortment is always the catalog framing.
  const catalogLabel = 'Assortment';

  // What did the user choose to analyze? Analysis emphasis follows that
  // choice: product pages analyzed → product matchups lead; collections
  // analyzed → collection matchups lead. Homepage-only → positioning focus.
  const pageTypeMix = sites.reduce((acc, s) => {
    Object.entries(s.pageTypesAnalyzed || {}).forEach(([t, n]) => { acc[t] = (acc[t] || 0) + Number(n || 0); });
    return acc;
  }, {});
  const productFocused = (pageTypeMix.product || 0) > 0 && (pageTypeMix.collection || 0) === 0;

  const tabs = useMemo(() => [
    { key: 'overview', label: 'Overview', show: true,
      render: (p) => <><Summary {...p} /><AnalysisIdentity {...p} /><ProductDepth {...p} /><Merchandising {...p} /><Navigation {...p} /></> },
    { key: 'pricing', label: 'Pricing', show: priceRows.length > 0 || matchups.some((m) => arr(m.topProductMatches).length),
      render: (p) => <><PriceAnalysis {...p} /><TopProducts {...p} /></> },
    { key: 'catalog', label: catalogLabel,
      show: matchups.length > 0 || gaps.length > 0 || marketRows.length > 0 || catalogRows.length > 0 || inventoryRows.length > 0,
      render: (p) => productFocused
        ? <><ProductComparison {...p} /><SuggestedMatches {...p} /><CollectionData {...p} /></>
        : <><CollectionData {...p} /><ProductComparison {...p} /><SuggestedMatches {...p} /></> },
    { key: 'brand', label: 'Brand & Trust', show: matchups.length > 0 || homepageRows.length > 0 || seoRows.length > 0 || trustRows.length > 0,
      render: (p) => <><Positioning {...p} /><TrustSignals {...p} /><ShippingPayment {...p} /><SeoAnalysis {...p} /></> },
    { key: 'actions', label: 'Actions', show: recommendations.length > 0 || insights.length > 0,
      count: recommendations.length || null,
      render: (p) => <><KeyInsights {...p} /><Recommendation {...p} /></> },
    { key: 'history', label: 'History', show: !!props.competitorId,
      render: (p) => <CompetitorHistory competitorId={p.competitorId} /> },
  ].filter((t) => t.show), [catalogLabel, productFocused, priceRows.length, matchups, gaps.length, marketRows.length, catalogRows.length, inventoryRows.length, seoRows.length, trustRows.length, homepageRows.length, recommendations.length, insights.length, props.competitorId]);

  const [active, setActive] = useState(() => {
    const fromUrl = readTabFromUrl();
    return tabs.some((t) => t.key === fromUrl) ? fromUrl : tabs[0]?.key || 'overview';
  });
  useEffect(() => {
    if (!tabs.some((t) => t.key === active) && tabs.length) setActive(tabs[0].key);
  }, [tabs, active]);
  const selectTab = useCallback((key) => { setActive(key); writeTabToUrl(key); }, []);

  // Publish these tabs to the global Header (contextual top-bar menu).
  const setNav = usePageNav((s) => s.setNav);
  const clearNav = usePageNav((s) => s.clearNav);
  const navItems = useMemo(
    () => tabs.map((t) => ({ key: t.key, label: t.label, count: t.count || null, dot: (severityByTab[t.key] || 0) > 0 })),
    [tabs, severityByTab]
  );
  useEffect(() => {
    setNav({ items: navItems, activeKey: active }, selectTab);
  }, [navItems, active, setNav, selectTab]);
  useEffect(() => () => clearNav(), [clearNav]);

  const [showQuality, setShowQuality] = useState(false);
  const activeTab = tabs.find((t) => t.key === active) || tabs[0];
  const overall = ai?.executiveSummary?.overallFinding;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      {/* ─── Page header ─── */}
      <div className="mb-6 overflow-hidden rounded-3xl bg-(--primary) p-6 text-white sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[rgba(78,205,196,0.3)] bg-[rgba(78,205,196,0.12)] px-3 py-1 text-[11px] font-bold uppercase tracking-[0.08em] text-(--secondary)">
              {titleCase(businessType)} analysis
              {generatedAt && <span className="font-medium normal-case tracking-normal text-white/50">· {String(generatedAt).slice(0, 10)}</span>}
            </div>
            <h1 className="text-2xl font-extrabold tracking-[-0.02em] sm:text-3xl">
              {domains.user || 'Your site'}
              <em className="mx-2 font-['Fraunces',Georgia,serif] font-light italic text-(--secondary)">vs</em>
              {domains.competitor || 'Competitor'}
            </h1>
            {active === 'overview' && overall && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/65">{firstSentences(overall, 320)}</p>}
          </div>
          {active === 'overview' && (
            <div>
              <div className="flex gap-3">
                <HeaderScore label={domains.user || 'You'} score={userScore} tone="teal" />
                <HeaderScore label={domains.competitor || 'Competitor'} score={competitorScore} tone="coral" />
              </div>
              <p
                className="mt-2 max-w-[240px] text-left text-[10px] leading-snug text-white/40"
                title="Composite of up to nine dimensions — catalog depth, price accessibility, stock health, SEO, trust signals, collection breadth, product content depth, promotions and navigation breadth — weighted for this business type. Dimensions with no data for either store are dropped. Scores compare the two stores against each other on the analyzed pages; they are not absolute grades. The radar in Overview shows the dimension-by-dimension breakdown."
              >
                Competitive score / 100 — the two stores measured against each other. See the radar in Overview for the breakdown.
              </p>
            </div>
          )}
        </div>
        {(warnings.length > 0 || sites.length > 0) && (
          <div className="mt-5 border-t border-white/10 pt-4">
            <button type="button" onClick={() => setShowQuality((v) => !v)} className="text-xs font-semibold text-white/60 hover:text-white">
              Data quality & scope {warnings.length ? `· ${warnings.length} warning${warnings.length > 1 ? 's' : ''}` : ''} {showQuality ? '▴' : '▾'}
            </button>
            {showQuality && (
              <div className="mt-3 space-y-2.5 text-xs text-white/70">
                {sites.map((s, i) => {
                  const plat = s.displayPlatform || (s.platform && String(s.platform).toLowerCase() !== 'unknown' ? s.platform : 'Custom / Undetected');
                  // The homepage always anchors the analysis but isn't a "tracked page",
                  // so report it separately: "N pages + homepage", not N+1.
                  const total = typeof s.pagesAnalyzedCount === 'number' ? s.pagesAnalyzedCount : null;
                  const chip = "inline-flex items-center rounded-full bg-white/10 px-2 py-0.5 text-[11px] font-medium text-white/70";
                  return (
                    <div key={i} className="flex flex-wrap items-center gap-1.5">
                      <span className="mr-0.5 text-[11px] font-semibold text-white/85">{s.domain}</span>
                      <span className={chip}>{total == null ? '—' : Math.max(0, total - 1)} pages</span>
                      {total != null && <span className={chip}>+ homepage</span>}
                      {s.uniqueProducts ? <span className={chip}>{s.uniqueProducts} products</span> : null}
                      {s.collectionCount ? <span className={chip}>{s.collectionCount} collections</span> : null}
                      {plat ? <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold text-(--secondary)" style={{ background: 'color-mix(in srgb, var(--secondary) 16%, transparent)' }}>{plat}</span> : null}
                    </div>
                  );
                })}
                {warnings.map((w, i) => <p key={`w${i}`} className="text-(--warning)">⚠ {w}</p>)}
              </div>
            )}
          </div>
        )}
      </div>

      <ReadQualityBanner quality={comparison?.dataQuality} />

      {/* Tab bar now lives in the global Header (contextual top-bar menu). */}

      {/* ─── Active tab content (lazy: only the active tab renders) ─── */}
      <div className="space-y-5">
        <TabErrorBoundary tabKey={activeTab?.key}>
          {activeTab ? activeTab.render({ ...props, currency }) : null}
        </TabErrorBoundary>
      </div>

      {/* Bridge to monitoring — the recurring-value loop. Renders only when
          the app provides a handler or URL, so it's safe to ship unwired. */}
      {(props.onTrackCompetitor || props.trackCompetitorUrl) && (
        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-(--primary) p-6 text-white">
          <div>
            <p className="font-bold">Keep watching {domains.competitor || 'this competitor'}</p>
            <p className="mt-1 text-sm text-white/60">Get alerted when their prices, products or messaging change — this analysis is a snapshot in time.</p>
          </div>
          {props.trackCompetitorUrl
            ? <a href={props.trackCompetitorUrl} className="rounded-xl bg-(--accent) px-5 py-2.5 text-sm font-bold text-white transition hover:bg-(--accent-dark)">Set up monitoring</a>
            : <button type="button" onClick={props.onTrackCompetitor} className="rounded-xl bg-(--accent) px-5 py-2.5 text-sm font-bold text-white transition hover:bg-(--accent-dark)">Set up monitoring</button>}
        </div>
      )}

      <p className="mt-8 text-center text-xs text-(--text-light)">
        IntelShift AI and can make mistakes. Findings reflect only the analyzed pages — verify important details on the live sites.
      </p>
    </div>
  );
}

function HeaderScore({ label, score, tone }) {
  const color = tone === 'teal' ? 'text-(--secondary)' : 'text-(--accent)';
  const ring = tone === 'teal' ? 'border-[rgba(78,205,196,0.35)]' : 'border-[rgba(255,107,107,0.35)]';
  return (
    <div className={`min-w-[110px] rounded-2xl border ${ring} bg-white/[0.04] px-4 py-3 text-center`}>
      <p className={`text-3xl font-extrabold ${color}`}>{score || '—'}</p>
      <p className="mt-1 max-w-[130px] truncate text-[11px] font-semibold uppercase tracking-wide text-white/55" title={label}>{label}</p>
    </div>
  );
}
