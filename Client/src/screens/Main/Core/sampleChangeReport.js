/* Sample fixture matching the Python change_detection_app (detector.py) output
   schema. Used only for previewing ChangeDetails during development — the page
   shows a "Sample data" badge when rendering this. Replace with a real report
   via the `changeReport` prop. */

export const sampleChangeReport = {
  schemaVersion: 'change_detection_v1',
  generatedAt: '2026-07-06T09:00:00Z',
  domain: 'competitor-store.com',
  previousGeneratedAt: '2026-06-29T09:00:00Z',
  currentGeneratedAt: '2026-07-06T09:00:00Z',
  overallSeverity: 'high',
  changeScore: 72,
  shouldSendToAI: true,
  extractionStable: true,
  warnings: [],
  summary: {
    totalChanges: 9,
    criticalChanges: 1,
    highChanges: 4,
    mediumChanges: 3,
    lowChanges: 1,
    changesByType: {
      price_change: 2, new_product: 2, sale_started: 1, out_of_stock: 1,
      plan_price_change: 1, navigation_change: 1, rank_change: 1,
    },
  },
  changes: [
    {
      type: 'plan_price_change', severity: 'critical',
      whyImportant: 'A pricing plan price changed - direct monetization move.',
      plan: { name: 'Pro' }, oldValue: 29, newValue: 39, changePercent: 34.48,
    },
    {
      type: 'price_change', severity: 'high',
      whyImportant: 'Price moved beyond the configured threshold.',
      product: { name: 'Velvet Matte Lipstick — Ruby', productUrl: 'https://competitor-store.com/products/velvet-matte-ruby', category: 'lipstick' },
      oldValue: 2450, newValue: 1950, changePercent: -20.41, direction: 'decrease',
    },
    {
      type: 'price_change', severity: 'medium',
      whyImportant: 'Price moved beyond the configured threshold.',
      product: { name: 'Hydra Silk Foundation 30ml', productUrl: 'https://competitor-store.com/products/hydra-silk-foundation', category: 'foundation' },
      oldValue: 3200, newValue: 3550, changePercent: 10.94, direction: 'increase',
    },
    {
      type: 'sale_started', severity: 'high',
      whyImportant: 'Promotion state changed - a direct competitive pricing move.',
      product: { name: 'Lash Amplify Mascara', productUrl: 'https://competitor-store.com/products/lash-amplify', category: 'mascara' },
      discountPercent: 25,
    },
    {
      type: 'new_product', severity: 'high',
      whyImportant: 'New product detected since the previous snapshot.',
      product: { name: 'Glow Serum Blush — 4 shades', productUrl: 'https://competitor-store.com/products/glow-serum-blush', category: 'blush' },
    },
    {
      type: 'new_product', severity: 'high',
      whyImportant: 'New product detected since the previous snapshot.',
      product: { name: 'Barrier Repair Night Cream', productUrl: 'https://competitor-store.com/products/barrier-repair', category: 'skincare' },
    },
    {
      type: 'out_of_stock', severity: 'medium',
      whyImportant: 'Stock availability changed.',
      product: { name: 'Velvet Matte Lipstick — Nude 02', productUrl: 'https://competitor-store.com/products/velvet-matte-nude02', category: 'lipstick' },
      oldValue: true, newValue: false,
    },
    {
      type: 'navigation_change', severity: 'medium',
      whyImportant: 'Main navigation changed - new categories or repositioned priorities.',
      addedLabels: ['Skincare', 'Gift Sets'], removedLabels: ['Clearance'],
    },
    {
      type: 'rank_change', severity: 'low',
      whyImportant: 'Listing position changed significantly - merchandising signal.',
      product: { name: 'Hydra Silk Foundation 30ml', productUrl: 'https://competitor-store.com/products/hydra-silk-foundation', category: 'foundation' },
      oldRank: 14, newRank: 3, positionsMoved: 11,
    },
  ],
  changesTruncated: false,
  aiPromptHint: 'These are deterministic week-over-week changes for one site.',
};

export const sampleAiInterpretation = {
  strategicIntent:
    'The competitor is pairing a SaaS-style plan increase with aggressive retail promotion: raising recurring revenue on the Pro plan while cutting hero-product prices and launching into skincare. This looks like a margin re-balance — monetize loyal plan subscribers, win new customers on visible price points, and expand into a higher-LTV category.',
  impactScore: 8,
  whyThisMatters: [
    { title: 'Entry-price pressure', detail: 'Their flagship lipstick is now 20% cheaper and on the top of the collection page. If it is a traffic driver for you too, expect comparison shopping within days.' },
    { title: 'Category expansion', detail: 'Two skincare launches plus a new "Skincare" nav item signal a deliberate move into a category you currently own. Early — but consistent.' },
    { title: 'Monetization confidence', detail: 'A 34% Pro plan increase suggests strong retention. They believe their customers will absorb it; that is useful pricing intelligence for your own plans.' },
  ],
  recommendedActions: [
    { priority: 'high', title: 'Price-check your matching lipstick SKUs', detail: 'Compare your equivalents against the new 1,950 price point and decide: match, bundle, or reposition on quality.' },
    { priority: 'high', title: 'Monitor the skincare rollout weekly', detail: 'Track whether more SKUs appear in the new Skincare category — two products is a test, ten is a strategy.' },
    { priority: 'medium', title: 'Review your own plan pricing headroom', detail: 'Their 34% increase gives you cover for a smaller, well-communicated adjustment if your retention metrics support it.' },
  ],
};
