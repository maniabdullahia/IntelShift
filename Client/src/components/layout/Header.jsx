import { useState, useRef, useEffect } from "react";
import useAuthStore from "../../store/auth.store";
import { logout } from "../../api/user.api";
import useWindowController from "../../store/window.store";
import useWorkspaceStore from "../../store/workspace.store";
import { useNavigate, useLocation } from "react-router-dom";
import { Menu, Settings, LogOut, CreditCard } from "lucide-react";

import NotificationBell from "../features/Notifications/NotificationBell";
import usePageNav from "../../store/pageNav.store";

// Sub-navigation shown in the header when on any /settings/* screen.
const SETTINGS_TABS = [
  { path: "/settings/profile", label: "Profile" },
  { path: "/settings/billing", label: "Billing & Usage" },
  { path: "/settings/workspace", label: "Workspace" },
  { path: "/settings/alerts", label: "Alerts" },
];

function Header() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const toggleSidebar = useWindowController((state) => state.toggleSidebar);
  const workspace = useWorkspaceStore((state) => state.workspace);
  const competitors = workspace?.competitors?.filter((c) => c.role === "Competitor") || [];
  const isWorkspaceAnalyzing = useWorkspaceStore((state) => state.isworkspaceAnalyzing);

  const competitorLimit = useAuthStore(
    (state) => state?.user?.subscription?.planId?.limits?.competitors,
  );
  const totalCompetitors = competitors.length;

  const planName = useAuthStore((state) => state?.user?.subscription?.planId?.displayName) || "";
  const isPro = String(planName).toLowerCase() === "pro";
  const usagePct = competitorLimit ? Math.min((totalCompetitors / competitorLimit) * 100, 100) : 0;

  // Contextual nav published by the current screen (e.g. Analysis tabs).
  const nav = usePageNav((state) => state.nav);
  const onSelectNav = usePageNav((state) => state.onSelect);

  const location = useLocation();
  const onSettings = location.pathname.startsWith("/settings");

  // Unified header tab list: settings sub-nav on /settings/*, otherwise whatever
  // the current screen published (Analysis sections, Change Detail competitors…).
  const headerTabs = onSettings
    ? SETTINGS_TABS.map((t) => ({
        key: t.path,
        label: t.label,
        active: location.pathname === t.path,
        onClick: () => navigate(t.path),
      }))
    : (nav?.items || []).map((item) => ({
        key: item.key,
        label: item.label,
        count: item.count,
        dot: item.dot,
        active: item.key === nav.activeKey,
        onClick: () => onSelectNav(item.key),
      }));


  const [open, setOpen] = useState(false);
  const [usageOpen, setUsageOpen] = useState(false);
  const dropdownRef = useRef(null);

  const atCapacity = competitorLimit != null && totalCompetitors >= competitorLimit;

  const initials = user?.name
    ? user.name
      .split(" ")
      .map((n) => n[0])
      .join("")
    : "U";

  const handleLogout = async () => {
    try {
      setOpen(false);
      await logout();
    } catch (error) {
      console.error("❌ Logout failed:", error);
    }
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
        setUsageOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="bg-white border-b border-gray-100 sticky top-0 z-30 shadow-sm">
      <div className="container mx-auto px-3 py-2.5 sm:px-4 flex items-center justify-between gap-3">
        {/* LEFT SECTION — contextual options for the open page (e.g. Analysis tabs) */}
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {headerTabs.length > 0 && (
            <nav
              aria-label="Page sections"
              className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
            >
              {headerTabs.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={item.onClick}
                  className={`relative flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-[13px] font-semibold transition md:px-3.5 md:py-1.5 md:text-sm ${item.active
                      ? "bg-(--primary) text-white shadow-sm"
                      : "text-(--text-light) hover:bg-[rgba(26,26,46,0.06)] hover:text-(--primary)"
                    }`}
                >
                  {item.label}
                  {item.count ? (
                    <span className={`rounded-full px-1.5 text-[11px] font-bold ${item.active ? "bg-white/15" : "bg-(--border)"}`}>{item.count}</span>
                  ) : null}
                  {item.dot ? <span className="h-1.5 w-1.5 rounded-full bg-(--accent)" title="High-severity findings" /> : null}
                </button>
              ))}
            </nav>
          )}

          {isWorkspaceAnalyzing && (
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 border border-amber-200">
              <span className="relative inline-block w-1.5 h-1.5">
                <span className="absolute inset-0 bg-amber-600 rounded-full animate-pulse"></span>
              </span>
              <span className="hidden sm:inline">Analyzing...</span>
            </span>
          )}
        </div>

        {/* RIGHT SECTION */}
        <div className="shrink-0 flex items-center gap-2 relative" ref={dropdownRef}>
          {/* Usage pill — shows competitor capacity for every plan and opens an
              add-competitor / upgrade popover. Upgrade is hidden entirely for Pro. */}
          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => { setUsageOpen((v) => !v); setOpen(false); }}
              aria-label="Competitor usage"
              className="flex items-center gap-2 rounded-full border border-gray-200 bg-[#f8f9fa] px-2.5 py-1.5 transition hover:border-gray-300 active:scale-95"
            >
              <span className="text-xs font-semibold text-(--primary) whitespace-nowrap">
                {totalCompetitors}/{competitorLimit ?? '—'}
              </span>
              <span className="hidden md:block h-1.5 w-14 overflow-hidden rounded-full bg-gray-200">
                <span className={`block h-full rounded-full ${atCapacity ? 'bg-(--accent)' : 'bg-(--secondary)'}`} style={{ width: `${usagePct}%` }} />
              </span>
              {!isPro && <span className="hidden sm:inline text-xs font-bold text-(--secondary-dark)">Upgrade</span>}
            </button>

            {usageOpen && (
              <div className="absolute right-0 top-11 w-64 rounded-xl border border-gray-100 bg-white p-4 shadow-xl z-50">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Competitors</p>
                <p className="mt-1 text-sm text-(--text)">
                  <span className="font-bold text-(--primary)">{totalCompetitors}</span> of {competitorLimit ?? '—'} used{planName ? ` · ${planName}` : ''}
                </p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-100">
                  <div className={`h-full rounded-full ${atCapacity ? 'bg-(--accent)' : 'bg-(--secondary)'}`} style={{ width: `${usagePct}%` }} />
                </div>

                {!atCapacity ? (
                  <button
                    type="button"
                    onClick={() => { setUsageOpen(false); navigate('/competitors?add=1'); }}
                    className="mt-4 w-full rounded-lg bg-(--secondary) px-3 py-2 text-sm font-bold text-white transition hover:opacity-90"
                  >
                    ＋ Add competitor
                  </button>
                ) : (
                  <div className="mt-3">
                    <p className="text-xs text-(--text-light)">You've used all your competitor slots.</p>
                    {!isPro && (
                      <button
                        type="button"
                        onClick={() => { setUsageOpen(false); navigate('/settings/billing'); }}
                        className="mt-2 w-full rounded-lg bg-(--accent) px-3 py-2 text-sm font-bold text-white transition hover:bg-(--accent-dark)"
                      >
                        Upgrade to add more
                      </button>
                    )}
                  </div>
                )}

                {!isPro && !atCapacity && (
                  <button
                    type="button"
                    onClick={() => { setUsageOpen(false); navigate('/settings/billing'); }}
                    className="mt-2 w-full rounded-lg border border-(--border) px-3 py-2 text-sm font-semibold text-(--text-light) transition hover:border-(--primary) hover:text-(--primary)"
                  >
                    Upgrade plan
                  </button>
                )}
              </div>
            )}
          </div>

          <NotificationBell />

          <button
            type="button"
            onClick={toggleSidebar}
            className="lg:hidden p-2 rounded-lg border border-gray-200 text-gray-700 bg-white transition-all duration-200 hover:bg-gray-50 hover:border-gray-300 active:scale-95"
            aria-label="Toggle sidebar"
          >
            <Menu size={20} />
          </button>

          {/* Avatar */}
          <span
            onClick={() => { setOpen((prev) => !prev); setUsageOpen(false); }}
            className="hidden lg:flex overflow-hidden text-white w-9 h-9 rounded-full bg-linear-to-br from-(--secondary) to-(--accent) items-center justify-center text-sm font-semibold cursor-pointer shadow-md hover:shadow-lg transition-all duration-200 hover:scale-105"
          >
            {user?.profilePicture ? (
              <img
                src={user.profilePicture}
                alt="Profile"
                className="h-full w-full rounded-full object-cover"
                onError={(e) => { e.currentTarget.style.display = "none"; }}
              />
            ) : (
              initials
            )}
          </span>

          {/* Dropdown */}
          {open && (
            <div className="absolute right-0 top-14 w-52 bg-white rounded-xl shadow-xl overflow-hidden z-50 border border-gray-100 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="px-4 py-3 border-b border-gray-100 bg-linear-to-r from-gray-50 to-[#f8f9fa]">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Account</p>
              </div>

              <button
                className="w-full text-left px-4 py-3 text-sm text-gray-700 font-medium hover:bg-gray-50 transition-colors duration-150 flex items-center gap-2"
                onClick={() => {
                  navigate('/settings/profile');
                  setOpen(false);
                }}
              >
                <Settings size={16} className="text-(--primary)" />
                Profile Settings
              </button>

              <button
                className="w-full text-left px-4 py-3 text-sm text-gray-700 font-medium hover:bg-gray-50 transition-colors duration-150 flex items-center gap-2 border-t border-gray-100"
                onClick={() => {
                  navigate('/settings/billing');
                  setOpen(false);
                }}
              >
                <CreditCard size={16} className="text-(--primary)" />
                Billing & Usage
              </button>

              <button
                className="w-full text-left px-4 py-3 text-sm font-medium text-(--accent) hover:bg-[rgba(255,107,107,0.08)] transition-colors duration-150 flex items-center gap-2 border-t border-gray-100"
                onClick={handleLogout}
              >
                <LogOut size={16} className="text-(--accent)" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export default Header;
