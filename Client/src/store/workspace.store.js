import { create } from "zustand";
import { persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

import {
  getWorkspace,
  createWorkspace,
  updateWorkspace,
  deleteWorkspace,
  createWorkspaceWithCompetitor,
} from "../api/workspace.api";

import {
  createCompetitor,
  updateCompetitor,
  deleteCompetitor,
  undoCompetitorChange,
} from "../api/competitor.api";

const useWorkspaceStore = create(
  persist(
    immer((set, get) => ({
      workspace: null,
      isSyncing: false,
      isworkspaceAnalyzing: false,

    setWorkspace: (workspace) => set({ workspace }),
    setSyncing: (bool) => set({ isSyncing: bool }),

    syncWorkspace: async () => {
      set({ isSyncing: true });

      try {
        const data = await getWorkspace();

        set((state) => {
          state.workspace = data;
        });

        return data;
      } catch (error) {
        console.error("Failed to sync workspace:", error);
        throw error;
      } finally {
        set({ isSyncing: false });
      }
    },

    createWorkspace: async (workspaceData) => {
      try {
        const data = await createWorkspace(workspaceData);

        set((state) => {
          state.workspace = data;
        });

        return data;
      } catch (error) {
        console.error("Failed to create workspace:", error);
        throw error;
      }
    },

    createWorkspaceWithCompetitor: async (workspaceData) => {
      try {
        const data = await createWorkspaceWithCompetitor(workspaceData);

        set((state) => {
          state.workspace = data;
        });

        return data;
      } catch (error) {
        console.error(
          "Failed to create workspace with competitor:",
          error
        );
        throw error;
      }
    },

    updateWorkspace: async (workspaceData) => {
      try {
        const data = await updateWorkspace(workspaceData);

        set((state) => {
          if (!state.workspace) return;
          if (data?.name !== undefined) state.workspace.name = data.name;
          if (data?.industry !== undefined) state.workspace.industry = data.industry;
        });

        return data;
      } catch (error) {
        console.error("Failed to update workspace:", error);
        throw error;
      }
    },

    deleteWorkspace: async () => {
      try {
        await deleteWorkspace();

        set((state) => {
          state.workspace = null;
          state.isworkspaceAnalyzing = false;
        });
      } catch (error) {
        console.error("Failed to delete workspace:", error);
        throw error;
      }
    },

    clearStorage: () => {
      set((state) => {
        state.workspace = null;
        state.isSyncing = false;
        state.isworkspaceAnalyzing = false;
      });
    },

    addCompetitor: async (competitor) => {
      try {
        const data = await createCompetitor(competitor);
        // Staged endpoint returns { competitor, pending, message }.
        const created = data?.competitor || data;

        set((state) => {
          if (!state.workspace) return;

          if (!Array.isArray(state.workspace.competitors)) {
            state.workspace.competitors = [];
          }

          if (created) state.workspace.competitors.push(created);
        });

        return data;
      } catch (error) {
        console.error("Failed to add competitor:", error);
        throw error;
      }
    },

    updateCompetitor: async (competitor) => {
      try {
        const data = await updateCompetitor(competitor);

        set((state) => {
          if (!state.workspace?.competitors) return;

          const index = state.workspace.competitors.findIndex(
            (c) => c._id === data._id
          );

          if (index !== -1) {
            state.workspace.competitors[index] = data;
          }
        });

        return data;
      } catch (error) {
        console.error("Failed to update competitor:", error);
        throw error;
      }
    },

    deleteCompetitor: async (competitorId, workspaceId) => {
      try {
        const res = await deleteCompetitor({ workspaceId, competitorId });

        set((state) => {
          if (!state.workspace?.competitors) return;
          if (res?.dropped) {
            // Was a never-analyzed staged add — remove outright.
            state.workspace.competitors = state.workspace.competitors.filter(
              (c) => c._id !== competitorId
            );
          } else {
            // Staged for removal — keep visible, mark pending.
            const c = state.workspace.competitors.find((c) => c._id === competitorId);
            if (c) c.pendingChange = "remove";
          }
        });
        return res;
      } catch (error) {
        console.error("Failed to delete competitor:", error);
        throw error;
      }
    },

    undoCompetitor: async (competitorId) => {
      try {
        const res = await undoCompetitorChange({ competitorId });
        set((state) => {
          if (!state.workspace?.competitors) return;
          if (res?.removed) {
            // Undoing a staged add drops it.
            state.workspace.competitors = state.workspace.competitors.filter(
              (c) => c._id !== competitorId
            );
          } else {
            const c = state.workspace.competitors.find((c) => c._id === competitorId);
            if (c) c.pendingChange = "none";
          }
        });
        return res;
      } catch (error) {
        console.error("Failed to undo competitor change:", error);
        throw error;
      }
    },

    updateWorkspaceStatus: async (status) => {
      const normalizedStatus = String(status).toLowerCase();

      set((state) => {
        if (!state.workspace) return;

        state.isworkspaceAnalyzing =
          normalizedStatus === "processing";

        state.workspace.scanStatus = status;
      });

      if (normalizedStatus === "completed") {
        await get().syncWorkspace();
      }
    },

    updateCompetitorStatus: (competitorId, status) => {
      set((state) => {
        const competitor = state.workspace?.competitors?.find(
          (c) => c._id === competitorId
        );

        if (competitor) {
          competitor.scanStatus = status;
        }
      });
    },

    updatePageStatus: (competitorId, pageId, status) => {
      set((state) => {
        const competitor = state.workspace?.competitors?.find(
          (c) => String(c._id) === String(competitorId)
        );

        if (!competitor?.pages) return;

        const page = competitor.pages.find(
          (p) => String(p._id) === String(pageId)
        );

        if (page) {
          page.scanStatus = status;
        }
      });
    },
  })),
  {
    name: "workspace-storage",
  })
);

export default useWorkspaceStore;