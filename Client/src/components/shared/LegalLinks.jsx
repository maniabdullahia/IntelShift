import React from "react";

/* Terms / Privacy / Refund links → the published policy pages on the marketing
   site (intelshift.ai). Reused on the login/signup screens and app-wide footer so
   the legal pages are always one click away. */
const LINKS = [
  { label: "Terms of Service", href: "https://intelshift.ai/terms" },
  { label: "Privacy Notice", href: "https://intelshift.ai/privacy-policy" },
  { label: "Refund Policy", href: "https://intelshift.ai/refund" },
];

export default function LegalLinks({ className = "", showCopyright = false }) {
  return (
    <div className={`flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-(--text-light) ${className}`}>
      {showCopyright && (
        <span className="mr-1">© {new Date().getFullYear()} IntelShift AI</span>
      )}
      {LINKS.map((l, i) => (
        <React.Fragment key={l.href}>
          {(showCopyright || i > 0) && <span className="opacity-40">·</span>}
          <a
            href={l.href}
            target="_blank"
            rel="noreferrer"
            className="transition hover:text-(--primary) hover:underline"
          >
            {l.label}
          </a>
        </React.Fragment>
      ))}
    </div>
  );
}
