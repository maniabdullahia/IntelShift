function HowItWorks() {
    return (
        <section
            className="how section"
            id="how"
            aria-labelledby="how-heading"
        >
            <div className="how-bg" aria-hidden="true"></div>

            <div className="container how-inner">
                <div className="section-head reveal">
                    <div className="eyebrow">
                        <span className="eyebrow-pulse"></span>
                        How It Works
                    </div>

                    <h2 id="how-heading">
                        From competitor URLs to actionable intelligence — in
                        minutes.
                    </h2>

                    <p>
                        IntelShift monitors the right pages, removes noise,
                        scores impact, and turns competitor changes into clear
                        recommendations for your team.
                    </p>
                </div>

                <div className="steps-grid" role="list">
                    <div
                        className="step-connector"
                        aria-hidden="true"
                    ></div>

                    <div
                        className="step reveal reveal-delay-1"
                        role="listitem"
                    >
                        <div className="step-num" aria-hidden="true">
                            <div className="step-num-inner">1</div>
                        </div>

                        <h3>Add competitors</h3>

                        <p>
                            Select competitor URLs and choose your industry.
                        </p>
                    </div>

                    <div
                        className="step reveal reveal-delay-2"
                        role="listitem"
                    >
                        <div className="step-num" aria-hidden="true">
                            <div className="step-num-inner">2</div>
                        </div>

                        <h3>Choose pages to monitor</h3>

                        <p>
                            Track pricing, product pages, collections, offers,
                            homepage messaging, blogs, careers, or custom pages.
                        </p>
                    </div>

                    <div
                        className="step reveal reveal-delay-3"
                        role="listitem"
                    >
                        <div className="step-num" aria-hidden="true">
                            <div className="step-num-inner">3</div>
                        </div>

                        <h3>We detect meaningful changes</h3>

                        <p>
                            Our engine crawls pages, removes noise like headers,
                            footers, and cookie banners, then scores impact
                            severity.
                        </p>
                    </div>

                    <div
                        className="step reveal reveal-delay-4"
                        role="listitem"
                    >
                        <div className="step-num" aria-hidden="true">
                            <div className="step-num-inner">4</div>
                        </div>

                        <h3>Get AI recommendations</h3>

                        <p>
                            Your competitor report explains strategic intent,
                            why it matters, and the concrete actions your team
                            should take next.
                        </p>
                    </div>
                </div>
            </div>
        </section>
    );
}

export default HowItWorks;