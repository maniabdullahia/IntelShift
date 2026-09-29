import React from "react";
import { AlertTriangle } from "lucide-react";

/* Onboarding site-readiness feedback, shown directly under the Website URL field.
   Driven by the validation state in OnBoarding: a spinner + staged message while
   we confirm the site can be read (homepage + collection + product), or a blocking
   error naming the stage that failed. Renders nothing when idle. */
export default function SiteReadinessBar({ validating = false, stage = "", error = "" }) {
  if (!validating && !error) return null;

  if (validating) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, padding: "12px 14px", background: "var(--glow-teal, rgba(78,205,196,0.08))", border: "1px solid color-mix(in srgb, var(--secondary) 30%, transparent)", borderRadius: "var(--radius-sm, 10px)" }}>
        <span style={{ width: 16, height: 16, border: "2px solid var(--secondary)", borderTopColor: "transparent", borderRadius: "50%", display: "inline-block", animation: "is-spin 0.8s linear infinite", flexShrink: 0 }} />
        <span style={{ fontSize: 13, color: "var(--text)" }}>
          Reading the site — {stage || "checking…"}
          <span style={{ display: "block", fontSize: 11.5, color: "var(--text-light)", marginTop: 2 }}>
            This can take a few minutes.
          </span>
        </span>
        <style>{`@keyframes is-spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginTop: 10, padding: "12px 14px", background: "var(--glow-coral)", border: "1px solid color-mix(in srgb, var(--accent) 32%, transparent)", borderRadius: "var(--radius-sm, 10px)" }}>
      <AlertTriangle size={15} style={{ color: "var(--accent-dark)", marginTop: 1, flexShrink: 0 }} />
      <span style={{ fontSize: 13, color: "var(--text)" }}>
        {error} <span style={{ color: "var(--text-light)" }}>You won&apos;t be able to add this store — try a different one.</span>
      </span>
    </div>
  );
}
