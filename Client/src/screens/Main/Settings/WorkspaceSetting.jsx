import Input from "../../../components/ui/Input";
import Select from "../../../components/ui/Select";
import Button from "../../../components/ui/Button";
import Swal from "../../../components/shared/Alert";

const INDUSTRY_OPTIONS = [
  { value: "E-Commerce", label: "E-commerce" },
  { value: "SaaS", label: "SaaS" },
  { value: "Services", label: "Services" },
  { value: "Agency", label: "Agency" },
  { value: "Other", label: "Other" },
];

import { Activity, BarChart3, Globe, ExternalLink, RefreshCw, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import useWorkspaceStore from "../../../store/workspace.store";
import useAuthStore from "../../../store/auth.store";
import { rescanWorkspace } from "../../../api/workspace.api";
import TrackedPagesManager from "../../../components/features/Pages/TrackedPagesManager";


const formatDateTime = (value) => {
  if (!value) return "Not available";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid date";

  return date.toLocaleString();
};


function WorkspaceSetting() {
  const workspace = useWorkspaceStore((state) => state.workspace);

  const owner = workspace?.competitors?.find((c) => c.role === "Owner") || {};

  const pages = owner.pages || [];

  // The homepage anchors the analysis but isn't a tracked page — exclude it from
  // the Page Analysis counts.
  const isHome = (raw) => {
    const s = String(raw || "").trim();
    if (!s) return false;
    try {
      const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
      return u.pathname === "" || u.pathname === "/";
    } catch {
      return false;
    }
  };

  const pageStats = pages.reduce(
    (acc, page) => {
      if (isHome(page?.url)) return acc;
      const normalized = String(page?.scanStatus || "").toLowerCase();

      if (normalized === "completed") acc.completed += 1;
      else if (normalized === "failed") acc.failed += 1;
      else acc.pending += 1;

      return acc;
    },
    { completed: 0, failed: 0, pending: 0 },
  );

  // const planName = useAuthStore(
  //   (state) => state.user.subscription.planId.displayName,
  // );

  const updateWorkspace = useWorkspaceStore((state) => state.updateWorkspace);
  const user = useAuthStore((state) => state.user);
  // const frequency = user.subscription.planId.limits.reportFrequency.toString().charAt(0).toUpperCase() + user.subscription.planId.limits.reportFrequency.toString().slice(1);

  const [workspaceName, setWorkspaceName] = useState(workspace?.name || "");
  const [industry, setIndustry] = useState(workspace?.industry || "");
  // const [timezone, setTimezone] = useState(workspace?.timezone || "");
  // const [weeklyReportDay, setWeeklyReportDay] = useState(
  //   workspace?.weeklyReportDay || "",
  // );

  const frequency = user?.subscription?.planId?.planReportingFrequency || "N/A";

  const navigate = useNavigate();
  const planName = user?.subscription?.planId?.displayName || "";
  const isPro = String(planName).toLowerCase() === "pro";
  const pagesLimit = user?.subscription?.planId?.limits?.pagesPerCompetitor;
  const ownerUrl = workspace?.url || owner?.url || "";
  const isDev = import.meta.env.DEV;

  const [isSaving, setIsSaving] = useState(false);
  const [rescanning, setRescanning] = useState(false);

  const handleRescan = async () => {
    setRescanning(true);
    try {
      await rescanWorkspace(workspace?._id || workspace?.id);
      Swal.fire({ icon: "success", title: "Monitoring started", text: "A fresh scan has been triggered for this workspace." });
    } catch (e) {
      Swal.fire({ icon: "error", title: "Could not start", text: e?.response?.data?.message || e?.message || "Rescan failed.", confirmButtonColor: "#ff6b6b" });
    } finally {
      setRescanning(false);
    }
  };

  const hasChanges = useMemo(() => {
    return (
      workspaceName.trim() !== (workspace?.name || "").trim() ||
      industry !== (workspace?.industry || "")
    );
  }, [workspaceName, industry, workspace]);

  function handleSaveChanges() {
    if (!workspaceName) {
      Swal.fire({
        icon: "error",
        title: "Required Fields Missing",
        text: "Please fill in all the required fields.",
      });
      return;
    }

    if (!hasChanges) {
      Swal.fire({
        icon: "info",
        title: "No Changes",
        text: "Update any field before saving workspace settings.",
      });
      return;
    }

    setIsSaving(true);
    updateWorkspace({ name: workspaceName.trim(), industry })
      .then(() => {
        Swal.fire({
          icon: "success",
          title: "Settings Updated",
          text: "Workspace settings were saved successfully.",
        });
      })
      .catch((e) => {
        Swal.fire({
          icon: "error",
          title: "Update Failed",
          text: e?.message || "Could not save workspace settings. Please try again.",
          confirmButtonColor: "#ff6b6b",
        });
      })
      .finally(() => setIsSaving(false));
  }

  // const industryOptions = [
  //   { value: "Saas", label: "SaaS" },
  //   { value: "E-Commerce", label: "E-commerce" },
  //   { value: "Agency", label: "Agency" },
  //   { value: "Other", label: "Other" },
  // ];

  // const timezoneOptions = [
  //   { value: "UTC", label: "UTC (GMT)" },
  //   { value: "UTC-8", label: "UTC-8 (Pacific Time)" },
  //   { value: "UTC-5", label: "UTC-5 (Eastern Time)" },
  // ];

  // const reportFrequencyOptions = [
  //   { value: 'Daily', label: 'Daily' },
  //   { value: '3D', label: 'Every 3 Days' },
  //   { value: 'Weekly', label: 'Weekly' },
  // ];

  // const allFrequencyOptions = [
  //   { value: "Daily", label: "Daily" },
  //   { value: "3D", label: "Every 3 Days" },
  //   { value: "Weekly", label: "Weekly" },
  // ];

  // const reportFrequencyOptions = allFrequencyOptions.map((option) => {
  //   let disabled = false;

  //   if (planName === "Starter") {
  //     disabled = option.value !== "Weekly";
  //   } else if (planName === "Growth") {
  //     disabled = !["3D", "Weekly"].includes(option.value);
  //   } else if (planName === "Pro") {
  //     disabled = false;
  //   }

  //   return {
  //     ...option,
  //     disabled,
  //   };
  // });

  return (
    <section className="relative mx-auto w-full max-w-6xl overflow-hidden px-4 py-6 sm:px-6 sm:py-8">
      <div className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-[rgba(78,205,196,0.16)] blur-3xl" />
      <div className="pointer-events-none absolute -bottom-28 -left-20 h-64 w-64 rounded-full bg-[rgba(255,107,107,0.12)] blur-3xl" />

      <div className="relative rounded-3xl border border-(--border) bg-linear-to-r from-(--primary) to-[rgba(26,26,46,0.9)] p-5 shadow-md sm:p-8">
        <div className="inline-flex items-center rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white/90">
          Workspace Center
        </div>
        <h2
          className="mt-3 text-3xl font-semibold leading-tight tracking-tight text-white sm:text-4xl"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Workspace Settings
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-white/80 sm:text-base">
          Configure your workspace preferences
        </p>
      </div>

      {/* Account closure / deletion now lives in Billing & Usage. */}

      <div className="relative mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          {isDev && (
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed border-amber-300 bg-amber-50 p-4">
              <div>
                <p className="text-sm font-semibold text-amber-800">Developer tools</p>
                <p className="text-xs text-amber-700">Trigger a monitoring scan immediately (dev only — never shown to users).</p>
              </div>
              <button
                type="button"
                onClick={handleRescan}
                disabled={rescanning}
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-2 text-sm font-bold text-white transition hover:bg-amber-700 disabled:opacity-60"
              >
                <RefreshCw size={14} className={rescanning ? "animate-spin" : ""} />
                {rescanning ? "Running…" : "Run monitoring now"}
              </button>
            </div>
          )}
          <div className="w-full rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-8">
            <div className="mb-6 flex items-center justify-between gap-3">
              <h4 className="text-lg font-semibold text-slate-800 sm:text-xl">
                General Settings
              </h4>
              <div className="flex items-center gap-2">
                {hasChanges && (
                  <span className="rounded-full bg-[rgba(78,205,196,0.18)] px-2.5 py-1 text-xs font-semibold text-(--primary)">
                    Unsaved Changes
                  </span>
                )}
                <span className="h-2 w-14 rounded-full bg-(--secondary)" />
              </div>
            </div>

            <div className="space-y-5 sm:space-y-6">
              <div>
                <label
                  htmlFor="workspaceName"
                  className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base"
                >
                  Workspace Name
                </label>

                <Input
                  id="workspaceName"
                  type="text"
                  value={workspaceName}
                  placeholder="Enter workspace name"
                  onChange={(e) => setWorkspaceName(e.target.value)}
                />
              </div>

              <div>
                <label
                  htmlFor="industry"
                  className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base"
                >
                  Industry
                </label>
                <Select
                  id="industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  options={INDUSTRY_OPTIONS}
                  placeholder="Select industry"
                />
                <p className="mt-1.5 text-xs text-(--text-light)">
                  Used to tailor your AI competitive insights to your sector.
                </p>
              </div>

              {/* <div>
                <label
                  htmlFor="industry"
                  className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base"
                >
                  Industry
                </label>
                <Select
                  id="industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  options={industryOptions}
                  placeholder="Select industry"
                />
              </div>

              <div>
                <label
                  htmlFor="timezone"
                  className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base"
                >
                  Timezone (Disabled - Coming Soon)
                </label>
                <Select
                  id="timezone"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  disabled
                  options={timezoneOptions}
                  placeholder="Select timezone"
                  style={{
                    backgroundColor: "rgba(0,0,0,0.03)",
                    color: "#94a3b8",
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="weeklyDay"
                  className="mb-2 block text-sm font-medium text-(--text-light) sm:text-base"
                >
                  Reporting Frequency
                </label>
                <Select
                  id="weeklyDay"
                  value={frequency}
                  disabled
                  onChange={(e) => setWeeklyReportDay(e.target.value)}
                  options={reportFrequencyOptions}
                  placeholder="Select frequency"
                />
              </div> */}
            </div>

            <div className="mt-6 flex justify-end">
              <Button
                title={isSaving ? "Saving..." : "Save Changes"}
                onClick={handleSaveChanges}
                className="w-full sm:w-auto"
                disabled={isSaving}
              />
            </div>
          </div>
          <div className="mt-10">
            {/* Your website & tracked pages */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 mb-8 shadow-sm">
              <h3 className="text-lg font-bold text-(--primary) mb-4 flex items-center gap-2">
                <Globe size={20} className="text-(--secondary)" />
                Your Website
              </h3>
              {ownerUrl ? (
                <a
                  href={ownerUrl.startsWith("http") ? ownerUrl : `https://${ownerUrl}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 break-all text-sm font-semibold text-(--secondary-dark) hover:text-(--accent)"
                >
                  {ownerUrl} <ExternalLink size={14} />
                </a>
              ) : (
                <p className="text-sm text-(--text-light)">Not set</p>
              )}

              <div className="mt-5">
                {owner?._id ? (
                  <TrackedPagesManager competitorId={owner._id} role="Owner" />
                ) : (
                  <p className="text-sm text-(--text-light)">No pages tracked yet.</p>
                )}
              </div>
            </div>

            {/* Timeline Info */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 mb-8 shadow-sm">
              <h3 className="text-lg font-bold text-(--primary) mb-6 flex items-center gap-2">
                <Activity size={20} className="text-(--secondary)" />
                Timeline
              </h3>
              <div className="grid sm:grid-cols-2 gap-6">
                <div className="flex items-start gap-4">
                  <div className="flex flex-col items-center shrink-0">
                    <div className="w-4 h-4 rounded-full bg-(--secondary)" />
                    <div className="w-1 h-12 bg-linear-to-b from-(--secondary) to-transparent" />
                  </div>
                  <div className="flex-1 pt-1">
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                      Last Rebuild
                    </p>
                    <p className="text-sm font-medium text-(--text)">
                      {formatDateTime(workspace?.lastRebuiltAt)}
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-4">
                  <div className="flex flex-col items-center shrink-0">
                    <div className="w-4 h-4 rounded-full bg-(--accent)" />
                  </div>
                  <div className="flex-1 pt-1">
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                      Last Updated
                    </p>
                    <p className="text-sm font-medium text-(--text)">
                      {formatDateTime(workspace?.updatedAt)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Pages Analysis */}
            <div className="rounded-2xl border border-gray-200 bg-white p-6 mb-8 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-(--primary) flex items-center gap-2">
                  <BarChart3 size={20} className="text-(--secondary)" />
                  Pages Analysis
                </h3>
                <span className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700">
                  Total: {pageStats.completed + pageStats.pending + pageStats.failed}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3 mb-6">
                <div className="rounded-lg bg-linear-to-br from-green-50 to-emerald-50 border border-green-200 p-4">
                  <p className="text-xs font-medium text-green-700 uppercase tracking-wide">
                    Completed
                  </p>
                  <p className="text-3xl font-bold text-green-700 mt-2">
                    {pageStats.completed}
                  </p>
                </div>
                <div className="rounded-lg bg-linear-to-br from-amber-50 to-yellow-50 border border-amber-200 p-4">
                  <p className="text-xs font-medium text-amber-700 uppercase tracking-wide">
                    Pending
                  </p>
                  <p className="text-3xl font-bold text-amber-700 mt-2">
                    {pageStats.pending}
                  </p>
                </div>
                <div className="rounded-lg bg-linear-to-br from-red-50 to-rose-50 border border-red-200 p-4">
                  <p className="text-xs font-medium text-red-700 uppercase tracking-wide">
                    Failed
                  </p>
                  <p className="text-3xl font-bold text-red-700 mt-2">
                    {pageStats.failed}
                  </p>
                </div>
              </div>

              {/* {competitor.pages.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
                      <p className="text-gray-500 text-sm font-medium">
                        No pages found for this competitor yet.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-100 overflow-y-auto">
                      {competitor.pages.map((page, idx) => (
                        <div
                          key={page._id || page.id || page.url}
                          className="flex items-center justify-between rounded-lg border border-gray-200 bg-linear-to-r from-white to-gray-50 p-4 hover:border-gray-300 transition-all"
                        >
                          <div className="flex items-start gap-3 flex-1 min-w-0">
                            <span className="text-xs font-bold text-gray-400 pt-0.5 shrink-0">
                              #{idx + 1}
                            </span>
                            <a
                              href={page.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-sm font-medium text-(--secondary) hover:text-(--accent) break-all underline-offset-2 hover:underline transition-colors"
                            >
                              {page.url}
                            </a>
                          </div>
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold shrink-0 ${statusPillClass(
                              page.scanStatus,
                            )}`}
                          >
                            {getStatusIcon(page.scanStatus)}
                            {toLabel(page.scanStatus)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )} */}
            </div>

            {/* Account closure / deletion moved to Billing & Usage. */}
          </div>
        </div>

        <div className="lg:col-span-4">
          <div className="rounded-3xl border border-(--border) bg-white p-5 shadow-sm sm:p-8">
            <h4 className="text-lg font-semibold text-slate-800 sm:text-xl">
              Workspace Snapshot
            </h4>
            <p className="mt-2 text-sm text-(--text-light)">
              Quick reference to your current setup and update status.
            </p>

            <div className="mt-6 space-y-4 text-sm">
              <div className="flex items-center justify-between rounded-xl bg-[rgba(0,0,0,0.02)] px-3 py-2">
                <span className="text-(--text-light)">Workspace</span>
                <span className="font-semibold text-(--text)">
                  {workspaceName || "Not set"}
                </span>
              </div>

              <div className="flex items-center justify-between rounded-xl bg-[rgba(0,0,0,0.02)] px-3 py-2">
                <span className="text-(--text-light)">Industry</span>
                <span className="font-semibold text-(--text)">
                  {industry || "Not set"}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-[rgba(0,0,0,0.02)] px-3 py-2">
                <span className="text-(--text-light)">Frequency</span>
                <span className="font-semibold text-(--text)">
                  {frequency || "Not set"}
                </span>
              </div>

              <div className="rounded-xl border border-(--border) bg-[rgba(78,205,196,0.1)] px-3 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-(--primary)">
                  Status
                </p>
                <p className="mt-1 text-sm text-(--text)">
                  {hasChanges
                    ? "You have unsaved workspace changes."
                    : "Everything is up to date."}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default WorkspaceSetting;
