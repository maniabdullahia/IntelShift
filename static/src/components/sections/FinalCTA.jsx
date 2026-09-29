function FinalCTA() {
  const trustItems = [
    "Setup in minutes",
    "Public pages only",
    "Plan-based alerts & reports",
    "Cancel anytime",
  ];

  return (
    <section className="final-cta section" aria-labelledby="cta-heading">
      <div className="final-cta-bg" aria-hidden="true">
        <div className="final-cta-glow" />
        <div className="final-cta-grid" />
      </div>

      <div className="container final-cta-inner">
        <div className="reveal">
          <div
            className="eyebrow"
            style={{ justifyContent: "center", display: "inline-flex" }}
          >
            <span className="eyebrow-pulse"></span>
            Get Started
          </div>

          <h2 id="cta-heading">
            Stop finding out <em>secondhand.</em>
          </h2>

          <p>
            Turn competitor changes into a focused intelligence brief — what
            moved, why it matters, and what your team should do next.
          </p>

          <div className="final-cta-actions">
            <a href="#pricing" className="btn btn-primary btn-lg">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
              Start monitoring in 5 minutes
            </a>

            <a href="#demo" className="btn btn-secondary btn-lg">
              View sample report
            </a>
          </div>

          <div className="final-trust">
            {trustItems.map((item) => (
              <div key={item} className="final-trust-item">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ecdc4" strokeWidth="2.5" aria-hidden="true">
                  <path d="M2 6l3 3 5-5" />
                </svg>
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default FinalCTA;
