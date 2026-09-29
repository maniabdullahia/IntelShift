import { Link } from "react-router";
import { useEffect } from "react";

import './privacy.css';
import SEO from '../../components/seo/SEO';

function PrivacyPolicy() {
  useEffect(() => {
    const links=document.querySelectorAll(".toc-list a");
    const sections=document.querySelectorAll(".legal-section");
    const observer=new IntersectionObserver((entries)=>{entries.forEach(e=>{if(e.isIntersecting){links.forEach(l=>l.classList.remove("active"));const active=document.querySelector(`.toc-list a[href="#${e.target.id}"]`);if(active)active.classList.add("active");}})},{threshold:0.3,rootMargin:"-80px 0px -60% 0px"});
    sections.forEach(s=>observer.observe(s));
    return ()=>observer.disconnect();
  },[]);
    return (
        <>
            <SEO
                title="Privacy Policy"
                description="Read IntelShift's privacy policy. Learn how we collect, store, and protect your data when you use our competitor intelligence platform."
                canonical="/privacy-policy"
                noIndex={false}
            />
            {/* <!-- HERO --> */}
            <div className="legal-hero">
                <div className="container">
                    <div className="legal-hero-inner">
                        <div className="legal-hero-tag">Legal</div>
                        <h1>Privacy Policy</h1>
                        <p>We take your privacy seriously. This policy explains exactly what data we collect, why we collect it, how we protect it, and the rights you have over it — wherever in the world you are.</p>
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

                    {/* <!-- SIDEBAR TOC --> */}
                    <aside className="legal-toc" aria-label="Table of contents">
                        <div className="toc-label">On this page</div>
                        <ul className="toc-list" role="list">
                            <li><a href="#overview">Overview</a></li>
                            <li><a href="#who-we-are">Who we are</a></li>
                            <li><a href="#data-we-collect">Data we collect</a></li>
                            <li><a href="#how-we-use">How we use your data</a></li>
                            <li><a href="#legal-basis">Legal basis (GDPR)</a></li>
                            <li><a href="#sharing">Data sharing</a></li>
                            <li><a href="#paddle">Payments &amp; Paddle</a></li>
                            <li><a href="#ai-processing">AI processing</a></li>
                            <li><a href="#cookies">Cookies</a></li>
                            <li><a href="#international">International transfers</a></li>
                            <li><a href="#retention">Data retention</a></li>
                            <li><a href="#security">Security</a></li>
                            <li><a href="#your-rights">Your rights</a></li>
                            <li><a href="#gdpr">GDPR (EU/EEA)</a></li>
                            <li><a href="#ccpa">CCPA (California)</a></li>
                            <li><a href="#children">Children's privacy</a></li>
                            <li><a href="#changes">Policy changes</a></li>
                            <li><a href="#contact-privacy">Contact us</a></li>
                        </ul>
                        <div className="toc-divider"></div>
                        <Link to="/terms" className="toc-back">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6" /></svg>
                            Terms &amp; Conditions
                        </Link>
                        <Link to="/" className="toc-back">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
                            Back to home
                        </Link>
                    </aside>

                    {/* <!-- CONTENT --> */}
                    <main className="legal-content">

                        <div className="legal-notice">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                            <p><strong>Plain-language summary:</strong> We collect only what we need to provide IntelShift to you. We do not sell your data. We do not share it with advertisers. Your competitor URLs and intelligence data are yours. We use Paddle as our payment processor — they handle billing independently and have their own privacy obligations.</p>
                        </div>

                        {/* <!-- 1. OVERVIEW --> */}
                        <section className="legal-section" id="overview">
                            <h2>1. Overview</h2>
                            <p>IntelShift ("<strong>IntelShift</strong>", "<strong>we</strong>", "<strong>us</strong>", or "<strong>our</strong>") operates the website at <a href="https://intelshift.ai">intelshift.ai</a> and the IntelShift platform (collectively, the "<strong>Service</strong>"). This Privacy Policy explains how we collect, use, disclose, and protect information about you when you use our Service.</p>
                            <p>By accessing or using IntelShift, you agree to the collection and use of information in accordance with this policy. If you do not agree, please do not use the Service.</p>
                            <div className="highlight-box accent">
                                <h4>Key principle</h4>
                                <p>We collect the minimum data necessary to deliver, improve, and support IntelShift. We do not sell personal data. We do not use your data for advertising. We do not share your competitor intelligence with third parties for their commercial purposes.</p>
                            </div>
                        </section>

                        {/* <!-- 2. WHO WE ARE --> */}
                        <section className="legal-section" id="who-we-are">
                            <h2>2. Who we are</h2>
                            <p>IntelShift is an AI-powered competitor intelligence platform for SaaS and ecommerce teams. Our registered business operates under the domain <strong>intelshift.ai</strong>.</p>
                            {/* <!-- REPLACE: insert full legal entity name, registration number, and registered address once available --> */}
                            <p>For privacy-related enquiries, the data controller is IntelShift. Contact details are provided in the <a href="#contact-privacy">Contact Us</a> section of this policy.</p>
                        </section>

                        {/* <!-- 3. DATA WE COLLECT --> */}
                        <section className="legal-section" id="data-we-collect">
                            <h2>3. Data we collect</h2>

                            <h3>3.1 Information you provide to us</h3>
                            <ul>
                                <li><strong>Account registration:</strong> Name, email address, password (stored hashed), company name, and website URL.</li>
                                <li><strong>Social sign-in (Google / Facebook):</strong> If you register or log in with Google or Facebook, we receive your name, email address, profile picture, and a provider account identifier from that provider. We do not receive your social account password. Your email is treated as verified by the provider, and your profile picture is used only as your account avatar (you can change or remove it in your profile).</li>
                                <li><strong>Competitor configuration:</strong> Competitor URLs, page types you select for monitoring, and industry category. This is core product data required to deliver the Service.</li>
                                <li><strong>Billing information:</strong> Collected and processed exclusively by Paddle (our payment processor). We do not store credit card numbers or full payment details on our servers. See <a href="#paddle">Section 7</a> for details.</li>
                                <li><strong>Support communications:</strong> Any information you share when contacting us via email or support channels.</li>
                                <li><strong>Profile and preferences:</strong> Notification preferences, reporting frequency settings, and workspace configuration.</li>
                            </ul>

                            <h3>3.2 Information collected automatically</h3>
                            <ul>
                                <li><strong>Usage data:</strong> Pages visited within the application, features used, session duration, actions taken (e.g., adding competitors, viewing reports), and frequency of use.</li>
                                <li><strong>Device and browser data:</strong> IP address, browser type and version, operating system, screen resolution, and referring URL.</li>
                                <li><strong>Log data:</strong> Server logs recording access times, errors, and API requests. Retained for security and debugging purposes.</li>
                                <li><strong>Cookies and similar technologies:</strong> See <a href="#cookies">Section 9</a> for full details.</li>
                            </ul>

                            <h3>3.3 Information we do not collect</h3>
                            <ul>
                                <li>We do not collect data from competitor websites on behalf of ourselves — the crawled content is stored solely for your account's intelligence delivery.</li>
                                <li>We do not collect sensitive personal data (e.g., health, racial origin, political opinions, biometric data).</li>
                                <li>We do not knowingly collect data from individuals under 18 years of age.</li>
                                <li>We do not access pages behind authentication or collect data from private competitor systems.</li>
                            </ul>
                        </section>

                        {/* <!-- 4. HOW WE USE --> */}
                        <section className="legal-section" id="how-we-use">
                            <h2>4. How we use your data</h2>
                            <p>We use the data we collect for the following purposes:</p>
                            <ul>
                                <li><strong>Service delivery:</strong> To create and manage your account, monitor competitor pages you configure, generate AI insights and reports, and send alerts based on your plan.</li>
                                <li><strong>Service improvement:</strong> To understand how users interact with IntelShift, identify bugs, and develop new features. Usage analytics are aggregated and anonymised where possible.</li>
                                <li><strong>Communication:</strong> To send intelligence reports, alerts, product update notifications, and support responses. You may opt out of non-essential communications at any time.</li>
                                <li><strong>Billing and account management:</strong> To process subscriptions, manage plan limits, send receipts, and handle upgrades, downgrades, or cancellations through Paddle.</li>
                                <li><strong>Security and fraud prevention:</strong> To detect and prevent abuse, unauthorised access, and violations of our Terms of Service.</li>
                                <li><strong>Legal compliance:</strong> To comply with applicable laws, regulations, and lawful requests from authorities.</li>
                            </ul>
                            <div className="highlight-box warn">
                                <h4>What we never do</h4>
                                <p>We never sell your personal data. We never use your competitor URLs or intelligence data to train AI models for external sale or benefit. We never share your account data with advertisers or data brokers.</p>
                            </div>
                        </section>

                        {/* <!-- 5. LEGAL BASIS --> */}
                        <section className="legal-section" id="legal-basis">
                            <h2>5. Legal basis for processing (GDPR)</h2>
                            <p>If you are in the European Union or European Economic Area, we rely on the following legal bases under the General Data Protection Regulation (GDPR):</p>
                            <ul>
                                <li><strong>Contract performance (Art. 6(1)(b)):</strong> Processing necessary to deliver the IntelShift Service under the terms you agreed to — including account management, competitor monitoring, reporting, and billing.</li>
                                <li><strong>Legitimate interests (Art. 6(1)(f)):</strong> Security monitoring, fraud prevention, product analytics (aggregated), and improving the Service. We balance this against your rights and interests.</li>
                                <li><strong>Legal obligation (Art. 6(1)(c)):</strong> Where we are required to process data to comply with applicable law.</li>
                                <li><strong>Consent (Art. 6(1)(a)):</strong> For optional cookies and marketing communications. You may withdraw consent at any time without affecting the lawfulness of prior processing.</li>
                            </ul>
                        </section>

                        {/* <!-- 6. SHARING --> */}
                        <section className="legal-section" id="sharing">
                            <h2>6. Data sharing and disclosure</h2>
                            <p>We do not sell, rent, or trade your personal data. We share it only in the following limited circumstances:</p>

                            <h3>6.1 Service providers (data processors)</h3>
                            <p>We engage trusted third-party providers who process data on our behalf under binding data processing agreements:</p>
                            <ul>
                                <li><strong>Paddle.com:</strong> Payment processing and subscription management. Acts as Merchant of Record. See <a href="#paddle">Section 7</a>.</li>
                                <li><strong>Cloud infrastructure providers:</strong> Hosting, storage, and database services.</li>
                                <li><strong>AI model providers:</strong> For generating competitor intelligence interpretations. Data sent is limited to detected page-change content and is not used to train external models under our agreements. See <a href="#ai-processing">Section 8</a>.</li>
                                <li><strong>Email delivery services:</strong> For sending intelligence reports, alerts, and transactional emails.</li>
                                <li><strong>Analytics tools:</strong> Aggregated, anonymised usage data to understand product performance.</li>
                            </ul>

                            <h3>6.2 Legal requirements</h3>
                            <p>We may disclose your information if required to do so by law, court order, or governmental authority, or where we believe in good faith that disclosure is necessary to protect the rights, property, or safety of IntelShift, our users, or the public.</p>

                            <h3>6.3 Business transfers</h3>
                            <p>In the event of a merger, acquisition, or sale of all or a portion of our assets, your data may be transferred as part of that transaction. We will notify you via email or prominent notice on the Service before your data becomes subject to a different privacy policy.</p>

                            <h3>6.4 With your consent</h3>
                            <p>We may share your data with third parties in any other circumstance where you have given explicit consent.</p>
                        </section>

                        {/* <!-- 7. PADDLE --> */}
                        <section className="legal-section" id="paddle">
                            <h2>7. Payments and Paddle</h2>
                            <div className="highlight-box accent">
                                <h4>Paddle acts as Merchant of Record</h4>
                                <p>All IntelShift subscriptions are sold by <strong>Paddle.com Market Limited</strong> as the Merchant of Record. This means Paddle handles payment collection, tax compliance, refund processing, and billing support on our behalf. When you purchase an IntelShift plan, you are entering into a transaction with Paddle.</p>
                            </div>
                            <p>As a result:</p>
                            <ul>
                                <li>Your payment card details are collected and stored by Paddle — not by IntelShift. We never see or store full card numbers.</li>
                                <li>Paddle processes your payment data under their own <a href="https://www.paddle.com/legal/privacy" target="_blank" rel="noopener">Privacy Policy</a> and applicable payment regulations (PCI-DSS).</li>
                                <li>Receipts, invoices, and billing correspondence will come from Paddle on behalf of IntelShift.</li>
                                <li>Subscription management (upgrades, downgrades, cancellations) may be available through Paddle's customer portal.</li>
                                <li>For billing disputes, refund requests, or payment issues, you may contact either Paddle's support or IntelShift support — we will coordinate as needed.</li>
                            </ul>
                            <p>We share your name, email address, and plan selection with Paddle solely to facilitate your subscription. We do not share competitor data, intelligence reports, or usage data with Paddle.</p>
                        </section>

                        {/* <!-- 8. AI PROCESSING --> */}
                        <section className="legal-section" id="ai-processing">
                            <h2>8. AI processing and competitor intelligence</h2>
                            <p>IntelShift uses AI to interpret detected competitor page changes and generate intelligence insights for your account. Here is how that works:</p>
                            <ul>
                                <li><strong>What is sent to AI:</strong> When our system detects a meaningful change on a competitor page you monitor, the relevant before-and-after page content (text only, public data) is sent to an AI model to generate the insight, impact score, and recommended actions.</li>
                                <li><strong>Your data isolation:</strong> AI processing is performed per-account. Competitor content from your monitoring is not mixed with or visible to other IntelShift users.</li>
                                <li><strong>No model training on your data:</strong> We use AI providers under contractual terms that prohibit the use of submitted content to train or improve their general models.</li>
                                <li><strong>Public data only:</strong> The competitor content we process is exclusively from public-facing web pages. No private, authenticated, or confidential data is ever crawled or processed.</li>
                                <li><strong>Retention:</strong> AI-generated insights are stored in your account and subject to the same data retention policy as the rest of your account data. See <a href="#retention">Section 11</a>.</li>
                            </ul>
                        </section>

                        {/* <!-- 9. COOKIES --> */}
                        <section className="legal-section" id="cookies">
                            <h2>9. Cookies and tracking technologies</h2>
                            <p>We use cookies and similar technologies to operate and improve IntelShift. Here is a breakdown by category:</p>

                            <h3>Strictly necessary cookies</h3>
                            <p>Required for the Service to function. They cannot be disabled. Examples: session authentication tokens, CSRF protection, and user preference persistence.</p>

                            <h3>Analytics cookies</h3>
                            <p>Help us understand how users interact with IntelShift — which features are used, where users encounter friction, and overall product health. Data is aggregated. You may opt out via your browser settings or a cookie preference centre if displayed.</p>

                            <h3>Payment cookies</h3>
                            <p>Set by Paddle during checkout and subscription management. Governed by Paddle's cookie and privacy policies.</p>

                            <h3>How to manage cookies</h3>
                            <p>You can control and delete cookies through your browser settings. Disabling strictly necessary cookies may impair Service functionality. For more information, visit <a href="https://www.allaboutcookies.org" target="_blank" rel="noopener">allaboutcookies.org</a>.</p>
                        </section>

                        {/* <!-- 10. INTERNATIONAL TRANSFERS --> */}
                        <section className="legal-section" id="international">
                            <h2>10. International data transfers</h2>
                            <p>IntelShift serves users globally. Your data may be stored and processed in countries outside your country of residence, including countries that may have different data protection laws.</p>
                            <p>Where we transfer data outside the European Economic Area (EEA) or United Kingdom, we ensure appropriate safeguards are in place, including:</p>
                            <ul>
                                <li>Standard Contractual Clauses (SCCs) approved by the European Commission</li>
                                <li>Adequacy decisions where applicable</li>
                                <li>Data Processing Agreements with all sub-processors that impose equivalent protections</li>
                            </ul>
                            <p>By using IntelShift, you acknowledge that your data may be transferred to and processed in countries where data protection standards may differ from those in your home jurisdiction.</p>
                        </section>

                        {/* <!-- 11. RETENTION --> */}
                        <section className="legal-section" id="retention">
                            <h2>11. Data retention</h2>
                            <p>We retain your data for as long as your account is active or as needed to provide the Service, comply with legal obligations, resolve disputes, and enforce our agreements.</p>
                            <ul>
                                <li><strong>Account data:</strong> Retained for the duration of your subscription and for up to 90 days following account deletion or subscription expiry.</li>
                                <li><strong>Competitor snapshots and intelligence:</strong> Retained according to your plan's historical data limits. Upon account deletion, this data is permanently purged within 90 days.</li>
                                <li><strong>Billing records:</strong> Retained for up to 7 years as required by applicable tax and accounting laws.</li>
                                <li><strong>Server logs:</strong> Typically retained for 30–90 days for security and debugging purposes.</li>
                                <li><strong>Support communications:</strong> Retained for up to 3 years to assist with recurring issues and service quality.</li>
                            </ul>
                            <p>You may request deletion of your personal data at any time. See <a href="#your-rights">Your Rights</a> below.</p>
                        </section>

                        {/* <!-- 12. SECURITY --> */}
                        <section className="legal-section" id="security">
                            <h2>12. Security</h2>
                            <p>We implement appropriate technical and organisational measures to protect your data against unauthorised access, loss, destruction, or alteration. These include:</p>
                            <ul>
                                <li>Encryption of data in transit (TLS/HTTPS) and at rest</li>
                                <li>Hashed and salted password storage — we never store plaintext passwords</li>
                                <li>Account isolation — competitor data and intelligence is separated per workspace</li>
                                <li>Access controls limiting employee access to personal data on a need-to-know basis</li>
                                <li>Regular security reviews and dependency updates</li>
                            </ul>
                            <p>No method of internet transmission or electronic storage is 100% secure. While we strive to protect your data, we cannot guarantee absolute security. In the event of a data breach that affects your rights and freedoms, we will notify you and applicable authorities as required by law.</p>
                        </section>

                        {/* <!-- 13. YOUR RIGHTS --> */}
                        <section className="legal-section" id="your-rights">
                            <h2>13. Your rights</h2>
                            <p>Depending on your location, you have various rights regarding your personal data. We honour these rights regardless of where you are based.</p>
                            <div className="rights-grid">
                                <div className="right-item">
                                    <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" /></svg>Right to access</h4>
                                    <p>Request a copy of the personal data we hold about you.</p>
                                </div>
                                <div className="right-item">
                                    <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>Right to rectification</h4>
                                    <p>Request correction of inaccurate or incomplete data.</p>
                                </div>
                                <div className="right-item">
                                    <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" /><path d="M10 11v6M14 11v6" /></svg>Right to erasure</h4>
                                    <p>Request deletion of your personal data ("right to be forgotten").</p>
                                </div>
                                <div className="right-item">
                                    <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="4.93" y1="4.93" x2="19.07" y2="19.07" /></svg>Right to restrict</h4>
                                    <p>Request that we limit how we use your data in certain circumstances.</p>
                                </div>
                                <div className="right-item">
                                    <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>Right to portability</h4>
                                    <p>Receive your data in a structured, machine-readable format.</p>
                                </div>
                                <div className="right-item">
                                    <h4><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>Right to object</h4>
                                    <p>Object to processing based on legitimate interests or for direct marketing.</p>
                                </div>
                            </div>
                            <p>To exercise any of these rights, contact us at <a href="mailto:privacy@intelshift.ai">privacy@intelshift.ai</a>. We will respond within 30 days (GDPR requires 1 month). We may need to verify your identity before processing your request.</p>
                        </section>

                        {/* <!-- 14. GDPR --> */}
                        <section className="legal-section" id="gdpr">
                            <h2>14. EU/EEA users — GDPR</h2>
                            <p>If you are located in the European Union or European Economic Area, you have additional rights and protections under the General Data Protection Regulation (GDPR 2016/679).</p>
                            <p>You have the right to lodge a complaint with your local supervisory authority. A full list of EU data protection authorities is available at <a href="https://edpb.europa.eu" target="_blank" rel="noopener">edpb.europa.eu</a>.</p>
                            <p>Our legal bases for processing are described in <a href="#legal-basis">Section 5</a>. Where we rely on consent, you may withdraw it at any time without affecting prior processing.</p>
                            <p>For transfers of personal data outside the EEA, we rely on Standard Contractual Clauses (SCCs) as described in <a href="#international">Section 10</a>.</p>
                        </section>

                        {/* <!-- 15. CCPA --> */}
                        <section className="legal-section" id="ccpa">
                            <h2>15. California users — CCPA/CPRA</h2>
                            <p>If you are a California resident, you have additional rights under the California Consumer Privacy Act (CCPA) as amended by the California Privacy Rights Act (CPRA).</p>
                            <ul>
                                <li><strong>Right to know:</strong> You may request disclosure of the categories and specific pieces of personal information we collect, the sources, our business purpose, and the categories of third parties we share it with.</li>
                                <li><strong>Right to delete:</strong> You may request deletion of personal information we collected, subject to certain exceptions.</li>
                                <li><strong>Right to correct:</strong> You may request correction of inaccurate personal information.</li>
                                <li><strong>Right to opt out of sale or sharing:</strong> We do not sell personal data. We do not share personal data for cross-context behavioural advertising.</li>
                                <li><strong>Right to non-discrimination:</strong> We will not discriminate against you for exercising your CCPA rights.</li>
                            </ul>
                            <p>To submit a CCPA request, contact <a href="mailto:privacy@intelshift.ai">privacy@intelshift.ai</a> with subject line "CCPA Request". We will verify your identity and respond within 45 days.</p>
                        </section>

                        {/* <!-- 16. CHILDREN --> */}
                        <section className="legal-section" id="children">
                            <h2>16. Children's privacy</h2>
                            <p>IntelShift is a business tool intended for adults. We do not knowingly collect personal data from individuals under 18 years of age (or the applicable age of digital consent in your jurisdiction).</p>
                            <p>If you believe we have inadvertently collected personal data from a minor, please contact us at <a href="mailto:privacy@intelshift.ai">privacy@intelshift.ai</a> and we will delete it promptly.</p>
                        </section>

                        {/* <!-- 17. CHANGES --> */}
                        <section className="legal-section" id="changes">
                            <h2>17. Changes to this policy</h2>
                            <p>We may update this Privacy Policy from time to time to reflect changes in our practices, technology, legal requirements, or other factors. When we do:</p>
                            <ul>
                                <li>We will update the "Last updated" date at the top of this page.</li>
                                <li>For material changes, we will notify you by email (to the address on your account) and/or by a prominent notice within the Service at least 14 days before the change takes effect.</li>
                                <li>Your continued use of IntelShift after the effective date constitutes acceptance of the revised policy.</li>
                            </ul>
                            <p>We encourage you to review this policy periodically.</p>
                        </section>

                        {/* <!-- 18. CONTACT --> */}
                        <section className="legal-section" id="contact-privacy">
                            <h2>18. Contact us</h2>
                            <p>For any privacy-related questions, requests to exercise your rights, or concerns about how we handle your data, please contact us:</p>
                            <div className="contact-box">
                                <h3>Privacy enquiries</h3>
                                <p>We aim to respond to all privacy requests within 5 business days and to fully resolve them within 30 days.</p>
                                <div className="contact-details">
                                    {/* <!-- REPLACE: update with real legal entity name, address, and DPO if applicable --> */}
                                    <div className="contact-detail">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                                        <a href="mailto:privacy@intelshift.ai">privacy@intelshift.ai</a>
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

export default PrivacyPolicy;
