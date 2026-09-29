import { useEffect } from "react";
import { Link } from "react-router";

import './terms.css';
import SEO from '../../components/seo/SEO';

function Terms() {
    useEffect(() => { const tocLinks = document.querySelectorAll(".toc-list a"); const sections = document.querySelectorAll(".legal-section"); const observer = new IntersectionObserver((entries) => { entries.forEach(e => { if (e.isIntersecting) { tocLinks.forEach(l => l.classList.remove("active")); const active = document.querySelector(`.toc-list a[href="#${e.target.id}"]`); if (active) active.classList.add("active"); } }) }, { threshold: 0.25, rootMargin: "-80px 0px -60% 0px" }); sections.forEach(s => observer.observe(s)); return () => observer.disconnect(); }, []);
    return (
        <>
            <SEO
                title="Terms of Service"
                description="Read IntelShift's terms of service. Understand your rights and obligations when using our AI-powered competitor intelligence platform."
                canonical="/terms"
                noIndex={false}
            />
            {/* <!-- HERO --> */}
            <div className="legal-hero">
                <div className="container">
                    <div className="legal-hero-inner">
                        <div className="legal-hero-tag">Legal</div>
                        <h1>Terms & Conditions</h1>
                        <p>These terms govern your use of IntelShift. By creating an account or using the Service, you agree to be bound by these terms. Please read them carefully before using IntelShift.</p>
                        <div className="legal-meta">
                            <div className="legal-meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
                                Last updated: July 26, 2026
                            </div>
                            <div className="legal-meta-item">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                                Effective: July 26, 2026
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* <!-- LAYOUT --> */}
            <div className="container">
                <div className="legal-layout">

                    {/* <!-- TOC --> */}
                    <aside className="legal-toc">
                        <div className="toc-label">On this page</div>
                        <ul className="toc-list">
                            <li><a href="#agreement">Agreement</a></li>
                            <li><a href="#definitions">Definitions</a></li>
                            <li><a href="#eligibility">Eligibility</a></li>
                            <li><a href="#accounts">Accounts</a></li>
                            <li><a href="#service">The Service</a></li>
                            <li><a href="#subscriptions">Subscriptions</a></li>
                            <li><a href="#paddle-billing">Billing &amp; Paddle</a></li>
                            <li><a href="#free-trial">Free trial</a></li>
                            <li><a href="#refunds">Refunds</a></li>
                            <li><a href="#acceptable-use">Acceptable use</a></li>
                            <li><a href="#monitoring-rules">Monitoring rules</a></li>
                            <li><a href="#ip">Intellectual property</a></li>
                            <li><a href="#your-data">Your data</a></li>
                            <li><a href="#ai-content">AI-generated content</a></li>
                            <li><a href="#confidentiality">Confidentiality</a></li>
                            <li><a href="#disclaimers">Disclaimers</a></li>
                            <li><a href="#liability">Limitation of liability</a></li>
                            <li><a href="#indemnification">Indemnification</a></li>
                            <li><a href="#termination">Termination</a></li>
                            <li><a href="#governing-law">Governing law</a></li>
                            <li><a href="#disputes">Dispute resolution</a></li>
                            <li><a href="#changes-terms">Changes</a></li>
                            <li><a href="#contact-terms">Contact</a></li>
                        </ul>
                        <div className="toc-divider"></div>
                        <Link to="/privacy" className="toc-back">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6" /></svg>
                            Privacy Policy
                        </Link>
                        <Link to="/" className="toc-back">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
                            Back to home
                        </Link>
                    </aside>

                    {/* <!-- CONTENT --> */}
                    <main className="legal-content">

                        <div className="legal-notice">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
                            <p><strong>Important:</strong> These Terms constitute a legally binding agreement. By registering for or using IntelShift, you confirm you have read, understood, and accepted these Terms. If you do not agree, do not use the Service. If you are using IntelShift on behalf of an organisation, you confirm you have authority to bind that organisation to these Terms.</p>
                        </div>

                        {/* <!-- 1. AGREEMENT --> */}
                        <section className="legal-section" id="agreement">
                            <h2>1. Agreement to terms</h2>
                            <p>These Terms and Conditions ("<strong>Terms</strong>") govern your access to and use of the IntelShift platform, including the website at <a href="https://intelshift.ai">intelshift.ai</a>, the web application, APIs, intelligence reports, alerts, and all related features (collectively, the "<strong>Service</strong>") provided by IntelShift ("<strong>IntelShift</strong>", "<strong>we</strong>", "<strong>us</strong>", or "<strong>our</strong>").</p>
                            <p>These Terms apply to all users, including visitors, registered users, free trial participants, and paid subscribers. Your use of the Service constitutes acceptance of these Terms and our <a href="./privacy.html">Privacy Policy</a>, which is incorporated herein by reference.</p>
                            {/* <!-- REPLACE: insert full legal entity name and jurisdiction once registered --> */}
                        </section>

                        {/* <!-- 2. DEFINITIONS --> */}
                        <section className="legal-section" id="definitions">
                            <h2>2. Definitions</h2>
                            <ul>
                                <li><strong>"Service"</strong> — The IntelShift platform, website, application, APIs, and all features described herein.</li>
                                <li><strong>"User" / "you"</strong> — Any individual or entity accessing or using the Service.</li>
                                <li><strong>"Account"</strong> — A registered user account granting access to the Service.</li>
                                <li><strong>"Workspace"</strong> — The isolated environment within your account where competitor monitoring is configured and intelligence is stored.</li>
                                <li><strong>"Competitor Data"</strong> — Publicly available web content crawled from competitor URLs you configure within the Service.</li>
                                <li><strong>"Intelligence"</strong> — AI-generated insights, impact scores, and recommendations derived from Competitor Data.</li>
                                <li><strong>"Plan"</strong> — A paid subscription tier (Starter, Growth, or Pro) governing usage limits and features.</li>
                                <li><strong>"Paddle"</strong> — Paddle.com Market Limited, our payment processor and Merchant of Record.</li>
                                <li><strong>"Content"</strong> — All information, data, text, or materials submitted to or generated by the Service.</li>
                            </ul>
                        </section>

                        {/* <!-- 3. ELIGIBILITY --> */}
                        <section className="legal-section" id="eligibility">
                            <h2>3. Eligibility</h2>
                            <p>To use IntelShift, you must:</p>
                            <ul>
                                <li>Be at least 18 years of age (or the age of majority in your jurisdiction, whichever is higher)</li>
                                <li>Have the legal capacity to enter into binding contracts</li>
                                <li>Not be prohibited from using the Service under applicable law</li>
                                <li>Not be located in a country subject to applicable trade sanctions or embargoes that would prevent use of the Service</li>
                            </ul>
                            <p>If you are using IntelShift on behalf of a company or other legal entity, you represent and warrant that you have the authority to bind that entity to these Terms.</p>
                        </section>

                        {/* <!-- 4. ACCOUNTS --> */}
                        <section className="legal-section" id="accounts">
                            <h2>4. Accounts and registration</h2>
                            <p>You must register for an account to use IntelShift. When registering, you agree to:</p>
                            <ul>
                                <li>Provide accurate, complete, and current information</li>
                                <li>Maintain and promptly update your account information as necessary</li>
                                <li>Keep your login credentials confidential and not share them with third parties</li>
                                <li>Notify us immediately at <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> if you become aware of any unauthorised use of your account</li>
                                <li>Be responsible for all activity that occurs under your account</li>
                            </ul>
                            <p>One account may be used by one individual unless you are on a plan that explicitly permits team access. You may not create multiple accounts to circumvent plan limits.</p>
                            <p>We reserve the right to refuse registration, suspend, or terminate accounts at our sole discretion if we determine that information is inaccurate, that these Terms have been violated, or that use is otherwise harmful.</p>
                        </section>

                        {/* <!-- 5. SERVICE --> */}
                        <section className="legal-section" id="service">
                            <h2>5. The Service</h2>
                            <p>IntelShift provides an AI-powered competitor intelligence platform that:</p>
                            <ul>
                                <li>Monitors publicly accessible competitor web pages you configure</li>
                                <li>Detects and scores meaningful changes to competitor pricing, messaging, product pages, and other public content</li>
                                <li>Generates AI-powered insights, impact scores, and recommended actions</li>
                                <li>Delivers intelligence via dashboard, email alerts, and periodic reports</li>
                            </ul>
                            <p>The Service is provided on an "as is" basis subject to the availability, features, and limits of your selected Plan.</p>
                            <div className="highlight-box accent">
                                <h4>What IntelShift does not do</h4>
                                <p>IntelShift does not access, monitor, or process content behind authentication (logins), paywalls, or private systems. We monitor only publicly accessible web pages. We do not guarantee the completeness or accuracy of all changes on competitor websites.</p>
                            </div>
                            <p>We may update, modify, add, or remove features of the Service at any time. Where changes materially reduce functionality, we will provide reasonable notice.</p>
                        </section>

                        {/* <!-- 6. SUBSCRIPTIONS --> */}
                        <section className="legal-section" id="subscriptions">
                            <h2>6. Subscriptions and plans</h2>
                            <p>IntelShift is offered on a subscription basis. Your access to the Service is governed by the Plan you select at signup or most recently upgraded/downgraded to.</p>

                            <h3>Plan limits</h3>
                            <table className="plan-table">
                                <thead>
                                    <tr><th>Plan</th><th>Competitors</th><th>Pages/Competitor</th><th>Monitoring</th><th>History</th></tr>
                                </thead>
                                <tbody>
                                    <tr><td><strong>Starter</strong></td><td>2</td><td>5</td><td>Weekly</td><td>Standard</td></tr>
                                    <tr><td><strong>Growth</strong></td><td>5</td><td>10</td><td>Every 3 days</td><td>Full timeline</td></tr>
                                    <tr><td><strong>Pro</strong></td><td>10</td><td>25</td><td>Every 2 days</td><td>Advanced</td></tr>
                                </tbody>
                            </table>

                            <h3>Plan changes</h3>
                            <ul>
                                <li><strong>Upgrades</strong> take effect immediately. The difference in cost is prorated for the remaining billing period.</li>
                                <li><strong>Downgrades</strong> take effect at the end of the current billing period. Existing data within the higher-plan limits is preserved until the new limits apply.</li>
                                <li>Exceeding plan limits may result in suspension of monitoring until the account is upgraded or the limit period resets.</li>
                            </ul>
                        </section>

                        {/* <!-- 7. BILLING & PADDLE --> */}
                        <section className="legal-section" id="paddle-billing">
                            <h2>7. Billing and payments — Paddle</h2>

                            <div className="highlight-box dark">
                                <h4>Paddle is our Merchant of Record</h4>
                                <p>
                                    All purchases of IntelShift subscriptions are processed by{" "}
                                    <strong>Paddle.com Market Limited</strong>, acting as our Merchant of
                                    Record. This means Paddle is the seller of record for billing,
                                    invoicing, tax collection, and payment processing purposes. Your
                                    contract for payment is with Paddle, subject to their{" "}
                                    <a
                                        href="https://www.paddle.com/legal/terms"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: "var(--secondary)" }}
                                    >
                                        Terms of Service
                                    </a>{" "}
                                    and{" "}
                                    <a
                                        href="https://www.paddle.com/legal/privacy"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: "var(--secondary)" }}
                                    >
                                        Privacy Policy
                                    </a>.
                                </p>                            </div>

                            <h3>7.1 Billing cycle</h3>
                            <p>Subscriptions are billed monthly in advance, on the same date each month as your original sign-up date. Paddle will charge your payment method automatically at the start of each billing cycle.</p>

                            <h3>7.2 Taxes</h3>
                            <p>Paddle handles all applicable taxes, including VAT, GST, and sales tax, depending on your location. The price displayed at checkout is inclusive of all applicable taxes. Paddle is responsible for remitting these taxes to the appropriate authorities.</p>

                            <h3>7.3 Failed payments</h3>
                            <p>If a payment fails, Paddle will attempt to retry the charge. After repeated failed attempts, your account may be suspended. You will receive email notifications from Paddle regarding payment issues. Access to the Service will be restored upon successful payment.</p>

                            <h3>7.4 Currency</h3>
                            <p>Subscriptions are priced in US Dollars (USD). Paddle may display local currency equivalents. Exchange rates and currency conversion fees may apply depending on your bank or card issuer.</p>
                        </section>

                        {/* <!-- 8. FREE TRIAL --> */}
                        <section className="legal-section" id="free-trial">
                            <h2>8. Free trial</h2>
                            <p>IntelShift offers a free trial that allows you to monitor 1 competitor across up to 10 pages with no payment required. The free trial is subject to the following conditions:</p>
                            <ul>
                                <li>No credit card is required to start the free trial</li>
                                <li>Free trial accounts are limited to 1 workspace, 1 competitor, and up to 10 pages</li>
                                <li>Free trial duration is determined at our discretion and may change without notice</li>
                                <li>One free trial per person or organisation — creating multiple accounts to extend trial access is prohibited</li>
                                <li>We reserve the right to modify or discontinue the free trial at any time</li>
                            </ul>
                            <p>To continue using IntelShift after your trial, you must subscribe to a paid Plan. Trial data (competitor snapshots and insights generated during the trial) will be available on your account when you upgrade.</p>
                        </section>

                        {/* <!-- 9. REFUNDS --> */}
                        <section className="legal-section" id="refunds">
                            <h2>9. Refunds and right of withdrawal</h2>
                            <p>IntelShift is a digital service offered with a free trial, so you can evaluate it before you pay. Accordingly, <strong>subscription fees are non-refundable except where required by law</strong> or as set out below. Full details are in our <a href="/refund">Refund Policy</a>.</p>

                            <h3>9.1 Immediate performance and withdrawal</h3>
                            <p>When you subscribe, you expressly request that we begin providing the Service (competitor monitoring) immediately, and you acknowledge that once the Service has begun you lose any statutory 14-day right of withdrawal that would otherwise apply to a distance contract for digital services (EU Consumer Rights Directive 2011/83/EU, as amended, and the UK Consumer Contracts Regulations 2013). This consent and acknowledgement are captured at checkout.</p>

                            <h3>9.2 When refunds may be issued</h3>
                            <ul>
                                <li><strong>Statutory rights:</strong> Where a non-waivable consumer right requires a refund in your jurisdiction, we honour it.</li>
                                <li><strong>Billing errors:</strong> Duplicate charges, incorrect amounts, or unauthorised charges will be refunded.</li>
                                <li><strong>Material failure:</strong> Where the Service was materially unavailable or defective and we were unable to resolve it, we will consider a refund on a case-by-case basis.</li>
                            </ul>

                            <h3>9.3 What is not refundable</h3>
                            <ul>
                                <li>Change of mind after the Service has started</li>
                                <li>Renewal charges — cancel before the renewal date to avoid the next period's charge</li>
                                <li>Unused time remaining after a mid-period cancellation</li>
                                <li>Accounts suspended or terminated for breach of these Terms</li>
                            </ul>

                            <h3>9.4 How to request</h3>
                            <p>Contact us at <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> with the subject line "Refund request". We review requests within 1–3 business days. Approved refunds are issued through Paddle to your original payment method and may take 5–10 business days to appear.</p>
                            <p>Cancelling your subscription stops future charges but does not automatically trigger a refund for the current billing period. Access continues until the end of the paid period.</p>
                        </section>

                        {/* <!-- 10. ACCEPTABLE USE --> */}
                        <section className="legal-section" id="acceptable-use">
                            <h2>10. Acceptable use policy</h2>
                            <p>You agree to use IntelShift only for lawful purposes and in accordance with these Terms. You must not:</p>
                            <ul>
                                <li>Use the Service to monitor pages you do not have legitimate business reason to analyse (e.g., personal individuals' websites, private individuals' social profiles)</li>
                                <li>Attempt to access, monitor, or extract content from pages behind authentication, paywalls, or private systems</li>
                                <li>Use the Service in any way that violates applicable laws, regulations, or third-party rights</li>
                                <li>Circumvent, disable, or interfere with security features of the Service or any linked website</li>
                                <li>Attempt to gain unauthorised access to the Service, other accounts, or IntelShift's systems</li>
                                <li>Use automated scripts, bots, or crawlers to access the Service (other than through our authorised API)</li>
                                <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
                                <li>Resell, sublicense, or redistribute the Service or intelligence generated by it to third parties without our written consent</li>
                                <li>Use the Service to harass, stalk, or cause harm to any individual or organisation</li>
                                <li>Upload or transmit malicious code, viruses, or any content that could damage our systems or those of other users</li>
                                <li>Misrepresent your identity or affiliation to gain access to the Service</li>
                            </ul>
                            <div className="highlight-box warn">
                                <h4>Violation consequences</h4>
                                <p>Violations of this Acceptable Use Policy may result in immediate suspension or termination of your account, without refund, and may expose you to legal liability where applicable law has been breached.</p>
                            </div>
                        </section>

                        {/* <!-- 11. MONITORING RULES --> */}
                        <section className="legal-section" id="monitoring-rules">
                            <h2>11. Competitor monitoring — rules and responsibilities</h2>
                            <p>IntelShift is designed to monitor <strong>publicly accessible competitor websites</strong> for legitimate competitive intelligence purposes. By using the monitoring features of the Service, you agree that:</p>
                            <ul>
                                <li><strong>Public pages only:</strong> You will only configure IntelShift to monitor URLs that are publicly accessible without authentication. You will not attempt to add or monitor pages that require login, subscription, or other credentials.</li>
                                <li><strong>Legitimate business purpose:</strong> You will only monitor competitors or market participants for genuine competitive intelligence, market research, or business strategy purposes.</li>
                                <li><strong>Compliance with target website terms:</strong> While IntelShift monitors pages on your behalf, you acknowledge that the act of crawling may be subject to terms of service of the monitored website. IntelShift uses responsible crawling practices including robots.txt compliance, but you accept responsibility for ensuring your use is consistent with applicable laws in your jurisdiction.</li>
                                <li><strong>No unlawful competitive conduct:</strong> Intelligence gathered through IntelShift must not be used in furtherance of unlawful competitive practices, including corporate espionage, tortious interference, or violations of trade secret laws.</li>
                            </ul>
                            <p>IntelShift is not responsible for the content of competitor websites, the accuracy of publicly available information, or any business decisions made based on intelligence derived from the Service.</p>
                        </section>

                        {/* <!-- 12. IP --> */}
                        <section className="legal-section" id="ip">
                            <h2>12. Intellectual property</h2>

                            <h3>12.1 IntelShift's intellectual property</h3>
                            <p>IntelShift and its licensors own all right, title, and interest in and to the Service, including but not limited to the software, platform, algorithms, AI models, brand, trademarks, logos, design, documentation, and all related intellectual property rights. Nothing in these Terms grants you any ownership rights in the Service.</p>
                            <p>Subject to your compliance with these Terms and payment of applicable subscription fees, we grant you a limited, non-exclusive, non-transferable, revocable licence to access and use the Service solely for your internal business purposes.</p>

                            <h3>12.2 Your content and data</h3>
                            <p>You retain ownership of all data, competitor URLs, and configuration you submit to the Service ("<strong>Your Content</strong>"). You grant IntelShift a limited licence to use Your Content solely to provide, maintain, and improve the Service for your account.</p>
                            <p>You represent and warrant that you have all necessary rights to submit Your Content to the Service and that doing so does not violate any third-party rights or applicable law.</p>

                            <h3>12.3 Intelligence output</h3>
                            <p>AI-generated intelligence, reports, alerts, and insights produced by the Service for your account ("<strong>Intelligence Output</strong>") are made available to you for your internal business use. You may share Intelligence Output internally within your organisation. You may not resell, publicly publish, or commercially distribute Intelligence Output without our prior written consent.</p>

                            <h3>12.4 Feedback</h3>
                            <p>If you submit suggestions, ideas, or feedback about the Service, you grant us a worldwide, perpetual, irrevocable, royalty-free licence to use, incorporate, and build upon that feedback without restriction or compensation to you.</p>
                        </section>

                        {/* <!-- 13. YOUR DATA --> */}
                        <section className="legal-section" id="your-data">
                            <h2>13. Your data and privacy</h2>
                            <p>Our collection and use of personal data is governed by our <a href="./privacy.html">Privacy Policy</a>, which forms part of these Terms. By using the Service, you consent to the data practices described in the Privacy Policy.</p>
                            <p>You are responsible for ensuring you have the right to submit any personal data to the Service, and that doing so complies with applicable data protection laws. Where IntelShift processes personal data on your behalf as a data processor, we will do so only in accordance with your instructions and our Data Processing Agreement (available upon request).</p>
                        </section>

                        {/* <!-- 14. AI CONTENT --> */}
                        <section className="legal-section" id="ai-content">
                            <h2>14. AI-generated content and accuracy</h2>
                            <p>IntelShift uses artificial intelligence to generate competitor intelligence insights, interpretations, and recommendations. You acknowledge and agree that:</p>
                            <ul>
                                <li><strong>AI limitations:</strong> AI-generated insights are probabilistic in nature and may contain errors, omissions, or inaccuracies. They are intended to assist your analysis, not replace human judgment.</li>
                                <li><strong>Not professional advice:</strong> Intelligence Output does not constitute legal, financial, strategic, or professional advice. You should independently verify material insights before making significant business decisions.</li>
                                <li><strong>Evolving technology:</strong> AI capabilities and accuracy may evolve over time. We do not warrant that AI outputs will be error-free or achieve any particular outcome for your business.</li>
                                <li><strong>Before-and-after evidence:</strong> While we provide before-and-after evidence for each insight, the crawled content reflects a point-in-time snapshot and may not represent real-time competitor status.</li>
                            </ul>
                        </section>

                        {/* <!-- 15. CONFIDENTIALITY --> */}
                        <section className="legal-section" id="confidentiality">
                            <h2>15. Confidentiality</h2>
                            <p>Each party may have access to confidential information of the other party. "<strong>Confidential Information</strong>" means any non-public information disclosed by one party to the other that is designated as confidential or that reasonably should be understood to be confidential given the nature of the information.</p>
                            <p>Each party agrees to: (a) keep the other's Confidential Information confidential using at least reasonable care; (b) not disclose it to third parties without prior written consent; and (c) use it only to perform obligations or exercise rights under these Terms.</p>
                            <p>Your IntelShift account data, competitor configuration, and Intelligence Output are treated as your confidential information. We do not share it with other users or third parties except as described in these Terms and our Privacy Policy.</p>
                        </section>

                        {/* <!-- 16. DISCLAIMERS --> */}
                        <section className="legal-section" id="disclaimers">
                            <h2>16. Disclaimers and warranties</h2>
                            <div className="highlight-box warn">
                                <h4>Important disclaimer</h4>
                                <p>THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED. TO THE FULLEST EXTENT PERMITTED BY APPLICABLE LAW, INTELSHIFT DISCLAIMS ALL WARRANTIES, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.</p>
                            </div>
                            <p>Without limiting the foregoing, we do not warrant that:</p>
                            <ul>
                                <li>The Service will meet your specific requirements or produce particular business outcomes</li>
                                <li>The Service will be uninterrupted, timely, secure, or error-free at all times</li>
                                <li>Intelligence Output will be accurate, complete, or reliable for any particular purpose</li>
                                <li>All competitor website changes will be detected — our monitoring is thorough but not exhaustive</li>
                                <li>Any defects or errors in the Service will be corrected within a specific timeframe</li>
                            </ul>
                            <p>Some jurisdictions do not allow the exclusion of implied warranties. In such cases, the above exclusions apply to the maximum extent permitted by applicable law.</p>
                        </section>

                        {/* <!-- 17. LIABILITY --> */}
                        <section className="legal-section" id="liability">
                            <h2>17. Limitation of liability</h2>
                            <p>TO THE FULLEST EXTENT PERMITTED BY APPLICABLE LAW:</p>
                            <ul>
                                <li>IN NO EVENT SHALL INTELSHIFT, ITS DIRECTORS, EMPLOYEES, PARTNERS, OR SUPPLIERS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, REVENUE, DATA, GOODWILL, OR BUSINESS OPPORTUNITIES, ARISING FROM YOUR USE OF OR INABILITY TO USE THE SERVICE.</li>
                                <li>INTELSHIFT'S TOTAL CUMULATIVE LIABILITY TO YOU FOR ANY CLAIMS ARISING OUT OF OR RELATED TO THESE TERMS OR THE SERVICE SHALL NOT EXCEED THE GREATER OF: (A) THE TOTAL AMOUNT YOU PAID TO INTELSHIFT IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM, OR (B) ONE HUNDRED US DOLLARS (USD $100).</li>
                            </ul>
                            <p>These limitations apply regardless of the theory of liability (contract, tort, negligence, strict liability, or otherwise) and even if IntelShift has been advised of the possibility of such damages.</p>
                            <p>Some jurisdictions do not allow limitations on liability for certain types of damages. In such cases, the above limitations apply to the maximum extent permitted by law. Nothing in these Terms limits liability for death or personal injury caused by negligence, fraud, or any other liability that cannot be excluded by law.</p>
                        </section>

                        {/* <!-- 18. INDEMNIFICATION --> */}
                        <section className="legal-section" id="indemnification">
                            <h2>18. Indemnification</h2>
                            <p>You agree to defend, indemnify, and hold harmless IntelShift, its affiliates, directors, employees, and agents from and against any claims, liabilities, damages, losses, and expenses (including reasonable legal fees) arising out of or in any way connected with:</p>
                            <ul>
                                <li>Your use of the Service in violation of these Terms</li>
                                <li>Your violation of any third-party rights, including intellectual property rights or privacy rights</li>
                                <li>Your violation of any applicable law or regulation</li>
                                <li>Any content or competitor URLs you submit to the Service</li>
                                <li>Any claim that your use of IntelShift caused harm to a third party</li>
                            </ul>
                            <p>IntelShift reserves the right to assume the exclusive defence and control of any matter subject to indemnification by you, at your expense. You agree to cooperate with our defence of such claims.</p>
                        </section>

                        {/* <!-- 19. TERMINATION --> */}
                        <section className="legal-section" id="termination">
                            <h2>19. Termination</h2>

                            <h3>19.1 Termination by you</h3>
                            <p>You may cancel your IntelShift subscription at any time through your account settings or by contacting Paddle's support. Cancellation takes effect at the end of the current billing period. You will retain access to the Service until that date.</p>

                            <h3>19.2 Termination or suspension by IntelShift</h3>
                            <p>We may suspend or terminate your account immediately, with or without notice, if:</p>
                            <ul>
                                <li>You materially breach these Terms and fail to cure the breach within 7 days of written notice</li>
                                <li>You violate the Acceptable Use Policy in a serious or repeated manner</li>
                                <li>Your use of the Service poses a risk to security, integrity, or other users</li>
                                <li>Payment is overdue and remains uncured after Paddle's collection attempts</li>
                                <li>We are required to do so by law or regulatory authority</li>
                            </ul>

                            <h3>19.3 Effect of termination</h3>
                            <p>Upon termination:</p>
                            <ul>
                                <li>Your right to access the Service ceases immediately (or at end of paid period for voluntary cancellation)</li>
                                <li>Your account data and intelligence history will be retained for up to 90 days before permanent deletion, in accordance with our Privacy Policy</li>
                                <li>You may export your data within the 90-day window by contacting <a href="mailto:info@intelshift.ai">info@intelshift.ai</a></li>
                                <li>Accrued payment obligations survive termination</li>
                                <li>Provisions of these Terms that by their nature should survive termination shall do so, including intellectual property, disclaimers, limitations of liability, indemnification, and governing law</li>
                            </ul>
                        </section>

                        {/* <!-- 20. GOVERNING LAW --> */}
                        <section className="legal-section" id="governing-law">
                            <h2>20. Governing law</h2>
                            {/* <!-- REPLACE: update with the jurisdiction where IntelShift is incorporated once confirmed --> */}
                            <p>These Terms and any disputes arising out of or related to them or the Service shall be governed by and construed in accordance with the laws of the jurisdiction in which IntelShift is incorporated, without regard to conflict of law principles.</p>
                            <p>Where local mandatory consumer protection or data protection laws apply in your jurisdiction and provide you with rights that cannot be waived by contract, those rights are not affected by this clause.</p>
                            <p>For users in the European Union: Nothing in these Terms limits your rights under EU consumer protection laws, including the EU Consumer Rights Directive (2011/83/EU) and applicable national implementing legislation.</p>
                        </section>

                        {/* <!-- 21. DISPUTES --> */}
                        <section className="legal-section" id="disputes">
                            <h2>21. Dispute resolution</h2>

                            <h3>21.1 Informal resolution</h3>
                            <p>Before initiating any formal proceeding, you agree to first contact IntelShift at <a href="mailto:info@intelshift.ai">info@intelshift.ai</a> with a written description of the dispute and your preferred resolution. We will attempt to resolve the issue within 30 days of receiving your notice.</p>

                            <h3>21.2 Formal proceedings</h3>
                            <p>If informal resolution fails, disputes may be brought in the competent courts of IntelShift's jurisdiction of incorporation. For EU/EEA users, you may also bring claims in the courts of your country of residence where required by EU consumer law.</p>

                            <h3>21.3 EU Online Dispute Resolution</h3>
                            <p>If you are an EU consumer and have a dispute with us related to a transaction made through Paddle, you may use the European Commission's Online Dispute Resolution platform at <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener">ec.europa.eu/consumers/odr</a>.</p>

                            <h3>21.4 No class actions</h3>
                            <p>To the extent permitted by applicable law, you agree that any dispute resolution proceedings will be conducted on an individual basis and not in a class, consolidated, or representative action. This does not apply where prohibited by law, including for EU consumers.</p>
                        </section>

                        {/* <!-- 22. CHANGES --> */}
                        <section className="legal-section" id="changes-terms">
                            <h2>22. Changes to these Terms</h2>
                            <p>We may modify these Terms at any time. When we do:</p>
                            <ul>
                                <li>We will update the "Last updated" date at the top of this page</li>
                                <li>For material changes, we will notify you via email and/or a prominent in-app notice at least 14 days before the changes take effect</li>
                                <li>Your continued use of the Service after the effective date constitutes acceptance of the revised Terms</li>
                                <li>If you do not agree to revised Terms, you must stop using the Service before the effective date</li>
                            </ul>
                            <p>Non-material changes (such as clarifications, typographical corrections, or updates to reflect new features) may take effect immediately.</p>
                        </section>

                        {/* <!-- 23. GENERAL --> */}
                        <section className="legal-section" id="general">
                            <h2>23. General provisions</h2>
                            <ul>
                                <li><strong>Entire agreement:</strong> These Terms, together with the Privacy Policy and any order confirmation from Paddle, constitute the entire agreement between you and IntelShift regarding the Service and supersede all prior agreements.</li>
                                <li><strong>Severability:</strong> If any provision of these Terms is found to be unenforceable, the remaining provisions will continue in full force and effect.</li>
                                <li><strong>Waiver:</strong> Failure by IntelShift to enforce any right or provision of these Terms shall not constitute a waiver of that right or provision.</li>
                                <li><strong>Assignment:</strong> You may not assign or transfer your rights under these Terms without our written consent. We may assign our rights and obligations without restriction.</li>
                                <li><strong>Force majeure:</strong> Neither party shall be liable for failure to perform due to circumstances beyond their reasonable control, including natural disasters, internet outages, government actions, or pandemics.</li>
                                <li><strong>No agency:</strong> Nothing in these Terms creates a partnership, joint venture, employment, or agency relationship between you and IntelShift.</li>
                                <li><strong>Notices:</strong> We will send notices to the email address on your account. You may send notices to us at <a href="mailto:legal@intelshift.ai">legal@intelshift.ai</a>.</li>
                            </ul>
                        </section>

                        {/* <!-- 24. CONTACT --> */}
                        <section className="legal-section" id="contact-terms">
                            <h2>24. Contact us</h2>
                            <p>If you have any questions about these Terms, please contact us:</p>
                            <div className="contact-box">
                                <h3>Legal enquiries</h3>
                                <p>For questions about these Terms, account issues, data requests, or billing disputes, we're here to help.</p>
                                <div className="contact-details">
                                    {/* <!-- REPLACE: update with verified legal entity and address once registered --> */}
                                    <div className="contact-detail">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                                        General: <a href="mailto:info@intelshift.ai">info@intelshift.ai</a>
                                    </div>
                                    <div className="contact-detail">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                                        Legal: <a href="mailto:legal@intelshift.ai">legal@intelshift.ai</a>
                                    </div>
                                    <div className="contact-detail">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                                        Privacy: <a href="mailto:privacy@intelshift.ai">privacy@intelshift.ai</a>
                                    </div>
                                    <div className="contact-detail">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 010 20M12 2a15.3 15.3 0 000 20" /></svg>
                                                   <a href="https://intelshift.ai">intelshift.ai</a>
                                    </div>
                                </div>
                            </div>
                        </section>
                    </main>
                </div>
            </div>
        </>
    );
}

export default Terms;
