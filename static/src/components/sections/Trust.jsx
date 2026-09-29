function Trust() {
    const trustItems = [
        {
            delay: "reveal-delay-1",
            title: "Public pages only",
            description:
                "We monitor only publicly accessible competitor web pages. No login bypass, no restricted content, no private data.",
            icon: (
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            ),
        },
        {
            delay: "reveal-delay-2",
            title: "No login tracking",
            description:
                "IntelShift does not access or monitor any pages behind authentication, customer dashboards, or private portals.",
            icon: (
                <>
                    <circle cx="12" cy="12" r="10" />
                    <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
                </>
            ),
        },
        {
            delay: "reveal-delay-3",
            title: "robots.txt respected",
            description:
                "Our crawlers follow each website's robots.txt directives and crawl rate settings. We are good citizens of the web.",
            icon: (
                <>
                    <path d="M9 11l3 3L22 4" />
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </>
            ),
        },
        {
            delay: "reveal-delay-1",
            title: "Secure workspace",
            description:
                "Your workspace data, competitor snapshots, and insight reports are encrypted and isolated per account. No data sharing between organizations.",
            icon: (
                <>
                    <rect
                        x="3"
                        y="11"
                        width="18"
                        height="11"
                        rx="2"
                        ry="2"
                    />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </>
            ),
        },
        {
            delay: "reveal-delay-2",
            title: "Usage limits enforced",
            description:
                "Fair-use crawl limits are enforced per plan. Abuse protections and rate limiting prevent any single account from over-crawling competitor domains.",
            icon: (
                <>
                    <line x1="18" y1="20" x2="18" y2="10" />
                    <line x1="12" y1="20" x2="12" y2="4" />
                    <line x1="6" y1="20" x2="6" y2="14" />
                </>
            ),
        },
        {
            delay: "reveal-delay-3",
            title: "Responsible crawl cadence",
            description:
                "Monitoring runs on scheduled intervals, not continuous crawls. We don't hammer competitor infrastructure—we check at sensible intervals by plan tier.",
            icon: (
                <>
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                </>
            ),
        },
    ];

    return (
        <section
            className="trust section"
            aria-labelledby="trust-heading"
        >
            <div className="container">
                <div className="section-head reveal">
                    <div className="eyebrow">
                        <span className="eyebrow-pulse"></span>
                        Responsible by Design
                    </div>

                    <h2 id="trust-heading">
                        Built for competitive intelligence.
                        <br />
                        Not competitive espionage.
                    </h2>

                    <p>
                        We take monitoring ethics seriously. IntelShift is
                        designed to be legal, responsible, and transparent—from
                        the crawl to the insight.
                    </p>
                </div>

                <div className="trust-grid">
                    {trustItems.map((item, index) => (
                        <div
                            key={index}
                            className={`trust-card reveal ${item.delay}`}
                        >
                            <div
                                className="trust-icon-wrap"
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

                            <h3>{item.title}</h3>

                            <p>{item.description}</p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

export default Trust;