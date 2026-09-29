import React, { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import Checkbox from "../ui/Checkbox";
import useWorkspaceStore from "../../store/workspace.store";
import Button from "../ui/Button";

const DowngradeModel = () => {
  const competitors = useWorkspaceStore((state) => state.competitors);
  const filteredCompetitors = competitors.filter(
    (competitor) => competitor.role == "Competitor",
  );
  const [expandedCompetitors, setExpandedCompetitors] = useState({});
  const [selectedPages, setSelectedPages] = useState({});

  // For expanding and collapsing competitor sections
  const toggleCompetitorExpanded = (competitorId) => {
    setExpandedCompetitors((prev) => ({
      ...prev,
      [competitorId]: !prev[competitorId],
    }));
  };

  // For toggling individual page selection
  const handleTogglePage = (pageId) => {
    setSelectedPages((prev) => ({
      ...prev,
      [pageId]: !prev[pageId],
    }));
  };

  // For toggling all pages under a competitor
  const handleToggleCompetitor = (pageIds, allSelected) => {
    setSelectedPages((prev) => {
      const updated = { ...prev };
      pageIds.forEach((id) => {
        updated[id] = !allSelected;
      });
      return updated;
    });
  };

  // Count total selected pages for display
  const selectedCount = Object.values(selectedPages).filter(Boolean).length;

  return (
    <div className="space-y-6">
      <section className="space-y-4">
        <div>
          <p className="text-(--accent) text-sm font-medium">
            {" "}
            {selectedCount} page{selectedCount === 1 ? "" : "s"} selected
          </p>
        </div>
        {filteredCompetitors.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center text-gray-600">
            <p className="text-lg font-semibold">No competitors available</p>
            <p className="mt-2 text-sm text-gray-500">
              Sync or add competitors to select model downgrade pages.
            </p>
          </div>
        ) : (
          filteredCompetitors.map((competitor) => {
            const pages = Array.isArray(competitor.pages)
              ? competitor.pages
              : [];
            const pageIds = pages.map((page) => page._id || page.id || page.url);
            const expanded = expandedCompetitors[competitor._id];

            return (
              <div
                key={competitor._id || competitor.id}
                className="rounded-3xl border border-gray-200 bg-white shadow-sm"
              >
                <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-4">
                    <button
                      type="button"
                      onClick={() => toggleCompetitorExpanded(competitor._id)}
                      className="mt-1 inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-gray-200 bg-gray-100 text-slate-700 transition hover:bg-gray-200"
                      aria-label={
                        expanded ? "Collapse competitor" : "Expand competitor"
                      }
                    >
                      {expanded ? (
                        <ChevronDown size={18} />
                      ) : (
                        <ChevronRight size={18} />
                      )}
                    </button>

                    <div className="flex items-center gap-3">
                      <Checkbox
                        checked={pageIds.length > 0 && pageIds.every((id) => selectedPages[id])}
                        onChange={() => handleToggleCompetitor(pageIds, pageIds.length > 0 && pageIds.every((id) => selectedPages[id]))}
                      />
                      <div>
                        <h3 className="text-lg font-semibold text-slate-900">
                          {competitor.name ||
                            "Unnamed competitor"}
                        </h3>
                        <p className="text-sm text-slate-500">
                          {pages.length} page{pages.length === 1 ? "" : "s"}{" "}
                          tracked
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-4">
                    <span className="rounded-2xl bg-slate-100 px-3 py-2 text-sm text-slate-600">
                      {competitor.scanStatus || "Status unknown"}
                    </span>
                  </div>
                </div>

                {expanded && (
                  <div className="border-t border-gray-200 bg-slate-50 p-4">
                    {pages.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-5 text-sm text-slate-500">
                        No pages available for this competitor.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {pages.map((page) => {
                          const pageId = page._id || page.id || page.url;
                          const checked = !!selectedPages[pageId];

                          return (
                            <label
                              key={pageId}
                              className="flex items-center justify-between gap-4 rounded-2xl border border-gray-200 bg-white p-4 transition hover:border-blue-200"
                            >
                              <div className="flex flex-1 flex-col gap-1">
                                <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                                  <Checkbox
                                    checked={checked}
                                    onChange={() => handleTogglePage(pageId)}
                                  />
                                  <span className="truncate">
                                    {page.name ||
                                      page.title ||
                                      page.url ||
                                      pageId}
                                  </span>
                                </span>
                                <span className="text-xs text-slate-500 break-all">
                                  {page.url || pageId}
                                </span>
                              </div>
                              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-gray-600">
                                {page.scanStatus || "Unknown"}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </section>

      <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
        <Button
          variant="secondary"
          title="Clear selections"
          onClick={() => setSelectedPages({})}
        />

        <Button title="Apply downgrade" />
      </div>
    </div>
  );
};

export default DowngradeModel;
