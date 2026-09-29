import express from "express";

const adminRouter = express.Router();

import { adminLogin } from "../controllers/admin.auth.controller.js";

import { getAllUsers, getUserById } from "../controllers/user.controller.js";
import { getAllWorkspaces, getWorkspaceById } from "../controllers/workspace.controller.js";
import { getAllPages } from "../controllers/page.controller.js";
import { getAllCompetitors, getCompetitorById } from "../controllers/competitor.controller.js";
import { getAIStats } from "../controllers/usage.ai.controller.js";
import { getJobs, getJobById, getJobEvents } from "../controllers/job.controller.js";
import { getAllSubscriptions } from "../controllers/subscription.controller.js";

import adminAuthenticate from "../middleware/admin.authenticate.js";

// ------------------ ADMIN ROUTES ------------------
// These routes should ideally be protected by an admin middleware that checks user roles/permissions.  

// AUTHENTICATION
adminRouter.post("/login", adminLogin);

// USER MANAGEMENT
adminRouter.get("/users", getAllUsers);
adminRouter.get("/users/:userId", getUserById);

// WORKSPACE MANAGEMENT
adminRouter.get("/workspaces", getAllWorkspaces);
adminRouter.get("/workspaces/:workspaceId", getWorkspaceById);

// COMPETITOR MANAGEMENT
adminRouter.get("/competitors", getAllCompetitors);
adminRouter.get("/competitors/:competitorId", getCompetitorById);

// PAGE MANAGEMENT
adminRouter.get("/pages", getAllPages);

// AI USAGE STATS
adminRouter.get("/ai-usage", getAIStats);

// JOB MANAGEMENT
adminRouter.get("/jobs", getJobs);
adminRouter.get("/jobs/:jobId", getJobById);
adminRouter.get("/jobs/:jobId/events", getJobEvents);

// SUBSCRIPTION MANAGEMENT
adminRouter.get("/subscriptions", getAllSubscriptions);

export default adminRouter;