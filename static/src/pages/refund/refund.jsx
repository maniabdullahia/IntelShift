
import './refund.css';
import SEO from '../../components/seo/SEO';

function Refund() {
  return (
    <>
      <SEO
        title="Refund Policy"
        description="IntelShift subscriptions are non-refundable except where required by law. Try IntelShift free before you subscribe, and cancel anytime. EU/UK statutory rights honoured. Payments processed by Paddle."
        canonical="/refund"
        noIndex={false}
      />
      {/* <!-- HERO --> */}
      <div className="legal-hero">
        <div className="refund-container-wide">
          <div className="refund-hero-inner">
            <div className="refund-hero-tag">Refund policy</div>
            <h1>Try before you buy</h1>
            <p>Every account starts with a free trial, so you can see IntelShift in action before you pay. Because of that, paid subscriptions are non-refundable except where the law requires — and you can cancel anytime.</p>
            <div className="legal-meta">
              <div className="legal-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
                Last updated: July 26, 2026
              </div>
              <div className="legal-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
                Payments processed by Paddle
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* <!-- BODY --> */}
      <div className="refund-body">
        <div className="refund-container">

          {/* <!-- FREE TRIAL CARD --> */}
          <div className="guarantee-card">
            <div className="guarantee-badge">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <polyline points="9 12 11 14 15 10" />
              </svg>
            </div>
            <div className="guarantee-text">
              <h2>Start with a free trial — no card required</h2>
              <p>You can monitor a competitor and see the intelligence IntelShift produces <strong>before you pay anything.</strong> When you subscribe, your monitoring begins immediately at your request, so subscription fees are <strong>non-refundable except where required by law.</strong></p>
            </div>
          </div>

          {/* <!-- POLICY AT A GLANCE --> */}
          <div className="refund-section">
            <h2>Our policy at a glance</h2>
            <div className="two-col">
              <div className="col-card green">
                <h4>You may be eligible for a refund</h4>
                <ul>
                  <li>A billing error, duplicate charge, or unauthorised charge</li>
                  <li>A non-waivable statutory right applies in your country (see below)</li>
                  <li>The Service was materially unavailable or defective and we couldn't resolve it</li>
                </ul>
              </div>
              <div className="col-card red">
                <h4>Generally non-refundable</h4>
                <ul>
                  <li>Change of mind after your subscription has started</li>
                  <li>Renewal charges — cancel before the renewal date to avoid them</li>
                  <li>Unused time after you cancel mid-period</li>
                  <li>Accounts suspended or terminated for Terms violations</li>
                </ul>
              </div>
            </div>
            <p>If your situation falls outside the above, contact us anyway — we review edge cases like billing errors and Service outages individually and in good faith.</p>
          </div>

          {/* <!-- IMMEDIATE START & WITHDRAWAL --> */}
          <div className="refund-section">
            <h2>Immediate start &amp; your right to cancel</h2>
            <p>IntelShift is a digital service. When you subscribe, you ask us to <strong>start monitoring immediately</strong> and you acknowledge at checkout that, once the service has begun, you lose any 14-day &ldquo;cooling-off&rdquo; right of withdrawal that might otherwise apply. This is standard practice for online software, and it's why we offer a free trial — so you can evaluate IntelShift at no cost and no commitment first.</p>
            <p>You can <strong>cancel your subscription at any time.</strong> Cancellation stops the next renewal; you keep full access until the end of the period you've already paid for. Cancelling does not, by itself, trigger a refund for the current period.</p>
          </div>

          {/* <!-- HOW TO REQUEST --> */}
          <div className="refund-section">
            <h2>How to request a refund</h2>
            <p>If you believe you qualify under this policy or a statutory right, here's the process:</p>
            <div className="refund-steps">
              <div className="refund-step">
                <div className="refund-step-num">1</div>
                <div className="refund-step-body">
                  <h4>Email us</h4>
                  <p>Send a request to <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> with the subject line "Refund request". Include the email address on your account and a short note on why you're requesting it.</p>
                </div>
              </div>
              <div className="refund-step">
                <div className="refund-step-num">2</div>
                <div className="refund-step-body">
                  <h4>We review within 1–3 business days</h4>
                  <p>We'll assess your request against this policy and any statutory rights that apply to you, and reply to let you know. Where a refund is due, we initiate it through Paddle, our payment processor — you don't need to contact Paddle separately.</p>
                </div>
              </div>
              <div className="refund-step">
                <div className="refund-step-num">3</div>
                <div className="refund-step-body">
                  <h4>Paddle processes the refund</h4>
                  <p>Paddle returns approved refunds to your original payment method. This typically takes <strong>5–10 business days</strong> depending on your bank or card issuer.</p>
                </div>
              </div>
            </div>
          </div>

          {/* <!-- PADDLE NOTE --> */}
          <div className="refund-section">
            <h2>About Paddle and payments</h2>
            <p>All IntelShift subscriptions are sold by <strong>Paddle.com Market Limited</strong> as the Merchant of Record. Paddle is the seller on your receipt, handles tax compliance, and processes payments and refunds on our behalf.</p>
            <p>When a refund is issued it goes through Paddle's system. Your bank statement may show the refund from Paddle rather than IntelShift — this is normal, and the amount will always match what you originally paid.</p>
            <p>You can also contact <a href="https://paddle.com/support" target="_blank" rel="noopener">Paddle's support</a> directly for payment queries. As Merchant of Record, Paddle applies its own buyer terms and may make refund decisions independently.</p>
          </div>

          {/* <!-- EU RIGHTS --> */}
          <div className="refund-section">
            <h2>Your statutory rights</h2>
            <div className="eu-box">
              <div className="eu-flag" aria-hidden="true">🇪🇺</div>
              <div>
                <h4>EU &amp; EEA consumers — 14-day right of withdrawal</h4>
                <p>Under the EU Consumer Rights Directive, consumers generally have a 14-day right to withdraw from a distance contract. For digital services, this right is <strong>lost once the service begins</strong> if you gave prior express consent to immediate performance and acknowledged losing the right — which you do at checkout. Where the right still applies to you and has not been validly waived, we honour it. Contact <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> within 14 days of purchase.</p>
              </div>
            </div>
            <div className="eu-box" style={{ marginTop: '12px' }}>
              <div className="eu-flag" aria-hidden="true">🇬🇧</div>
              <div>
                <h4>UK consumers</h4>
                <p>UK consumers have equivalent protections under the Consumer Contracts Regulations 2013. As with the EU, the 14-day cancellation right for a digital service can be lost once supply begins with your express consent. Where it applies and has not been waived, contact <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> to exercise it.</p>
              </div>
            </div>
            <p style={{ marginTop: '16px' }}>Nothing in this policy removes any statutory right you have that cannot be waived by contract. Where such a right applies, it takes precedence over the general terms above.</p>
          </div>

          {/* <!-- CANCELLATION --> */}
          <div className="refund-section">
            <h2>Cancellation vs. refund</h2>
            <p>These are two separate things:</p>
            <ul>
              <li><strong>Cancellation</strong> stops future billing. Your account stays active until the end of the current paid period, and no refund is issued for that period.</li>
              <li><strong>Refund</strong> returns money you've already paid, and is only issued where this policy or a statutory right applies.</li>
            </ul>
            <p>You can cancel anytime from your account's Billing &amp; Usage settings, or by emailing us. To request a refund, follow the steps above.</p>
          </div>

          {/* <!-- CONTACT BOX --> */}
          <div className="contact-box">
            <div className="contact-box-text">
              <h3>Questions about billing?</h3>
              <p>Email us at <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> and we'll help within 1–3 business days. No hoops, no lengthy forms.</p>
            </div>
            <a href="mailto:info@intelshift.ai?subject=Refund request" className="btn-contact">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
              Contact billing support
            </a>
          </div>

        </div>
      </div>
    </>
  );
}

export default Refund;
