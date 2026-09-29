import { Link } from 'react-router';
import Logo from '../assets/logo.png';

function Footer() {
    return (
        <footer>
            <div className="container">
                <div className="footer-grid">

                    <div className="footer-brand">
                        <Link to="/" className="nav-brand" aria-label="IntelShift home">
                            <div className="nav-logo">
                                <img src={Logo} alt="IntelShift" style={{ borderRadius: '50%' }} />
                            </div>
                            <span className="nav-name">IntelShift</span>
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
                        <h4>Use cases</h4>
                        <a href="/#usecases">For founders</a>
                        <a href="/#usecases">For marketing</a>
                        <a href="/#usecases">For sales</a>
                        <a href="/#usecases">Growth teams</a>
                    </div>

                    <div className="footer-col">
                        <h4>Company</h4>
                        <Link to="/about">About</Link>
                        <a href="mailto:info@intelshift.ai">Contact</a>
                        <Link to="/privacy-policy">Privacy policy</Link>
                        <Link to="/terms">Terms of service</Link>
                        <Link to="/refund">Refund policy</Link>
                    </div>

                </div>

                <div className="footer-bottom">
                    <div className="footer-copy">© 2026 IntelShift. All rights reserved.</div>
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

export default Footer;
