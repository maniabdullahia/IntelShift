import { useState, useEffect, useRef } from "react";
import { Bell } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getNotifications, markNotificationsRead } from "../../../api/notification.api";
import useNotificationStore from "../../../store/notification.store";

/* Header notification bell. Reads from the shared notification store, which is
   updated live by the socket handler (`notification:new`) — no polling. On
   mount it does a one-time fetch to seed history. */
export default function NotificationBell() {
  const items = useNotificationStore((s) => s.items);
  const unread = useNotificationStore((s) => s.unread);
  const setAll = useNotificationStore((s) => s.setAll);
  const markAllReadLocal = useNotificationStore((s) => s.markAllRead);

  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  // One-time seed from the server (history + unread count). Live updates after
  // this arrive via the socket handler.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await getNotifications();
        if (alive) setAll(d?.notifications || [], d?.unread || 0);
      } catch {
        /* silent */
      }
    })();
    return () => { alive = false; };
  }, [setAll]);

  useEffect(() => {
    const onOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  const togglePanel = async () => {
    const opening = !open;
    setOpen(opening);
    if (opening && unread > 0) {
      markAllReadLocal();
      try { await markNotificationsRead(); } catch { /* ignore */ }
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={togglePanel}
        aria-label="Notifications"
        className="relative p-2 rounded-lg border border-gray-200 text-gray-700 bg-white transition-all duration-200 hover:bg-gray-50 hover:border-gray-300 active:scale-95"
      >
        <Bell size={20} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-(--accent) text-white text-[10px] font-bold flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 w-80 max-h-96 overflow-y-auto bg-white rounded-xl shadow-xl border border-gray-100 z-50">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-bold text-(--primary)">Notifications</p>
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-(--text-light)">No notifications yet</p>
          ) : (
            items.map((n) => (
              <button
                key={n._id}
                type="button"
                onClick={() => { if (n.link) navigate(n.link); setOpen(false); }}
                className={`block w-full text-left px-4 py-3 border-b border-gray-50 transition hover:bg-(--bg) ${n.read ? "" : "bg-[rgba(255,107,107,0.04)]"}`}
              >
                <p className="text-sm font-semibold text-(--primary)">{n.title}</p>
                {n.body && <p className="mt-0.5 text-xs text-(--text-light) line-clamp-2">{n.body}</p>}
                <p className="mt-1 text-[11px] text-(--text-light)">{n.createdAt ? new Date(n.createdAt).toLocaleString() : ""}</p>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
