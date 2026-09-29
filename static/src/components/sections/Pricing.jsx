
import { useState, useEffect, useRef } from "react";

import { getPlans } from "../../api/plans.api";

function Pricing() {

  const [plans, setPlans]         = useState([]);
  const [visible, setVisible]     = useState(false);
  const sectionRef                = useRef(null);

  const APP_URL = import.meta.env.VITE_APP_URL || "https://intelshift.ai";

  const baseLink = `${APP_URL}/register?plan=`;

  // Only start the API call once the pricing section scrolls into view.
  // This removes /api/plans from the critical path (saves ~3 s on first paint).
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { rootMargin: '300px' }   // start 300 px before it enters viewport
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Turn a raw cadence value ("weekly", "3D", "daily"…) into human copy.
  const cadenceText = (raw) => {
    const map = {
      daily: "daily",
      "2D": "every 2 days",
      "3D": "every 3 days",
      weekly: "weekly",
      monthly: "monthly",
      once: "one-time",
    };
    return map[raw] || "weekly";
  };

  const normalizePlan = (plan) => {
    const slug = (plan?.name || "").toLowerCase();
    const displayName = plan?.displayName || plan?.name || "Plan";
    const price = Number(plan?.price ?? 0);
    const cadence = cadenceText(plan?.limits?.reportFrequency || plan?.planReportingFrequency);

    return {
      ...plan,
      name: displayName,
      price,
      featured: Boolean(plan?.featured || slug === "growth"),
      buttonClass: plan?.buttonClass || `btn ${price === 0 ? "btn-ghost" : "btn-primary"}`,
      cta: plan?.cta || (price === 0 ? "Start free trial" : `Start ${displayName} plan`),
      description:
        plan?.description ||
        `Monitor up to ${plan?.limits?.competitors ?? 1} competitors, ${plan?.limits?.pagesPerCompetitor ?? 20} pages each, checked ${cadence}.`,
      features:
        Array.isArray(plan?.features) && plan.features.length > 0
          ? plan.features
          : [
              `${plan?.limits?.competitors ?? 1} competitors monitored`,
              `Up to ${plan?.limits?.pagesPerCompetitor ?? 20} pages per competitor`,
              "Homepage included for every competitor",
              `Checked ${cadence}`,
            ],
      link: plan?.link || `${baseLink}${plan?._id}`,
    };
  };

  useEffect(() => {
    if (!visible) return;   // wait until section is near viewport
    const fetchPlans = async () => {
      try {
        const response = await getPlans();
        setPlans(Array.isArray(response) ? response : response?.plans ?? []);
      }
      catch (error) {
        console.error("Error fetching plans:", error);
      }
    };
    fetchPlans();
  }, [visible]);

  const normalizedPlans = plans.map(normalizePlan);
  const paidPlans = normalizedPlans.filter((plan) => plan.price > 0);
  const freePlan = normalizedPlans.find((plan) => plan.price === 0);

  return (
    <section className="pricing section" id="pricing" aria-labelledby="pricing-heading" ref={sectionRef}>
      <div className="container">
        <div className="section-head reveal">
          <div className="eyebrow">
            <span className="eyebrow-pulse"></span>
            Pricing
          </div>
          <h2 id="pricing-heading">Choose the coverage your market needs</h2>
          <p>
            Every plan includes homepage monitoring, AI insights, and email
            alerts. Upgrade when you need more competitors, more pages per
            competitor, faster monitoring, and historical tracking.
          </p>
        </div>

        <div className="trial-card reveal">
          <div>
            <span className="badge badge-ok">
              <span className="badge-dot"></span>
              Free trial
            </span>
            <h3>Try IntelShift before choosing a plan.</h3>
            <p>
              Track 1 competitor across up to 10 pages, checked weekly, with no
              credit card required. Test the monitoring flow, AI insights, and
              alerts before choosing a plan.
            </p>
          </div>
          <a href={freePlan?.link || `${baseLink}trial`} className="btn btn-primary">
            {freePlan?.cta || "Start free trial"}
          </a>
        </div>

        <div className="pricing-grid reveal">
          {paidPlans.map((plan) => (
            <div
              key={plan.name}
              className={`price-card ${plan.featured ? "featured" : ""}`}
            >
              <div className="price-plan">{plan.name}</div>

              <div className="price-amount">
                ${plan.price}
                <span className="price-period">/mo</span>
              </div>

              <p className="price-desc">{plan.description}</p>

              <ul className="price-features" role="list">
                {plan.features.map((feature) => (
                  <li key={feature} className="price-feature" role="listitem">
                    <div className="price-check" aria-hidden="true">
                      <svg
                        viewBox="0 0 12 12"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                      >
                        <path d="M2 6l3 3 5-5" />
                      </svg>
                    </div>
                    {feature}
                  </li>
                ))}
              </ul>

              <a
                href={plan.link}
                className={plan.buttonClass}
                style={{ justifyContent: "center", marginTop: "auto" }}
              >
                {plan.featured && (
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    aria-hidden="true"
                  >
                    <path d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                )}
                {plan.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default Pricing;
