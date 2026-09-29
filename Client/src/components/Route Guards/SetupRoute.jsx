import useAuthStore from "../../store/auth.store";
import useWorkspaceStore from "../../store/workspace.store";

import { useEffect } from "react";
import { joinWorkspace } from "../../socket/socketManager";

import { Navigate, useLocation } from "react-router-dom";
import { logout } from "../../api/user.api";

const SetupRoute = ({ children }) => {
  const { user } = useAuthStore();
  const { workspace } = useWorkspaceStore();
  const { pathname } = useLocation();

  const workspaceId = workspace?.id;

  const isEmailVerified = user?.isEmailVerified;
  const haveSubscription = Boolean(user?.subscription);
  const needsWorkspace = !workspace;
  const firstAnalysis = Boolean(workspace?.analysis?.length > 0);

  useEffect(() => {
    if (workspaceId) {
      joinWorkspace(workspaceId);
      console.log("Joined workspace room:", workspaceId);
    }
  }, [workspaceId]);

  if (!user) {
    logout();
  }

  // Checkout + the post-payment success page must be reachable at any setup
  // stage. In particular, right after payment the subscription webhook hasn't
  // landed yet, so the store still shows no subscription — without this, the
  // guard would bounce /billing-success back to /billing (the plans page).
  // BillingSuccess itself polls syncUser until the paid plan appears.
  if (pathname === "/checkout" || pathname === "/billing-success") {
    return children;
  }

  if (!isEmailVerified) {
    return <Navigate to="/email-verification" replace />;
  }

  if (!haveSubscription) {
    if (pathname !== "/billing") {
      return <Navigate to="/billing" replace />;
    }

    return children;
  }

  // ── Capture-first setup routing ──────────────────────────────────────────
  // A recon-created workspace walks recon → selecting → analyzing → ready. Route
  // on that stage BEFORE the legacy analysis-based rules below. Legacy workspaces
  // have setupStage "ready" (or undefined) and fall straight through, unchanged.
  const setupStage = workspace?.setupStage;
  if (workspace && setupStage === "recon") {
    // Capturing every site — the recon progress screen lives at /intro.
    if (pathname !== "/intro") {
      return <Navigate to="/intro" replace />;
    }
    return children;
  }
  if (workspace && setupStage === "selecting") {
    // Recon done — page selection + mapping happen in the workspace panel, so
    // the dashboard/analysis routes must be reachable even before any analysis.
    if (pathname === "/billing" || pathname === "/onboarding" || pathname === "/intro") {
      return <Navigate to="/dashboard" replace />;
    }
    return children;
  }
  if (workspace && setupStage === "analyzing") {
    // Deep crawl running — progress lives inside the in-workspace modal, so keep
    // the dashboard reachable (don't bounce to the /intro progress screen).
    if (pathname === "/billing" || pathname === "/onboarding" || pathname === "/intro") {
      return <Navigate to="/dashboard" replace />;
    }
    return children;
  }

  if (needsWorkspace) {
    // Free-trial users are allowed to revisit /billing mid-onboarding to change
    // their plan (safe — no active paid subscription to duplicate). Paid users
    // stay on /onboarding.
    const sub = user?.subscription;
    const isTrial =
      String(sub?.status || "").toLowerCase() === "trialing" ||
      String(user?.plan || "").toLowerCase() === "trial" ||
      Number(sub?.planId?.price) === 0;

    if (pathname === "/billing" && isTrial) {
      return children;
    }

    if (pathname !== "/onboarding") {
      return <Navigate to="/onboarding" replace />;
    }

    return children;
  }

  if (!firstAnalysis) {
    if (pathname !== "/intro") {
      return <Navigate to="/intro" replace />;
    }
    return children;
  }

  if (pathname === "/billing" || pathname === "/onboarding") {
    const nextPath = workspace?.introCompleted ? "/dashboard" : "/intro";
    return <Navigate to={nextPath} replace />;
  }

  return children;
};

export default SetupRoute;
