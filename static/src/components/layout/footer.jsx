import { Link } from "react-router";
import logo from "../../assets/logo.png";

export default function Footer() {
  return (
    <footer>
      <div className="container">
        <div className="footer-grid">
          <div className="footer-brand">
            <Link to="/" className="nav-brand" aria-label="IntelShift home">
              <div className="nav-logo">
                <img src={logo} alt="IntelShift logo" style={{ borderRadius: '50%' }} loading="lazy" width="36" height="36" />
              </div>
              <span className="nav-name">IntelShift AI</span>
            </Link>
            <p>AI-powered competitor intelligence and analysis</p>
          </div>

          <div className="footer-col">
            <h4>Product</h4>
            <a href="/#features">Features</a>
            <a href="/#how">How it works</a>
            <a href="/#pricing">Pricing</a>
            <a href="/#demo">Sample report</a>
          </div>

          <div className="footer-col">
            <h4>Use Cases</h4>
            <Link to="/#usecases">For founders</Link>
            <Link to="/#usecases">For marketing</Link>
            <Link to="/#usecases">For sales</Link>
            <Link to="/#usecases">Growth teams</Link>
          </div>

          <div className="footer-col">
            <h4>Company</h4>
            <Link to="/about">About</Link>
            <a href="mailto:info@intelshift.ai">Contact</a>
            <Link to="/privacy-policy">Privacy Policy</Link>
            <Link to="/terms">Terms of Service</Link>
            <Link to="/refund">Refund Policy</Link>
            <button
              className="footer-cookie-btn"
              onClick={() => window.openCookieSettings?.()}
              aria-label="Manage cookie preferences"
            >
              Cookie settings
            </button>
          </div>
        </div>

        <div className="footer-bottom">
          <div className="footer-copy">
            © 2026 IntelShift. All rights reserved.
          </div>

          <div className="footer-legal">
            <Link to="/privacy-policy">Privacy</Link>
            <Link to="/terms">Terms</Link>
            <Link to="/refund">Refund</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
