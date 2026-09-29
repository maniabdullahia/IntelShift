import { create } from "zustand";
import { immer } from "zustand/middleware/immer";

import { getAIUsageStats } from "../api/usage.ai.api";

const useAIUsageStore = create(
    immer((set) => ({
        usage: {},
        setUsage: (newUsage) =>
            set((state) => {
                state.usage = newUsage;
            }),
        loadUsage: async () => {
            try {
                const response = await getAIUsageStats();
                set((state) => {
                    state.usage = response;
                });
            } catch (error) {
                console.error("Error loading AI usage stats:", error);
            }
            },
    }))
);

export default useAIUsageStore;
