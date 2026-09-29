import { create } from "zustand";
import { persist } from "zustand/middleware";

import { getProfile, updateProfile, changePlan } from "../api/user.api";
import { register } from "../api/auth.api";

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      hasHydrated: false,
      isSyncing: false,

      register: async (data) => {
        try {
          const response = await register(data);
          set({
            user: response.user,
            token: response.accessToken,
            isAuthenticated: true,
          });
          return response;
        } catch (error) {
          console.error("Registration failed:", error);
          throw error;
        }
      },

      login: (user, token) =>
        set({
          user,
          token,
          isAuthenticated: true,
        }),

      setToken: (token) =>
        set({
          token,
          isAuthenticated: !!token,
        }),

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isSyncing: false,
        });
        localStorage.removeItem("auth-storage");
      },

      changePlan: async (planId, subscriptionId, priceId) => {
        await changePlan(planId, subscriptionId, priceId)
          .then((data) => set({ user: data.user }))
          .catch((error) => console.error("Failed to change plan:", error));
      },

      setSyncing: (bool) => set({ isSyncing: bool }),
      setHasHydrated: (bool) => set({ hasHydrated: bool }),

      syncUser: async () => {
        set({ isSyncing: true });
        try {
          const data = await getProfile();
          set({ user: data });
          return data;
        } catch (error) {
          console.error("Failed to sync user:", error);
        } finally {
          set({ isSyncing: false });
        }
      },

      updateUserProfile: async(data) => {
        await updateProfile(data);
        set((state) => ({
          user: {
            ...state.user,
            ...data,
          },
        }));
      }
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);

export default useAuthStore;
