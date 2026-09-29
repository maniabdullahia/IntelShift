import React, { useState, useEffect } from "react";
import { ChevronRight } from "lucide-react";

/* ── Responsive rules ──────────────────────────────────────────
   Five steps abreast do not fit a phone. Below 640px the circles
   shrink, the per-step description is dropped, and the footer
   buttons go full width and stack.
──────────────────────────────────────────────────────────────── */

const stepperCss = `
.is-stepper-track{display:flex;justify-content:space-between;width:100%;position:relative;z-index:1}
.is-stepper-step{display:flex;flex-direction:column;align-items:center;flex:1;min-width:0}
.is-stepper-label{margin-top:12px;font-size:13px;font-weight:600;text-align:center;line-height:1.3}
.is-stepper-desc{margin-top:4px;font-size:11px;text-align:center;line-height:1.3}
.is-stepper-nav{display:flex;gap:12px;margin-top:1.5rem;justify-content:space-between;align-items:flex-start;flex-wrap:wrap}
.is-stepper-actions{display:flex;gap:12px;flex-wrap:wrap;justify-content:flex-end}
@media (max-width:640px){
  /* The 5-step circle track is too cramped on a phone — hide it and rely on
     the slim progress bar + each step's own heading for context. */
  .is-stepper-head{display:none !important}
  .is-stepper-nav{flex-direction:column-reverse;align-items:stretch;gap:10px}
  /* Full-width, stacked buttons — including Next, which is nested in a div. */
  .is-stepper-nav > button{width:100%;justify-content:center}
  .is-stepper-nav > div{width:100%}
  .is-stepper-nav > div > button{width:100%;justify-content:center}
  .is-stepper-actions{flex-direction:column;align-items:stretch;width:100%}
  .is-stepper-actions > *{width:100%;justify-content:center}
}
`;

function ProcessStepper({
  currentStep = 1,
  steps = [],
  onStepChange,
  canProceed = true,
  nextBlockedMessage = "Please complete required fields to continue.",
  canJumpTo = () => true,
  // Optional async hook run when "Next" is clicked, BEFORE advancing. Return
  // false to keep the user on the current step (e.g. to confirm a choice).
  onBeforeNext = null,
  // Buttons rendered next to "Previous" on the final step, in place of
  // "Next". The parent owns these because what the last step should do
  // depends on how many competitors are still left to add.
  finalActions = null,
}) {
  const [activeStep, setActiveStep] = useState(currentStep);
  const [shake, setShake] = useState(false);

  useEffect(() => {
    setActiveStep(currentStep);
  }, [currentStep]);

  const handleStepChange = (stepId) => {
    setActiveStep(stepId);
    onStepChange && onStepChange(stepId);
  };

  const sampleSteps = [
    {
      id: 1,
      label: "Account Details",
      description: "Enter your basic information",
    },
    {
      id: 2,
      label: "Verification",
      description: "Verify your email address",
    },
    {
      id: 3,
      label: "Profile Setup",
      description: "Complete your profile",
    },
    {
      id: 4,
      label: "Confirmation",
      description: "Review and confirm",
    },
  ];

  steps = steps.length > 0 ? steps : sampleSteps;
  const totalSteps = steps.length;

  const isStepCompleted = (stepId) => stepId < activeStep;
  const isStepActive = (stepId) => stepId === activeStep;

  return (
    <div
      /* No card chrome here — OnBoarding already wraps this in a card.
         Nesting the two drew a second rounded border inside the
         "Welcome to IntelShift" panel. */
      style={{ padding: 0, background: "transparent" }}
    >
      <style>{stepperCss}</style>

      {/* Stepper Container (hidden on phones) */}
      <div
        className="is-stepper-head"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "1rem",
          marginBottom: "2rem",
          position: "relative",
        }}
      >
        {/* Progress Line Background */}
        <div
          style={{
            position: "absolute",
            top: "20px",
            left: "0",
            right: "0",
            height: "2px",
            backgroundColor: "var(--border)",
            zIndex: 0,
          }}
        ></div>

        {/* Steps */}
        <div className="is-stepper-track">
          {steps.map((step) => (
            <div key={step.id} className="is-stepper-step">
              {/* Step Circle */}
              <div
                className="is-stepper-circle"
                onClick={() => {
                  // prevent jumping forward unless allowed
                  if (step.id > activeStep && !canJumpTo(step.id)) {
                    setShake(true);
                    setTimeout(() => setShake(false), 600);
                    return;
                  }

                  handleStepChange(step.id);
                }}
                style={{
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  // Matches .step-num on the marketing site: a teal ring
                  // for upcoming steps, filled coral for the active one.
                  background: isStepCompleted(step.id)
                    ? "rgba(78,205,196,0.15)"
                    : isStepActive(step.id)
                      ? "var(--accent)"
                      : "rgba(78,205,196,0.07)",
                  border: isStepActive(step.id)
                    ? "1px solid var(--accent)"
                    : "1px solid rgba(78,205,196,0.25)",
                  boxShadow: isStepActive(step.id)
                    ? "0 8px 24px rgba(255,107,107,0.3)"
                    : "none",
                  color: isStepCompleted(step.id)
                    ? "var(--secondary-dark)"
                    : isStepActive(step.id)
                      ? "#fff"
                      : "var(--text-light)",
                  fontWeight: "900",
                  cursor: "pointer",
                  transition: "all 0.3s ease",
                  fontSize: "15px",
                }}
                title={`Step ${step.id}`}
              >
                {isStepCompleted(step.id) ? "✓" : step.id}
              </div>

              {/* Step Label */}
              <p
                className="is-stepper-label"
                style={{
                  color: isStepActive(step.id)
                    ? "var(--primary)"
                    : "var(--text)",
                  fontFamily: "var(--font-sans)",
                }}
              >
                {step.label}
              </p>

              {/* Step Description */}
              <p
                className="is-stepper-desc"
                style={{
                  color: "var(--text-light)",
                  fontFamily: "var(--font-sans)",
                }}
              >
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Progress Bar */}
      <div
        style={{
          height: "6px",
          backgroundColor: "var(--border)",
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
          marginBottom: "1.5rem",
        }}
      >
        <div
          style={{
            height: "100%",
            background: "var(--secondary)",
            width: `${(activeStep / totalSteps) * 100}%`,
            transition: "width 0.3s ease",
          }}
        ></div>
      </div>

      {/* Step Info

          Every step stays mounted and inactive ones are hidden with CSS.
          Unmounting them would discard whatever the user had selected on
          that step, so going "Previous" used to wipe their answers.

          Each step component receives an `isActive` prop so it can defer
          expensive work (site crawls) until it is actually on screen. */}
      <div>
        {steps.map((step) => {
          const active = step.id === activeStep;

          return (
            <div
              key={step.id}
              style={{ display: active ? "block" : "none" }}
              aria-hidden={!active}
            >
              {React.isValidElement(step.component)
                ? React.cloneElement(step.component, { isActive: active })
                : step.component}
            </div>
          );
        })}
      </div>

      {/* Navigation Buttons */}
      <div className="is-stepper-nav">
        <button
          onClick={() => activeStep > 1 && handleStepChange(activeStep - 1)}
          disabled={activeStep === 1}
          style={{
            padding: "13px 24px",
            background: activeStep === 1 ? "var(--border)" : "#fff",
            color: activeStep === 1 ? "var(--text-light)" : "var(--primary)",
            border: "1px solid var(--border)",
            borderRadius: "12px",
            fontWeight: "700",
            boxShadow: activeStep === 1 ? "none" : "var(--shadow-sm)",
            cursor: activeStep === 1 ? "not-allowed" : "pointer",
            transition: "all 0.2s ease",
            fontFamily: "var(--font-sans)",
            fontSize: "14px",
          }}
        >
          Previous
        </button>

        {activeStep === totalSteps && finalActions && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              gap: "8px",
            }}
          >
            <div className="is-stepper-actions">{finalActions}</div>

            {!canProceed && (
              <div
                style={{
                  color: "var(--text-light)",
                  fontSize: "12px",
                  textAlign: "right",
                  maxWidth: "420px",
                }}
              >
                {nextBlockedMessage}
              </div>
            )}
          </div>
        )}

        {activeStep !== totalSteps && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
            <button
              onClick={async () => {
                if (!canProceed) {
                  // trigger shake animation
                  setShake(true);
                  setTimeout(() => setShake(false), 600);
                  return;
                }

                // Let the parent confirm/veto before advancing (e.g. "add more
                // pages now, or continue?"). A false result keeps us here.
                if (onBeforeNext) {
                  const proceed = await onBeforeNext(activeStep);
                  if (!proceed) return;
                }

                if (activeStep < totalSteps) handleStepChange(activeStep + 1);
              }}
              disabled={!canProceed}
              style={{
                padding: "13px 24px",
                background: canProceed ? "var(--accent)" : "var(--border)",
                color: canProceed ? "#fff" : "var(--text-light)",
                border: "none",
                borderRadius: "12px",
                fontWeight: "700",
                boxShadow: canProceed ? "0 8px 24px rgba(255,107,107,0.3)" : "none",
                cursor: canProceed ? "pointer" : "not-allowed",
                transition: "all 0.2s ease",
                fontFamily: "var(--font-sans)",
                fontSize: "14px",
                transform: shake ? "translateX(-6px)" : undefined,
              }}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                Next
                <ChevronRight size={16} />
              </span>
            </button>
            {!canProceed && (
              <div style={{ marginTop: "8px", color: "var(--text-light)", fontSize: "12px" }}>
                {nextBlockedMessage}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ProcessStepper;
