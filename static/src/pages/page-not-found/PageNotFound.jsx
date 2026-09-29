import { Link } from 'react-router'
import './pageNotFound.css'

function PageNotFound() {
  return (
    <main className="not-found-page" role="main">
      <div className="not-found-shell">
        <div className="not-found-badge" aria-label="404 error">
          404
        </div>

        <div className="not-found-illustration" aria-hidden="true">
          <div className="orb orb-one"></div>
          <div className="orb orb-two"></div>
          <div className="not-found-card">
            <span className="card-dot"></span>
            <span className="card-dot"></span>
            <span className="card-dot"></span>
          </div>
        </div>

        <h1>Page not found</h1>
        <p>
          The page you were looking for has moved, disappeared, or never existed.
          Let’s get you back to the IntelShift experience.
        </p>

        <div className="not-found-actions">
          <Link to="/" className="btn btn-primary">
            Back home
          </Link>
          <a href="mailto:info@intelshift.ai" className="btn btn-secondary">
            Contact support
          </a>
        </div>
      </div>
    </main>
  )
}

export default PageNotFound
