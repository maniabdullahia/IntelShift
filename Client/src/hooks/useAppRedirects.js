import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useWorkspaceStore from "../store/workspace.store";

const useAppRedirects = ({
  bootstrapped,
  authHydrated,
  workspaceHydrated,
  authSyncing,
  workspaceSyncing,
  user,
  workspace,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const introCompleted = useWorkspaceStore((state) => state?.introCompleted);

  useEffect(() => {
    if (
      !bootstrapped ||
      !authHydrated ||
      !workspaceHydrated ||
      authSyncing ||
      workspaceSyncing
    ) {
      return;
    }

    const hasSubscription = !!user?.subscription;

    if (user && !hasSubscription && location.pathname !== "/billing") {
      navigate("/billing", { replace: true });
      return;
    }

    if (user && !workspace && location.pathname !== "/onboarding") {
      navigate("/onboarding", { replace: true });
      return;
    }

    // If intro has been completed and user tries to go back to /intro, redirect to /analysis
    if (introCompleted && location.pathname === "/intro") {
      navigate("/analysis", { replace: true });
    }
  }, [
    bootstrapped,
    authHydrated,
    workspaceHydrated,
    authSyncing,
    workspaceSyncing,
    workspace,
    user,
    navigate,
    location.pathname,
    introCompleted,
  ]);
};

export default useAppRedirects;