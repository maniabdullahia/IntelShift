function LongMarquee() {
    const logos = [
        "Keune",
        "Techosols",
        "Sivanna Colors",
        "Eveline",
        "FocusPC",
        "Mubah",
        "FoodToGo",
        "CheowPeow",
        "HavenGreens",
    ];

    return (
        <div className="marquee-section" aria-hidden="true">
            <div className="marquee-label">
                Used by ecommerce brands, SaaS companies, and growing businesses to stay ahead of the competition
            </div>

            <div className="marquee-track">
                <div className="marquee-inner">
                    {[...logos, ...logos].map((logo, index) => (
                        <span key={index} className="marquee-logo">
                            {logo}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default LongMarquee;