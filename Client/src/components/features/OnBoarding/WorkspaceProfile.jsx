import { useState } from 'react';
import Input from '../../ui/Input';
import SiteReadinessBar from '../../shared/SiteReadinessBar';

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding: Workspace profile
──────────────────────────────────────────────────────────────── */

// Scoped to the two verticals IntelShift actually supports well. Services /
// agency / general sites were removed — the product's page model (collections,
// PDPs, pricing, features) doesn't map to them.
// `name` is the stored value (persisted on the workspace + sent to competitor
// suggestion); `label` is only what we render — so fixing the "SaaS" casing
// never changes existing workspaces' stored industry.
/* Users type "sivanna.com.pk" far more often than they type the
   scheme. Normalise on blur rather than on every keystroke, so the
   protocol does not appear while they are still typing. */
const withProtocol = (value) => {
  const raw = (value || "").trim();
  if (!raw) return raw;

  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("//")) return "https:" + raw;

  // Leave it alone until it actually looks like a domain
  if (!raw.includes(".")) return raw;

  return "https://" + raw.replace(/^\/+/, "");
};

const labelStyle = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 8,
  color: 'var(--text)',
};

function WorkspaceProfile({
  workspaceName,
  setWorkspaceName,
  workspaceURL,
  setWorkspaceURL,
  // Saved store/currency for the user's own site, and a setter to persist it.
  workspaceStore = {},
  onWorkspaceStoreChange,
  // Bubbles the currency-probe in-progress state up so the parent can disable Next.
  onCurrencyCheckingChange,
  // Bubbles up whether the entered site is reachable (blocks Next when not).
  onUrlReachableChange,
  // Site-readiness validation state (shown under the URL field).
  validating = false,
  validateStage = "",
  validateError = "",
}) {
  // URL to probe for a currency switcher — set on blur so it doesn't fire
  // mid-typing. The user's URL is never changed by detection.
  const [probeUrl, setProbeUrl] = useState("");

  return (
    <div style={{ fontFamily: 'var(--font-sans)' }}>
      <h2
        style={{
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: '-0.025em',
          marginBottom: 6,
          color: 'var(--primary)',
        }}
      >
        Set up your workspace
      </h2>

      <p
        style={{
          fontSize: 14.5,
          color: 'var(--text-light)',
          marginBottom: '1.75rem',
          lineHeight: 1.6,
        }}
      >
        This is the brand IntelShift AI will treat as <strong>you</strong>.
        Everything else gets measured against it.
      </p>

      {/* Brand name + URL */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ marginBottom: '1.125rem' }}>
          <label htmlFor="workspaceName" style={labelStyle}>
            Brand Name <span style={{ color: 'var(--accent)' }}>*</span>
          </label>
          <Input
            id="workspaceName"
            placeholder="e.g. IntelShift AI"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
          />
          <p
            style={{
              fontSize: 12,
              color: 'var(--text-light)',
              margin: '8px 0 0',
              lineHeight: 1.55,
            }}
          >
            The name your customers know you by — it labels your reports and alerts.
          </p>
        </div>

        <div>
          <label htmlFor="workspaceURL" style={labelStyle}>
            Store URL <span style={{ color: 'var(--accent)' }}>*</span>
          </label>
          <Input
            id="workspaceURL"
            placeholder="yourstore.com"
            value={workspaceURL}
            onChange={(e) => setWorkspaceURL(e.target.value)}
            onBlur={(e) => {
              const v = withProtocol(e.target.value);
              setWorkspaceURL(v);
              setProbeUrl(v);
            }}
          />
          <p
            style={{
              fontSize: 12,
              color: 'var(--text-light)',
              margin: '8px 0 0',
              lineHeight: 1.55,
            }}
          >
            We crawl this domain next so you can choose exactly which pages to
            track.
          </p>

          {/* Store readiness (homepage + collection + product + currency) is
              confirmed on Next — its currency read pre-fills the workspace, so no
              separate currency/market probe is needed here. */}
          <SiteReadinessBar validating={validating} stage={validateStage} error={validateError} />
        </div>
      </div>

    </div>
  );
}

export default WorkspaceProfile;
