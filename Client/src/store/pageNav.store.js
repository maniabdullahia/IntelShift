import { create } from "zustand";

/**
 * Contextual header navigation. A screen (e.g. the Analysis page) publishes the
 * options relevant to what's open — the global Header renders and controls them.
 * Screens with no contextual options leave it null and the Header stays minimal.
 *
 *   nav: { items: [{ key, label, count, dot }], activeKey } | null
 *   onSelect(key): called when the user picks a header option
 */
const usePageNav = create((set) => ({
  nav: null,
  onSelect: () => {},
  setNav: (nav, onSelect) => set({ nav, onSelect: onSelect || (() => {}) }),
  clearNav: () => set({ nav: null, onSelect: () => {} }),
}));

export default usePageNav;
