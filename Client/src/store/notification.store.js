import { create } from "zustand";

/**
 * Notification store — shared between the header bell and the socket handler,
 * so a live `notification:new` socket event updates the bell instantly (no poll).
 */
const useNotificationStore = create((set) => ({
  items: [],
  unread: 0,

  setAll: (items, unread) =>
    set({ items: items || [], unread: unread ?? 0 }),

  addOne: (n) =>
    set((s) => ({
      items: [
        {
          _id: n._id || `live-${Date.now()}`,
          type: n.type || "change_alert",
          title: n.title,
          body: n.body || "",
          link: n.link || "/dashboard",
          read: false,
          createdAt: n.createdAt || new Date().toISOString(),
        },
        ...s.items,
      ].slice(0, 30),
      unread: s.unread + 1,
    })),

  markAllRead: () =>
    set((s) => ({ unread: 0, items: s.items.map((i) => ({ ...i, read: true })) })),
}));

export default useNotificationStore;
