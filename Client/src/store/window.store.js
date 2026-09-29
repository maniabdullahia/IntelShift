import { create } from "zustand";

/**
 * Window/layout UI state.
 *
 * Navigation is owned entirely by react-router (see Router.jsx). This store now
 * only holds transient layout state — currently the mobile sidebar drawer.
 * The former `currentScreen` screen-switch machinery was removed in favour of
 * URL-based routing; every navigation already went through react-router.
 */
const useWindowController = create((set) => ({
    showSidebar: false,
    setShowSidebar: (show) => set({ showSidebar: show }),
    toggleSidebar: () => set((state) => ({ showSidebar: !state.showSidebar })),
}));

export default useWindowController;
