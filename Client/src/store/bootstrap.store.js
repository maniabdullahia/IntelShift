import { create } from "zustand";

import useAuthStore from "./auth.store";
import useWorkspaceStore from "./workspace.store";

const useBootstrapStore = create((set, get) => ({
  bootstrapped: false,
  syncing: false,

  syncData: async () => {
    if (get().syncing) return;

    const { hasHydrated, isAuthenticated, syncUser } =
      useAuthStore.getState();

    const { syncWorkspace } = useWorkspaceStore.getState();

    if (!hasHydrated) {
      set({ bootstrapped: false });
      return;
    }

    if (!isAuthenticated) {
      set({ bootstrapped: true });
      return;
    }

    set({
      syncing: true,
      bootstrapped: false,
    });

    try {
      await syncUser();
      await syncWorkspace();

      set({
        bootstrapped: true,
        syncing: false,
      });
    } catch (error) {
      console.error("Bootstrap failed:", error);

      set({
        syncing: false,
        bootstrapped: false,
      });
    }
  },
}));

export default useBootstrapStore;