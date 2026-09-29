import { useEffect, useMemo, useRef, useState } from "react";
import Checkbox from "./Checkbox";
import { ExternalLink, Search, X, Sparkles, Info, Menu } from "lucide-react";
import Swal from "../shared/Alert";

/* A synthetic menu-group header (e.g. "Men", "Clothing") the tree injects to
   mirror the storefront nav — carries no url, slug "grp-<label>" but not the
   "grp-bucket-*" top-level tab. Its label is a page's menu ancestor, which lets
   us flag when a picked page is already covered by a broader picked category. */
const isMenuGroupNode = (node) =>
  !!node &&
  node.url == null &&
  typeof node.slug === "string" &&
  node.slug.startsWith("grp-") &&
  !node.slug.startsWith("grp-bucket-");

const prettifyName = (name = "") =>
  name
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

/* Build the searchable text for a node: its name, its URL, and its slug — plus a
   separator-normalised copy so a search for "new releases" also matches a
   "new-releases" slug (hyphens/underscores/slashes ↔ spaces). */
const searchHaystack = (node) => {
  let urlSlug = node.url || "";
  try {
    urlSlug = new URL(node.url).pathname;
  } catch {
    /* keep as-is */
  }
  const raw = `${prettifyName(node.name || "")} ${node.name || ""} ${node.slug || ""} ${urlSlug}`;
  return `${raw} ${raw.replace(/[-_/]+/g, " ")}`.toLowerCase();
};

/* Keep a node when it (or any descendant) matches the query. A matching parent
   keeps all its children; an unmatched parent keeps only its matching subtree. */
const filterTree = (nodes = {}, term) => {
  const out = {};
  for (const [id, node] of Object.entries(nodes)) {
    const hay = searchHaystack(node);
    const selfMatch = hay.includes(term);

    const hasKids = node.children && Object.keys(node.children).length > 0;
    const filteredKids = hasKids ? filterTree(node.children, term) : {};
    const kidMatch = Object.keys(filteredKids).length > 0;

    if (selfMatch || kidMatch) {
      out[id] = {
        ...node,
        children: selfMatch ? node.children : filteredKids,
      };
    }
  }
  return out;
};

function TreeNode({
  data = {},
  selectionLimit = Infinity || 5,
  homepage = null,
  onSelectionChange = null,
  searchable = true,
  // A parent can uncheck a tree page from outside (e.g. the "Will be analysed"
  // list): pass { url, nonce } — changing the nonce re-triggers the deselect.
  deselectRequest = null,
  // URLs to pre-select the first time a tree loads, so the user starts from a
  // sensible default rather than a blank slate (nav-order top collections, etc.).
  // Applied once per tree and only while nothing is selected yet, so it never
  // fights the user's own choices.
  defaultSelectedUrls = null,
}) {
  const [expanded, setExpanded] = useState({});
  const [selected, setSelected] = useState({});
  const [search, setSearch] = useState("");
  const autoAppliedForRef = useRef(null);

  const query = search.trim().toLowerCase();
  const searchActive = query.length > 0;

  const viewData = useMemo(
    () => (searchActive ? filterTree(data, query) : data),
    [data, query, searchActive]
  );

  // URLs we auto-suggested, so their rows can carry a subtle "Suggested" tag —
  // the user can see at a glance which picks were ours vs. their own edits.
  const suggestedSet = useMemo(
    () => new Set(Array.isArray(defaultSelectedUrls) ? defaultSelectedUrls : []),
    [defaultSelectedUrls]
  );

  // Lower-cased names of currently-selected pages, so a leaf can tell whether one
  // of its menu ancestors (e.g. "Men") is already picked — the containment hint.
  const selectedNames = useMemo(() => {
    const names = new Set();
    const walk = (nodes) => {
      for (const node of Object.values(nodes || {})) {
        if (node.url && selected[node.id]) names.add((node.name || "").toLowerCase());
        if (node.children) walk(node.children);
      }
    };
    walk(data);
    return names;
  }, [selected, data]);

  // O(n) precomputed subtree stats. Recomputing per-node (countSelectedInSubtree /
  // countTotalInSubtree) is O(n^2) and made large catalogs (breakout: 150+
  // collections, 1000s of product nodes) hang on every click — the subtree walks
  // even recursed into COLLAPSED children. One post-order pass fills id → totals so
  // renderNode does O(1) lookups.
  const { totalById, selectedById } = useMemo(() => {
    const totalById = new Map();
    const selectedById = new Map();
    const walk = (node) => {
      let total = 1;
      let sel = selected[node.id] ? 1 : 0;
      if (node.children) {
        for (const child of Object.values(node.children)) {
          const [ct, cs] = walk(child);
          total += ct;
          sel += cs;
        }
      }
      totalById.set(node.id, total);
      selectedById.set(node.id, sel);
      return [total, sel];
    };
    for (const node of Object.values(data || {})) walk(node);
    return { totalById, selectedById };
  }, [data, selected]);

  // Total selected across the whole tree — computed ONCE per render instead of
  // once per node (the old `blocked` check called getTotalSelectedCount per node).
  const totalSelectedNow = useMemo(
    () => Object.values(selected).filter(Boolean).length + (homepage ? 1 : 0),
    [selected, homepage]
  );

  // Accordion behaviour: opening a node collapses its siblings (the ones sharing
  // the same parent), so only one branch per level stays open at a time.
  const toggleNode = (nodeId, siblingIds = []) => {
    setExpanded((prev) => {
      const willOpen = !prev[nodeId];
      const next = { ...prev };
      if (willOpen) {
        for (const sid of siblingIds) {
          if (sid !== nodeId) next[sid] = false;
        }
      }
      next[nodeId] = willOpen;
      return next;
    });
  };

  const getTotalSelectedCount = (currentSelection = selected) => {
    return Object.values(currentSelection).filter(Boolean).length + (homepage ? 1 : 0);
  };

  // NOTE: selection/expansion are keyed by the node's globally-unique `id` (from
  // the backend), NOT the object key/slug — sibling collections across branches
  // can share a slug (e.g. Gymshark's /…/mens views), which previously made them
  // toggle together.
  const countSelectedInNode = (node) => {
    let count = 1;
    if (node.children) {
      Object.values(node.children).forEach((childNode) => {
        count += countSelectedInNode(childNode);
      });
    }
    return count;
  };

  const handleSelectAll = (node, isSelected) => {
    const newSelected = { ...selected };
    const toggleValue = !isSelected;

    if (toggleValue) {
      const nodeSelectionCount = countSelectedInNode(node);
      const currentTotal = getTotalSelectedCount(newSelected);
      const newTotal = currentTotal + nodeSelectionCount;

      if (newTotal > selectionLimit) {
        Swal.fire({
          icon: "warning",
          title: "Limit Exceeded!",
          text: "You have exceeded the maximum number of pages you can select.",
          confirmButtonColor: "var(--accent)",
        });
        return;
      }
    }

    newSelected[node.id] = toggleValue;

    const selectAllChildren = (children) => {
      Object.values(children).forEach((childNode) => {
        newSelected[childNode.id] = toggleValue;
        if (childNode.children) selectAllChildren(childNode.children);
      });
    };

    if (node.children) selectAllChildren(node.children);

    setSelected(newSelected);
  };

  const countSelectedInSubtree = (node) => {
    let count = selected[node.id] ? 1 : 0;
    if (node.children) {
      Object.values(node.children).forEach((childNode) => {
        count += countSelectedInSubtree(childNode);
      });
    }
    return count;
  };

  const countTotalInSubtree = (node) => {
    let count = 1;

    if (node.children && Object.keys(node.children).length > 0) {
      // eslint-disable-next-line no-unused-vars
      Object.entries(node.children).forEach(([_, childNode]) => {
        count += countTotalInSubtree(childNode);
      });
    }

    return count;
  };

  const formatNodeName = (name) => {
    return name
      .split("-")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const renderNode = (node, level = 0, siblingIds = [], groupChain = []) => {
    const nodeId = node.id;
    const isExpanded = searchActive ? true : expanded[nodeId] || false;
    const isSelected = selected[nodeId] || false;
    const hasChildren = node.children && Object.keys(node.children).length > 0;
    const selectedCount = selectedById.get(nodeId) || 0;
    const totalCount = totalById.get(nodeId) || 1;
    const isParent = hasChildren;

    // Menu ancestry passed to this node's children (append self if it's a group
    // header). A leaf is "already covered" when one of its ancestors is selected.
    const childChain = isMenuGroupNode(node) ? [...groupChain, node.name] : groupChain;
    const coveredBy =
      !isParent && isSelected
        ? groupChain.find(
            (g) =>
              selectedNames.has((g || "").toLowerCase()) &&
              (g || "").toLowerCase() !== (node.name || "").toLowerCase()
          )
        : null;

    // A leaf can't be picked once the page limit is reached.
    const blocked = totalSelectedNow >= selectionLimit && !isSelected;

    const indentClass = level === 0 ? "" : "ml-3";

    // Distinct left-border colour per nesting level, so the hierarchy reads at a
    // glance: level 0 (Collections/Products) coral, level 1 teal, level 2+ navy.
    const LEVEL_BORDER = ["var(--accent)", "var(--secondary)", "var(--primary)"];
    const parentBorderColor = LEVEL_BORDER[Math.min(level, LEVEL_BORDER.length - 1)];

    return (
      <div key={nodeId} className={indentClass}>
        <div className="rounded-xl overflow-hidden border border-gray-200 transition hover:border-gray-300">
          <div
            className={`flex items-center gap-2.5 px-3 py-2 transition-colors duration-150
            ${isParent
                ? "bg-gray-100 hover:bg-gray-200 border-l-4 cursor-pointer"
                : "bg-white hover:bg-gray-50"
              }`}
            style={isParent ? { borderLeftColor: parentBorderColor } : undefined}
            onClick={isParent ? () => toggleNode(nodeId, siblingIds) : undefined}
          >
            {/* Categories (Products, Collections…) expand only — no checkbox.
                Only the individual options inside get a checkbox. */}
            {isParent ? (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); toggleNode(nodeId, siblingIds); }}
                aria-label={isExpanded ? "Collapse" : "Expand"}
                className="w-7 h-7 shrink-0 flex items-center justify-center rounded-lg bg-white border border-gray-300 text-(--accent) shadow-sm hover:bg-(--accent) hover:text-white transition"
              >
                {isExpanded ? "−" : "+"}
              </button>
            ) : (
              <Checkbox
                className={`shrink-0 w-4 h-4 rounded border-gray-300 focus:ring-2 focus:ring-(--accent)
                ${blocked ? "cursor-not-allowed opacity-40" : "cursor-pointer"}`}
                checked={isSelected}
                disabled={blocked}
                onChange={() => handleSelectAll(node, isSelected)}
              />
            )}

            <span
              className={`min-w-0 flex-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 ${isParent
                  ? "font-semibold text-base text-(--accent)"
                  : "font-medium text-gray-800"
                }`}
            >
              <span className="break-words">{formatNodeName(node.name)}</span>

              {node.inNav && (
                <span
                  className="inline-flex items-center gap-1 text-[10.5px] font-medium text-(--secondary) shrink-0"
                  title="Appears in the site's navigation menu"
                >
                  <Menu className="w-3 h-3 shrink-0" />
                  In menu
                </span>
              )}

              {coveredBy && (
                <span
                  className="inline-flex items-center gap-1 text-[10.5px] font-medium text-amber-600"
                  title={`Already covered by ${formatNodeName(coveredBy)} — you may be doubling up`}
                >
                  <Info className="w-3 h-3 shrink-0" />
                  Covered by {formatNodeName(coveredBy)}
                </span>
              )}

              {node.url && (
                <a
                  href={node.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 text-(--secondary) opacity-80 hover:opacity-100 transition"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </span>

            {isParent ? (
              <div className="shrink-0 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                {/* Bulk toggle: fill this group's pages or clear them in one tap. */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); handleSelectAll(node, selectedCount > 0); }}
                  className="text-[11px] font-semibold px-2 py-0.5 rounded-full border border-gray-300 bg-white text-gray-600 hover:border-(--accent) hover:text-(--accent) transition"
                >
                  {selectedCount > 0 ? "Clear" : "Select all"}
                </button>
                <span className="inline-flex items-center justify-center text-xs font-semibold px-2 py-0.5 rounded-full bg-(--accent)/10 text-(--accent) border border-(--accent)/15">
                  {selectedCount}/{totalCount - 1}
                </span>
              </div>
            ) : suggestedSet.has(node.url) ? (
              // Amber "Suggested" = we auto-picked it; green "✓" = the user's own pick.
              <span className="shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
                <Sparkles size={11} className="shrink-0" />
                <span className="hidden sm:inline">Suggested</span>
              </span>
            ) : (
              isSelected && (
                <span className="shrink-0 inline-flex items-center justify-center text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                  ✓<span className="hidden sm:inline">&nbsp;Selected</span>
                </span>
              )
            )}
          </div>

          {isExpanded && hasChildren && (
            <div className="bg-white border-t border-gray-200 max-h-96 overflow-y-auto p-1.5 space-y-1">
              {(() => {
                const childNodes = Object.values(node.children);
                const childIds = childNodes.map((c) => c.id);
                return childNodes.map((childNode) =>
                  renderNode(childNode, level + 1, childIds, childChain),
                );
              })()}
            </div>
          )}
        </div>
      </div>
    );
  };

  useEffect(() => {
    if (onSelectionChange) {
      const findNodeById = (id, nodes = data) => {
        for (const node of Object.values(nodes)) {
          if (node.id === id) return node;

          if (node.children && Object.keys(node.children).length > 0) {
            const found = findNodeById(id, node.children);
            if (found) return found;
          }
        }

        return null;
      };

      const selectedPages = Object.entries(selected)
        .filter(([nodeId, isSelected]) => {
          if (!isSelected) return false;

          if (nodeId === "homepage") return true;

          const node = findNodeById(nodeId);

          // include only nodes that actually have a url
          return !!node?.url;
        })
        .map(([nodeId]) => {
          if (nodeId === "homepage") return homepage;
          return findNodeById(nodeId)?.url;
        })
        .filter(Boolean);

      if (homepage) {
        selectedPages.unshift(homepage);
      }

      onSelectionChange(selectedPages);
    }

  }, [selected, data, homepage, onSelectionChange]);

  // One-time auto-default: when a fresh tree arrives, pre-check the suggested
  // URLs (up to the page limit) — but only if the user hasn't picked anything,
  // so re-renders and back-navigation never clobber their choices. Keyed on the
  // `data` reference so a genuinely new store re-applies its own defaults.
  useEffect(() => {
    if (!Array.isArray(defaultSelectedUrls) || defaultSelectedUrls.length === 0) return;
    if (!data || Object.keys(data).length === 0) return;
    if (autoAppliedForRef.current === data) return;
    autoAppliedForRef.current = data;

    const idByUrl = new Map();
    const walk = (nodes) => {
      for (const node of Object.values(nodes)) {
        if (node.url) idByUrl.set(node.url, node.id);
        if (node.children) walk(node.children);
      }
    };
    walk(data);

    const picks = {};
    let count = homepage ? 1 : 0;
    for (const url of defaultSelectedUrls) {
      if (count >= selectionLimit) break;
      const id = idByUrl.get(url);
      if (id && !picks[id]) {
        picks[id] = true;
        count += 1;
      }
    }
    if (Object.keys(picks).length === 0) return;

    setSelected((prev) => (Object.values(prev).some(Boolean) ? prev : picks));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, defaultSelectedUrls, selectionLimit, homepage]);

  // Uncheck a tree page when the parent asks (deselect from the summary list).
  useEffect(() => {
    const url = deselectRequest?.url;
    if (!url) return;
    const findIdByUrl = (u, nodes = data) => {
      for (const node of Object.values(nodes)) {
        if (node.url === u) return node.id;
        if (node.children && Object.keys(node.children).length > 0) {
          const found = findIdByUrl(u, node.children);
          if (found) return found;
        }
      }
      return null;
    };
    const id = findIdByUrl(url);
    if (id) setSelected((prev) => (prev[id] ? { ...prev, [id]: false } : prev));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deselectRequest]);

  const hasResults = viewData && Object.keys(viewData).length > 0;

  return (
    <div className="space-y-3 text-sm">
      {searchable && data && Object.keys(data).length > 0 && (
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search pages…"
            className="w-full rounded-xl border border-gray-200 bg-white pl-9 pr-9 py-2.5 text-sm text-gray-800 placeholder-gray-400 shadow-sm focus:border-(--accent) focus:ring-2 focus:ring-(--accent)/20 focus:outline-none transition"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="Clear search"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      )}

      {/* Clear-all: quick reset of tree picks (manual URLs are handled separately). */}
      {data && Object.keys(data).length > 0 && Object.values(selected).some(Boolean) && (
        <div className="flex items-center justify-end -mt-1">
          <button
            type="button"
            onClick={() => setSelected({})}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-gray-500 hover:text-(--danger) transition"
          >
            <X className="w-3.5 h-3.5" /> Clear all
          </button>
        </div>
      )}

      {homepage && (
        <div className="mb-4" title="You cannot deselect the homepage. It is always selected."
        >
          <div className="rounded-2xl overflow-hidden shadow-sm border border-gray-200 transition hover:shadow-md">
            <div className="flex items-center gap-3 bg-white px-4 py-3 transition border-l-4 border-l-(--accent)">
              <svg
                className="w-5 h-5 text-(--accent)"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
              </svg>

              <Checkbox
                className={`flex-none w-4 h-4 rounded border-gray-300 focus:ring-2 focus:ring-(--accent)
                ${totalSelectedNow >= selectionLimit &&
                    !selected["homepage"]
                    ? "cursor-not-allowed opacity-40"
                    : "cursor-pointer"
                  }`}
                checked={true}
                disabled={true}
                onChange={() => { }}
              />

              <span className="font-semibold text-(--accent)">Homepage</span>

              <span className="ml-auto text-xs text-gray-600 break-all max-w-xs">
                {homepage}
              </span>

              {selected["homepage"] && (
                <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold">
                  ✓
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {hasResults ? (
        (() => {
          const topNodes = Object.values(viewData);
          const topIds = topNodes.map((n) => n.id);
          return topNodes.map((node) => renderNode(node, 0, topIds));
        })()
      ) : searchActive ? (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-white px-4 py-6 text-center text-sm text-gray-500">
          No pages match “{search.trim()}”.
        </div>
      ) : null}
    </div>
  );
}

export default TreeNode;
