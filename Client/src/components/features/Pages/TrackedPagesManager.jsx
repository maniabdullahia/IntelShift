import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  Trash2,
  RotateCcw,
  ExternalLink,
  Clock3,
  Lock,
  Sparkles,
  Info,
  LoaderCircle,
  ArrowLeftRight,
  Link2,
  LayoutGrid,
  Home,
} from "lucide-react";

import Alert from "../../shared/Alert";
import useWorkspaceStore from "../../../store/workspace.store";
import {
  getPages,
  createPage,
  deletePage,
  undoPageChange,
  getPageLimits,
} from "../../../api/page.api";
import { getWorkspaceRecon } from "../../../api/workspace.api";
import SearchSelect from "../../shared/SearchSelect";
import { matchScore } from "../../../utils/collectionMatch";

// Normalize a URL for cross-comparison (scheme/www/trailing-slash/case-insensitive).
const normU = (u) =>
  String(u || "").trim().replace(/[?#].*$/, "").replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/+$/, "").toLowerCase();

const fmtDate = (d) =>
  d
    ? new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : null;

// The homepage (site root) anchors the analysis: it can't be removed and isn't
// counted toward the tracked-pages limit.
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

/*
| Manage which pages we track for one competitor (owner site or a rival).
| Edits are STAGED — they take effect at the next monitoring run, never
| instantly. Removals are reversible until that run. Adds are gated by the
| plan's pages-per-competitor limit.
*/
export default function TrackedPagesManager({ competitorId, role = "Competitor", onChanged }) {
  const navigate = useNavigate();
  const syncWorkspace = useWorkspaceStore((s) => s.syncWorkspace);
  const workspace = useWorkspaceStore((s) => s.workspace);

  const isOwner = role === "Owner";
  const noun = isOwner ? "your site" : "this competitor";

  const [pages, setPages] = useState([]);
  const [limits, setLimits] = useState(null); // { pagesPerCompetitor, hasHistory, planName, appliesAt }
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const [newUrl, setNewUrl] = useState("");
  const [newOwnerUrl, setNewOwnerUrl] = useState(""); // your-site page a competitor page maps to
  const [adding, setAdding] = useState(false);
  // Input mode per side: false = pick from catalog dropdown, true = paste a URL.
  const [compPaste, setCompPaste] = useState(false);
  const [ownerPaste, setOwnerPaste] = useState(false);

  // Recon collections for the pick-a-page dropdowns (owner side + this competitor).
  const [ownerCols, setOwnerCols] = useState([]);
  const [compCols, setCompCols] = useState([]);

  // Homepage is excluded from the count toward the plan limit.
  const activePages = useMemo(
    () => pages.filter((p) => p.pendingChange !== "remove" && !isHomepageUrl(p.url)),
    [pages]
  );

  // Mapping summary (competitor pages only): how many tracked pages are paired
  // with an owner page for like-for-like comparison. Owner's own pages aren't
  // mapped, so this is skipped for the owner view.
  const mapStats = useMemo(() => {
    if (isOwner) return null;
    return activePages.reduce(
      (acc, p) => {
        if (p.mapStatus === "matched" && p.mappedOwnerUrl) acc.matched += 1;
        else if (p.mapStatus === "no_equivalent") acc.noEquivalent += 1;
        else acc.unmapped += 1;
        return acc;
      },
      { matched: 0, noEquivalent: 0, unmapped: 0 }
    );
  }, [activePages, isOwner]);
  const limit = limits?.pagesPerCompetitor ?? null;
  // The per-competitor page limit doesn't apply to your own site — owner pages map
  // across multiple competitors, so they aren't capped by pagesPerCompetitor.
  const atLimit = !isOwner && limit != null && activePages.length >= limit;
  // Homepage is always tracked (anchors the analysis) but never counted toward the limit.
  const hasHomepage = useMemo(() => pages.some((p) => isHomepageUrl(p.url) && p.pendingChange !== "remove"), [pages]);
  // Row numbers count only tracked pages — the homepage isn't numbered (it gets a
  // home icon), so #1 is the first real page, not the homepage.
  const pageNumbers = useMemo(() => {
    let n = 0;
    return pages.map((p) => (isHomepageUrl(p.url) ? null : ++n));
  }, [pages]);
  // Displayed "tracked" count = pages actually monitored: excludes the homepage and
  // pages staged to ADD (not monitored until the next run); staged removals still count.
  const monitoredCount = useMemo(
    () => pages.filter((p) => p.pendingChange !== "add" && !isHomepageUrl(p.url)).length,
    [pages]
  );
  // Owner view: reverse mapping — which competitor pages are paired to each of your
  // pages (a page can be mapped by several competitors). Keyed by normalized url.
  const ownerMappedBy = useMemo(() => {
    if (!isOwner) return {};
    const map = {};
    for (const c of (workspace?.competitors || []).filter((x) => x.role === "Competitor")) {
      for (const p of c.pages || []) {
        if (p.mapStatus === "matched" && p.mappedOwnerUrl && p.pendingChange !== "remove") {
          const k = normU(p.mappedOwnerUrl);
          (map[k] = map[k] || []).push({ name: c.name, url: p.url });
        }
      }
    }
    return map;
  }, [isOwner, workspace]);
  const appliesAt = limits?.appliesAt;
  // Editing pages is a paid capability; the free trial gets a read-only view.
  const canManage = !!limits?.canManage;

  // Show an upgrade prompt for server-side "paid feature" rejections.
  const maybeUpgrade = async (err) => {
    if (err?.code !== "UPGRADE_REQUIRED") return false;
    const r = await Alert.fire({
      icon: "info",
      title: "Upgrade to manage pages",
      text: err.message,
      showCancelButton: true,
      confirmButtonText: "Upgrade plan",
      cancelButtonText: "Not now",
      confirmButtonColor: "#4ecdc4",
    });
    if (r.isConfirmed) navigate("/settings/billing");
    return true;
  };

  const refresh = async () => {
    if (!competitorId) return;
    try {
      const [list, lim] = await Promise.all([
        getPages({ competitorId }),
        getPageLimits().catch(() => null),
      ]);
      setPages(Array.isArray(list) ? list : []);
      if (lim) setLimits(lim);
    } catch {
      /* non-fatal — surface via empty state */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competitorId]);

  // Load recon collections so the add form can offer a "pick a page" dropdown.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const recon = await getWorkspaceRecon();
        if (!alive) return;
        const notEmpty = (cols) => (cols || []).filter((c) => c?.url && (c.productCount == null || Number(c.productCount) > 0));
        const oCols = notEmpty(recon?.owner?.collections);
        setOwnerCols(oCols);
        const me = (recon?.competitors || []).find((c) => String(c.competitorId) === String(competitorId));
        setCompCols(isOwner ? oCols : notEmpty(me?.collections));
      } catch {
        /* recon unavailable — dropdowns simply won't render */
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competitorId, isOwner]);

  // Only collections that aren't already tracked on their side.
  const trackedCompUrls = useMemo(
    () => new Set(pages.filter((p) => p.pendingChange !== "remove").map((p) => normU(p.url))),
    [pages]
  );
  // Nav/menu collections first, so the pages actually linked in the site's menu
  // surface at the top of the dropdown.
  const menuFirst = (cols) => cols.slice().sort((a, b) => (b.inNav ? 1 : 0) - (a.inNav ? 1 : 0));
  const availComp = useMemo(() => menuFirst(compCols.filter((c) => !trackedCompUrls.has(normU(c.url)))), [compCols, trackedCompUrls]);
  // Show ALL of your pages here — one page can be mapped to multiple competitors,
  // so pages already mapped to another competitor should still be selectable.
  const availOwner = useMemo(() => menuFirst(ownerCols), [ownerCols]);

  // The competitor collection currently chosen (from catalog, or a pasted URL) —
  // used to suggest matching pages on your own site.
  const pickedCompCol = useMemo(
    () => (newUrl ? (compCols.find((c) => c.url === newUrl) || { url: newUrl }) : null),
    [newUrl, compCols]
  );
  const ownerSuggested = useMemo(() => {
    if (isOwner || !pickedCompCol) return [];
    return availOwner
      .map((o) => ({ url: o.url, s: matchScore(o, pickedCompCol) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 4)
      .map((x) => x.url);
  }, [availOwner, pickedCompCol, isOwner]);

  // One add-field: a searchable catalog dropdown by default with a paste-URL toggle
  // icon (icon flips to "catalog" while pasting) — same pattern as the modal picker.
  const renderAddPicker = ({ avail, value, setValue, paste, setPaste, pickLabel, pasteLabel, suggested = [] }) => {
    const hasCatalog = avail.length > 0;
    const showPaste = paste || !hasCatalog;
    const options = avail.map((c) => ({ value: c.url, label: c.name || c.handle || c.url }));
    return (
      <div className="flex min-w-0 flex-1 items-center gap-1">
        {showPaste ? (
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={pasteLabel}
            className="min-w-0 flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-(--secondary)"
          />
        ) : (
          <SearchSelect
            value={value}
            options={options}
            placeholder={pickLabel}
            suggested={suggested}
            onChange={(v) => setValue(v)}
          />
        )}
        {hasCatalog && (
          <button
            type="button"
            onClick={() => setPaste((v) => !v)}
            title={showPaste ? "Choose from catalog" : "Paste a URL"}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-(--secondary) transition hover:bg-[color-mix(in_srgb,var(--secondary)_12%,transparent)]"
          >
            {showPaste ? <LayoutGrid size={16} /> : <Link2 size={16} />}
          </button>
        )}
        <a
          href={value ? (/^https?:\/\//i.test(value) ? value : `https://${value}`) : undefined}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => { if (!value) e.preventDefault(); }}
          title={value ? "Open page" : "Pick or paste a page to open it"}
          aria-disabled={!value}
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg transition ${value ? "text-(--accent) hover:bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]" : "pointer-events-none text-gray-300"}`}
        >
          <ExternalLink size={15} />
        </a>
      </div>
    );
  };

  const afterMutation = async () => {
    await refresh();
    await syncWorkspace?.().catch(() => {});
    onChanged?.();
  };

  const handleAdd = async (e) => {
    e?.preventDefault?.();
    if (!newUrl.trim()) return;
    // A competitor page must map to a page on your own site (mapped-only).
    if (!isOwner && !newOwnerUrl.trim()) {
      Alert.fire({ icon: "info", title: "Map it to your site", text: "Add the page on your own site that this competitor page maps to.", confirmButtonColor: "#4ecdc4" });
      return;
    }
    setAdding(true);
    try {
      const res = await createPage({
        url: newUrl.trim(),
        competitorId,
        ...(isOwner ? {} : { mappedOwnerUrl: newOwnerUrl.trim() }),
      });
      setNewUrl("");
      setNewOwnerUrl("");
      await afterMutation();
      Alert.fire({
        icon: "success",
        title: res?.restored ? "Page restored" : "Page staged",
        text:
          res?.message ||
          "It will be analyzed on the next monitoring run.",
        timer: 2600,
        showConfirmButton: false,
      });
    } catch (err) {
      if (err.code === "PLAN_LIMIT") {
        const r = await Alert.fire({
          icon: "info",
          title: "Page limit reached",
          text: err.message,
          showCancelButton: true,
          confirmButtonText: "Upgrade plan",
          cancelButtonText: "Not now",
          confirmButtonColor: "#4ecdc4",
        });
        if (r.isConfirmed) navigate("/settings/billing");
      } else if (!(await maybeUpgrade(err))) {
        Alert.fire({ icon: "error", title: "Couldn't add page", text: err.message, confirmButtonColor: "#ff6b6b" });
      }
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (page) => {
    const remap = isOwner
      ? "If this page maps to a competitor page, update that one too — before the next run — so comparisons stay aligned."
      : "Update your matching page too — before the next run — so comparisons stay aligned.";
    const r = await Alert.fire({
      icon: "warning",
      title: "Stop tracking this page?",
      html: `<p style="word-break:break-all;color:#8a8a99;font-size:13px;margin-bottom:10px;">${page.url}</p>
             <p style="margin-bottom:8px;">Takes effect at your next monitoring run — you can undo before then.</p>
             <p style="color:#636e72;font-size:13px;">${remap}</p>`,
      showCancelButton: true,
      confirmButtonText: "Remove",
      cancelButtonText: "Keep",
      confirmButtonColor: "#fc5c65",
    });
    if (!r.isConfirmed) return;

    setBusyId(page._id);
    try {
      await deletePage({ pageId: page._id });
      await afterMutation();
    } catch (err) {
      if (!(await maybeUpgrade(err))) {
        Alert.fire({ icon: "error", title: "Couldn't remove page", text: err.message, confirmButtonColor: "#ff6b6b" });
      }
    } finally {
      setBusyId(null);
    }
  };

  const handleUndo = async (page) => {
    setBusyId(page._id);
    try {
      await undoPageChange({ pageId: page._id });
      await afterMutation();
    } catch (err) {
      if (!(await maybeUpgrade(err))) {
        Alert.fire({ icon: "error", title: "Couldn't undo", text: err.message, confirmButtonColor: "#ff6b6b" });
      }
    } finally {
      setBusyId(null);
    }
  };

  const pendingCount = pages.filter((p) => p.pendingChange && p.pendingChange !== "none").length;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Tracked pages{isOwner ? ` · ${monitoredCount}` : (limit ? ` · ${monitoredCount}/${limit}` : ` · ${monitoredCount}`)}
          {hasHomepage && <span className="font-normal normal-case text-gray-400"> + homepage</span>}
        </p>
        {limits?.hasHistory === false && (
          <span className="text-[11px] text-gray-400">No history timeline on this plan</span>
        )}
      </div>

      {/* Mapping summary — how tracked competitor pages pair with your own site. */}
      {mapStats && activePages.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-gray-500">
          <span className="inline-flex items-center gap-1 font-medium text-(--secondary-dark)">
            <ArrowLeftRight size={12} className="shrink-0" />
            {mapStats.matched} mapped to your site
          </span>
          {mapStats.noEquivalent > 0 && <span>· {mapStats.noEquivalent} no equivalent</span>}
          {mapStats.unmapped > 0 && (
            <span className="text-amber-600">· {mapStats.unmapped} not mapped yet</span>
          )}
        </div>
      )}

      {/* Staged-change banner */}
      {(pendingCount > 0 || limits?.pendingPageChanges) && (
        <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <Clock3 size={14} className="mt-0.5 shrink-0" />
          <span>
            You have staged page changes. They apply on your next monitoring run
            {appliesAt ? ` (around ${fmtDate(appliesAt)})` : ""}. Before then, update the pages.
          </span>
        </div>
      )}

      {/* Page list */}
      {loading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-gray-500">
          <LoaderCircle size={16} className="animate-spin" /> Loading pages…
        </div>
      ) : pages.length === 0 ? (
        <p className="py-4 text-sm text-(--text-light)">No pages tracked for {noun} yet.</p>
      ) : (
        <div className="max-h-72 space-y-1.5 overflow-y-auto">
          {pages.map((p, i) => {
            const removing = p.pendingChange === "remove";
            const added = p.pendingChange === "add";
            const isHome = isHomepageUrl(p.url);
            return (
              <div
                key={p._id || p.url || i}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                  removing
                    ? "border-red-200 bg-red-50/60"
                    : added
                      ? "border-amber-200 bg-amber-50/60"
                      : "border-gray-100 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                <span className="flex w-5 shrink-0 justify-center text-xs font-bold text-gray-400">
                  {pageNumbers[i] == null ? <Home size={13} aria-label="Homepage" /> : `#${pageNumbers[i]}`}
                </span>
                <div className="min-w-0 flex-1">
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    className={`block truncate text-(--secondary-dark) hover:text-(--accent) ${
                      removing ? "line-through opacity-70" : ""
                    }`}
                  >
                    {p.url}
                  </a>

                  {/* Mapped owner page — the page on your own site this competitor
                      page is paired with for like-for-like comparison. */}
                  {!isOwner && !isHome &&
                    (p.mapStatus === "matched" && p.mappedOwnerUrl ? (
                      <span className="mt-0.5 flex items-center gap-1 text-[11px] text-gray-400">
                        <ArrowLeftRight size={11} className="shrink-0 text-(--secondary)" />
                        <span className="truncate">
                          Your page: {p.mappedOwnerUrl}
                        </span>
                      </span>
                    ) : p.mapStatus === "no_equivalent" ? (
                      <span className="mt-0.5 flex items-center gap-1 text-[11px] text-gray-400">
                        <ArrowLeftRight size={11} className="shrink-0 text-gray-300" />
                        <span>No equivalent on your site</span>
                      </span>
                    ) : (
                      <span className="mt-0.5 flex items-center gap-1 text-[11px] text-amber-600">
                        <ArrowLeftRight size={11} className="shrink-0" />
                        <span>Not mapped to your site yet</span>
                      </span>
                    ))}

                  {/* Owner view: the competitor pages paired to THIS page of yours. */}
                  {isOwner && !isHome && (() => {
                    const maps = ownerMappedBy[normU(p.url)] || [];
                    if (!maps.length) {
                      return (
                        <span className="mt-0.5 flex items-center gap-1 text-[11px] text-gray-400">
                          <ArrowLeftRight size={11} className="shrink-0 text-gray-300" />
                          <span>Not mapped to a competitor yet</span>
                        </span>
                      );
                    }
                    return (
                      <div className="mt-0.5 space-y-0.5">
                        {maps.map((m, mi) => (
                          <span key={mi} className="flex items-center gap-1 text-[11px] text-gray-400">
                            <ArrowLeftRight size={11} className="shrink-0 text-(--secondary)" />
                            <span className="truncate"><span className="font-semibold text-gray-500">{m.name}:</span> {m.url}</span>
                          </span>
                        ))}
                      </div>
                    );
                  })()}
                </div>

                {isHome && (
                  <span className="shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase text-gray-500">
                    Homepage
                  </span>
                )}
                {added && (
                  <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">
                    New · pending
                  </span>
                )}
                {removing && (
                  <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase text-red-700">
                    Removing
                  </span>
                )}

                {isHome ? (
                  <Lock size={13} className="shrink-0 text-gray-300" aria-label="The homepage is always tracked" />
                ) : (!isOwner && canManage) ? (
                  p.pendingChange && p.pendingChange !== "none" ? (
                    <button
                      type="button"
                      onClick={() => handleUndo(p)}
                      disabled={busyId === p._id}
                      title="Undo staged change"
                      className="shrink-0 rounded-md p-1.5 text-gray-500 transition hover:bg-white hover:text-(--secondary-dark) disabled:opacity-50"
                    >
                      <RotateCcw size={14} className={busyId === p._id ? "animate-spin" : ""} />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleRemove(p)}
                      disabled={busyId === p._id}
                      title="Stop tracking this page"
                      className="shrink-0 rounded-md p-1.5 text-gray-400 transition hover:bg-red-50 hover:text-(--danger) disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                    </button>
                  )
                ) : null}
                <a
                  href={p.url}
                  target="_blank"
                  rel="noreferrer"
                  className="shrink-0 rounded-md p-1.5 text-gray-300 transition hover:text-gray-500"
                  title="Open page"
                >
                  <ExternalLink size={13} />
                </a>
              </div>
            );
          })}
        </div>
      )}

      {/* Owner pages are managed from the competitor side — no add/delete here. */}
      {isOwner ? (
        <p className="mt-4 flex items-start gap-1.5 text-[11px] text-gray-400">
          <Info size={12} className="mt-0.5 shrink-0" />
          These pages are managed from your competitors — add or remove a page on a competitor to update the matching page on your site.
        </p>
      ) : limits && !canManage ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[rgba(78,205,196,0.35)] bg-[rgba(78,205,196,0.08)] p-4">
          <p className="text-sm text-(--text)">
            Editing tracked pages is a paid feature. Upgrade to add, remove or remap the pages you monitor.
          </p>
          <button
            type="button"
            onClick={() => navigate("/settings/billing")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-(--accent) px-4 py-2 text-sm font-bold text-white transition hover:bg-(--accent-dark)"
          >
            <Sparkles size={14} /> Upgrade
          </button>
        </div>
      ) : !canManage ? null : atLimit ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[rgba(78,205,196,0.35)] bg-[rgba(78,205,196,0.08)] p-4">
          <p className="text-sm text-(--text)">
            You've reached your plan's limit of {limit} pages for {noun}. Upgrade to track more.
          </p>
          <button
            type="button"
            onClick={() => navigate("/settings/billing")}
            className="inline-flex items-center gap-1.5 rounded-lg bg-(--accent) px-4 py-2 text-sm font-bold text-white transition hover:bg-(--accent-dark)"
          >
            <Sparkles size={14} /> Upgrade
          </button>
        </div>
      ) : (
        <form onSubmit={handleAdd} className="mt-4 space-y-2">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {renderAddPicker({
              avail: availComp, value: newUrl, setValue: setNewUrl,
              paste: compPaste, setPaste: setCompPaste,
              pickLabel: `Pick a ${noun} collection…`, pasteLabel: `Paste a page URL for ${noun}`,
            })}
            {!isOwner && renderAddPicker({
              avail: availOwner, value: newOwnerUrl, setValue: setNewOwnerUrl,
              paste: ownerPaste, setPaste: setOwnerPaste,
              pickLabel: "Pick a page on your site…", pasteLabel: "Paste the matching page on your site",
              suggested: ownerSuggested,
            })}
            <button
              type="submit"
              disabled={adding || !newUrl.trim() || (!isOwner && !newOwnerUrl.trim())}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-(--secondary) px-4 py-2 text-sm font-bold text-white transition hover:bg-(--secondary-dark) disabled:opacity-50"
            >
              <Plus size={15} />
              {adding ? "Adding…" : "Add"}
            </button>
          </div>
          <p className="flex items-start gap-1.5 text-[11px] text-gray-400">
            <Info size={12} className="mt-0.5 shrink-0" />
            New pages are staged and analyzed on your next monitoring run. Keep matching pages across your site and competitors aligned so comparisons stay meaningful.
          </p>
        </form>
      )}
    </div>
  );
}
