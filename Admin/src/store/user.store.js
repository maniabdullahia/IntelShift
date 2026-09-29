import { create } from "zustand";
import { persist } from "zustand/middleware";

import { getUsers } from "../api/user.api.js";

const useUserStore = create(
    persist(
        (set) => ({
            users: [],
            setUsers: (users) => set({ users }),
            loadUsers: async (page, limit) => {
                const response = await getUsers(page, limit);
                console.log("API response for users:", response);
                set({ users: response || [] });
                console.log(`Loaded ${response?.length || 0} users from API`);
            }
        }),
        {
            name: "user-storage",
        }
    )
);

export default useUserStore;