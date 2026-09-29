import { useState } from 'react';

function ProductIntelligence() {
  const [activeTab, setActiveTab] = useState('ai');

  const tabs = [
    { key: 'ai',      label: 'AI Insight' },
    { key: 'before',  label: 'Before'     },
    { key: 'after',   label: 'After'      },
    { key: 'actions', label: 'Actions'    },
  ];

  const points = [
    {
      title: 'AI reads the move, not just the page',
      text:  'Your competitor report includes an AI interpretation — what the competitor is likely trying to achieve and what it signals for your market position.',
      icon:  <path d="M12 2a10 10 0 110 20A10 10 0 0112 2zm0 4v4l3 3" />,
    },
    {
      title: 'Impact scored — so you know what to act on first',
      text:  'Findings are scored 0–100 by business impact. Critical moves (like the 91/100 above) surface first. Minor noise stays quiet.',
      icon:  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />,
    },
    {
      title: 'Timestamped before & after — always on record',
      text:  'Every insight is backed by a side-by-side snapshot. You see the exact wording, price, or feature that changed — not just a summary you have to trust.',
      icon:  <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18M9 21V9" /></>,
    },
    {
      title: 'Actions by team — not a report to file away',
      text:  'Recommendations are split by function: Pricing, Sales, Marketing. Each person knows exactly what to do without reading the whole report.',
      icon:  <><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>,
    },
  ];

  return (
    <section className="product-intel section" id="features" aria-labelledby="intel-heading">
      <div className="container">
        <div className="intel-grid">

          {/* LEFT: Change Detail card */}
          <div className="change-detail-card reveal">
            <div className="cdc-header">
              <div className="cdc-dots">
                <div className="cdc-dot cdc-dot-r" />
                <div className="cdc-dot cdc-dot-y" />
                <div className="cdc-dot cdc-dot-g" />
              </div>
              <span className="cdc-title">Competitor Report — AI Analysis View</span>
            </div>

            <div className="cdc-body">
              <div style={{ marginBottom: 12 }}>
                <div className="cdc-change-title">Pricing page change detected</div>
                <div className="cdc-meta">
                  <span className="cdc-competitor">competitor.com</span>
                  <span className="badge badge-high" style={{ fontSize: 10 }}><span className="badge-dot" />High Impact</span>
                  <span className="cdc-date">Jun 28, 2026</span>
                </div>
              </div>

              {/* Tab buttons */}
              <div className="cdc-tabs" role="tablist">
                {tabs.map(t => (
                  <button
                    key={t.key}
                    className={`cdc-tab${activeTab === t.key ? ' active' : ''}`}
                    role="tab"
                    aria-selected={activeTab === t.key}
                    onClick={() => setActiveTab(t.key)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* ── AI Insight panel ── */}
              {activeTab === 'ai' && (
                <>
                  <div className="cdc-ai-section">
                    <div className="cdc-ai-label">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a10 10 0 110 20A10 10 0 0112 2zm0 4v4l3 3" /></svg>
                      AI Interpretation
                    </div>
                    <div className="cdc-ai-text">
                      competitor.com is moving upmarket. Bundling AI into the Growth tier at +$30 signals a push toward higher-value buyers — and away from competing on price. Expect this messaging to appear in their ads and sales calls within weeks.
                    </div>
                  </div>
                  <div className="cdc-impact">
                    <div className="cdc-impact-box">
                      <div className="label">Intent</div>
                      <div className="value">Upmarket move &amp; value bundling</div>
                    </div>
                    <div className="cdc-impact-box">
                      <div className="label">Impact Score</div>
                      <div className="value" style={{ color: 'var(--accent)' }}>91 / 100 — Critical</div>
                    </div>
                  </div>
                  <div className="cdc-actions-label">Recommended actions</div>
                  <div className="cdc-action">
                    <div className="cdc-action-num">1</div>
                    <div className="cdc-action-text">Audit your own AI feature messaging before prospects compare both offers side by side.</div>
                  </div>
                  <div className="cdc-action">
                    <div className="cdc-action-num">2</div>
                    <div className="cdc-action-text">Brief sales with updated objection-handling notes — reps will hear "competitor.com includes AI now" on calls this week.</div>
                  </div>
                </>
              )}

              {/* ── Before panel ── */}
              {activeTab === 'before' && (
                <>
                  <div className="cdc-snap-header">
                    <span className="cdc-snap-url">competitor.com/pricing</span>
                    <span className="cdc-snap-ts before-ts">Jun 14, 2026 · 09:42 UTC</span>
                  </div>
                  <div className="cdc-snap-plan">Growth plan</div>
                  <div className="cdc-snap-rows">
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">Price</span>
                      <span className="cdc-snap-val">$99 / month</span>
                    </div>
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">Team seats</span>
                      <span className="cdc-snap-val">Up to 10 members</span>
                    </div>
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">Support</span>
                      <span className="cdc-snap-val">Email support only</span>
                    </div>
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">AI features</span>
                      <span className="cdc-snap-val muted">Not mentioned</span>
                    </div>
                  </div>
                </>
              )}

              {/* ── After panel ── */}
              {activeTab === 'after' && (
                <>
                  <div className="cdc-snap-header">
                    <span className="cdc-snap-url">competitor.com/pricing</span>
                    <span className="cdc-snap-ts after-ts">Jun 28, 2026 · Changed</span>
                  </div>
                  <div className="cdc-snap-plan">Growth plan</div>
                  <div className="cdc-snap-rows">
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">Price</span>
                      <span className="cdc-snap-val">$129 / month <span className="cdc-snap-delta">+$30 ↑</span></span>
                    </div>
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">Team seats</span>
                      <span className="cdc-snap-val">Up to 10 members</span>
                    </div>
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">Support</span>
                      <span className="cdc-snap-val">Priority support <span className="cdc-snap-new">New</span></span>
                    </div>
                    <div className="cdc-snap-row-kv">
                      <span className="cdc-snap-key">AI features</span>
                      <span className="cdc-snap-val">AI add-on included <span className="cdc-snap-new">New</span></span>
                    </div>
                  </div>
                  <div className="cdc-change-summary">⚡ Price +$30/mo · AI bundled · Support tier upgraded</div>
                </>
              )}

              {/* ── Actions panel ── */}
              {activeTab === 'actions' && (
                <div className="cdc-action-list">
                  {[
                    { area: 'Pricing',   text: 'Review your Growth plan value narrative. Counter the AI bundle before it shapes buyer expectations.' },
                    { area: 'Sales',     text: 'Brief the team today. Prospects will ask why competitor.com includes AI at $129 — reps need a ready answer before the next demo.' },
                    { area: 'Marketing', text: 'Update comparison pages and paid-search copy to address "AI-powered growth" positioning before it lands in buyer conversations.' },
                  ].map((a, i) => (
                    <div key={i} className="cdc-action-item">
                      <div className="cdc-action-item-num">{i + 1}</div>
                      <div className="cdc-action-body">
                        <div className="cdc-action-area">{a.area}</div>
                        {a.text}
                      </div>
                    </div>
                  ))}
                </div>
              )}

            </div>
          </div>

          {/* RIGHT: copy */}
          <div className="intel-content reveal reveal-delay-2">
            <div className="intel-label">Core Intelligence</div>
            <h2 id="intel-heading">See the change. Understand the intent. Take action.</h2>
            <p>When a competitor moves, IntelShift tells you what changed, what they're trying to do, how serious it is — and exactly what your pricing, sales, and marketing teams should do next.</p>

            <div className="intel-points">
              {points.map((p, i) => (
                <div key={i} className="intel-point">
                  <div className="intel-point-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">{p.icon}</svg>
                  </div>
                  <div className="intel-point-text">
                    <h4>{p.title}</h4>
                    <p>{p.text}</p>
                  </div>
                </div>
              ))}
            </div>

            <a href="#pricing" className="btn btn-primary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
              Start monitoring competitors
            </a>
          </div>

        </div>
      </div>
    </section>
  );
}

export default ProductIntelligence;
