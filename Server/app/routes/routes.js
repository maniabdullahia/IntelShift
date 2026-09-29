import { Router } from "express";
import express from "express";

// CONTROLLERS
import { register, login, refreshToken, logout, forgetPassword, resetPassword, verifyEmail, sendEmailVerificationLink } from "../controllers/auth.controller.js";
import { getProfile, updateProfile, updateNotificationSettings, deleteProfile, changePassword, changePlan, getAllUsers, getUserById } from "../controllers/user.controller.js";
import { createWorkspace, getWorkspace, updateWorkspace, deleteWorkspace, createWorkspaceWithCompetitor, markIntroCompleted, getAllWorkspaces, getWorkspaceById, rescanWorkspace, createWorkspaceWithCompetitors, createWorkspaceRecon, getWorkspaceRecon, previewCollections, saveSelectionDraft, commitSelection, replaceCompetitor, getAnalysis } from "../controllers/workspace.controller.js";
import { createCompetitor, getCompetitor, updateCompetitor, deleteCompetitor, undoCompetitor, getAllCompetitors, getCompetitorById } from "../controllers/competitor.controller.js";
import { createPage, getPages, getPageAnalytics, updatePage, deletePage, getPage, getAllPages, undoPage, getPageLimits, getMappings, backfillMappings } from "../controllers/page.controller.js";
import { createSubscription, createFreeTrialSubscription } from "../controllers/subscription.controller.js";
import { monitorChangeDetails } from "../controllers/monitoring.controller.js";
import { getNotifications, markNotificationsRead } from "../controllers/notification.controller.js";
import { getCompetitorHistory } from "../controllers/history.controller.js";
import { sendTestAlert } from "../controllers/alert.controller.js";
import { getPlans } from "../controllers/plan.controller.js";
import { buildTree, validateUrl, detectStores, debugFetch, validateSite, suggestCompetitors, collectionCount, productMatches } from "../controllers/utils.controller.js";
import { deleteRequest, deleteConfirm, reactivate } from "../controllers/account.controller.js";
import { scheduleDowngradeController, cancelDowngradeController } from "../controllers/downgrade.controller.js";
import { actionCenter } from "../controllers/actionCenter.controller.js";
import { getBillingActions, cancelSubscription } from "../controllers/billing.controller.js";

// MIDDLEWARES
import authenticate from "../middleware/authenticate.js";
import adminAuthenticate from "../middleware/admin.authenticate.js";
import { workspaceOwnershipMiddleware } from "../middleware/workspace.middleware.js";
import { competitorMiddleware } from "../middleware/competitor.middleware.js";
import { socialCheck } from "../middleware/social.middleware.js";
import { blockReadOnly } from "../middleware/entitlement.middleware.js";

// SERVICES


const router = Router();

// AUTH ROUTES
router.post("/register", socialCheck,  register);
router.post("/login", socialCheck, login);
router.post("/refresh-token", refreshToken);
router.post("/logout", logout);
router.post("/forget-password", forgetPassword);
router.post("/reset-password", resetPassword);
router.post("/email-verification-link", sendEmailVerificationLink);
router.post("/verify-email", verifyEmail);

// USER ROUTES
router.get("/profile", authenticate, getProfile);
router.put("/profile", authenticate, updateProfile);
router.delete("/profile", authenticate, deleteProfile);
router.post("/change-password", authenticate, changePassword);
router.put("/settings/alerts", authenticate, blockReadOnly, updateNotificationSettings);
router.post("/alerts/test", authenticate, sendTestAlert);
router.post("/change-plan", authenticate, changePlan);
router.post("/free-trial-subscription", authenticate, createFreeTrialSubscription);

// PLAN DOWNGRADE (scheduled at renewal, with keep-selection)
router.post("/downgrade/schedule", authenticate, scheduleDowngradeController);
router.post("/downgrade/cancel", authenticate, cancelDowngradeController);

// BILLING ACTIONS (update payment method, cancel/unsubscribe with 14-day refund)
router.get("/billing/management", authenticate, getBillingActions);
router.post("/billing/cancel", authenticate, cancelSubscription);

// ACTION CENTER (setup to-dos / gaps for the current workspace)
router.get("/action-center", authenticate, workspaceOwnershipMiddleware, actionCenter);

// ACCOUNT CLOSURE ROUTES (staged, reversible deletion)
router.post("/account/delete-request", authenticate, deleteRequest);
router.post("/account/delete-confirm", deleteConfirm); // public — token proves identity
router.post("/account/reactivate", authenticate, reactivate);

// WORKSPACE ROUTES
router.post("/workspace", authenticate, createWorkspace);
router.get("/workspace", authenticate, workspaceOwnershipMiddleware, getWorkspace);
router.put("/workspace", authenticate, blockReadOnly, workspaceOwnershipMiddleware, updateWorkspace);
router.delete("/workspace", authenticate, blockReadOnly, workspaceOwnershipMiddleware, deleteWorkspace);
router.post("/workspace-with-competitor", authenticate, createWorkspaceWithCompetitor);
router.post("/workspace-with-competitors", authenticate, createWorkspaceWithCompetitors);
// Capture-first creation: urls only → recon jobs (page selection happens in-workspace)
router.post("/workspace-recon", authenticate, createWorkspaceRecon);
// Capture-first selection: fetch captured recon for the panel, then commit the picks
router.get("/workspace/recon", authenticate, getWorkspaceRecon);
router.post("/workspace/preview-collections", authenticate, previewCollections);
router.post("/workspace/selection-draft", authenticate, blockReadOnly, saveSelectionDraft);
router.post("/workspace/commit-selection", authenticate, blockReadOnly, commitSelection);
router.post("/workspace/replace-competitor", authenticate, blockReadOnly, replaceCompetitor);
router.post('/workspace/mark-intro-completed', authenticate, workspaceOwnershipMiddleware, markIntroCompleted);
router.get("/workspace-rescan/:workspaceId", authenticate, rescanWorkspace);
router.get("/analysis/:analysisId", authenticate, workspaceOwnershipMiddleware, getAnalysis);

// COMPETITOR ROUTES
router.post("/competitor", authenticate, blockReadOnly, workspaceOwnershipMiddleware, createCompetitor);
router.get("/competitor", authenticate, workspaceOwnershipMiddleware, getCompetitor);
router.put("/competitor", authenticate, blockReadOnly, workspaceOwnershipMiddleware, updateCompetitor);
router.delete("/competitor", authenticate, blockReadOnly, workspaceOwnershipMiddleware, deleteCompetitor);
router.post("/competitor/undo", authenticate, blockReadOnly, workspaceOwnershipMiddleware, undoCompetitor);


// PAGE ROUTES (tracked-page management is staged — see page.service.js)
router.post("/page", authenticate, blockReadOnly, workspaceOwnershipMiddleware, competitorMiddleware, createPage);
router.get("/pages", authenticate, workspaceOwnershipMiddleware, getPages);
router.get("/page/limits", authenticate, workspaceOwnershipMiddleware, getPageLimits);
router.get("/page", authenticate, workspaceOwnershipMiddleware, getPage);
router.put("/page", authenticate, blockReadOnly, workspaceOwnershipMiddleware, updatePage);
router.delete("/page", authenticate, blockReadOnly, workspaceOwnershipMiddleware, deletePage);
router.post("/page/undo", authenticate, blockReadOnly, workspaceOwnershipMiddleware, undoPage);

// PAGE MAPPING (owner ↔ competitor page pairing; lazy-backfills old accounts)
router.get("/mappings", authenticate, workspaceOwnershipMiddleware, getMappings);
router.post("/mappings/backfill", authenticate, workspaceOwnershipMiddleware, backfillMappings);

// MONITORING ROUTES (Change Details, Dashboard... etc)
router.get("/monitoring/status/:workspaceId", authenticate, monitorChangeDetails);

// NOTIFICATION ROUTES
router.get("/notifications", authenticate, getNotifications);
router.put("/notifications/read", authenticate, markNotificationsRead);

// HISTORY ROUTES (historical competitor timeline — Growth/Pro)
router.get("/history/:competitorId", authenticate, getCompetitorHistory);


// PLAN ROUTES
router.get("/plans", getPlans);

// BUILD URL TREE
router.post('/url-tree', buildTree);
router.post('/collection-count', collectionCount);
router.post('/product-matches', authenticate, productMatches);

// VALIDATE URL EXISTS
router.post('/validate-url', validateUrl);

// DETECT REGIONAL STORES / CURRENCIES (for the onboarding store picker)
router.post('/detect-stores', detectStores);

// SUGGEST DIRECT COMPETITORS (onboarding assist)
router.post('/suggest-competitors', suggestCompetitors);

// DEBUG — inspect exactly what the crawler fetched for a URL (raw HTML + categories)
router.post('/debug-fetch', debugFetch);

// ONBOARDING READINESS — confirm homepage + collection + product are reachable
router.post('/validate-site', validateSite);

// HEALTH CHECK
router.get("/health", (req, res) => {
    res.json({ status: "OK", timestamp: new Date() });
});

// // ------------------ ADMIN ROUTES ------------------
// // These routes should ideally be protected by an admin middleware that checks user roles/permissions.  

// // USER MANAGEMENT
// router.get("/admin/users", getAllUsers);
// router.get("/admin/users/:userId", getUserById);

// // WORKSPACE MANAGEMENT
// router.get("/admin/workspaces", getAllWorkspaces);
// router.get("/admin/workspaces/:workspaceId", getWorkspaceById);

// // COMPETITOR MANAGEMENT
// router.get("/admin/competitors", getAllCompetitors);
// router.get("/admin/competitors/:competitorId", getCompetitorById);

// // PAGE MANAGEMENT
// router.get("/admin/pages", getAllPages);


// 404 ROUTE
router.use((req, res) => {
    res.status(404).json({ message: "Invalid Route" });
});

export default router;