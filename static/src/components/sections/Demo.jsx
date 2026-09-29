import { useState } from 'react';
import logo from '../../assets/logo.png';

const DEMO_TABS = [
  { key: 'overview',    label: 'Overview'           },
  { key: 'pricing',     label: 'Pricing',  dot: true },
  { key: 'catalog',     label: 'Catalog & Products', dot: true },
  { key: 'positioning', label: 'Positioning'        },
  { key: 'seo',         label: 'SEO & Trust'        },
  { key: 'actions',     label: 'Actions', badge: '5'},
];

function PriceBar({ label, value, pct, color }) {
  return (
    <div className="app-price-bar-wrap">
      <div className="app-price-bar-label"><span>{label}</span><span>{value}</span></div>
      <div className="app-price-bar-track">
        <div className="app-price-bar-fill" style={{ width: pct, background: color }} />
      </div>
    </div>
  );
}

function THead({ cols, labels }) {
  return (
    <div className="app-table-head" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {labels.map(l => <span key={l}>{l}</span>)}
    </div>
  );
}

function TRow({ cols, values, hi }) {
  return (
    <div className="app-table-row" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {values.map((v, i) => <span key={i} style={hi?.[i] || {}}>{v}</span>)}
    </div>
  );
}

const PANELS = {
  overview: (
    <>
      <div className="app-section-title">Sites &amp; collections analyzed</div>
      <div className="app-section-sub">Snapshot scope for this competitive run.</div>
      <THead cols={4} labels={['User', 'Competitor', 'Pages', 'Type']} />
      <TRow cols={4} values={[
        <span className="user-pill">yourbrand.com</span>,
        <span className="comp-pill">competitor.com</span>,
        '14 pages', 'Full scan'
      ]} hi={{ 2: { color: '#2d3436', fontWeight: 600 }, 3: { color: '#2d3436', fontWeight: 600 } }} />
      <div className="app-verdict risk" style={{ marginTop: 10 }}>
        <strong style={{ color: '#ff6b6b' }}>Key finding:</strong> Competitor leads on assortment depth, SEO coverage, and price competitiveness. 5 high-priority actions identified.
      </div>
    </>
  ),

  pricing: (
    <>
      <div className="app-section-title">Price positioning</div>
      <div className="app-section-sub">Average price comparison across analyzed pages.</div>
      <PriceBar label="yourbrand.com" value="$74 avg" pct="58%" color="#4ecdc4" />
      <PriceBar label="competitor.com" value="$58 avg" pct="45%" color="#ff6b6b" />
      <div className="app-verdict risk">Your average price is 28% above competitor.com ($74 vs $58). Competitor is cheaper on 7 of 12 matched products.</div>
      <THead cols={3} labels={['Metric', 'Your brand', 'Competitor']} />
      <TRow cols={3} values={['Min price', '$12', '$9']}   hi={{ 0: { fontWeight: 600, color: '#2d3436' } }} />
      <TRow cols={3} values={['Avg price', '$74', '$58']}  hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 1: { color: '#ff6b6b', fontWeight: 700 }, 2: { color: '#20bf6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Max price', '$320', '$275']} hi={{ 0: { fontWeight: 600, color: '#2d3436' } }} />
      <TRow cols={3} values={['Priced items', '142', '198']} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 2: { color: '#ff6b6b', fontWeight: 700 } }} />
    </>
  ),

  catalog: (
    <>
      <div className="app-section-title">Catalog &amp; Products</div>
      <div className="app-section-sub">Assortment depth and category coverage.</div>
      <THead cols={3} labels={['Category', 'Your brand', 'Competitor']} />
      <TRow cols={3} values={['Total SKUs',    '142', '386']} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 2: { color: '#ff6b6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Categories',    '8',   '14' ]} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 2: { color: '#ff6b6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Skincare',      '24',  '91' ]} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 2: { color: '#ff6b6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Foundation',    '18',  '62' ]} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 2: { color: '#ff6b6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Lip & colour',  '44',  '38' ]} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 1: { color: '#4ecdc4', fontWeight: 700 } }} />
      <div className="app-verdict risk">Competitor has 2.7× more SKUs and 6 additional categories. Largest gap: Skincare (91 vs 24).</div>
    </>
  ),

  positioning: (
    <>
      <div className="app-section-title">Positioning signals</div>
      <div className="app-section-sub">Messaging attributes detected across matched products.</div>
      <div className="app-signal-group">
        <div className="app-signal-group-title">Shared keywords</div>
        <div className="app-pills">
          {['dermatologist tested','cruelty-free','long-lasting','hydrating formula','spf protection'].map(k => (
            <span key={k} className="app-pill shared">{k}</span>
          ))}
        </div>
      </div>
      <div className="app-signal-group">
        <div className="app-signal-group-title">Your brand only</div>
        <div className="app-pills">
          {['premium packaging','locally sourced','fragrance-free'].map(k => (
            <span key={k} className="app-pill user-kw">{k}</span>
          ))}
        </div>
      </div>
      <div className="app-signal-group">
        <div className="app-signal-group-title">Competitor only</div>
        <div className="app-pills">
          {['clinical results','best seller','bundle deals','free shipping','loyalty rewards','derma-tested'].map(k => (
            <span key={k} className="app-pill comp-kw">{k}</span>
          ))}
        </div>
      </div>
      <div className="app-verdict good">You lead on clean beauty messaging. Competitor uses 2× more trust &amp; urgency signals.</div>
    </>
  ),

  seo: (
    <>
      <div className="app-section-title">SEO &amp; Trust</div>
      <div className="app-section-sub">Meta, H1 and trust signal coverage across analyzed pages.</div>
      <div className="app-seo-grid">
        <div className="app-seo-card"><div className="app-seo-num risk">6</div><div className="app-seo-lbl">Your brand — missing meta</div></div>
        <div className="app-seo-card"><div className="app-seo-num good">1</div><div className="app-seo-lbl">Competitor — missing meta</div></div>
        <div className="app-seo-card"><div className="app-seo-num risk">4</div><div className="app-seo-lbl">Your brand — missing H1</div></div>
        <div className="app-seo-card"><div className="app-seo-num good">0</div><div className="app-seo-lbl">Competitor — missing H1</div></div>
      </div>
      <THead cols={3} labels={['Trust signal', 'Your brand', 'Competitor']} />
      <TRow cols={3} values={['Reviews widget',   '✗', '✓']} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 1: { color: '#ff6b6b' }, 2: { color: '#20bf6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Security badge',   '✓', '✓']} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 1: { color: '#20bf6b', fontWeight: 700 }, 2: { color: '#20bf6b', fontWeight: 700 } }} />
      <TRow cols={3} values={['Newsletter popup', '✗', '✓']} hi={{ 0: { fontWeight: 600, color: '#2d3436' }, 1: { color: '#ff6b6b' }, 2: { color: '#20bf6b', fontWeight: 700 } }} />
    </>
  ),

  actions: (
    <>
      <div className="app-section-title">Recommended actions</div>
      <div className="app-section-sub">5 prioritized next steps from this analysis.</div>
      {[
        { level: 'high',   n: 1, text: 'Review pricing on 7 matched SKUs where you are 28% pricier — test competitive price bands before peak season.',    area: 'Pricing · High'      },
        { level: 'high',   n: 2, text: 'Fix 6 missing meta descriptions on product pages — competitor has near-complete SEO coverage.',                     area: 'SEO · High'          },
        { level: 'medium', n: 3, text: 'Add reviews widget and loyalty messaging to key category pages to match competitor trust signals.',                  area: 'Conversion · Medium' },
        { level: 'medium', n: 4, text: 'Expand skincare assortment — competitor has 3.8× more SKUs in this category.',                                      area: 'Catalog · Medium'    },
        { level: 'low',    n: 5, text: 'Test bundle offers and free-shipping thresholds — competitor actively promotes both in positioning signals.',         area: 'Merchandising · Low' },
      ].map(({ level, n, text, area }) => (
        <div key={n} className={`app-action-card ${level}`}>
          <div className={`app-action-num ${level}`}>{n}</div>
          <div>
            <div className="app-action-text">{text}</div>
            <div className="app-action-area">{area}</div>
          </div>
        </div>
      ))}
    </>
  ),
};

function Demo() {
  const [activeTab, setActiveTab] = useState('overview');

  const highlights = [
    { color: 'rh-coral',  title: 'Pricing gap — you\'re 28% more expensive',     description: 'Competitor averages $58 vs your $74 across 7 matched products. Cheaper on 7 of 12 compared SKUs.',                icon: (<><path d="M4 7h16M4 12h10M4 17h7" /><path d="M17 14l3 3-3 3" /></>) },
    { color: 'rh-teal',   title: 'Catalog depth — 2.7× more SKUs',               description: '386 products across 14 categories vs your 142 across 8. Skincare alone: 91 vs 24.',                               icon: (<><path d="M6 2h12v20H6z" /><path d="M9 6h6M9 10h6M9 14h3" /></>) },
    { color: 'rh-yellow', title: 'SEO & trust signals lagging',                   description: '6 missing meta descriptions and no reviews widget — competitor has near-complete coverage on both.',              icon: (<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></>) },
    { color: 'rh-green',  title: '5 prioritised actions, ready to act on',        description: 'Pricing, SEO, conversion, catalog, and merchandising — each with context and priority level.',                    icon: (<><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>) },
  ];

  return (
    <section className="demo-section section" id="demo" aria-labelledby="demo-heading">
      <div className="container">
        <div className="demo-grid">

          {/* Left: copy */}
          <div className="demo-content reveal">
            <div className="eyebrow"><span className="eyebrow-pulse" />Sample Report</div>
            <h2 id="demo-heading">Your competitor is outperforming you in 3 key areas</h2>
            <p>IntelShift scanned 14 pages across both brands and surfaced exactly where the gap is — with scores, evidence, and actions ready for your team.</p>
            <div className="report-highlights" role="list">
              {highlights.map((item, i) => (
                <div key={i} className="rh-item" role="listitem">
                  <div className={`rh-icon ${item.color}`} aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{item.icon}</svg>
                  </div>
                  <div className="rh-text"><h4>{item.title}</h4><p>{item.description}</p></div>
                </div>
              ))}
            </div>
            <a href="#pricing" className="btn btn-primary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
              Get your analysis
            </a>
          </div>

          {/* Right: interactive dashboard mockup */}
          <div className="reveal reveal-delay-2" id='right'>
            <div className="app-mockup" aria-label="IntelShift dashboard preview">
              <div className="app-shell">

                {/* Sidebar */}
                <div className="app-sidebar">
                  <div className="app-logo">
                    <img src={logo} alt="IntelShift" />
                    <span>IntelShift</span>
                  </div>
                  {['Dashboard','Change Detail','Competitors List','Weekly Reports','Alert Settings','Billing & Usage','Workspace Settings'].map((item, i) => (
                    <div key={item} className={`app-nav-item${i === 0 ? ' active' : ''}`}>{item}</div>
                  ))}
                </div>

                {/* Main area */}
                <div className="app-main">
                  <div className="app-topbar">
                    <span className="app-topbar-title">Competitor Analysis</span>
                    <div className="app-upgrade-btn">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ width: 10, height: 10 }}><path d="M12 2l3 7h7l-5.5 4 2 7L12 16l-6.5 4 2-7L2 9h7z" /></svg>
                      Upgrade
                    </div>
                    <div className="app-pagination">1 / 1<div className="app-progress"><div className="app-progress-fill" style={{ width: '100%' }} /></div></div>
                    <div className="app-avatar">U</div>
                  </div>

                  <div className="app-content">
                    <div className="app-intel-card">
                      <div className="app-intel-badge">Ecommerce Analysis</div>
                      <div className="app-intel-title">yourbrand.com <em>vs</em> competitor.com</div>
                      <div className="app-intel-desc">Competitor shows deeper product assortment, stronger SEO coverage, and more aggressive pricing. Immediate action recommended on pricing and content gaps.</div>
                      <div className="app-scores">
                        <div className="app-score-box"><div className="app-score-num teal">43</div><div className="app-score-label">Your Brand</div></div>
                        <div className="app-score-box"><div className="app-score-num coral">86</div><div className="app-score-label">Competitor</div></div>
                      </div>
                    </div>

                    <div className="app-tabs">
                      {DEMO_TABS.map(tab => (
                        <button key={tab.key} className={`app-tab${activeTab === tab.key ? ' active' : ''}`} onClick={() => setActiveTab(tab.key)}>
                          {tab.label}
                          {tab.dot   && <div className="app-tab-dot" />}
                          {tab.badge && <span className="app-tab-badge">{tab.badge}</span>}
                        </button>
                      ))}
                    </div>

                    <div className="app-section-card">
                      {PANELS[activeTab]}
                    </div>
                  </div>
                </div>

              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

export default Demo;
