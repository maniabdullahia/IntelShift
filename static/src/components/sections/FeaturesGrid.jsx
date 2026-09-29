function FeaturesGrid() {
    return (
        <section className="features section" aria-labelledby="features-heading">
            <div className="container">
                <div className="section-head reveal">
                    <div className="eyebrow">
                        <span className="eyebrow-pulse"></span>
                        Features
                    </div>

                    <h2 id="features-heading">
                        Everything your team needs.
                        <br />
                        Nothing they don't.
                    </h2>

                    <p>
                        For teams that need answers, not another pile of competitor
                        data.
                    </p>
                </div>

                <div className="features-grid">
                    <div className="feat-card reveal reveal-delay-1">
                        <div className="feat-icon teal" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <circle cx="11" cy="11" r="8" />
                                <path d="m21 21-4.35-4.35" />
                            </svg>
                        </div>

                        <h3>Meaningful change detection</h3>

                        <p>
                            IntelShift filters out page noise like menus,
                            footers, popups, cookie banners, and repeated
                            layout updates — so your team only sees changes
                            that signal a real competitor move.
                        </p>
                    </div>

                    <div className="feat-card reveal reveal-delay-2">
                        <div className="feat-icon coral" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                            </svg>
                        </div>

                        <h3>Pricing &amp; positioning alerts</h3>

                        <p>
                            Get notified when important competitor pricing,
                            messaging, offer, or product changes are detected —
                            with alert speed and sensitivity based on your
                            selected plan.
                        </p>
                    </div>

                    <div className="feat-card reveal reveal-delay-3">
                        <div className="feat-icon green" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                            </svg>
                        </div>

                        <h3>Competitor intelligence reports</h3>

                        <p>
                            Get a concise summary of key competitor moves,
                            trends, and recommended actions — delivered
                            according to your plan's reporting schedule.
                        </p>
                    </div>

                    <div className="feat-card reveal reveal-delay-1">
                        <div className="feat-icon yellow" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <rect x="3" y="3" width="18" height="18" rx="2" />
                                <path d="M3 9h18M9 21V9" />
                            </svg>
                        </div>

                        <h3>Historical competitor timeline</h3>

                        <p>
                            See how competitor messaging, pricing, and strategy
                            evolved over time. Spot patterns, predict next
                            moves, and track positioning drift.
                        </p>
                    </div>

                    <div className="feat-card reveal reveal-delay-2">
                        <div className="feat-icon teal" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M12 2a10 10 0 110 20A10 10 0 0112 2z" />
                                <path d="M12 6v6l4 2" />
                            </svg>
                        </div>

                        <h3>Severity impact scoring</h3>

                        <p>
                            Every detected change is scored for business impact
                            so your team knows what to act on immediately
                            versus what to monitor over time.
                        </p>
                    </div>

                    <div className="feat-card reveal reveal-delay-3">
                        <div className="feat-icon coral" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                            </svg>
                        </div>

                        <h3>Public-page monitoring only</h3>

                        <p>
                            We only crawl publicly accessible competitor pages.
                            No logins, no scraping protected data. Ethical,
                            legal, and responsible by design.
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
}

export default FeaturesGrid;