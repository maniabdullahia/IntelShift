import { create } from "zustand";
import { persist } from "zustand/middleware";

import { getWorkspaces } from "../api/workspace.api"

const useWorkspaceStore = create(
    persist(
        (set) => ({
            workspaces: [],
            setWorkspaces: (workspaces) => set({ workspaces }),
            loadWorkspaces: async (page, limit) => {
                const response = await getWorkspaces(page, limit);
                set({ workspaces: response?.workspaces });
                console.log(`Loaded ${response?.workspaces?.length || 0} workspaces from API`);
            }
        }),
        {
            name: "workspace-storage",
        }
    )
);

export default useWorkspaceStore;