import { useState, useEffect } from "react";
import { Link } from "react-router";
import { LogOut } from "lucide-react";

import Brand from "../../shared/Brand";

/* ────────────────────────────────────────────────────────────────
   IntelShift — onboarding header.

   Design matches the marketing-site header exactly: 3-bar hamburger
   that morphs into an ×, a fixed dark blurred drawer (.mobile-menu),
   and the translucent .btn-secondary button styling (.is-logout).
──────────────────────────────────────────────────────────────── */

const navCss = `
.is-onboarding-header nav{height:72px;background:rgba(26,26,46,0.92);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.07);box-shadow:0 4px 32px rgba(0,0,0,0.2);position:sticky;top:0;z-index:100}
.is-onboarding-header .nav-inner{max-width:1200px;margin:0 auto;padding:0 24px;height:100%;display:flex;align-items:center;justify-content:space-between;gap:16px}
.is-onboarding-header .nav-brand{display:flex;align-items:center;gap:10px;flex-shrink:0;text-decoration:none;min-width:0}
.is-onboarding-header .nav-actions{display:flex;align-items:center;gap:10px;flex-shrink:0}

/* Buttons — mirrors the site's .btn / .btn-secondary. */
.is-onboarding-header .is-logout{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:9px 18px;border-radius:10px;font-size:13px;font-weight:700;font-family:inherit;cursor:pointer;transition:all .2s ease;background:rgba(255,255,255,0.08);color:#fff;border:1px solid rgba(255,255,255,0.18);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);white-space:nowrap}
.is-onboarding-header .is-logout:hover{background:rgba(255,255,255,0.14);transform:translateY(-2px)}
.is-onboarding-header .is-logout:active{transform:translateY(0)}

/* Hamburger — 3 white bars morphing into an ×, exactly like the site. */
.is-onboarding-header .hamburger{display:none;flex-direction:column;gap:5px;padding:8px;margin-right:-4px;cursor:pointer;background:none;border:none}
.is-onboarding-header .hamburger span{display:block;width:22px;height:2px;background:#fff;border-radius:2px;transition:all .3s ease;transform-origin:center}
.is-onboarding-header .hamburger.open span:nth-child(1){transform:translateY(7px) rotate(45deg)}
.is-onboarding-header .hamburger.open span:nth-child(2){opacity:0;transform:scaleX(0)}
.is-onboarding-header .hamburger.open span:nth-child(3){transform:translateY(-7px) rotate(-45deg)}

/* Mobile drawer — mirrors the site's .mobile-menu. */
.is-onboarding-header .mobile-menu{display:none;position:fixed;top:60px;left:0;right:0;background:rgba(26,26,46,0.97);-webkit-backdrop-filter:blur(24px);backdrop-filter:blur(24px);border-bottom:1px solid rgba(255,255,255,0.08);padding:20px 24px;z-index:99}
.is-onboarding-header .mobile-menu .is-logout{width:100%;padding:13px 24px;font-size:15px;border-radius:12px}

@media (max-width:640px){
  .is-onboarding-header nav{height:60px}
  .is-onboarding-header .nav-inner{padding:0 14px;gap:12px}
  .is-onboarding-header .nav-actions{display:none}
  .is-onboarding-header .hamburger{display:flex}
  .is-onboarding-header .mobile-menu.open{display:flex;flex-direction:column;gap:10px}
}
`;

function OnboardingHeader({ onLogout, children }) {
  const [open, setOpen] = useState(false);

  // Lock body scroll while the drawer is open (like the marketing site).
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  const actions = (
    <>
      {children}
      {onLogout && (
        <button type="button" className="is-logout" onClick={onLogout}>
          <LogOut size={14} />
          Logout
        </button>
      )}
    </>
  );

  return (
    <div className="is-onboarding-header">
      <style>{navCss}</style>

      <nav id="navbar" aria-label="IntelShift AI">
        <div className="nav-inner">
          <Link to="/" className="nav-brand" aria-label="IntelShift AI home">
            <Brand tone="light" />
          </Link>

          {/* Desktop: inline actions */}
          <div className="nav-actions">{actions}</div>

          {/* Mobile: 3-bar hamburger → × */}
          <button
            type="button"
            className={`hamburger${open ? " open" : ""}`}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>
      </nav>

      {/* Mobile: dark blurred drawer with the same actions */}
      <div
        className={`mobile-menu${open ? " open" : ""}`}
        aria-hidden={!open}
        onClick={() => setOpen(false)}
      >
        {actions}
      </div>
    </div>
  );
}

export default OnboardingHeader;
