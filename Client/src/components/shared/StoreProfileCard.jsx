import React from "react";
import { Store, MapPin, Tag, ShieldCheck, AlertTriangle } from "lucide-react";

/* "Here's how we read your store" — the onboarding store profile (Steps 1–4):
   business type, market & delivery scope, Industry → Category → Subcategory,
   and whether the full shopping journey was accessible. Read-only; renders
   nothing until a profile exists. */

const SCOPE_LABEL = {
  domestic: "delivers domestically",
  selected: "delivers to selected countries",
  worldwide: "delivers worldwide",
};

const JOURNEY_LABEL = { search: "search", cart: "cart", checkout: "checkout" };

export const describeMarket = (market) => {
  if (!market) return null;
  const where = market.countryName || market.country;
  const scope = SCOPE_LABEL[market.scope];
  if (!where && !scope) return null;
  const n = market.scope === "selected" && market.shipsToCount > 1 ? ` (${market.shipsToCount})` : "";
  return [where, scope ? `${scope}${n}` : null].filter(Boolean).join(" · ");
};

const Row = ({ icon: Icon, label, value }) =>
  value ? (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 13, color: "var(--text)" }}>
      <Icon size={14} style={{ color: "var(--secondary-dark, var(--secondary))", marginTop: 2, flexShrink: 0 }} />
      <span>
        <span style={{ color: "var(--text-light)" }}>{label}: </span>
        {value}
      </span>
    </div>
  ) : null;

export default function StoreProfileCard({ profile, title = "Here's how we read your store" }) {
  if (!profile) return null;
  const market = describeMarket(profile.market);
  const category = profile.taxonomy?.path || null;
  const incomplete = profile.accessStatus === "incomplete";
  const issues = (profile.accessIssues || []).map((k) => JOURNEY_LABEL[k] || k);

  if (!profile.businessTypeLabel && !market && !category) return null;

  return (
    <div
      style={{
        margin: "0 0 18px",
        padding: "14px 16px",
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm, 10px)",
        display: "grid",
        gap: 7,
      }}
    >
      <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--text)" }}>{title}</div>
      <Row icon={Store} label="Store type" value={profile.businessTypeLabel} />
      <Row icon={MapPin} label="Market" value={market} />
      <Row icon={Tag} label="Category" value={category} />
      {incomplete ? (
        <div style={{ display: "flex", gap: 8, fontSize: 12.5, color: "var(--text)" }}>
          <AlertTriangle size={14} style={{ color: "var(--accent-dark, var(--accent))", marginTop: 2, flexShrink: 0 }} />
          <span>
            We couldn&apos;t access the {issues.join(" / ") || "full shopping journey"}. We&apos;ll still analyze this
            store, and reports will mark those areas as not covered.
          </span>
        </div>
      ) : (
        <Row icon={ShieldCheck} label="Access" value={profile.accessStatus === "complete" ? "full shopping journey readable" : null} />
      )}
      <div style={{ fontSize: 11.5, color: "var(--text-light)" }}>
        We use this to find comparable competitors.
      </div>
    </div>
  );
}
