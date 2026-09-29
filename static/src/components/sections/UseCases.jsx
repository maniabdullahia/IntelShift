function UseCases() {
    const useCases = [
        {
            color: "teal",
            delay: "reveal-delay-1",
            role: "For founders & operators",
            title: "Stay ahead of market moves",
            description:
                "Stop checking competitor sites manually. See pricing shifts, new offers, product changes, and positioning moves before they affect pipeline, sales, or growth.",
            points: [
                "Track competitor pricing and offers",
                "Spot market and category shifts",
                "Get concise intelligence briefs",
            ],
            icon: (
                <>
                    <path d="M4 19V5" />
                    <path d="M4 7h12l-2 4 2 4H4" />
                    <path d="M18 16l2 2-2 2" />
                </>
            ),
        },
        {
            color: "coral",
            delay: "reveal-delay-2",
            role: "For marketing teams",
            title: "Spot messaging shifts early",
            description:
                "See when competitors update homepage, landing pages, product descriptions, product collections, campaigns, or audience focus before your messaging starts feeling outdated.",
            points: [
                "Monitor homepage & feature pages",
                "Track product and campaign messaging",
                "Find new angles before competitors scale them",
            ],
            icon: (
                <>
                    <circle cx="12" cy="12" r="8" />
                    <path d="M12 8v8" />
                    <path d="M8 12h8" />
                    <path d="M20 4l-3 3" />
                </>
            ),
        },
        {
            color: "yellow",
            delay: "reveal-delay-3",
            role: "For sales teams",
            title: "Keep battlecards current",
            description:
                "Never let reps get blindsided again. Get alerts when competitors change pricing, features, or proof points so battlecards are always one step ahead of the next call.",
            points: [
                "Prepare stronger competitive talking points",
                "Catch pricing and feature objections early",
                "Share clear insights with the team",
            ],
            icon: (
                <>
                    <path d="M21 15a4 4 0 01-4 4H8l-5 3V7a4 4 0 014-4h10a4 4 0 014 4z" />
                    <path d="M8 9h8" />
                    <path d="M8 13h5" />
                </>
            ),
        },
    ];

    return (
        <section
            className="usecases section"
            id="usecases"
            aria-labelledby="uc-heading"
        >
            <div className="usecases-bg" aria-hidden="true"></div>

            <div className="container usecases-inner">
                <div className="section-head reveal">
                    <div className="eyebrow">
                        <span className="eyebrow-pulse"></span>
                        Use Cases
                    </div>

                    <h2 id="uc-heading">
                        Built for the people who
                        <br />
                        need to react fastest.
                    </h2>

                    <p>
                        IntelShift gives founders, marketing, sales, and ecommerce
                        teams the signals they need to respond faster to competitor
                        moves.
                    </p>
                </div>

                <div className="uc-grid">
                    {useCases.map((item, index) => (
                        <div
                            key={index}
                            className={`uc-card reveal ${item.delay}`}
                        >
                            <div
                                className={`uc-avatar ${item.color}`}
                                aria-hidden="true"
                            >
                                <svg
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                >
                                    {item.icon}
                                </svg>
                            </div>

                            <div className="uc-role">{item.role}</div>

                            <h3>{item.title}</h3>

                            <p>{item.description}</p>

                            <div className="uc-points" role="list">
                                {item.points.map((point, i) => (
                                    <div
                                        key={i}
                                        className="uc-point"
                                        role="listitem"
                                    >
                                        <div
                                            className="uc-check"
                                            aria-hidden="true"
                                        >
                                            <svg
                                                viewBox="0 0 12 12"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2.5"
                                            >
                                                <path d="M2 6l3 3 5-5" />
                                            </svg>
                                        </div>

                                        {point}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

export default UseCases;