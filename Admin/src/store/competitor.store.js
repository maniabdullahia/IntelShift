import { create } from "zustand";
import { persist } from "zustand/middleware";

import { getCompetitors } from "../api/competitor.api"

const useCompetitorStore = create(
    persist(
        (set) => ({
            competitors: [],
            setCompetitors: (competitors) => set({ competitors }),
            loadCompetitors: async (page, limit) => {
                const response = await getCompetitors(page, limit);
                
                set({ competitors: response });
                console.log(`Loaded ${response?.length || 0} competitors from API`);
            }
        }),
        {
            name: "competitor-storage",
        }
    )
);

export default useCompetitorStore;