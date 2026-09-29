import { useEffect, useState } from "react";
import { Link } from "react-router";
import logo from "../../assets/logo.png";

const APP_URL = import.meta.env.VITE_APP_URL;

function Header() {
    const [scrolled, setScrolled]     = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        handleScroll();
        window.addEventListener("scroll", handleScroll);
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    // Lock body scroll when menu is open
    useEffect(() => {
        document.body.style.overflow = mobileOpen ? "hidden" : "";
        return () => { document.body.style.overflow = ""; };
    }, [mobileOpen]);

    const toggleMenu = () => setMobileOpen(prev => !prev);
    const closeMenu  = () => setMobileOpen(false);

    return (
        <>
            <nav
                id="navbar"
                className={scrolled ? "scrolled" : ""}
                aria-label="Main navigation"
            >
                <div className="nav-inner">
                    <Link to="/" className="nav-brand" aria-label="IntelShift home" onClick={closeMenu}>
                        <div className="nav-logo">
                            <img src={logo} alt="IntelShift logo" style={{ borderRadius: "50px" }} fetchpriority="high" width="36" height="36" />
                        </div>
                        <span className="nav-name">IntelShift AI</span>
                    </Link>

                    <div className="nav-links">
                        <a href="/#features"  className="nav-link">Features</a>
                        <a href="/#how"       className="nav-link">How it works</a>
                        <a href="/#usecases"  className="nav-link">Use Cases</a>
                        <a href="/#pricing"   className="nav-link">Pricing</a>
                        <a href="/#resources" className="nav-link">Resources</a>
                        <a href="/about"      className="nav-link">About</a>
                    </div>

                    <div className="nav-actions">
                        <a href="/#pricing" className="btn btn-primary btn-sm">Start monitoring</a>
                        <a href={`${APP_URL}/login`} className="btn btn-light btn-sm">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14" aria-hidden="true" style={{ marginRight: '5px', verticalAlign: 'middle', flexShrink: 0 }}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                            Login
                        </a>
                    </div>

                    {/* Hamburger — becomes × when open */}
                    <button
                        className={`hamburger${mobileOpen ? " open" : ""}`}
                        onClick={toggleMenu}
                        aria-label={mobileOpen ? "Close menu" : "Open menu"}
                        aria-expanded={mobileOpen}
                    >
                        <span />
                        <span />
                        <span />
                    </button>
                </div>
            </nav>

            {/* Mobile drawer */}
            <div
                id="mobileMenu"
                className={`mobile-menu${mobileOpen ? " open" : ""}`}
                aria-hidden={!mobileOpen}
            >
                <a href="/#features"  className="nav-link" onClick={closeMenu}>Features</a>
                <a href="/#how"       className="nav-link" onClick={closeMenu}>How it works</a>
                <a href="/#usecases"  className="nav-link" onClick={closeMenu}>Use Cases</a>
                <a href="/#pricing"   className="nav-link" onClick={closeMenu}>Pricing</a>
                <a href="/#resources" className="nav-link" onClick={closeMenu}>Resources</a>
                <a href="/about"      className="nav-link" onClick={closeMenu}>About</a>

                {/* Login only — no duplicate CTAs */}
                <div className="mobile-cta-group">
                    <a
                        href={`${APP_URL}/login`}
                        className="btn btn-primary mobile-btn-full"
                        onClick={closeMenu}
                    >
                        Log in to IntelShift AI
                    </a>
                    <a
                        href="/#pricing"
                        className="mobile-login-link"
                        onClick={closeMenu}
                    >
                        New here? <span>Start monitoring →</span>
                    </a>
                </div>
            </div>
        </>
    );
}

export default Header;
