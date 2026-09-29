import { create } from "zustand";
import { persist } from "zustand/middleware";

import { login as loginApi } from "../api/auth.api";

const useAuthStore = create(
    persist(
        (set) => ({
            user: null,
            token: null,
            isAuthenticated: false,

            login: async (email, password) => {
                try {
                    const response = await loginApi(email, password);

                    set({
                        user: response.user,
                        token: response.accessToken,
                        isAuthenticated: true,
                    });

                    console.log("Login successful:", response);
                } catch (error) {
                    console.error("Login failed:", error.message);

                    set({
                        user: null,
                        token: null,
                        isAuthenticated: false,
                    });

                    return {
                        success: false,
                        error: error.message,
                    };
                }
            },

            logout: () =>
                set({
                    user: null,
                    token: null,
                    isAuthenticated: false,
                }),
        }),
        {
            name: "auth-storage",
        }
    )
);

export default useAuthStore;