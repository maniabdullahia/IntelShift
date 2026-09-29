import { useState } from "react";
import { FileText, Users, GitCompareArrows, Check, ChevronDown, ChevronUp, BarChart3 } from "lucide-react";

/* ────────────────────────────────────────────────────────────────
   IntelShift AI — floating onboarding progress.
   A persistent, at-a-glance summary of what's left to pick: the
   user's own pages, how many competitors, and the current
   competitor's paired pages. The row tied to the current step is
   highlighted. Collapsible, and on small screens it docks
   bottom-CENTER (between Previous/Next) and starts collapsed so it
   never covers the primary action button.
──────────────────────────────────────────────────────────────── */

const STYLES = `
.ob-progress{
  position:fixed; right:clamp(12px,2vw,28px); bottom:clamp(12px,3vh,32px);
  z-index:40; width:232px; max-width:calc(100vw - 24px);
  border-radius:var(--radius); background:var(--card);
  border:1px solid var(--border); box-shadow:var(--shadow-lg,0 12px 32px rgba(0,0,0,.12));
  font-family:var(--font-sans); overflow:hidden;
}
.ob-progress__head{
  display:flex; align-items:center; gap:8px; width:100%;
  padding:10px 12px; background:transparent; border:none; cursor:pointer;
  text-align:left; color:var(--text-light);
}
.ob-progress__title{
  font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  color:var(--text-light); flex:1; min-width:0;
}
.ob-progress__body{ padding:0 12px 12px; display:grid; gap:4px; }
@media (max-width:1200px){
  .ob-progress{
    right:auto; left:50%; transform:translateX(-50%);
    bottom:calc(env(safe-area-inset-bottom,0px) + 12px);
    width:auto; max-width:calc(100vw - 24px);
  }
  .ob-progress--collapsed .ob-progress__head{ padding:8px 14px; }
  .ob-progress--open{ width:260px; }
}
`;

const Row = ({ icon: Icon, label, done, total, active, complete }) => {
  const atLimit = total > 0 && done >= total;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 10px",
        borderRadius: "var(--radius-sm)",
        background: active ? "var(--glow-teal)" : "transparent",
        border: active
          ? "1px solid color-mix(in srgb, var(--secondary) 40%, transparent)"
          : "1px solid transparent",
      }}
    >
      <span
        style={{
          width: 26,
          height: 26,
          flexShrink: 0,
          borderRadius: "var(--radius-sm)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: active ? "var(--secondary-dark)" : "var(--bg)",
          border: active ? "none" : "1px solid var(--border)",
        }}
      >
        <Icon size={14} style={{ color: active ? "#fff" : "var(--text-light)" }} />
      </span>

      <span
        style={{
          flex: 1,
          minWidth: 0,
          fontSize: 11,
          fontWeight: 600,
          color: active ? "var(--secondary-dark)" : "var(--text-light)",
        }}
      >
        {label}
      </span>

      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          fontSize: 12,
          fontWeight: 700,
          padding: "2px 8px",
          borderRadius: 999,
          background: complete ? "var(--glow-teal)" : atLimit ? "var(--glow-coral)" : "var(--bg)",
          color: complete ? "var(--secondary-dark)" : atLimit ? "var(--accent-dark)" : "var(--text)",
          border: "1px solid var(--border)",
          whiteSpace: "nowrap",
        }}
      >
        {complete && <Check size={11} strokeWidth={3} />}
        {done}
        {total ? `/${total}` : ""}
      </span>
    </div>
  );
};

function OnboardingProgress({
  currentStep,
  pagesSelected = 0,
  pageLimit = 0,
  competitorsResolved = 0,
  maxCompetitors = 1,
  competitorPagesMatched = 0,
  competitorPageTarget = 0,
}) {
  // Start collapsed below 1200px so the pill can't cover the Next button.
  const [collapsed, setCollapsed] = useState(
    () => typeof window !== "undefined" && window.innerWidth <= 1200
  );

  // Nothing worth showing until the user is choosing pages.
  if (currentStep < 3) return null;

  return (
    <>
      <style>{STYLES}</style>
      <div
        className={`ob-progress ${collapsed ? "ob-progress--collapsed" : "ob-progress--open"}`}
      >
        <button
          type="button"
          className="ob-progress__head"
          onClick={() => setCollapsed((v) => !v)}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Show setup progress" : "Hide setup progress"}
        >
          <BarChart3 size={13} style={{ color: "var(--secondary-dark)", flexShrink: 0 }} />
          <span className="ob-progress__title">Setup progress</span>
          {collapsed ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>

        {!collapsed && (
          <div className="ob-progress__body">
            <Row
              icon={FileText}
              label="Your pages"
              done={pagesSelected}
              total={pageLimit}
              active={currentStep === 3}
              complete={currentStep > 3 && pagesSelected > 0}
            />
            <Row
              icon={Users}
              label="Competitors"
              done={competitorsResolved}
              total={maxCompetitors}
              active={currentStep === 4}
              complete={competitorsResolved >= maxCompetitors}
            />
            <Row
              icon={GitCompareArrows}
              label="Competitor pages"
              done={competitorPagesMatched}
              total={competitorPageTarget}
              active={currentStep === 5}
              complete={
                competitorPageTarget > 0 && competitorPagesMatched >= competitorPageTarget
              }
            />
          </div>
        )}
      </div>
    </>
  );
}

export default OnboardingProgress;
