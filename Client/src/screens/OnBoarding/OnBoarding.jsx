import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Check, Clock, CreditCard, ArrowRight } from "lucide-react";

import ProcessStepper from "../../components/ui/ProcessStepper";
import WorkspaceIntro from "../../components/features/OnBoarding/WorkspaceIntro";
import WorkspaceProfile from "../../components/features/OnBoarding/WorkspaceProfile";
import FocusCategories from "../../components/features/OnBoarding/FocusCategories";
import OnBoardCompetitor from "../../components/features/OnBoarding/OnBoardCompetitor";
import OnboardingHeader from "../../components/features/OnBoarding/OnboardingHeader";

import Swal from "../../components/shared/Alert";
import EnterpriseGateModal from "../../components/shared/EnterpriseGateModal";

import useWorkspaceStore from "../../store/workspace.store";
import useAuthStore from "../../store/auth.store";
import * as workspaceApi from "../../api/workspace.api";
import { validateSite } from "../../api/utils.api";

/* ────────────────────────────────────────────────────────────────
   IntelShift — Onboarding (capture-first)

   Onboarding now collects URLs ONLY: the owner's site + industry,
   then one or more competitor URLs. It does NOT pick or map pages —
   that happens inside the workspace, against the breadth-only recon
   we capture for every site right after this. So the flow is:

     1. Get started
     2. Your workspace  (name · URL · industry · region)
     3. Add competitor  (repeats per competitor — URL · region)

   Finishing calls /workspace-recon, which creates the workspace with
   zero pages and kicks off recon. Page selection + mapping live in
   the workspace and drive the deep per-page crawl from there.
──────────────────────────────────────────────────────────────── */

/* Page-shell responsive rules. */
const shellCss = `
.is-ob-shell{padding:24px 16px}
.is-ob-card{width:100%;max-width:1024px;padding:32px;background:var(--card);border-radius:var(--radius-lg);box-shadow:var(--shadow-lg)}
.is-ob-title{font-size:30px;font-weight:800;letter-spacing:-0.025em;line-height:1.1;margin:0 0 10px;color:var(--primary)}
.is-ob-dot{width:7px;height:7px;border-radius:50%;background:var(--secondary);animation:is-ob-dot-pulse 2s ease infinite}
@keyframes is-ob-dot-pulse{0%,100%{box-shadow:0 0 0 0 rgba(78,205,196,0.5)}50%{box-shadow:0 0 0 8px rgba(78,205,196,0)}}
@media (max-width:640px){
  .is-ob-shell{padding:16px 12px}
  .is-ob-card{padding:20px 16px;border-radius:var(--radius)}
  .is-ob-title{font-size:23px}
}
`;

const newId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "c_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
};

const makeCompetitor = () => ({
  id: newId(),
  name: "",
  url: "",
  // Regional store / currency the user confirmed for this competitor.
  region: "",
  storeUrl: "",
  currency: "",
  availableStores: [],
  availableCurrencies: [],
});

/* Mirrors .btn / .btn-primary / .btn-light from the marketing site. */
const actionButtonStyle = (variant, enabled) => {
  const base = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "13px 24px",
    borderRadius: 12,
    fontWeight: 700,
    fontSize: 15,
    fontFamily: "var(--font-sans)",
    cursor: enabled ? "pointer" : "not-allowed",
    transition: "all 0.2s ease",
    whiteSpace: "nowrap",
    border: "none",
  };

  if (!enabled) {
    return { ...base, background: "var(--border)", color: "var(--text-light)" };
  }

  if (variant === "primary") {
    return {
      ...base,
      background: "var(--accent)",
      color: "#fff",
      boxShadow: "0 8px 24px rgba(255,107,107,0.3)",
    };
  }

  return {
    ...base,
    background: "#fff",
    color: "var(--primary)",
    border: "1px solid var(--border)",
    boxShadow: "var(--shadow-sm)",
  };
};

const lift = (enabled, variant) => ({
  onMouseEnter: (e) => {
    if (!enabled) return;
    e.currentTarget.style.transform = "translateY(-2px)";
    e.currentTarget.style.boxShadow =
      variant === "primary" ? "0 12px 32px rgba(255,107,107,0.4)" : "var(--shadow)";
    if (variant === "primary") e.currentTarget.style.background = "var(--accent-dark)";
  },
  onMouseLeave: (e) => {
    if (!enabled) return;
    e.currentTarget.style.transform = "translateY(0)";
    e.currentTarget.style.boxShadow =
      variant === "primary" ? "0 8px 24px rgba(255,107,107,0.3)" : "var(--shadow-sm)";
    if (variant === "primary") e.currentTarget.style.background = "var(--accent)";
  },
});

function OnBoarding() {
  const [url, setURL] = useState("");
  // IntelShift targets e-commerce; the vertical is detected from the site itself,
  // so we no longer ask. Kept as a fixed default for the fields/services that still
  // pass an "industry" hint (competitor suggestion, business context).
  const [industry] = useState("E-Commerce");
  const [workspaceName, setWorkspaceName] = useState("");
  // Regional store / currency the user confirmed for their OWN site.
  const [workspaceStore, setWorkspaceStore] = useState({
    currency: "",
    storeUrl: "",
    region: "",
    availableCurrencies: [],
  });

  // Focus categories (step 3): detected list from the owner's store + the user's
  // ordered picks (order = priority). `focusAll` = the "all categories" choice.
  const [detectedCategories, setDetectedCategories] = useState([]);
  const [focusSelected, setFocusSelected] = useState([]);
  const [focusAll, setFocusAll] = useState(false);
  const focusForUrlRef = useRef("");

  const [competitors, setCompetitors] = useState([makeCompetitor()]);
  const [activeCompetitor, setActiveCompetitor] = useState(0);

  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // True while a workspace/competitor URL is being probed for a currency
  // switcher — Next stays disabled until the check finishes.
  const [currencyChecking, setCurrencyChecking] = useState(false);
  // False when the entered website doesn't exist / can't be reached — blocks Next.
  const [urlReachable, setUrlReachable] = useState(true);

  // Site-readiness validation (homepage + collection + product must be reachable
  // before a site is confirmed). Runs on the confirm action — slow (can render JS
  // sites in a browser), so we cache passing URLs and show staged progress.
  const [validating, setValidating] = useState(false);
  const [validateStage, setValidateStage] = useState("");
  const [validateError, setValidateError] = useState("");
  // Set when a store is enterprise/marketplace-scale — shows the "talk to us" modal
  // and blocks self-serve onboarding.
  const [enterpriseBlock, setEnterpriseBlock] = useState(null);
  const validatedRef = useRef(new Map()); // cleanURL(url) -> { ok, currency }

  // Clear stale flags when moving between steps; the active step re-sets them if
  // it actually probes a URL.
  useEffect(() => {
    setCurrencyChecking(false);
    setUrlReachable(true);
    setValidateError("");
  }, [currentStep]);

  // Run the readiness check for a URL, with staged progress + result caching.
  // Returns { ok, currency }. A failed URL keeps the user on the step.
  const runValidation = async (rawUrl) => {
    const u = cleanURL(rawUrl);
    if (!u) return { ok: false };
    const cached = validatedRef.current.get(u);
    if (cached?.ok) return cached;

    const stages = [
      "Loading the homepage…",
      "Checking a collection page…",
      "Checking a product page…",
      "Reading the store currency…",
    ];
    let i = 0;
    setValidateError("");
    setValidateStage(stages[0]);
    setValidating(true);
    const timer = setInterval(() => {
      i = Math.min(i + 1, stages.length - 1);
      setValidateStage(stages[i]);
    }, 18000);

    try {
      const res = await validateSite(u);

      // Scale/marketplace gateway: giants (Amazon/Daraz) and marketplaces can't be
      // self-served — surface the "talk to us" modal and block progression, even if
      // the site itself is readable.
      if (res?.scale?.scaleTier === "enterprise") {
        setEnterpriseBlock({
          url: u,
          isMarketplace: !!res.scale.isMarketplace,
          totalProducts: res.scale.totalProducts ?? null,
          reason: res.scale.reason || "",
        });
        return { ok: false, enterprise: true };
      }

      if (res?.ok) {
        const out = { ok: true, currency: res.currency || "", categories: res.categories || [] };
        validatedRef.current.set(u, out);
        return out;
      }
      // Frame failures as "the site blocks automated access and we respect that",
      // rather than "we couldn't open a product page" (which reads like our fault).
      // Kept in sync with the server's readiness gate (siteReadiness.service.js).
      const s = res?.stages || {};
      const reason = !s.homepage?.ok
        ? "We couldn't access this store — it uses bot protection or access rules (robots.txt / Cloudflare) that block automated reading. IntelShift respects those protections and doesn't bypass them, so this site can't be monitored."
        : "We couldn't fully read this store. It likely uses access protection that stops automated reading — and we respect that, so it can't be monitored. Please try a different store URL.";
      setValidateError(reason);
      return { ok: false };
    } catch (e) {
      setValidateError(
        e?.response?.data?.message || e?.message || "We couldn't validate this store. Check the URL and try again."
      );
      return { ok: false };
    } finally {
      clearInterval(timer);
      setValidating(false);
      setValidateStage("");
    }
  };

  // Stepper "Next" hook.
  //  • Step 2 (owner URL): gate on readiness, then capture the detected categories
  //    for the focus step. Reset focus picks if the store URL changed.
  //  • Step 3 (focus): required, but not hard-blocking — if nothing is picked and
  //    "all" isn't chosen, confirm that we'll analyze everything.
  const handleBeforeNext = async (stepId) => {
    if (stepId === 2) {
      const r = await runValidation(url);
      if (!r.ok) return false;
      if (r.currency) {
        setWorkspaceStore((prev) => ({ ...prev, currency: prev.currency || r.currency }));
      }
      const cats = r.categories || [];
      setDetectedCategories(cats);
      // New store URL → clear stale focus picks.
      const cu = cleanURL(url);
      if (focusForUrlRef.current !== cu) {
        setFocusSelected([]);
        setFocusAll(false);
        focusForUrlRef.current = cu;
      }
      return true;
    }

    if (stepId === 3) {
      // Nothing detected → nothing to pick; treat as "all".
      if (!detectedCategories.length) {
        setFocusAll(true);
        return true;
      }
      if (focusAll || focusSelected.length > 0) return true;
      // Empty selection → confirm "analyze all".
      const res = await Swal.fire({
        icon: "question",
        title: "Analyze all categories?",
        text: "You haven't picked any focus categories. We'll analyze all of them. You can refine this later from your workspace.",
        showCancelButton: true,
        confirmButtonText: "Analyze all",
        cancelButtonText: "Pick focus",
      });
      if (res.isConfirmed) {
        setFocusAll(true);
        return true;
      }
      return false;
    }

    return true;
  };

  const workspace = useWorkspaceStore((state) => state.workspace);
  const user = useAuthStore((state) => state.user);
  const introCompleted = workspace?.introCompleted;
  const navigate = useNavigate();

  // Only free-trial users can switch plans mid-onboarding.
  const _sub = user?.subscription;
  const isTrialUser =
    String(_sub?.status || "").toLowerCase() === "trialing" ||
    String(user?.plan || "").toLowerCase() === "trial" ||
    Number(_sub?.planId?.price) === 0;

  /* How many competitors this plan allows. */
  const maxCompetitors = Math.max(
    1,
    user?.subscription?.planId?.limits?.competitors ??
      user?.subscription?.planId?.limits?.maxCompetitors ??
      1
  );

  const competitor = competitors[activeCompetitor] || competitors[0];
  const canAddMore = competitors.length < maxCompetitors;

  useEffect(() => {
    if (workspace && workspace.id && !introCompleted) {
      navigate("/intro", { replace: true });
    } else if (workspace && workspace.id && introCompleted) {
      navigate("/dashboard", { replace: true });
    }
  }, [workspace, navigate, introCompleted]);

  const handleLogout = () => {
    const auth = useAuthStore.getState();
    const signOut = auth?.logout || auth?.signOut || auth?.clearAuth || auth?.reset;
    if (typeof signOut === "function") signOut();
    navigate("/login", { replace: true });
  };

  const cleanName = (value) => (value || "").trim().replace(/\s+/g, " ");
  const cleanURL = (value) => {
    const raw = (value || "").trim().replace(/\s+/g, "");
    if (!raw) return raw;
    if (/^https?:\/\//i.test(raw)) return raw;
    if (raw.startsWith("//")) return "https:" + raw;
    if (!raw.includes(".")) return raw;
    return "https://" + raw.replace(/^\/+/, "");
  };

  /* ── Competitor helpers ──────────────────────────────────── */

  const updateCompetitor = (index, patch) =>
    setCompetitors((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)));

  const patchActive = (patch) => updateCompetitor(activeCompetitor, patch);

  // Changing the competitor's URL invalidates its confirmed region/currency —
  // reset those so swapping a competitor starts clean.
  const setActiveCompetitorURL = (value) => {
    setCompetitors((prev) =>
      prev.map((c, i) => {
        if (i !== activeCompetitor) return c;
        if (cleanURL(c.url) === cleanURL(value)) return { ...c, url: value };
        return {
          ...c,
          url: value,
          region: "",
          storeUrl: "",
          currency: "",
          availableStores: [],
          availableCurrencies: [],
        };
      })
    );
  };

  // Capture-first: a competitor is "resolved" once it simply has a name + URL.
  // No page matching happens here — that's done in the workspace.
  const isCompetitorResolved = (c) => Boolean(c && cleanName(c.name) && cleanURL(c.url));

  const activeResolved = isCompetitorResolved(competitor);

  const handleAddCompetitor = async () => {
    if (!canAddMore || !activeResolved || validating) return;
    // Confirm we can actually read this competitor before locking it in.
    const r = await runValidation(competitor?.url);
    if (!r.ok) return;
    if (r.currency) patchActive({ currency: competitor?.currency || r.currency });
    setCompetitors((prev) => [...prev, makeCompetitor()]);
    setActiveCompetitor(competitors.length);
    setCurrentStep(4); // stay on "add a competitor" for the new one
  };

  // Back from the Add step of competitor 2+ should return to the PREVIOUS
  // competitor's Add step, not skip the loop back to the profile.
  const handleStepChange = (next) => {
    // Back from a 2nd+ competitor's step returns to the PREVIOUS competitor's step
    // (still step 4), not out of the competitor loop.
    if (currentStep === 4 && next === 3 && activeCompetitor > 0) {
      setActiveCompetitor(activeCompetitor - 1);
      setCurrentStep(4);
      return;
    }
    setCurrentStep(next);
  };

  // Move FORWARD to the next competitor that already exists.
  const handleNextCompetitor = () => {
    if (activeCompetitor < competitors.length - 1) {
      setActiveCompetitor(activeCompetitor + 1);
      setCurrentStep(4);
    }
  };

  /* ── Submit (capture-first: URLs only → recon) ───────────── */

  const handleSubmit = async () => {
    if (isSubmitting || validating) return;

    // Gate the current competitor on readiness before starting analysis. Earlier
    // competitors were validated when they were added, so this covers the last one.
    const gate = await runValidation(competitor?.url);
    if (!gate.ok) return;
    if (gate.currency) patchActive({ currency: competitor?.currency || gate.currency });

    try {
      setIsSubmitting(true);

      const sanitizedWorkspaceName = cleanName(workspaceName);
      const sanitizedURL = cleanURL(url);

      if (!sanitizedWorkspaceName || !sanitizedURL) {
        Swal.fire({
          icon: "error",
          title: "Missing information",
          text: "Please fill in your workspace name and store URL to proceed.",
        });
        return;
      }

      const ready = competitors.filter(isCompetitorResolved);
      if (ready.length === 0) {
        Swal.fire({
          icon: "error",
          title: "No competitor added",
          text: "Add at least one competitor store before finishing.",
        });
        return;
      }

      const competitorsPayload = ready.map((c) => {
        const compUrl = cleanURL(c.url);
        return {
          name: cleanName(c.name),
          url: compUrl,
          region: c.region || "",
          storeUrl: c.storeUrl || compUrl,
          currency: c.currency || "",
        };
      });

      // Focus categories: drop any stale picks not in the detected list, keep
      // order (= priority), cap at 5. "selected" only when there are real picks
      // and the user didn't choose "all".
      const detectedNames = new Set(detectedCategories.map((c) => c.name));
      const cleanFocus = focusSelected.filter((n) => detectedNames.has(n)).slice(0, 5);
      const focusMode = !focusAll && cleanFocus.length > 0 ? "selected" : "all";

      const payload = {
        workspaceName: sanitizedWorkspaceName,
        url: sanitizedURL,
        industry,
        currency: workspaceStore.currency || "",
        region: workspaceStore.region || "",
        storeUrl: workspaceStore.storeUrl || sanitizedURL,
        competitors: competitorsPayload,
        focusMode,
        focusCategories: focusMode === "selected" ? cleanFocus : [],
      };

      await workspaceApi.createWorkspaceRecon(payload);
      await useWorkspaceStore.getState().syncWorkspace();
    } catch (error) {
      console.error("Failed to create workspace:", error);
      Swal.fire({
        icon: "error",
        title: "Couldn't create workspace",
        text:
          error?.response?.data?.message ||
          error?.message ||
          "Something went wrong while setting up your workspace. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ── Step validation ─────────────────────────────────────── */

  const isStepValid = (stepId) => {
    if (stepId === 1) return true;

    if (stepId === 2) {
      return (
        Boolean(cleanName(workspaceName) && cleanURL(url)) &&
        !currencyChecking &&
        urlReachable
      );
    }

    // Focus step: always "proceedable" — the empty case is handled by a confirm
    // in handleBeforeNext (required, but not hard-blocking).
    if (stepId === 3) return true;

    if (stepId === 4) {
      return (
        Boolean(cleanName(competitor?.name) && cleanURL(competitor?.url)) &&
        !currencyChecking &&
        urlReachable
      );
    }

    return true;
  };

  const getBlockedMessage = (stepId) => {
    if (stepId === 2) return "Workspace name and workspace URL are required.";
    if (stepId === 3) return "Pick your focus categories, or choose “all categories”.";
    if (stepId === 4) return "Provide both competitor name and competitor URL.";
    return "Please complete required fields to continue.";
  };

  const canJumpTo = (targetStep) => {
    if (targetStep <= 1) return true;
    for (let i = 1; i < targetStep; i += 1) {
      if (!isStepValid(i)) return false;
    }
    return true;
  };

  /* ── Steps ───────────────────────────────────────────────── */

  const steps = useMemo(
    () => [
      {
        id: 1,
        label: "Get Started",
        component: <WorkspaceIntro />,
      },
      {
        id: 2,
        label: "Your Workspace",
        component: (
          <WorkspaceProfile
            workspaceName={workspaceName}
            setWorkspaceName={setWorkspaceName}
            workspaceURL={url}
            setWorkspaceURL={setURL}
            workspaceStore={workspaceStore}
            onWorkspaceStoreChange={(patch) =>
              setWorkspaceStore((prev) => ({ ...prev, ...patch }))
            }
            onCurrencyCheckingChange={setCurrencyChecking}
            onUrlReachableChange={setUrlReachable}
            validating={validating}
            validateStage={validateStage}
            validateError={validateError}
          />
        ),
      },
      {
        id: 3,
        label: "Your Focus",
        component: (
          <FocusCategories
            categories={detectedCategories}
            selected={focusSelected}
            setSelected={setFocusSelected}
            allSelected={focusAll}
            setAllSelected={setFocusAll}
          />
        ),
      },
      {
        id: 4,
        label: maxCompetitors > 1 ? `Competitor ${activeCompetitor + 1}` : "Add Competitor",
        component: (
          <OnBoardCompetitor
            key={competitor?.id}
            competitorName={competitor?.name || ""}
            setCompetitorName={(value) => patchActive({ name: value })}
            competitorURL={competitor?.url || ""}
            setCompetitorURL={setActiveCompetitorURL}
            workspacePages={[]}
            workspaceName={workspaceName}
            workspaceURL={cleanURL(url)}
            industry={industry}
            workspaceCurrency={workspaceStore?.currency || ""}
            focusCategories={focusAll ? [] : focusSelected}
            competitorIndex={activeCompetitor}
            competitorTotal={maxCompetitors}
            addedCompetitors={competitors.slice(0, activeCompetitor)}
            competitorStore={{
              currency: competitor?.currency || "",
              storeUrl: competitor?.storeUrl || "",
              availableCurrencies: competitor?.availableCurrencies || [],
            }}
            onStoreChange={(patch) => patchActive(patch)}
            onCurrencyCheckingChange={setCurrencyChecking}
            onUrlReachableChange={setUrlReachable}
            validating={validating}
            validateStage={validateStage}
            validateError={validateError}
          />
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [workspaceName, url, industry, workspaceStore, competitors, activeCompetitor, maxCompetitors, validating, validateStage, validateError, detectedCategories, focusSelected, focusAll]
  );

  /* ── Final-step actions ──────────────────────────────────── */

  const remaining = maxCompetitors - competitors.length;
  const hasNextCompetitor = activeCompetitor < competitors.length - 1;

  const nextCompetitorButton = (
    <button
      key="next-comp"
      type="button"
      onClick={handleNextCompetitor}
      disabled={!activeResolved}
      style={actionButtonStyle("secondary", activeResolved)}
      {...lift(activeResolved, "secondary")}
      title={activeResolved ? "Continue to your next competitor" : "Add this competitor's URL first"}
    >
      Next competitor
      <ArrowRight size={16} />
    </button>
  );

  const finishButton = (
    <button
      key="finish"
      type="button"
      onClick={handleSubmit}
      disabled={!activeResolved || isSubmitting}
      style={actionButtonStyle("primary", activeResolved && !isSubmitting)}
      {...lift(activeResolved && !isSubmitting, "primary")}
      className="border! border-(--accent)! hover:text-black!"
      title="Finish and start capturing each store"
    >
      <Clock size={16} />
      {isSubmitting ? "Setting up…" : "Finish & capture"}
    </button>
  );

  const finalActions = hasNextCompetitor
    ? [nextCompetitorButton, finishButton]
    : canAddMore
    ? [
        <button
          key="add"
          type="button"
          onClick={handleAddCompetitor}
          disabled={!activeResolved}
          style={actionButtonStyle("secondary", activeResolved)}
          {...lift(activeResolved, "secondary")}
          title={activeResolved ? "Set up another competitor now" : "Add this competitor's URL first"}
        >
          <Plus size={16} />
          Add another competitor
          {remaining > 0 ? ` (${remaining} left)` : ""}
        </button>,
        finishButton,
      ]
    : [
        <button
          key="complete"
          type="button"
          onClick={handleSubmit}
          disabled={!activeResolved || isSubmitting}
          style={actionButtonStyle("primary", activeResolved && !isSubmitting)}
          {...lift(activeResolved && !isSubmitting, "primary")}
        >
          <Check size={16} />
          {isSubmitting ? "Setting up…" : "Complete onboarding"}
        </button>,
      ];

  return (
    <>
      <OnboardingHeader onLogout={handleLogout}>
        {isTrialUser ? (
          <button type="button" className="is-logout" onClick={() => navigate("/billing")}>
            <CreditCard size={14} />
            Change plan
          </button>
        ) : (
          <span
            className="is-logout"
            style={{ opacity: 0.5, cursor: "not-allowed" }}
            title="You can change your plan any time after setting up your workspace — from Billing & Usage."
          >
            <CreditCard size={14} />
            Change plan
          </span>
        )}
      </OnboardingHeader>
      <style>{shellCss}</style>

      <div
        className="is-ob-shell"
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "center",
          background: "var(--background)",
        }}
      >
        <div className="is-ob-card">
          <div style={{ textAlign: "center", marginBottom: "1.75rem" }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "6px 14px",
                borderRadius: 999,
                background: "rgba(78,205,196,0.1)",
                color: "var(--secondary)",
                border: "1px solid rgba(78,205,196,0.25)",
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                marginBottom: 16,
              }}
            >
              <span className="is-ob-dot" aria-hidden="true" />
              Setup
            </span>

            <h2 className="is-ob-title">Welcome to IntelShift AI</h2>

            <p style={{ color: "var(--text-light)", fontSize: 15, lineHeight: 1.6, margin: 0 }}>
              Add your store and your competitors — we'll capture each one, then you choose what to track.
            </p>
          </div>

          <ProcessStepper
            currentStep={currentStep}
            steps={steps}
            onStepChange={handleStepChange}
            canProceed={isStepValid(currentStep) && !validating}
            nextBlockedMessage={getBlockedMessage(currentStep)}
            canJumpTo={canJumpTo}
            onBeforeNext={handleBeforeNext}
            finalActions={finalActions}
          />
        </div>
      </div>

      <EnterpriseGateModal
        open={!!enterpriseBlock}
        info={enterpriseBlock}
        onClose={() => setEnterpriseBlock(null)}
      />
    </>
  );
}

export default OnBoarding;
