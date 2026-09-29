import React from 'react';
import { pickSource, Card, Pill, SimpleTable, DomainTag, getMatchups, getHomepageRows, getDomains, titleCase, arr } from './_helpers';

/* Positioning tab:
   1. Homepage highlights — what each side pushes on their homepage
      (homepage-scoped data lives HERE, never mixed into product stats)
   2. Messaging signals from matched products (chips only — the frequency
      chart added nothing at real data volumes) */

// Map a raw homepage section type (Shopify/theme slug) to a human label.
const SECTION_LABELS = [
  [/hero|slideshow|slide-?show|image-?banner|banner|cover/i, 'Hero banner'],
  [/announcement|marquee|ticker/i, 'Announcement bar'],
  [/collection-?list|featured-?collection|collections/i, 'Featured collections'],
  [/featured-?product|product-?recommend|product-?grid|products/i, 'Featured products'],
  [/rich-?text|text|story/i, 'Text / story'],
  [/image-?with-?text|image-text/i, 'Image + text'],
  [/multicolumn|multi-?column|columns|icons?/i, 'Feature columns'],
  [/video/i, 'Video'],
  [/testimonial|review|rating/i, 'Testimonials / reviews'],
  [/newsletter|email|subscribe/i, 'Newsletter signup'],
  [/blog|article|news/i, 'Blog / content'],
  [/instagram|ugc|social/i, 'Social feed'],
  [/logo|brand|press|trust|guarantee|shipping|badge/i, 'Trust / logos'],
  [/faq|accordion/i, 'FAQ'],
  [/countdown|timer/i, 'Countdown timer'],
  [/footer/i, 'Footer'],
];
const sectionLabel = (type) => {
  const t = String(type || '');
  for (const [re, label] of SECTION_LABELS) if (re.test(t)) return label;
  return titleCase(t.replace(/[-_]+/g, ' ')) || 'Section';
};
const snip = (s, n = 130) => { const t = String(s || '').replace(/\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t; };

function HomepageColumn({ row, who, user }) {
  const secs = arr(row?.topSections);
  return (
    <div className="rounded-xl border border-(--border) p-3">
      <p className="mb-2"><DomainTag user={user}>{who}</DomainTag></p>
      {secs.length ? (
        <ol className="space-y-1.5">
          {secs.map((s, i) => {
            const text = snip(s.heading || s.label || s.title || s.textPreview);
            return (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-(--bg) text-[11px] font-bold text-(--text-light)">{i + 1}</span>
                <span className="min-w-0">
                  <span className="font-semibold text-(--text)">{sectionLabel(s.type)}</span>
                  {s.importanceLevel === 'high' ? <span className="ml-1 align-middle text-[10px] font-bold uppercase text-(--accent)">key</span> : null}
                  {text ? <span className="text-(--text-light)"> — {text}</span> : null}
                </span>
              </li>
            );
          })}
        </ol>
      ) : <p className="text-sm text-(--text-light)">No homepage sections captured.</p>}
    </div>
  );
}

function HomepageHighlights({ rows, domains }) {
  const useful = arr(rows);
  const userRow = useful.find((r) => r.domain === domains.user);
  const compRow = useful.find((r) => r.domain === domains.competitor) || useful.find((r) => r.domain !== domains.user);
  const anySections = arr(userRow?.topSections).length || arr(compRow?.topSections).length;
  if (!anySections) return null;

  return (
    <Card
      title="Homepage walkthrough"
      subtitle="What each store actually presents on its homepage, top to bottom — the sections in order and what each one is. Homepage merchandising only; these products are excluded from price and catalog stats."
    >
      <div className="grid gap-3 md:grid-cols-2">
        <HomepageColumn row={userRow} who={domains.user || 'You'} user />
        <HomepageColumn row={compRow} who={domains.competitor || 'Competitor'} />
      </div>
    </Card>
  );
}

export default function Positioning(props) {
  const { ai, comparison, aiPayload } = pickSource(props);
  const matchups = getMatchups(ai, comparison, aiPayload);
  const domains = getDomains(ai, comparison, aiPayload);
  const homepageRows = getHomepageRows(ai, comparison, aiPayload);
  const signals = matchups.flatMap(m => arr(m.topProductMatches).map(x => ({ category:m.category, signals:x.positioningComparisonSignals }))).filter(x => x.signals);
  const shared = [...new Set(signals.flatMap(x => arr(x.signals.sharedSignals)))];
  const userOnly = [...new Set(signals.flatMap(x => arr(x.signals.userOnlySignals)))];
  const compOnly = [...new Set(signals.flatMap(x => arr(x.signals.competitorOnlySignals)))];
  const hasSignals = shared.length || userOnly.length || compOnly.length;
  const hasHomepage = arr(homepageRows).length > 0;
  if (!hasSignals && !hasHomepage) return null;

  return <div className="space-y-5">
    {hasHomepage ? <HomepageHighlights rows={homepageRows} domains={domains} /> : null}

    {hasSignals ? <Card title="Messaging signals" subtitle="Positioning attributes observed on matched products.">
      <div className="grid gap-4 md:grid-cols-3">
        <SignalBox title="Shared" items={shared}/>
        <SignalBox title="Only you use" items={userOnly}/>
        <SignalBox title="Only they use" items={compOnly}/>
      </div>
    </Card> : null}
  </div>;
}
function SignalBox({title,items}){ return <div className="rounded-xl border border-(--border) p-4"><p className="mb-3 font-semibold text-(--primary)">{title}</p><div className="flex flex-wrap gap-2">{items.length ? items.slice(0,18).map(x=><Pill key={x} tone="low">{titleCase(x)}</Pill>) : <span className="text-sm text-(--text-light)">None detected</span>}</div></div> }
