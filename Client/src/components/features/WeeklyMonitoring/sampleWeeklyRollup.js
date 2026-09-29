/* Sample weekly-rollup fixture for previewing the Dashboard without a backend.
   Shape = an array of change_detection_v1 reports (one per monitored
   competitor) plus an optional AI-interpretation map keyed by domain.

   These two reports are the REAL output of the Python change_detection_app
   (detector.py) run over week-1 vs week-2 snapshots of gabrini.pk and
   in2it.com.pk — see ./fixtures. Replace `sampleReports` with live reports
   via the Dashboard `reports` prop. */

import gabriniChanges from './fixtures/gabrini_changes.json';
import in2itChanges from './fixtures/in2it_changes.json';

export const sampleReports = [gabriniChanges, in2itChanges];

/* Optional AI interpretation (schema mirrors ChangeDetails aiInterpretation /
   the Python openai insights output). Keyed by domain so the Dashboard can
   surface strategic actions and the ChangeDetails page can show its AI block.
   Illustrative content for the high-severity gabrini week. */
export const sampleAiByDomain = {
  'gabrini.pk': {
    strategicIntent:
      'Gabrini is running a promo-led acquisition week: cutting price on a hero haircare SKU, launching a 30% BB-powder promotion and pushing a primer to the top of the collection, while quietly raising entry-price brow SKUs and expanding into fragrance and gift sets.',
    impactScore: 7,
    whyThisMatters: [
      { title: 'Entry-price creep', detail: 'Eye Brow Pencil is up 25%. If brow is a traffic driver for you, their raise gives you room to hold or undercut.' },
      { title: 'Category expansion', detail: 'New "Fragrance" and "Gift Sets" nav plus categories signal a deliberate move beyond colour cosmetics ahead of gifting season.' },
      { title: 'Merchandising push', detail: 'Photo Finish Primer jumped 11 positions to #1 — they are actively steering traffic to it. Worth watching whether it goes on promo next.' },
    ],
    recommendedActions: [
      { priority: 'high', title: 'Price-check your primer + BB range', detail: 'Compare against the promoted Gabrini SKUs before the weekend traffic peak.' },
      { priority: 'medium', title: 'Watch the fragrance/gift-set rollout', detail: 'Two nav items is a test. Re-check next week to see if SKUs follow.' },
      { priority: 'medium', title: 'Hold brow pricing', detail: 'Their 25% raise gives you cover to keep yours steady and win on value messaging.' },
    ],
  },
};
