
function Hero() {
    return (
        <section className="hero" aria-labelledby="hero-heading">
            <div className="hero-bg" aria-hidden="true">
                <div className="hero-grid-lines"></div>
                <div className="hero-glow-1"></div>
                <div className="hero-glow-2"></div>
                <div className="hero-glow-3"></div>
            </div>

            <div className="container">
                <div className="hero-inner">
                    <div className="hero-content">
                        <div className="hero-tag" aria-label="Product category">
                            <span className="hero-tag-dot" aria-hidden="true"></span>
                            AI Competitor Intelligence
                        </div>
                        <h1 id="hero-heading">
                            Detect competitor moves.
                            <em>Understand intent. Take action.</em>
                        </h1>
                        <p className="hero-sub">
                            Track competitor pricing, products, offers, messaging, and market signals. Get AI-powered insights that explain what changed, why it matters, and what your team should do next.
                        </p>
                        <div className="hero-actions">
                            <a href="#pricing" className="btn btn-primary btn-lg">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                                Start monitoring in 5 minutes
                            </a>
                            <a href="#demo" className="btn btn-secondary btn-lg">
                                View sample report
                            </a>
                        </div>
                        <div className="trust-row" aria-label="Trust indicators">
                            <div className="trust-item">
                                <div className="trust-icon" aria-hidden="true">
                                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M2 6l3 3 5-5" /></svg>
                                </div>
                                AI-powered recommendations
                            </div>
                            <div className="trust-item">
                                <div className="trust-icon" aria-hidden="true">
                                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M2 6l3 3 5-5" /></svg>
                                </div>
                                Executive reports
                            </div>
                            <div className="trust-item">
                                <div className="trust-icon" aria-hidden="true">
                                    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M2 6l3 3 5-5" /></svg>
                                </div>
                                Meaningful changes
                            </div>
                        </div>
                    </div>

                    <div className="hero-visual" aria-hidden="true">
                        <div className="floating-insight">
                            <div className="insight-chip">AI Insight</div>
                            <div className="insight-chip-text">Competitor pivoting to enterprise segment</div>
                        </div>

                        <div className="dashboard-frame">
                            <div className="dash-topbar">
                                <div className="dash-dot dash-dot-r"></div>
                                <div className="dash-dot dash-dot-y"></div>
                                <div className="dash-dot dash-dot-g"></div>
                                <span className="dash-title">IntelShift — Competitor Intelligence</span>
                            </div>
                            <div className="dash-body">
                                <div className="dash-header-row">
                                    <span className="dash-title-main">Competitor Changes</span>
                                    <span className="dash-week-badge">Last 7 days</span>
                                </div>
                                <div className="dash-stats">
                                    <div className="dash-stat">
                                        <div className="dash-stat-num red">3</div>
                                        <div className="dash-stat-label">High Impact</div>
                                    </div>
                                    <div className="dash-stat">
                                        <div className="dash-stat-num yellow">7</div>
                                        <div className="dash-stat-label">Medium</div>
                                    </div>
                                    <div className="dash-stat">
                                        <div className="dash-stat-num teal">22</div>
                                        <div className="dash-stat-label">Total Changes</div>
                                    </div>
                                </div>
                                <div className="dash-change-card">
                                    <div className="dash-change-top">
                                        <div className="dash-change-title">High-impact competitor move detected</div>
                                        <span className="badge badge-high"><span className="badge-dot"></span>High</span>
                                    </div>
                                    <div className="dash-change-body">Multiple price points and offer terms changed on their pricing page since the last scan.</div>
                                    <div className="dash-change-footer">
                                        <span className="dash-competitor-tag">Market Rival</span>
                                        <span className="dash-time">Pricing / offer page · 2h ago</span>
                                    </div>
                                </div>
                                <div className="dash-change-card">
                                    <div className="dash-change-top">
                                        <div className="dash-change-title">Homepage messaging shifted toward premium buyers</div>
                                        <span className="badge badge-high"><span className="badge-dot"></span>High</span>
                                    </div>
                                    <div className="dash-change-body">New proof points and stronger value claims added to the homepage hero and headline.</div>
                                    <div className="dash-change-footer">
                                        <span className="dash-competitor-tag">GrowthBrand</span>
                                        <span className="dash-time">Homepage · 1d ago</span>
                                    </div>
                                </div>
                                <div className="dash-change-card">
                                    <div className="dash-change-top">
                                        <div className="dash-change-title">New product collection / feature page launched</div>
                                        <span className="badge badge-mid"><span className="badge-dot"></span>Medium</span>
                                    </div>
                                    <div className="dash-change-body">A new product collection page went live, expanding their catalog.</div>
                                    <div className="dash-change-footer">
                                        <span className="dash-competitor-tag">Competitor X</span>
                                        <span className="dash-time">Product page · 3d ago</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="floating-alert">
                            <div className="alert-icon">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
                            </div>
                            <div className="alert-text">
                                <strong>High-impact change detected</strong>
                                <span>GrowthBrand · Pricing page updated</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    )
}

export default Hero
