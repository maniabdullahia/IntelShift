function Problem() {
    return (
        <section className="problem section" aria-labelledby="problem-heading">
            <div className="container">
                <div className="section-head reveal">
                    <div className="eyebrow">
                        <span className="eyebrow-pulse"></span>
                        The Problem
                    </div>

                    <h2 id="problem-heading">
                        Competitors don't announce strategy shifts.
                        <br />
                        They ship them.
                    </h2>

                    <p>
                        Monitor the pages that reveal competitor strategy first —
                        pricing, products, offers, messaging, content, and hiring —
                        and turn every meaningful change into action.
                    </p>
                </div>

                <div className="problem-grid">
                    <div className="problem-card reveal reveal-delay-1">
                        <div className="problem-icon red" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M4 7h16M4 12h10M4 17h7" />
                                <path d="M17 14l3 3-3 3" />
                            </svg>
                        </div>

                        <h3>Pricing and offers move first</h3>

                        <p>
                            Competitors change SaaS plans, product prices, bundles,
                            discounts, and promotions before your team has time to
                            react.
                        </p>
                    </div>

                    <div className="problem-card reveal reveal-delay-2">
                        <div className="problem-icon yellow" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M4 19V5" />
                                <path d="M4 7h12l-2 4 2 4H4" />
                            </svg>
                        </div>

                        <h3>Positioning changes quietly</h3>

                        <p>
                            Homepage, landing pages, product descriptions, and
                            category messaging shift long before competitors announce
                            a new strategy.
                        </p>
                    </div>

                    <div className="problem-card reveal reveal-delay-3">
                        <div className="problem-icon blue" aria-hidden="true">
                            <svg
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                            >
                                <path d="M21 15a4 4 0 01-4 4H8l-5 3V7a4 4 0 014-4h10a4 4 0 014 4z" />
                                <path d="M8 9h8M8 13h5" />
                            </svg>
                        </div>

                        <h3>Your team finds out too late</h3>

                        <p>
                            Sales hears it from prospects. Marketing sees it after
                            campaigns underperform. E-commerce teams notice that
                            competitors have already captured demand.
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
}

export default Problem;