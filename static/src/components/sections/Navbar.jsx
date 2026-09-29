import { useEffect, useState } from "react";
import { Link } from "react-router";
import logo from "../assets/logo.png";

function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 20);
        };

        handleScroll();

        window.addEventListener("scroll", handleScroll);

        return () => {
            window.removeEventListener("scroll", handleScroll);
        };
    }, []);

    const toggleMenu = () => {
        setMobileOpen((prev) => !prev);
    };

    const closeMenu = () => {
        setMobileOpen(false);
    };

    return (
        <>
            <nav
                id="navbar"
                className={scrolled ? "scrolled" : ""}
                aria-label="Main navigation"
            >
                <div className="nav-inner">
                    <Link
                        to="/"
                        className="nav-brand"
                        aria-label="IntelShift home"
                        onClick={closeMenu}
                    >
                        <div className="nav-logo">
                            <img src={logo} alt="IntelShift logo" style={{ borderRadius: '50px' }} fetchpriority="high" width="36" height="36" />
                        </div>

                        <span className="nav-name">
                            IntelShift
                        </span>
                    </Link>

                    <div className="nav-links" role="menubar">
                        <a href="#features" className="nav-link">Features</a>
                        <a href="#how" className="nav-link">How it works</a>
                        <a href="#usecases" className="nav-link">Use Cases</a>
                        <a href="#pricing" className="nav-link">Pricing</a>
                        <a href="#resources" className="nav-link">Resources</a>
                    </div>

                    <div className="nav-actions">


                        <a href="#pricing" className="btn btn-primary btn-sm">
                            Start monitoring
                        </a>

                        <a href="#demo" className="btn btn-light btn-sm">
                            Login
                        </a>
                    </div>

                    <button
                        className="hamburger"
                        onClick={toggleMenu}
                        aria-label="Toggle menu"
                        aria-expanded={mobileOpen}
                    >
                        <span></span>
                        <span></span>
                        <span></span>
                    </button>
                </div>
            </nav>

            <div
                id="mobileMenu"
                className={`mobile-menu ${mobileOpen ? "open" : ""}`}
                aria-hidden={!mobileOpen}
            >
                <a href="#features" className="nav-link" onClick={closeMenu}>
                    Features
                </a>

                <a href="#how" className="nav-link" onClick={closeMenu}>
                    How it works
                </a>

                <a href="#usecases" className="nav-link" onClick={closeMenu}>
                    Use Cases
                </a>

                <a href="#pricing" className="nav-link" onClick={closeMenu}>
                    Pricing
                </a>

                <a href="#resources" className="nav-link" onClick={closeMenu}>
                    Resources
                </a>

                <div
                    className="nav-actions"
                    style={{
                        marginTop: 16,
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                    }}
                >
                    <a
                        href="#demo"
                        className="btn btn-secondary"
                        style={{ justifyContent: "center" }}
                        onClick={closeMenu}
                    >
                        View sample report
                    </a>

                    <a
                        href="#pricing"
                        className="btn btn-primary"
                        style={{ justifyContent: "center" }}
                        onClick={closeMenu}
                    >
                        Start monitoring
                    </a>
                </div>
            </div>
        </>
    );
}

export default Navbar;