import { Link } from 'react-router'
import './page-under-dev.css'

function PageUnderDev() {
  return (
    <main className="under-dev-page" role="main">
      <div className="under-dev-shell">
        <div className="under-dev-badge">Coming Soon</div>

        <div className="under-dev-visual" aria-hidden="true">
          <div className="under-dev-orb orb-one"></div>
          <div className="under-dev-orb orb-two"></div>
          <div className="under-dev-card">
            <span className="bar"></span>
            <span className="bar"></span>
            <span className="bar"></span>
          </div>
        </div>

        <h1>This page is under development</h1>
        <p>
          We’re building this experience to make your IntelShift workflow smoother,
          faster, and more insightful. Check back soon for the launch.
        </p>

        <div className="under-dev-actions">
          <Link to="/" className="btn btn-primary">
            Go back home
          </Link>
          <a href="mailto:info@intelshift.ai" className="btn btn-secondary">
            Contact us
          </a>
        </div>
      </div>
    </main>
  )
}

export default PageUnderDev
