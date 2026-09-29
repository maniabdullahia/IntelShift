import { useState } from "react";

function Faq() {
    const [openIndex, setOpenIndex] = useState(null);

    const toggleFaq = (index) => {
        setOpenIndex((prev) => (prev === index ? null : index));
    };

    const faqs = [
        {
            question: "Is competitor website monitoring legal?",
            answer:
                "Yes. Monitoring publicly accessible competitor web pages is legal and a standard practice in competitive intelligence. IntelShift only accesses content that anyone with a browser can view — no logins, no bypassing security, no scraping protected data. We also respect each website's robots.txt directives.",
        },
        {
            question: "Do you track pages behind logins or paywalls?",
            answer:
                "No. IntelShift only monitors publicly accessible pages such as competitor homepages, pricing pages, product pages, blogs, and careers pages. We do not access customer dashboards, internal tools, or any content behind authentication.",
        },
        {
            question: "How long does setup take?",
            answer:
                "Most teams complete setup in under 5 minutes. You sign up, select your industry, add competitor URLs, choose which pages to monitor, and start tracking. Reports and monitoring frequency are delivered according to your selected plan.",
        },
        {
            question: "Can I choose which specific pages to monitor?",
            answer:
                "Yes. You choose exactly which page types to monitor per competitor — homepage, pricing, product, blog, careers, or custom URLs. You're in full control of what gets tracked and how frequently.",
        },
        {
            question: "Can I upgrade my plan without losing data?",
            answer:
                "Yes. Upgrading your plan expands your limits immediately while preserving all existing competitors, page snapshots, detected changes, AI insights, and historical reports. No data is lost during an upgrade.",
        },
        {
            question: "Do I need to log in every day to get value?",
            answer:
                "No. IntelShift is designed to bring intelligence to you. Alerts and reports are delivered according to your plan, so you can review key competitor moves without checking the dashboard every day.",
        },
    ];

    return (
        <section
            className="faq-section section"
            id="resources"
            aria-labelledby="faq-heading"
        >
            <div className="container">
                <div className="section-head reveal">
                    <div className="eyebrow">
                        <span className="eyebrow-pulse"></span>
                        FAQ
                    </div>

                    <h2 id="faq-heading">
                        Common questions, answered clearly.
                    </h2>

                    <p>
                        Everything you need to know before you start monitoring.
                    </p>
                </div>

                <div className="faq-grid reveal" role="list">
                    {faqs.map((faq, index) => {
                        const isOpen = openIndex === index;

                        return (
                            <div
                                key={index}
                                className={`faq-item ${isOpen ? "open" : ""}`}
                                role="listitem"
                            >
                                <button
                                    className="faq-q"
                                    aria-expanded={isOpen}
                                    onClick={() => toggleFaq(index)}
                                >
                                    {faq.question}

                                    <svg
                                        className="faq-chevron"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="2.5"
                                        aria-hidden="true"
                                    >
                                        <path d="M6 9l6 6 6-6" />
                                    </svg>
                                </button>

                                <div className="faq-a">
                                    <div className="faq-a-inner">
                                        {faq.answer}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

export default Faq;