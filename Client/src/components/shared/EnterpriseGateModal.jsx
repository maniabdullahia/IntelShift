import React from "react";
import { Building2, X } from "lucide-react";

/* Shown when a store is enterprise/marketplace-scale (from the validate-site scale
   gateway). Marketplaces (Amazon, Daraz…) and mega-catalogs can't be self-served,
   so we blur the screen and route the user to "talk to us" instead of letting them
   continue onboarding. */
export default function EnterpriseGateModal({ open, info, onClose, contactEmail = "sales@intelshift.ai" }) {
  if (!open) return null;

  const isMarketplace = !!info?.isMarketplace;
  const total = info?.totalProducts;
  const host = (() => {
    try { return new URL(info?.url).hostname.replace(/^www\./, ""); } catch { return info?.url || "This store"; }
  })();

  const isGlobalBrand = info?.businessType === 2;
  const title = isGlobalBrand
    ? "This is a global brand"
    : isMarketplace ? "This looks like a marketplace" : "This store is enterprise-scale";
  const body = isGlobalBrand
    ? `${host} is a global / multinational brand. Brands at this scale (many regional stores, very large catalogs) are handled on our Enterprise plan, so we'll set you up properly there.`
    : isMarketplace
    ? `${host} is a large marketplace with many third-party sellers. Our self-serve plans are built for independent stores, so a marketplace this size needs a custom Enterprise setup.`
    : `${host}${Number.isFinite(total) ? ` carries roughly ${total.toLocaleString()}+ products` : " carries a very large catalog"}, which is beyond the self-serve plans. We'll set you up properly on Enterprise.`;

  const subject = encodeURIComponent(`Enterprise enquiry — ${host}`);
  const emailBody = encodeURIComponent(
    `Hi,\n\nI'd like to track ${info?.url || host} with IntelShift.\n` +
    (isGlobalBrand ? "(Flagged as a global brand during onboarding.)\n" : isMarketplace ? "(Flagged as a marketplace during onboarding.)\n" : `(Catalog size ~${total || "large"} during onboarding.)\n`) +
    `\nThanks,`
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20,
        background: "color-mix(in srgb, var(--secondary-dark, #0b1220) 55%, transparent)",
        backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
      }}
    >
      <div
        style={{
          position: "relative", width: "100%", maxWidth: 460,
          background: "var(--card)", border: "1px solid var(--border)",
          borderRadius: "var(--radius, 16px)", padding: "28px 26px",
          boxShadow: "0 24px 60px rgba(0,0,0,0.35)",
        }}
      >
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              position: "absolute", top: 14, right: 14, background: "transparent",
              border: "none", cursor: "pointer", color: "var(--text-light)", padding: 4,
            }}
          >
            <X size={18} />
          </button>
        )}

        <div
          style={{
            width: 46, height: 46, borderRadius: 12, display: "flex",
            alignItems: "center", justifyContent: "center", marginBottom: 16,
            background: "var(--glow-teal, rgba(78,205,196,0.12))",
            border: "1px solid color-mix(in srgb, var(--secondary) 30%, transparent)",
          }}
        >
          <Building2 size={22} style={{ color: "var(--secondary)" }} />
        </div>

        <h3 style={{ margin: "0 0 8px", fontSize: 19, fontWeight: 700, color: "var(--text)" }}>
          {title}
        </h3>
        <p style={{ margin: "0 0 20px", fontSize: 14, lineHeight: 1.55, color: "var(--text-light)" }}>
          {body}
        </p>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <a
            href={`mailto:${contactEmail}?subject=${subject}&body=${emailBody}`}
            style={{
              flex: "1 1 auto", textAlign: "center", textDecoration: "none",
              padding: "12px 18px", borderRadius: "var(--radius-sm, 10px)",
              background: "var(--primary)", color: "#fff", fontWeight: 600, fontSize: 14,
            }}
          >
            Talk to us
          </a>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                flex: "0 0 auto", padding: "12px 18px", borderRadius: "var(--radius-sm, 10px)",
                background: "transparent", border: "1px solid var(--border)",
                color: "var(--text)", fontWeight: 600, fontSize: 14, cursor: "pointer",
              }}
            >
              Use a different store
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
