# AnalysisSections advanced visuals v6

Updates in this version:

- Product tables are now grouped into one Product Match Explorer with tabs:
  - Matched products
  - Competitor-only products
  - User-only products
- Large product datasets are collapsed by default with “View all” controls.
- Priority product cards are limited and expandable, so they no longer repeat the full table.
- Opportunity Matrix now uses larger severity-based bubbles, quadrant labels and better visual hierarchy.
- Product Opportunity Quadrant now uses availability/price-band bubbles with stronger visual cues.
- Key Insights no longer repeats Recommended Actions.
- Existing charts remain inside their related sections instead of a separate chart block.

Install if missing:

```bash
npm install chart.js
```

Suggested rendering order:

1. AnalysisIdentity
2. Summary
3. CollectionData
4. KeyInsights
5. Positioning
6. PriceAnalysis
7. QuantitativeSignals
8. TopProducts
9. ProductComparison
10. TrustSignals
11. Recommendation
12. SeoAnalysis
13. SwotAnalysis

`VisualAnalysis` intentionally returns null to avoid duplicate standalone charts.
