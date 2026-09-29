import Page from "../models/page.js";
import {
  addTrackedPage,
  removeTrackedPage,
  undoPendingPageChange,
  estimateNextApply,
  getWorkspacePlan,
  planHasHistory,
  planAllowsPageManagement,
  backfillWorkspaceMappings,
  getWorkspaceMappings,
} from "../services/page.service.js";

// Never let the "when does this apply" nicety block or fail the core action.
const safeNextApply = async (workspace) => {
  try {
    return await estimateNextApply(workspace);
  } catch (e) {
    console.error("[estimateNextApply]", e.message);
    return null;
  }
};

/*
| Tracked pages are edited through a STAGED workflow: adds/removes are recorded
| but only take effect at the next monitoring run. See page.service.js.
*/

// POST /page  — stage a new tracked page (owner or competitor)
const createPage = async (req, res) => {
  try {
    const { url, label, mappedOwnerUrl } = req.body;
    if (!url) return res.status(400).json({ message: "URL is required" });

    const result = await addTrackedPage({
      workspace: req.workspace,
      competitor: req.competitor,
      url,
      label,
      mappedOwnerUrl,
    });

    const nextApply = await safeNextApply(req.workspace);
    return res.status(201).json({
      page: result.page,
      restored: !!result.restored,
      pending: true,
      appliesAt: nextApply,
      message: result.restored
        ? "This page was un-removed and will be tracked again from the next monitoring run."
        : "Page staged — it will be analyzed on the next monitoring run.",
    });
  } catch (error) {
    const status = error.code === "PLAN_LIMIT" || error.code === "UPGRADE_REQUIRED" ? 403 : 400;
    return res.status(status).json({ message: error.message, code: error.code });
  }
};

// GET /page  — list a competitor's tracked pages (includes staged state)
const getPages = async (req, res) => {
  try {
    const { competitorId } = { ...req.body, ...req.query };
    if (!competitorId) return res.status(400).json({ message: "Competitor ID is required" });
    const pages = await Page.find({ competitorId }).sort({ createdAt: 1 });
    return res.json(pages);
  } catch (error) {
    console.error("[GET PAGES ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

// PUT /page  — update a tracked page's label (staged edits handled via add/remove)
const updatePage = async (req, res) => {
  try {
    const { pageId, label } = req.body;
    if (!pageId) return res.status(400).json({ message: "Page ID is required" });

    const page = await Page.findById(pageId);
    if (!page) return res.status(404).json({ message: "Page not found" });
    if (String(page.workspaceId) !== String(req.workspace._id)) {
      return res.status(403).json({ message: "Page does not belong to this workspace" });
    }
    if (label !== undefined) page.label = label;
    await page.save();
    return res.json(page);
  } catch (error) {
    console.error("[UPDATE PAGE ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

// DELETE /page  — stage a removal (kept until next monitoring run)
const deletePage = async (req, res) => {
  try {
    const { pageId } = { ...req.body, ...req.query };
    if (!pageId) return res.status(400).json({ message: "Page ID is required" });

    const result = await removeTrackedPage({ workspace: req.workspace, pageId });
    const nextApply = await safeNextApply(req.workspace);
    return res.json({
      page: result.page,
      dropped: !!result.dropped,
      pending: !result.dropped,
      appliesAt: nextApply,
      message: result.dropped
        ? "Page removed."
        : "Page marked for removal — it stops being tracked at the next monitoring run.",
    });
  } catch (error) {
    console.error("[DELETE PAGE ERROR]", error);
    const status = error.code === "UPGRADE_REQUIRED" ? 403 : 400;
    return res.status(status).json({ message: error.message, code: error.code });
  }
};

// POST /page/undo  — cancel a staged add/remove
const undoPage = async (req, res) => {
  try {
    const { pageId } = req.body;
    if (!pageId) return res.status(400).json({ message: "Page ID is required" });
    const result = await undoPendingPageChange({ workspace: req.workspace, pageId });
    return res.json({ ...result, message: "Staged change reverted." });
  } catch (error) {
    const status = error.code === "UPGRADE_REQUIRED" || error.code === "PLAN_LIMIT" ? 403 : 400;
    return res.status(status).json({ message: error.message, code: error.code });
  }
};

// GET /page/limits  — plan page limit + history capability + pending state
const getPageLimits = async (req, res) => {
  try {
    const { plan } = await getWorkspacePlan(req.workspace);
    const nextApply = await safeNextApply(req.workspace);
    return res.json({
      pagesPerCompetitor: plan?.limits?.pagesPerCompetitor ?? null,
      hasHistory: planHasHistory(plan),
      canManage: planAllowsPageManagement(plan),
      planName: plan?.name || null,
      pendingPageChanges: !!req.workspace.pendingPageChanges,
      appliesAt: nextApply,
    });
  } catch (error) {
    return res.status(500).json({ message: error.message });
  }
};

// GET /mappings  — structured owner↔competitor page mapping (lazy-backfills)
const getMappings = async (req, res) => {
  try {
    const data = await getWorkspaceMappings(req.workspace);
    return res.json(data);
  } catch (error) {
    console.error("[GET MAPPINGS ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

// POST /mappings/backfill  — explicitly auto-match unmapped competitor pages
const backfillMappings = async (req, res) => {
  try {
    const result = await backfillWorkspaceMappings(req.workspace._id);
    return res.json({ ...result, message: `Auto-matched ${result.updated} competitor page(s).` });
  } catch (error) {
    console.error("[BACKFILL MAPPINGS ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

const getPage = async (req, res) => {
  try {
    const { pageId } = { ...req.body, ...req.query };
    if (!pageId) return res.status(400).json({ message: "Page ID is required" });
    const page = await Page.findById(pageId);
    if (!page) return res.status(404).json({ message: "Page not found" });
    return res.json(page);
  } catch (error) {
    console.error("[GET PAGE ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

const getPageAnalytics = async (req, res) => {
  try {
    const { pageId } = { ...req.body, ...req.query };
    const page = await Page.findById(pageId);
    if (!page) return res.status(404).json({ message: "Page not found" });
    return res.json(page.analysisData);
  } catch (error) {
    console.error("[GET PAGE ANALYTICS ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

const getAllPages = async (req, res) => {
  try {
    const { page = 1, limit = 10 } = req.query;
    const pages = await Page.find()
      .skip((page - 1) * limit)
      .limit(Number(limit));
    return res.json(pages);
  } catch (error) {
    console.error("[GET ALL PAGES ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

export {
  createPage,
  getPages,
  updatePage,
  deletePage,
  undoPage,
  getPageLimits,
  getPageAnalytics,
  getAllPages,
  getPage,
  getMappings,
  backfillMappings,
};
