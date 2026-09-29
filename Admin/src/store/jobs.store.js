import { create } from "zustand";
import { persist } from "zustand/middleware";

import { getJobs } from "../api/jobs.api";

const useJobStore = create(
    persist(
        (set) => ({
            jobs: [],
            setJobs: (jobs) => set({ jobs }),
            loadJobs: async (page, limit) => {
                const response = await getJobs(page, limit);
                console.log(response, 'response jobs');
                set({ jobs: response });
                console.log(`Loaded ${response?.length || 0} jobs from API`);
            }
        }),
        {
            name: "job-storage",
        }
    )
);

export default useJobStore;