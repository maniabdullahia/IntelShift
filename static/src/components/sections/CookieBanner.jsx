import { useState, useEffect } from 'react';

const PREFS_KEY = 'intelshift_cookie_prefs';
const GA_ID     = 'G-XDDDLE2K41';

let gaLoaded = false;

function loadGA() {
  if (gaLoaded) return;
  gaLoaded = true;
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = gtag;
  gtag('js', new Date());
  gtag('config', GA_ID);
}

function CookieBanner() {
  const [bannerVisible, setBannerVisible] = useState(false);
  const [showPrefs,     setShowPrefs]     = useState(false);
  const [prefs,         setPrefs]         = useState({ essential: true, analytics: false, marketing: false });

  // Expose global trigger so footer "Cookie settings" button works
  // regardless of whether the banner has been dismissed.
  useEffect(() => {
    window.openCookieSettings = () => {
      setBannerVisible(false);
      setShowPrefs(true);
    };
    return () => { delete window.openCookieSettings; };
  }, []);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(PREFS_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.analytics) loadGA();
        return; // already answered — don't show banner
      }
    } catch (_) {}
    setBannerVisible(true);
  }, []);

  function save(newPrefs) {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(newPrefs)); } catch (_) {}
    if (newPrefs.analytics) loadGA();
    setBannerVisible(false);
    setShowPrefs(false);
  }

  const acceptAll  = () => save({ essential: true, analytics: true, marketing: true });
  const rejectAll  = () => save({ essential: true, analytics: false, marketing: false });
  const saveChosen = () => save(prefs);

  if (!bannerVisible && !showPrefs) return null;

  return (
    <>
      {/* ── Main banner ── */}
      {bannerVisible && !showPrefs && (
        <div className="cb-banner" role="dialog" aria-live="polite" aria-label="Cookie consent">
          <div className="cb-inner">
            <div className="cb-text">
              <strong>We use cookies</strong>
              <p>
                We use essential cookies to keep the site running and optional analytics cookies (Google Analytics) to understand how visitors use IntelShift.
                No data is shared with advertisers.{' '}
                <a href="/privacy-policy" className="cb-link">Privacy policy</a>
              </p>
            </div>
            <div className="cb-actions">
              <button className="cb-btn cb-accept"  onClick={acceptAll}>Accept all</button>
              <button className="cb-btn cb-manage"  onClick={() => setShowPrefs(true)}>Manage preferences</button>
              <button className="cb-btn cb-reject"  onClick={rejectAll}>Reject optional</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Preferences modal ── */}
      {showPrefs && (
        <div className="cb-overlay" role="dialog" aria-modal="true" aria-label="Cookie preferences">
          <div className="cb-modal">
            <div className="cb-modal-header">
              <h3>Cookie preferences</h3>
              <button className="cb-close" onClick={() => setShowPrefs(false)} aria-label="Close">✕</button>
            </div>

            <div className="cb-modal-body">
              {/* Essential — always on */}
              <div className="cb-pref-row">
                <div className="cb-pref-info">
                  <strong>Essential cookies</strong>
                  <p>Required for the site to function. Cannot be disabled.</p>
                </div>
                <span className="cb-always-on">Always on</span>
              </div>

              {/* Analytics */}
              <div className="cb-pref-row">
                <div className="cb-pref-info">
                  <strong>Analytics cookies</strong>
                  <p>Help us understand how visitors use IntelShift (Google Analytics). No personal data is sold or shared.</p>
                </div>
                <label className="cb-toggle">
                  <input
                    type="checkbox"
                    checked={prefs.analytics}
                    onChange={e => setPrefs(p => ({ ...p, analytics: e.target.checked }))}
                  />
                  <span className="cb-slider" />
                </label>
              </div>

              {/* Marketing */}
              <div className="cb-pref-row">
                <div className="cb-pref-info">
                  <strong>Marketing cookies</strong>
                  <p>Used to serve relevant ads. IntelShift does not currently use marketing cookies.</p>
                </div>
                <label className="cb-toggle">
                  <input
                    type="checkbox"
                    checked={prefs.marketing}
                    onChange={e => setPrefs(p => ({ ...p, marketing: e.target.checked }))}
                  />
                  <span className="cb-slider" />
                </label>
              </div>
            </div>

            <div className="cb-modal-footer">
              <button className="cb-btn cb-reject"  onClick={rejectAll}>Reject all</button>
              <button className="cb-btn cb-manage"  onClick={saveChosen}>Save preferences</button>
              <button className="cb-btn cb-accept"  onClick={acceptAll}>Accept all</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default CookieBanner;
