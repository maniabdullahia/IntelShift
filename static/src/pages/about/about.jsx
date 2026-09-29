import './about.css';
import SEO from '../../components/seo/SEO';

function About() {
    return (
        <>
            <SEO
                title="About IntelShift — The Team Behind Competitor Intelligence"
                description="IntelShift helps ecommerce brands and SaaS companies monitor competitor websites, detect meaningful changes, and take action before falling behind. Learn who we are and why we built it."
                canonical="/about"
                keywords="about IntelShift, competitor intelligence company, competitor monitoring team, AI competitor analysis tool"
            />
            <section className="about-hero" aria-labelledby="about-heading">
                <div className="about-hero-bg" aria-hidden="true">
                    <div className="hero-grid-lines"></div>
                    <div className="hero-glow-top"></div>
                    <div className="hero-glow-bl"></div>
                    <div className="hero-glow-br"></div>
                </div>
                <div className="container">
                    <div className="about-hero-inner">
                        <div className="about-hero-eyebrow" role="doc-subtitle">
                            <span className="eyebrow-pulse" aria-hidden="true"></span>
                            About IntelShift
                        </div>
                        <h1 id="about-heading">
                            We built the tool<br />
                            we <em>wished we had.</em>
                        </h1>
                        <p className="about-hero-sub">
                            IntelShift exists because competitive intelligence shouldn't require a full-time analyst, a stack of bookmarked tabs, or a Friday afternoon of manual research. It should just arrive — clear, actionable, and ready for the team.
                        </p>
                        <div className="about-hero-actions">
                            <a href="/#pricing" className="btn btn-primary btn-lg">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                                Start monitoring
                            </a>
                            <a href="#story" className="btn btn-secondary btn-lg">Our story</a>
                        </div>
                    </div>
                </div>
            </section>

            {/* <!-- ══════════════════════════════════════════════════════════
            STATS BAR
            REPLACE: update numbers as IntelShift grows
══════════════════════════════════════════════════════════ --> */}
            <div className="stats-bar" aria-label="IntelShift at a glance">
                <div className="container">
                    <div className="stats-grid">
                        <div className="stat-item reveal">
                            <div className="stat-num">10<span>+</span></div>
                            <div className="stat-label">Brands monitored</div>
                        </div>
                        <div className="stat-item reveal reveal-delay-1">
                            <div className="stat-num">100<span>s</span></div>
                            <div className="stat-label">Competitor changes tracked</div>
                        </div>
                        <div className="stat-item reveal reveal-delay-2">
                            <div className="stat-num">5<span>min</span></div>
                            <div className="stat-label">Average setup time</div>
                        </div>
                        <div className="stat-item reveal reveal-delay-3">
                            <div className="stat-num">3<span>x</span></div>
                            <div className="stat-label">Plans to fit every team</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* <!-- ══════════════════════════════════════════════════════════
            ORIGIN STORY
══════════════════════════════════════════════════════════ --> */}
            <section className="story section" id="story" aria-labelledby="story-heading">
                <div className="container">
                    <div className="story-grid">
                        <div className="story-content reveal">
                            <div className="eyebrow"><span className="eyebrow-pulse"></span>Our Story</div>
                            <h2 id="story-heading">Competitive intelligence was <em>broken</em> for most teams.</h2>
                            <p>We kept seeing the same pattern across SaaS and ecommerce teams: someone checks a competitor's pricing page manually on a Thursday, screenshots it into a Slack message, and the thread gets buried. Two weeks later, the competitor launches a new offer and the sales team hears about it from a prospect on a call.</p>
                            <p>The tools that existed were either too complex, too expensive, or built for enterprise analyst teams — not for the founder running a 10-person SaaS or the marketing lead managing a busy ecommerce brand.</p>
                            <p>So we built IntelShift. A system that monitors the right pages, removes the noise, scores what matters, and delivers intelligence your team can actually act on — without anyone having to remember to check.</p>
                            <a href="/#pricing" className="btn btn-primary">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                                Try it yourself
                            </a>
                        </div>

                        {/* <!-- Visual card — right side --> */}
                        <div className="story-visual reveal reveal-delay-2">
                            <div className="story-card">
                                <div className="story-card-label">What started it all</div>
                                <div className="story-quote">
                                    "Our competitor changed their pricing on a Monday. We found out from a lost deal on Friday. That was the last time."
                                </div>
                                {/* <!-- REPLACE: update author name, role, and initials/photo --> */}
                                <div className="story-meta">
                                    <div className="story-avatar" aria-hidden="true">IS</div>
                                    <div className="story-meta-text">
                                        <strong>The IntelShift Team</strong>
                                        <span>The moment that started it all</span>
                                    </div>
                                </div>
                                <div className="story-timeline" role="list" aria-label="Key milestones">
                                    <div className="tl-item" role="listitem">
                                        <div className="tl-dot" aria-hidden="true"><div className="tl-dot-inner"></div></div>
                                        <div className="tl-text">
                                            <strong>The problem became clear</strong>
                                            <span>Competitive intelligence was manual, slow, and fragmented</span>
                                        </div>
                                    </div>
                                    <div className="tl-item" role="listitem">
                                        <div className="tl-dot" aria-hidden="true"><div className="tl-dot-inner"></div></div>
                                        <div className="tl-text">
                                            <strong>IntelShift was born</strong>
                                            <span>Built to detect, interpret, and recommend — not just report</span>
                                        </div>
                                    </div>
                                    <div className="tl-item" role="listitem">
                                        <div className="tl-dot" aria-hidden="true"><div className="tl-dot-inner"></div></div>
                                        <div className="tl-text">
                                            <strong>First teams onboarded</strong>
                                            <span>SaaS and ecommerce teams monitoring competitors from day one</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
{/* 
            <!-- ══════════════════════════════════════════════════════════
            MISSION
══════════════════════════════════════════════════════════ --> */}
            <section className="mission section" aria-labelledby="mission-heading">
                <div className="container">
                    <div className="mission-inner reveal">
                        <div className="eyebrow" style={{ justifyContent: "center", display: "inline-flex" }}><span className="eyebrow-pulse"></span>Our Mission</div>
                        <p className="mission-statement" id="mission-heading">
                            Make competitive intelligence <em>accessible to every team</em> — not just the ones with a full-time analyst and an enterprise budget.
                        </p>
                        <p className="mission-sub">
                            Every SaaS team and ecommerce brand deserves to know when a competitor moves. Not after the fact, not from a prospect on a call — but early, with context, and with a clear recommendation on what to do next. That's what we're building.
                        </p>
                    </div>
                </div>
            </section>

            {/* <!-- ══════════════════════════════════════════════════════════
            VALUES
══════════════════════════════════════════════════════════ --> */}
            <section className="values section" aria-labelledby="values-heading">
                <div className="container">
                    <div className="section-head reveal">
                        <div className="eyebrow"><span className="eyebrow-pulse"></span>Our Values</div>
                        <h2 id="values-heading">How we think about building IntelShift</h2>
                        <p>The principles that shape what we build, how we communicate, and how we treat the teams who trust us with their competitive intelligence.</p>
                    </div>
                    <div className="values-grid">
                        <div className="value-card reveal reveal-delay-1">
                            <div className="value-icon teal" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                            </div>
                            <h3>Clarity over volume</h3>
                            <p>We don't believe in alerting you to every pixel that moved. Intelligence means removing the noise so what matters is unmistakable. If it isn't actionable, we don't surface it.</p>
                        </div>
                        <div className="value-card reveal reveal-delay-2">
                            <div className="value-icon coral" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
                            </div>
                            <h3>Speed that respects context</h3>
                            <p>Fast alerts matter — but only when paired with enough context to act. We deliver insight at the right speed for each team, not a firehose that burns out your attention.</p>
                        </div>
                        <div className="value-card reveal reveal-delay-3">
                            <div className="value-icon green" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
                            </div>
                            <h3>Responsible by design</h3>
                            <p>We monitor public pages only. No login bypassing, no scraping protected content, no grey-area crawling. Ethical monitoring isn't a constraint — it's a foundation we're proud of.</p>
                        </div>
                        <div className="value-card reveal reveal-delay-1">
                            <div className="value-icon yellow" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><path d="M12 8v4l3 3" /></svg>
                            </div>
                            <h3>Built for real teams</h3>
                            <p>Not for enterprise analyst teams with dedicated headcount. IntelShift is built for the founder who checks Slack before meetings and the marketing lead who needs answers in under five minutes.</p>
                        </div>
                        <div className="value-card reveal reveal-delay-2">
                            <div className="value-icon navy" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></svg>
                            </div>
                            <h3>Every insight is verifiable</h3>
                            <p>We show before-and-after evidence for every change we flag. You should never have to take our word for it — the proof is always one click away.</p>
                        </div>
                        <div className="value-card reveal reveal-delay-3">
                            <div className="value-icon purple" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" /></svg>
                            </div>
                            <h3>Customer success = product success</h3>
                            <p>We win when our customers stay ahead of their markets. That means building for outcomes — better positioning, sharper battlecards, faster responses — not just feature counts.</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* <!-- ══════════════════════════════════════════════════════════
            TEAM
            REPLACE: all .team-card blocks with real team member data
══════════════════════════════════════════════════════════ -->

            <!-- ══════════════════════════════════════════════════════════
            PRINCIPLES
══════════════════════════════════════════════════════════ --> */}
            <section className="principles section" aria-labelledby="principles-heading">
                <div className="container">
                    <div className="section-head reveal">
                        <div className="eyebrow"><span className="eyebrow-pulse"></span>How We Build</div>
                        <h2 id="principles-heading">Product principles we don't compromise on</h2>
                        <p>The rules we set for ourselves — on every feature, every decision, every release.</p>
                    </div>
                    <div className="principles-grid">
                        <div className="principle-item reveal reveal-delay-1">
                            <div className="principle-num" aria-hidden="true">01</div>
                            <div className="principle-text">
                                <h3>Insights in under 30 seconds</h3>
                                <p>Every report, every change card, and every alert should communicate value within 30 seconds of opening. If it requires effort to interpret, we haven't finished the job.</p>
                            </div>
                        </div>
                        <div className="principle-item reveal reveal-delay-2">
                            <div className="principle-num" aria-hidden="true">02</div>
                            <div className="principle-text">
                                <h3>No false urgency</h3>
                                <p>We only send alerts when there is a real signal. Alert fatigue kills competitive intelligence programs. Every notification should feel worth opening.</p>
                            </div>
                        </div>
                        <div className="principle-item reveal reveal-delay-3">
                            <div className="principle-num" aria-hidden="true">03</div>
                            <div className="principle-text">
                                <h3>Always show the evidence</h3>
                                <p>Every AI insight is paired with before-and-after proof. Teams should be able to verify, share, and act on what they see — not just trust a summary.</p>
                            </div>
                        </div>
                        <div className="principle-item reveal reveal-delay-4">
                            <div className="principle-num" aria-hidden="true">04</div>
                            <div className="principle-text">
                                <h3>Build for the 5-minute reader</h3>
                                <p>Founders and marketers don't have hours. Every feature we build is tested against: "Can a busy person extract value from this in five minutes or less?"</p>
                            </div>
                        </div>
                        <div className="principle-item reveal reveal-delay-1">
                            <div className="principle-num" aria-hidden="true">05</div>
                            <div className="principle-text">
                                <h3>Monitoring should be invisible</h3>
                                <p>The best competitor intelligence system is one you don't have to think about. Set it up once, and intelligence comes to you — not the other way around.</p>
                            </div>
                        </div>
                        <div className="principle-item reveal reveal-delay-2">
                            <div className="principle-num" aria-hidden="true">06</div>
                            <div className="principle-text">
                                <h3>Ethical crawling, always</h3>
                                <p>Public pages only. robots.txt respected. Responsible crawl cadence. We built IntelShift to be something we'd be comfortable explaining to any competitor we monitor.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* <!-- ══════════════════════════════════════════════════════════
            HIRING BANNER
            REPLACE: update with real job link or careers page URL
══════════════════════════════════════════════════════════ --> */}
            <section className="hiring section" aria-labelledby="hiring-heading">
                <div className="container">
                    <div className="hiring-inner reveal">
                        <div className="hiring-content">
                            <div className="eyebrow" style={{ marginBottom: 12 }}><span className="eyebrow-pulse"></span>We're hiring</div>
                            <h2 id="hiring-heading">Want to help build the future of competitive intelligence?</h2>
                            <p>We're a small, focused team building something we genuinely care about. If you're excited by the intersection of AI, product intelligence, and helping teams move faster — we'd love to hear from you.</p>
                        </div>
                        <div className="hiring-action">
                            {/* <!-- REPLACE: href with real careers page or email --> */}
                            <a href="mailto:info@intelshift.ai" className="btn btn-primary btn-lg">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" /></svg>
                                Get in touch
                            </a>
                        </div>
                    </div>
                </div>
            </section>
        </>
    );
}

export default About;
