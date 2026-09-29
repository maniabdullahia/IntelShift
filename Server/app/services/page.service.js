import Page from "../models/page.js";
import Workspace from "../models/workspace.js";
import Competitor from "../models/competitor.js";
import ChangeReport from "../models/changeReport.js";
import MetricSnapshot from "../models/metricSnapshot.js";
import Notification from "../models/notification.js";

import { getSubscriptionByUserId } from "./subscription.service.js";
import { getPlanById } from "./plan.service.js";
import { getNextScanAt } from "../../utils/scan.js";
import { publishSocketEvent } from "../../utils/eventBus.publisher.js";
import { matchCompetitorPages } from "../../utils/pageMatch.js";

const STAGED_NOTIF_TYPE = "page_change_staged";

const fmtApplyDate = (d) =>
  d ? new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : null;

/*
 * Raise (once) an in-app bell notification when page edits are staged, nudging
 * the user to align the matching pages on their other sites before the next run.
 * Deduped: we only create one unread notification per staging session.
 */
const notifyStagedPageChanges = async (workspace) => {
  try {
    const userId = workspace.ownerId;
    const existing = await Notification.findOne({ userId, type: STAGED_NOTIF_TYPE, read: false });
    if (existing) return; // already nudged this session

    const when = fmtApplyDate(await estimateNextApply(workspace));
    const title = "Update matching competitor pages";
    const body =
      `You have staged page changes. They apply on your next monitoring run` +
      `${when ? ` (around ${when})` : ""}. Before then, update the matching pages on your ` +
      `competitors so comparisons stay aligned.`;

    await Notification.create({ userId, type: STAGED_NOTIF_TYPE, title, body, link: "/competitors" });
    await publishSocketEvent("notification.new", {
      userId: String(userId),
      workspaceId: String(workspace._id),
      type: STAGED_NOTIF_TYPE,
      title,
      body,
      link: "/competitors",
    }).catch(() => {});
  } catch (err) {
    console.error("Staged-page notification failed (continuing):", err.message);
  }
};

/** Clear the staged-changes nudge (e.g. once changes are applied or all undone). */
const clearStagedNotification = (userId) =>
  Notification.deleteMany({ userId, type: STAGED_NOTIF_TYPE }).catch(() => {});

/** Flag the workspace as having staged changes AND raise the bell nudge. */
const stageWorkspace = async (workspace) => {
  await flagWorkspace(workspace._id);
  await notifyStagedPageChanges(workspace);
};

/*
|--------------------------------------------------------------------------
| TRACKED-PAGE MANAGEMENT (staged, deferred to next monitoring run)
|--------------------------------------------------------------------------
| Users can edit which pages we track — both their own site's pages and each
| competitor's. Edits are STAGED, never applied instantly:
|   • adding a page      → created as pendingChange "add" (analyzed next run)
|   • removing a page    → marked pendingChange "remove" (still shown, pruned
|                          next run)
| The workspace is flagged so the UI can say "changes apply on <date>". At the
| start of the next monitoring run applyPendingPageChanges() commits them.
|
| History impact: monitoring history (MetricSnapshots / ChangeReports) is
| competitor-level. On plans WITHOUT a history timeline (trial/starter) a page
| change resets that competitor's baseline so no stale history lingers — those
| plans can't view history anyway. Growth/Pro keep their timeline intact.
*/

const HISTORY_PLANS = ["growth", "pro"];

const normalizeUrl = (raw) => {
  let u = String(raw || "").trim();
  if (!u) return "";
  if (!/^https?:\/\//i.test(u)) u = `https://${u}`;
  return u.replace(/\/+$/, ""); // drop trailing slash
};

// The homepage (site root, path "/" or empty) anchors the analysis: it can't be
// removed and doesn't count toward the tracked-pages limit.
export const isHomepageUrl = (raw) => {
  try {
    const s = String(raw || "").trim();
    if (!s) return false;
    const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
    return u.pathname === "" || u.pathname === "/";
  } catch {
    return false;
  }
};

/** Resolve the owning user's active plan (or null for free/trial with none). */
export const getWorkspacePlan = async (workspace) => {
  try {
    const subscription = await getSubscriptionByUserId(workspace.ownerId);
    if (!subscription?.planId) return { plan: null, subscription: null };
    const plan = await getPlanById(subscription.planId).catch(() => null);
    return { plan, subscription };
  } catch {
    return { plan: null, subscription: null };
  }
};

const planHasHistory = (plan) => HISTORY_PLANS.includes(String(plan?.name || "").toLowerCase());

// Editing tracked pages is a paid capability — the free trial can view its
// pages but must upgrade to add/remove/remap them.
const MANAGE_PLANS = ["starter", "growth", "pro"];
const planAllowsPageManagement = (plan) => MANAGE_PLANS.includes(String(plan?.name || "").toLowerCase());

const requirePaidPlan = async (workspace) => {
  const { plan } = await getWorkspacePlan(workspace);
  if (!planAllowsPageManagement(plan)) {
    const err = new Error(
      "Editing tracked pages is available on paid plans. Upgrade to add, remove or remap the pages you monitor."
    );
    err.code = "UPGRADE_REQUIRED";
    throw err;
  }
  return plan;
};

/**
 * Active (non-retired) page count for a competitor toward the plan limit —
 * the homepage is excluded (it's mandatory and free).
 */
const activePageCount = async (competitorId) => {
  const pages = await Page.find({ competitorId, pendingChange: { $ne: "remove" } }).select("url");
  return pages.filter((p) => !isHomepageUrl(p.url)).length;
};

// Normalize a URL for matching an owner page to a competitor page's mappedOwnerUrl
// (scheme/www/trailing-slash/case-insensitive).
const stripUrl = (u) =>
  String(u || "").trim().replace(/[?#].*$/, "").replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/+$/, "").toLowerCase();

// Is any OTHER competitor page still mapped to this owner url and NOT staged for
// removal? If so, the owner page is still needed for a comparison.
const ownerPageStillNeeded = async (workspace, ownerUrl, excludePageId) => {
  const want = stripUrl(ownerUrl);
  if (!want) return true; // unknown → keep (safe)
  const comps = await Page.find({
    workspaceId: workspace._id,
    mapStatus: "matched",
    pendingChange: { $ne: "remove" },
    ...(excludePageId ? { _id: { $ne: excludePageId } } : {}),
  }).select("mappedOwnerUrl");
  return comps.some((p) => stripUrl(p.mappedOwnerUrl) === want);
};

// Cascade a competitor-page change onto its OWNER counterpart so the two stay in
// lockstep. Removing: drop/stage-remove the owner page only if nothing else maps to
// it. restore: un-stage an owner-page removal (a mapping came back).
const cascadeOwnerPage = async (workspace, ownerUrl, excludePageId, { restore = false } = {}) => {
  const want = stripUrl(ownerUrl);
  if (!want) return;
  const owner = await Competitor.findOne({ workspaceId: workspace._id, role: "Owner" });
  if (!owner) return;
  const ownerPages = await Page.find({ competitorId: owner._id }).select("url pendingChange");
  const target = ownerPages.find((op) => stripUrl(op.url) === want && !isHomepageUrl(op.url));
  if (!target) return;

  if (restore) {
    if (target.pendingChange === "remove") {
      await Page.updateOne({ _id: target._id }, { $set: { pendingChange: "none", retiredAt: null } });
    }
    return;
  }
  // Removing — keep the owner page if another competitor still maps to it.
  if (await ownerPageStillNeeded(workspace, want, excludePageId)) return;
  if (target.pendingChange === "add") {
    await Page.deleteOne({ _id: target._id }); // was only staged → drop outright
  } else {
    await Page.updateOne({ _id: target._id }, { $set: { pendingChange: "remove", retiredAt: new Date() } });
  }
};

const flagWorkspace = (workspaceId) =>
  Workspace.findByIdAndUpdate(workspaceId, {
    pendingPageChanges: true,
    pendingPageChangesAt: new Date(),
  });

/* ── Add a tracked page (staged) ──────────────────────────────────────── */
export const addTrackedPage = async ({ workspace, competitor, url, label, mappedOwnerUrl }) => {
  const plan = await requirePaidPlan(workspace);

  const cleanUrl = normalizeUrl(url);
  if (!cleanUrl) throw new Error("A valid URL is required");

  if (String(competitor.workspaceId) !== String(workspace._id)) {
    throw new Error("Competitor does not belong to this workspace");
  }

  // A competitor page must be MAPPED to a page on your own site (mapped-only), so
  // comparisons stay like-for-like — the same rule as onboarding.
  const isOwnerSide = competitor.role === "Owner";
  let ownerUrlClean = "";
  if (!isOwnerSide) {
    ownerUrlClean = normalizeUrl(mappedOwnerUrl);
    if (!ownerUrlClean) throw new Error("Add the page on your own site that this maps to");
  }

  // Dedupe against existing pages (allow re-adding one staged for removal).
  const existing = await Page.findOne({ competitorId: competitor._id, url: cleanUrl });
  if (existing) {
    if (existing.pendingChange === "remove") {
      // Atomic update — avoids doc.save() (and its pre-save hook) entirely.
      await Page.updateOne(
        { _id: existing._id },
        { $set: {
          pendingChange: "none", retiredAt: null,
          ...(label !== undefined ? { label } : {}),
          ...(ownerUrlClean ? { mappedOwnerUrl: ownerUrlClean, mapStatus: "matched" } : {}),
        } }
      );
      if (ownerUrlClean) await ensureOwnerPage(workspace, ownerUrlClean);
      await stageWorkspace(workspace);
      const refreshed = await Page.findById(existing._id);
      return { page: refreshed, restored: true };
    }
    throw new Error("This page is already tracked for this competitor");
  }

  // Plan limit.
  const limit = plan?.limits?.pagesPerCompetitor;
  if (limit) {
    const count = await activePageCount(competitor._id);
    if (count >= limit) {
      const err = new Error(
        `You've reached your plan's limit of ${limit} pages per competitor. Upgrade to track more.`
      );
      err.code = "PLAN_LIMIT";
      throw err;
    }
  }

  const page = await Page.create({
    url: cleanUrl,
    label: label || "",
    competitorId: competitor._id,
    workspaceId: workspace._id,
    scanStatus: "Pending",
    pendingChange: "add",
    analysisData: {},
    ...(ownerUrlClean ? { mappedOwnerUrl: ownerUrlClean, mapStatus: "matched" } : {}),
  });

  // Ensure the mapped OWNER page exists too, so the pair is crawled like-for-like.
  if (ownerUrlClean) await ensureOwnerPage(workspace, ownerUrlClean);

  await stageWorkspace(workspace);
  return { page };
};

/* Make sure the owner site has a tracked page for `ownerUrl` (create it staged if
   missing, or un-stage a removal), so a newly mapped competitor page has its
   counterpart to compare against. */
const ensureOwnerPage = async (workspace, ownerUrl) => {
  const owner = await Competitor.findOne({ workspaceId: workspace._id, role: "Owner" });
  if (!owner) return;
  const existsOwner = await Page.findOne({ competitorId: owner._id, url: ownerUrl });
  if (!existsOwner) {
    await Page.create({
      url: ownerUrl,
      competitorId: owner._id,
      workspaceId: workspace._id,
      scanStatus: "Pending",
      pendingChange: "add",
      mapStatus: "none",
      analysisData: {},
    });
  } else if (existsOwner.pendingChange === "remove") {
    await Page.updateOne({ _id: existsOwner._id }, { $set: { pendingChange: "none", retiredAt: null } });
  }
};

/* ── Remove a tracked page (staged) ───────────────────────────────────── */
export const removeTrackedPage = async ({ workspace, pageId }) => {
  await requirePaidPlan(workspace);

  const page = await Page.findById(pageId);
  if (!page) throw new Error("Page not found");
  if (String(page.workspaceId) !== String(workspace._id)) {
    throw new Error("Page does not belong to this workspace");
  }
  if (isHomepageUrl(page.url)) {
    throw new Error("The homepage can't be removed — it anchors your analysis.");
  }

  // A page that was only ever staged for adding can just be dropped outright.
  if (page.pendingChange === "add") {
    await Page.deleteOne({ _id: page._id });
    // Remove its owner counterpart too, unless another competitor still maps to it.
    if (page.mappedOwnerUrl) await cascadeOwnerPage(workspace, page.mappedOwnerUrl, page._id);
    await stageWorkspace(workspace);
    return { page, dropped: true };
  }

  // Atomic update — avoids doc.save() (and its pre-save hook) entirely.
  await Page.updateOne(
    { _id: page._id },
    { $set: { pendingChange: "remove", retiredAt: new Date() } }
  );
  // Stage the owner counterpart for removal too (unless another competitor still
  // maps to it) — it shows "removing" until the next run, mirroring this page.
  if (page.mappedOwnerUrl) await cascadeOwnerPage(workspace, page.mappedOwnerUrl, page._id);
  await stageWorkspace(workspace);
  const refreshed = await Page.findById(page._id);
  return { page: refreshed };
};

/* ── Undo a staged change ─────────────────────────────────────────────── */
export const undoPendingPageChange = async ({ workspace, pageId }) => {
  const plan = await requirePaidPlan(workspace);

  const page = await Page.findById(pageId);
  if (!page) throw new Error("Page not found");
  if (String(page.workspaceId) !== String(workspace._id)) {
    throw new Error("Page does not belong to this workspace");
  }

  let result;
  if (page.pendingChange === "add") {
    await Page.deleteOne({ _id: page._id });
    // Drop the owner counterpart too (unless another competitor still maps to it),
    // so undoing a staged add doesn't leave an orphan page on your own site.
    if (page.mappedOwnerUrl) await cascadeOwnerPage(workspace, page.mappedOwnerUrl, page._id);
    result = { removed: true };
  } else {
    if (page.pendingChange === "remove") {
      // Restoring re-occupies a slot. If a replacement page was staged after this
      // removal, undoing it would push over the per-competitor limit — block it so
      // the count can't leak above the plan cap.
      const limit = plan?.limits?.pagesPerCompetitor;
      if (limit && !isHomepageUrl(page.url)) {
        // activePageCount excludes pending-remove, so it's the count WITHOUT this
        // page; restoring adds one back.
        const current = await activePageCount(page.competitorId);
        if (current + 1 > limit) {
          const err = new Error(
            `Restoring this page would exceed your limit of ${limit} pages for this competitor. Remove a newly added page first, then undo.`
          );
          err.code = "PLAN_LIMIT";
          throw err;
        }
      }
      // Atomic update — avoids doc.save() (and its pre-save hook) entirely.
      await Page.updateOne(
        { _id: page._id },
        { $set: { pendingChange: "none", retiredAt: null } }
      );
      // The mapping is back → un-stage the owner counterpart's removal too.
      if (page.mappedOwnerUrl) await cascadeOwnerPage(workspace, page.mappedOwnerUrl, page._id, { restore: true });
    }
    result = { page: await Page.findById(page._id) };
  }

  // If nothing is staged anymore, clear the workspace flag + the bell nudge.
  const remaining = await Page.countDocuments({
    workspaceId: workspace._id,
    pendingChange: { $in: ["add", "remove"] },
  });
  if (remaining === 0) {
    await Workspace.findByIdAndUpdate(workspace._id, {
      pendingPageChanges: false,
      pendingPageChangesAt: null,
    });
    await clearStagedNotification(workspace.ownerId);
  }
  return result;
};

/*
| Commit all staged page changes for a workspace. Called at the START of a
| monitoring run so edits "take effect next run". Returns the set of competitor
| ids whose page set actually changed.
*/
export const applyPendingPageChanges = async (workspaceId) => {
  const workspace = await Workspace.findById(workspaceId);
  if (!workspace || !workspace.pendingPageChanges) return { changed: [] };

  const staged = await Page.find({
    workspaceId,
    pendingChange: { $in: ["add", "remove"] },
  }).select("_id competitorId pendingChange");

  const changedCompetitors = new Set(staged.map((p) => String(p.competitorId)));

  // Commit removals.
  const toRemove = staged.filter((p) => p.pendingChange === "remove").map((p) => p._id);
  if (toRemove.length) await Page.deleteMany({ _id: { $in: toRemove } });

  // Promote adds to normal tracked pages (they get analyzed this run).
  await Page.updateMany(
    { workspaceId, pendingChange: "add" },
    { $set: { pendingChange: "none" } }
  );

  // On non-history plans, reset the baseline for changed competitors so stale
  // timeline data doesn't accumulate where it can never be shown.
  const { plan } = await getWorkspacePlan(workspace);
  if (!planHasHistory(plan) && changedCompetitors.size) {
    const ids = [...changedCompetitors];
    await MetricSnapshot.deleteMany({ competitorId: { $in: ids } });
    await ChangeReport.deleteMany({ competitorId: { $in: ids } });
  }

  workspace.pendingPageChanges = false;
  workspace.pendingPageChangesAt = null;
  await workspace.save();

  // Changes are live now — clear the "update matching pages" bell nudge.
  await clearStagedNotification(workspace.ownerId);

  return { changed: [...changedCompetitors] };
};

/** When will staged changes take effect? (workspace.nextScanAt, or plan cadence.) */
export const estimateNextApply = async (workspace) => {
  if (workspace.nextScanAt) return workspace.nextScanAt;
  const { plan } = await getWorkspacePlan(workspace);
  const cadence = plan?.planReportingFrequency || "once";
  if (cadence === "once") return null;
  return getNextScanAt(cadence, new Date());
};

/*
| Backfill mappings for a workspace that pre-dates mapping storage (or whose
| pages were never paired). Auto-matches each competitor's UNMAPPED pages to the
| owner's pages using the same scorer as onboarding. Never overrides a page that
| already has a mapping, so it's safe to run repeatedly.
*/
export const backfillWorkspaceMappings = async (workspaceId) => {
  const competitors = await Competitor.find({ workspaceId }).select("_id role");
  const owner = competitors.find((c) => c.role === "Owner");
  if (!owner) return { updated: 0 };

  const ownerPages = await Page.find({ competitorId: owner._id }).select("url");
  const ownerUrls = ownerPages.map((p) => p.url).filter(Boolean);
  if (!ownerUrls.length) return { updated: 0 };

  let updated = 0;
  const rivals = competitors.filter((c) => c.role !== "Owner");
  for (const comp of rivals) {
    const pages = await Page.find({
      competitorId: comp._id,
      $or: [{ mapStatus: { $in: [null, "none"] } }, { mappedOwnerUrl: { $in: [null, ""] } }],
    }).select("url");
    if (!pages.length) continue;

    const matches = matchCompetitorPages(ownerUrls, pages.map((p) => p.url));
    for (const page of pages) {
      const ownerUrl = matches.get(page.url);
      if (ownerUrl) {
        await Page.updateOne(
          { _id: page._id },
          { $set: { mappedOwnerUrl: ownerUrl, mapStatus: "matched" } }
        );
        updated += 1;
      }
    }
  }
  return { updated };
};

/*
| Structured mapping view for the settings editor: one "slot" per owner page,
| each listing the paired page on every competitor. Lazily backfills accounts
| that have no mappings yet (pre-existing accounts), so the mapping "just works".
*/
export const getWorkspaceMappings = async (workspace) => {
  const workspaceId = workspace._id;
  const competitors = await Competitor.find({ workspaceId }).select("_id name domain role");
  const owner = competitors.find((c) => c.role === "Owner");
  const rivals = competitors.filter((c) => c.role !== "Owner");
  if (!owner) return { owner: null, competitors: [], slots: [] };

  const rivalIds = rivals.map((c) => c._id);
  const anyMapped = rivalIds.length
    ? await Page.exists({ competitorId: { $in: rivalIds }, mapStatus: "matched" })
    : null;
  if (!anyMapped) await backfillWorkspaceMappings(workspaceId);

  const ownerPages = await Page.find({ competitorId: owner._id }).select("url");
  const compPages = await Page.find({ competitorId: { $in: rivalIds } })
    .select("url competitorId mappedOwnerUrl mapStatus");

  const slots = ownerPages.map((op) => ({
    ownerUrl: op.url,
    matches: rivals.map((c) => {
      const m = compPages.find(
        (p) => String(p.competitorId) === String(c._id) && p.mappedOwnerUrl === op.url
      );
      return { competitorId: c._id, competitorName: c.name, competitorUrl: m?.url || null };
    }),
  }));

  return {
    owner: { competitorId: owner._id, name: owner.name },
    competitors: rivals.map((c) => ({ competitorId: c._id, name: c.name, domain: c.domain })),
    slots,
  };
};

/* ── Legacy helpers (kept for existing callers) ───────────────────────── */
const updatePageStatus = async (pageId, status) => {
  const page = await Page.findById(pageId);
  if (!page) throw new Error("Page not found");
  page.scanStatus = status;
  await page.save();
};

const deletePage = async (pageId) => {
  await Page.findByIdAndDelete(pageId);
};

export { planHasHistory, planAllowsPageManagement, updatePageStatus, deletePage };
