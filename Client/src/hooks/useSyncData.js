/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState } from "react";
import useAuthStore from "../store/auth.store";
import useWorkspaceStore from "../store/workspace.store";

export const useSyncData = () => {

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [bootstrapPhase, setBootstrapPhase] = useState("hydrating");
  const [authHydrated, setAuthHydrated] = useState(false);
  const [workspaceHydrated, setWorkspaceHydrated] = useState(false);
  const [authSyncing, setAuthSyncing] = useState(false);
  const [workspaceSyncing, setWorkspaceSyncing] = useState(false);

  useEffect(() => {
    let isCancelled = false;

    const runBootstrap = async () => {
      if (!hasHydrated) {
        setBootstrapped(false);
        setBootstrapPhase("hydrating");
        setAuthHydrated(false);
        setWorkspaceHydrated(false);
        return;
      }

      setBootstrapped(false);
      setBootstrapPhase("hydrating");
      setAuthHydrated(false);
      setWorkspaceHydrated(false);

      if (!isAuthenticated) {
        if (!isCancelled) {
          setBootstrapPhase("ready");
          setBootstrapped(true);
          setAuthHydrated(true);
          setWorkspaceHydrated(true);
        }
        return;
      }

      setBootstrapPhase("loading-user");
      setAuthSyncing(true);
      
      try {
        const user = await useAuthStore.getState().syncUser();

        if (isCancelled) return;

        setAuthHydrated(true);
        setAuthSyncing(false);
        setBootstrapPhase("checking-billing");

        if (!user?.subscription) {
          setBootstrapPhase("billing-required");
          setBootstrapped(true);
          setWorkspaceHydrated(true);
          return;
        }

        setBootstrapPhase("loading-workspace");
        setWorkspaceSyncing(true);

        try {
          await useWorkspaceStore.getState().syncWorkspace();

          if (isCancelled) return;

          setWorkspaceHydrated(true);
          setWorkspaceSyncing(false);
          setBootstrapPhase("ready");
          setBootstrapped(true);
        } catch (workspaceError) {
          console.error("Failed to load workspace:", workspaceError);
          
          if (!isCancelled) {
            setWorkspaceHydrated(false);
            setWorkspaceSyncing(false);
            setBootstrapPhase("ready");
            setBootstrapped(true);
          }
        }
      } catch (authError) {
        console.error("Failed to load user:", authError);
        
        if (!isCancelled) {
          setAuthHydrated(false);
          setAuthSyncing(false);
          setBootstrapPhase("ready");
          setBootstrapped(true);
        }
      }
    };

    runBootstrap();

    return () => {
      isCancelled = true;
    }
  }, [hasHydrated, isAuthenticated]);

  return { 
    bootstrapped, 
    bootstrapPhase,
    authHydrated,
    workspaceHydrated,
    authSyncing,
    workspaceSyncing
  };

  // useEffect(() => {
  //   if (isAuthenticated) {
  //     const handleFocus = () => {
  //       useAuthStore.getState().syncUser();
  //       useWorkspaceStore.getState().syncWorkspace();
  //     };
  //     window.addEventListener("focus", handleFocus);
  //     return () => window.removeEventListener("focus", handleFocus);
  //   }
  // }, [isAuthenticated]);
};