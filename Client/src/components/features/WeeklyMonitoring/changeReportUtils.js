/* ─────────────────────────────────────────────────────────────
   Shared helpers for the same-site change-detection reports produced by the
   Python change_detection_app (schema: change_detection_v1, detector.py).

   Both the weekly Dashboard (rollup across competitors) and ChangeDetails
   (single competitor drill-down) read this shape:

     { schemaVersion, domain, previousGeneratedAt, currentGeneratedAt,
       overallSeverity, changeScore, shouldSendToAI, extractionStable,
       warnings[], summary:{ totalChanges, criticalChanges, highChanges,
       mediumChanges, lowChanges, changesByType{} }, changes[] }

   Keeping the headline/severity/format logic here means the Dashboard cards
   and the ChangeDetails rows always describe the same change identically.
──────────────────────────────────────────────────────────────── */

export const arr = (v) => (Array.isArray(v) ? v : []);
export const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);

export const SEV_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };
export const SEV_SCORE = { critical: 100, high: 70, medium: 35, low: 10 };

/* Tailwind classes keyed to the app's CSS variables (same palette
   ChangeDetails already uses). */
export const sevPillClass = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return 'bg-(--primary) text-white border-(--primary)';
  if (s === 'high') return 'bg-[rgba(255,107,107,0.10)] text-(--accent) border-[rgba(255,107,107,0.25)]';
  if (s === 'medium') return 'bg-[rgba(254,211,48,0.16)] text-(--warning-dark) border-[rgba(254,211,48,0.4)]';
  return 'bg-(--bg) text-(--text-light) border-(--border)';
};

export const sevTextClass = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return 'text-(--primary)';
  if (s === 'high') return 'text-(--accent)';
  if (s === 'medium') return 'text-(--warning-dark)';
  return 'text-(--text-light)';
};

export const titleCase = (s = '') =>
  String(s).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

export const fmtDate = (iso) => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return String(iso).slice(0, 10);
  }
};

/* "3 days ago" style relative label from an ISO date. */
export const relativeDate = (iso) => {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const days = Math.round((Date.now() - t) / 86400000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days} days ago`;
  if (days < 14) return 'last week';
  return `${Math.round(days / 7)} weeks ago`;
};

/* One-line, human headline for a change. Mirrors ChangeDetails.changeHeadline
   so a change reads the same in the rollup and the detail view. */
const HOMEPAGE_FEATURE_LABELS = {
  hasNewsletter: 'Newsletter capture',
  hasVideo: 'Video content',
  hasDiscountMessaging: 'Discount messaging',
  hasTrustSignals: 'Trust signals',
  hasHero: 'Hero banner',
  hasAnnouncementBar: 'Announcement bar',
  hasTestimonials: 'Testimonials',
  hasBlogPreview: 'Blog / content',
  hasInstagramFeed: 'Instagram feed',
  hasWhatsapp: 'WhatsApp',
  hasCollectionBanners: 'Collection banners',
  hasFeaturedProducts: 'Featured products',
  hasFeaturedCollections: 'Featured collections',
};

export function changeHeadline(c = {}) {
  const name = c.product?.name || c.plan?.name;
  switch (c.type) {
    case 'price_change':
      return `${name}: price ${c.direction === 'decrease' ? 'dropped' : 'increased'} ${Math.abs(num(c.changePercent) ?? 0)}%`;
    case 'plan_price_change':
      return `Plan "${name}": price changed ${num(c.changePercent) !== null ? `${c.changePercent > 0 ? '+' : ''}${c.changePercent}%` : ''}`;
    case 'pricing_plan_added':
      return `New pricing plan: "${name}"${c.plan?.priceRaw ? ` at ${c.plan.priceRaw}` : ''}`;
    case 'pricing_plan_removed':
      return `Pricing plan removed: "${name}"`;
    case 'sale_started':
      return `${name}: promotion started${num(c.discountPercent) !== null ? ` (${c.discountPercent}% off)` : ''}`;
    case 'sale_ended':
      return `${name}: promotion ended`;
    case 'new_product':
      return `New product: ${name}`;
    case 'product_removed':
    case 'removed_product':
      return `Product removed: ${name}`;
    case 'out_of_stock':
      return `${name}: went out of stock`;
    case 'back_in_stock':
      return `${name}: back in stock`;
    case 'rank_change':
      return `${name}: moved ${Math.abs(num(c.positionsMoved) ?? 0)} positions ${num(c.positionsMoved) > 0 ? 'up' : 'down'} (${c.oldRank} -> ${c.newRank})`;
    case 'name_change':
      return 'Product renamed';
    case 'variant_count_change':
      return `${name}: variants ${c.oldValue} -> ${c.newValue}`;
    case 'navigation_change':
      return 'Main navigation changed';
    case 'categories_added':
      return `New categories: ${arr(c.categories).join(', ')}`;
    case 'categories_removed':
      return `Categories removed: ${arr(c.categories).join(', ')}`;
    case 'collection_size_change':
      return `${c.collection?.name || 'Collection'}: ${c.oldValue} -> ${c.newValue} products`;
    case 'hero_message_change':
      return 'Homepage hero message changed';
    case 'homepage_feature_toggled': {
      const label = c.featureLabel || HOMEPAGE_FEATURE_LABELS[c.feature]
        || titleCase(String(c.feature || '').replace(/^has/, ''));
      return `${label} ${c.newValue ? 'added' : 'removed'}`;
    }
    default:
      return `${titleCase(c.type)}${name ? `: ${name}` : ''}`;
  }
}

/* ── Scheduling display helpers ──────────────────────────────────────────
   IMPORTANT: React never decides the cadence. The package -> cadence mapping
   (trial = none, starter = weekly, growth = 2/week, pro = 3/week) lives in
   the backend. These helpers only format what the backend sends. */

export const fmtDateTime = (iso) => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  } catch { return String(iso); }
};

/* Human "in 3 days" / "tomorrow" / "today" for a future ISO date. */
export const relativeFuture = (iso) => {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const days = Math.ceil((t - Date.now()) / 86400000);
  if (days <= 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days < 7) return `in ${days} days`;
  return `on ${fmtDate(iso)}`;
};

/* Turn a numeric cadence (runs-per-week, from the backend/package) into a
   human label. We phrase it as a day interval ("every 2 days") rather than a
   fractional frequency ("3.5 times a week"), which reads like a bug and doesn't
   match how the plans are described. */
export const cadenceLabel = (perWeek) => {
  const n = num(perWeek);
  if (!n || n <= 0) return 'periodic';
  const days = Math.round(7 / n);
  if (days <= 1) return 'daily';
  if (days === 7) return 'weekly';
  if (days >= 28) return 'monthly';
  return `every ${days} days`;
};

export const totalChangesOf = (reports = []) =>
  arr(reports).reduce((sum, r) => sum + ((r.summary || {}).totalChanges ?? arr(r.changes).length), 0);

/* Resolve which UI state to render, from data alone:
     'disabled'    monitoring not part of this plan (e.g. free trial)
     'never_run'   plan includes monitoring but no comparison has run yet
     'no_changes'  a run happened, nothing meaningful changed
     'has_changes' there are changes to show
   `lastMonitoredAt` is the discriminator between "not run yet" and
   "ran, nothing changed". */
export function monitoringState({ monitoringEnabled = true, reports = null, lastMonitoredAt = null } = {}) {
  if (!monitoringEnabled) return 'disabled';
  const ran = !!lastMonitoredAt || arr(reports).length > 0;
  if (!ran) return 'never_run';
  return totalChangesOf(reports) > 0 ? 'has_changes' : 'no_changes';
}

/* Roll a set of per-competitor reports into one weekly view:
   aggregate severity counts + the highest-impact individual changes. */
export function buildRollup(reports = []) {
  const list = arr(reports).filter(Boolean);
  const totals = { critical: 0, high: 0, medium: 0, low: 0, total: 0 };
  const flat = [];

  list.forEach((r) => {
    const s = r.summary || {};
    totals.critical += num(s.criticalChanges) ?? 0;
    totals.high += num(s.highChanges) ?? 0;
    totals.medium += num(s.mediumChanges) ?? 0;
    totals.low += num(s.lowChanges) ?? 0;
    totals.total += num(s.totalChanges) ?? arr(r.changes).length;
    arr(r.changes).forEach((c) => flat.push({ ...c, _domain: r.domain, _date: r.currentGeneratedAt }));
  });

  flat.sort((a, b) => {
    const sev = (SEV_ORDER[b.severity] || 0) - (SEV_ORDER[a.severity] || 0);
    if (sev) return sev;
    return Math.abs(num(b.changePercent) ?? 0) - Math.abs(num(a.changePercent) ?? 0);
  });

  const sites = list
    .map((r) => ({
      domain: r.domain,
      severity: r.overallSeverity,
      score: num(r.changeScore) ?? 0,
      total: (r.summary || {}).totalChanges ?? arr(r.changes).length,
      shouldSendToAI: !!r.shouldSendToAI,
      extractionStable: r.extractionStable !== false,
    }))
    .sort((a, b) => b.score - a.score);

  return { totals, topChanges: flat, sites, count: list.length };
}
