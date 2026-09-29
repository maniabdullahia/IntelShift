import { formatTimeAgo } from "../../../../utils/Time";
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { RotateCcw } from "lucide-react";

import useWorkspaceStore from "../../../store/workspace.store";
import Favicon from "../../shared/Favicon";


const isHomepageUrl = (raw) => {
  try {
    const s = String(raw || "").trim();
    if (!s) return false;
    const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
    return u.pathname === "" || u.pathname === "/";
  } catch {
    return false;
  }
};

function CompetitorCard({ competitor, pagesLimit }) {
  // "Last updated" = when this competitor's data was last (re)built, falling
  // back to the record's updatedAt.
  const lastUpdated = competitor?.lastRebuiltAt || competitor?.lastMonitoredAt || competitor?.updatedAt;
  const [timeAgo, setTimeAgo] = useState(formatTimeAgo(lastUpdated));
  const navigate = useNavigate();
  const undoCompetitor = useWorkspaceStore((state) => state.undoCompetitor);

  const pending = competitor?.pendingChange;
  const isPending = pending && pending !== "none";

  // Changes detected at the competitor's most recent monitoring run.
  const recentChanges = competitor?.recentChanges ?? 0;
  const severity = competitor?.recentSeverity;

  const handleUndo = async (e) => {
    e.stopPropagation();
    try { await undoCompetitor(competitor._id); } catch { /* ignore */ }
  };


  // "Pages monitored" = pages actively monitored for this competitor. Pages staged
  // to ADD aren't monitored until the next run (excluded). Pages staged to REMOVE
  // are STILL monitored until that run applies, so they stay counted.
  const pageStats = useMemo(() => {
    const pages = Array.isArray(competitor?.pages) ? competitor.pages : [];
    // Homepage is auto-tracked and doesn't count toward the plan limit.
    const tracked = pages.filter((p) => p?.pendingChange !== "add" && !isHomepageUrl(p.url));
    const completed = tracked.filter(
      (p) => String(p?.scanStatus || "").toLowerCase() === "completed"
    ).length;
    return { total: tracked.length, completed };
  }, [competitor]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeAgo(formatTimeAgo(lastUpdated));
    }, 60000); // refresh the relative time each minute

    return () => clearInterval(timer);
  }, [lastUpdated]);

  const handleRowClick = () => {
    navigate(`/competitors/${competitor._id}`);
  };

  return (
    <tr
      key={competitor._id}
      onClick={handleRowClick}
      className={`cursor-pointer hover:bg-[rgba(78,205,196,0.08)] transition ${pending === "remove" ? "opacity-60" : ""}`}
    >
      <td className="px-4 py-4 font-bold">
        <div className="flex items-center gap-2">
          <Favicon domain={competitor.domain || competitor.url} size={22} />
          <span className={pending === "remove" ? "line-through" : ""}>
            {competitor.name || competitor.domain}
          </span>
          {pending === "add" && (
            <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">
              New · pending
            </span>
          )}
          {pending === "remove" && (
            <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase text-red-700">
              Removing
            </span>
          )}
          {isPending && (
            <button
              type="button"
              onClick={handleUndo}
              title="Undo staged change"
              className="ml-1 shrink-0 rounded-md p-1 text-gray-500 transition hover:bg-gray-100 hover:text-(--secondary-dark)"
            >
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      </td>

      <td className="px-4 py-4">
        <span className="font-semibold text-(--text)">
          {pageStats.total}{pagesLimit ? `/${pagesLimit}` : ""}
        </span>
        {pageStats.total > 0 && pageStats.completed < pageStats.total && (
          <span className="ml-1.5 text-xs text-(--text-light)">({pageStats.completed} analyzed)</span>
        )}
      </td>

      <td className="px-4 py-4">
        <span
          className={`font-semibold ${
            recentChanges > 0
              ? severity === "critical" || severity === "high"
                ? "text-(--danger)"
                : severity === "medium"
                  ? "text-(--warning)"
                  : "text-(--secondary-dark)"
              : "text-(--text-light)"
          }`}
        >
          {recentChanges}
        </span>
      </td>

      <td className="px-4 py-4 text-(--text-light)">{timeAgo}</td>
    </tr>
  );
}

export default CompetitorCard;
