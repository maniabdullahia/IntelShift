import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  X,
  ChevronDown,
  ChevronRight,
  LayoutDashboard,
  BarChart3,
  Activity,
  Users,
  Settings,
  User,
  CreditCard,
  SlidersHorizontal,
  Bell,
} from "lucide-react";
import Brand from "../shared/Brand";
import useWorkspaceStore from "../../store/workspace.store";
import Favicon from "../shared/Favicon";

// Defined at module level (not inside Sidebar) so React keeps the same
// component identity across renders — no remounting / favicon flicker.
const LeafLink = ({ to, name, icon: Icon, indent = false, faviconDomain, active = false, onClick }) => (
  <Link
    to={to}
    onClick={onClick}
    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition ${indent ? "ml-3" : ""} ${
      active ? "bg-(--secondary) text-black font-semibold" : "text-white/90 hover:bg-white/10"
    }`}
  >
    {faviconDomain ? (
      <Favicon domain={faviconDomain} size={20} tile />
    ) : Icon ? (
      <Icon size={indent ? 15 : 17} className="shrink-0" />
    ) : (
      <span className="w-[15px]" />
    )}
    <span className="truncate">{name}</span>
  </Link>
);

const GroupHeader = ({ name, icon: Icon, open, onToggle }) => (
  <button
    type="button"
    onClick={onToggle}
    className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-sm text-white/90 transition hover:bg-white/10"
  >
    <span className="flex min-w-0 items-center gap-2.5">
      {Icon ? <Icon size={16} className="shrink-0" /> : null}
      <span className="truncate">{name}</span>
    </span>
    <span className="shrink-0">
      {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
    </span>
  </button>
);


function Sidebar({
  onNavigate,
  onClose,
  isMobileDrawer = false,
  className = "",
}) {
  const location = useLocation();
  const workspace = useWorkspaceStore((state) => state.workspace);
  const analysis = workspace?.analysis || [];

  // Map competitor name → domain so the analysis links can show site favicons
  // (analysis items carry the name, competitors carry the domain).
  const domainByName = {};
  (workspace?.competitors || []).forEach((c) => {
    if (c?.name) domainByName[c.name] = c.domain || c.url;
  });

  const isActive = (path) => location.pathname === path;
  const onSettings = location.pathname.startsWith("/settings");

  // Competitor Analysis stays open by default; Settings opens on a settings route.
  const [openAnalysis, setOpenAnalysis] = useState(true);
  const [openSettings, setOpenSettings] = useState(onSettings);

  const mainLinks = [
    { id: "dashboard", name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
    {
      id: "competitor_analysis",
      name: "Competitor Analysis",
      icon: BarChart3,
      children: analysis.map((item) => ({
        id: item.analysisId,
        name: item.competitorName || "Unnamed Competitor",
        path: `/analysis/${item.analysisId}`,
        domain: item.competitorDomain || item.domain || domainByName[item.competitorName] || item.competitorUrl,
      })),
    },
    { id: "change_detail", name: "Change Detail", path: "/change_detail", icon: Activity },
    { id: "competitors", name: "Competitors List", path: "/competitors", icon: Users },
  ];

  const settingsLinks = [
    { id: "profile", name: "Profile", path: "/settings/profile", icon: User },
    { id: "billing", name: "Billing & Usage", path: "/settings/billing", icon: CreditCard },
    { id: "workspace", name: "Workspace", path: "/settings/workspace", icon: SlidersHorizontal },
    { id: "alerts", name: "Alerts", path: "/settings/alerts", icon: Bell },
  ];

  // Shared click handler: close the mobile drawer after navigating.
  const handleNavigate = () => {
    if (onNavigate) onNavigate();
    if (isMobileDrawer && onClose) onClose();
  };

  return (
    <div className={`bg-(--primary) text-white w-60 h-full p-4 flex flex-col items-start ${className}`}>
      <div className="w-full flex items-center gap-2.5 px-1">
        <Brand tone="light" className="min-w-0" />

        {isMobileDrawer && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="lg:hidden ml-auto p-2 rounded-lg border border-white/30 text-white"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="flex flex-col gap-1.5 my-6 w-full" aria-label="Main navigation">
        {mainLinks.map((item) => {
          if (item.children) {
            return (
              <div key={item.id} className="w-full">
                <GroupHeader
                  name={item.name}
                  icon={item.icon}
                  open={openAnalysis}
                  onToggle={() => setOpenAnalysis((v) => !v)}
                />
                {openAnalysis && (
                  <div className="mt-1 flex flex-col gap-1">
                    {item.children.length === 0 && (
                      <span className="block py-2 px-4 ml-3 text-xs text-white/50">No analyses yet</span>
                    )}
                    {item.children.map((child) => (
                      <LeafLink key={child.id} to={child.path} active={isActive(child.path)} onClick={handleNavigate} name={child.name} indent faviconDomain={child.domain} />
                    ))}
                  </div>
                )}
              </div>
            );
          }
          return <LeafLink key={item.id} to={item.path} active={isActive(item.path)} onClick={handleNavigate} name={item.name} icon={item.icon} />;
        })}

        {/* Settings group */}
        <div className="mt-3 w-full border-t border-white/10 pt-3">
          <GroupHeader
            name="Settings"
            icon={Settings}
            open={openSettings}
            onToggle={() => setOpenSettings((v) => !v)}
          />
          {openSettings && (
            <div className="mt-1 flex flex-col gap-1">
              {settingsLinks.map((item) => (
                <LeafLink key={item.id} to={item.path} active={isActive(item.path)} onClick={handleNavigate} name={item.name} icon={item.icon} indent />
              ))}
            </div>
          )}
        </div>
      </nav>
    </div>
  );
}

export default Sidebar;
