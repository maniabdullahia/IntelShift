/**
 * Socket Event Definitions
 * =======================
 * Centralized registry of all socket events used in the application
 * This file serves as the source of truth for event names and structure
 * 
 * Usage:
 *   import { EVENTS } from './events'
 *   socket.on(EVENTS.WORKSPACE.UPDATED, handler)
 */

export const EVENTS = {
  /**
   * WORKSPACE EVENTS
   * Events related to workspace operations
   */
  WORKSPACE: {
    UPDATED: "workspace:updated",
    DELETED: "workspace:deleted",
    MEMBERS_UPDATED: "workspace:members-updated",
    SETTINGS_CHANGED: "workspace:settings-changed",
    DATA_SYNCED: "workspace:data-synced",
    ANALYSIS_STARTED: "workspace.analysis.started",
    ANALYSIS_PROGRESS: "workspace.analysis.progress",
    ANALYSIS_COMPLETED: "workspace.analysis.completed",
    ANALYSIS_FAILED: "workspace.analysis.failed",
  },

  /**
   * PAGE EVENTS
   * Events related to page analysis and crawling
   */
  PAGE: {
    ANALYSIS_STARTED: "page.analysis.started",
    ANALYSIS_PROGRESS: "page.analysis.progress",
    ANALYSIS_COMPLETED: "page.analysis.completed",
    ANALYSIS_FAILED: "page.analysis.failed",
    UPDATED: "page:updated",
    DELETED: "page:deleted",
  },

  /**
   * COMPETITOR EVENTS
   * Events related to competitor tracking
   */
  COMPETITOR: {
    ADDED: "competitor:added",
    UPDATED: "competitor:updated",
    DELETED: "competitor:deleted",
    ANALYSIS_STARTED: "competitor.analysis.started",
    ANALYSIS_COMPLETED: "competitor.analysis.completed",
    ANALYSIS_FAILED: "competitor.analysis.failed",
    ANALYSIS_PROGRESS: "competitor.analysis.progress",
  },

  /**
   * USER EVENTS
   * Events related to user profile and account
   */
  USER: {
    PROFILE_UPDATED: "user:profile-updated",
    PREFERENCES_CHANGED: "user:preferences-changed",
    ACTIVITY_LOG: "user:activity-log",
    SUBSCRIPTION_CREATED: "user.subscription.created",
  },

  /**
   * NOTIFICATION EVENTS
   * Events for user notifications
   */
  NOTIFICATION: {
    NEW: "notification:new",
    DISMISSED: "notification:dismissed",
    READ: "notification:read",
  },

  /**
   * USAGE & BILLING EVENTS
   * Events related to usage tracking and billing
   */
  USAGE: {
    AI_CREDITS_UPDATED: "usage:ai-credits-updated",
    AI_ANALYSIS_TRACKED: "usage:ai-analysis-tracked",
    QUOTA_WARNING: "usage:quota-warning",
  },

  /**
   * ADMIN EVENTS
   * Events for admin panel
   */
  ADMIN: {
    USER_ACTIVITY: "admin:user-activity",
    SYSTEM_ALERT: "admin:system-alert",
    ANALYTICS_UPDATE: "admin:analytics-update",
  },

  /**
   * CONNECTION EVENTS
   * Built-in events for connection management
   * Note: Using custom names instead of reserved Socket.IO names
   */
  CONNECTION: {
    CONNECTED: "socket:connected",
    DISCONNECTED: "socket:disconnected",
    ERROR: "socket:error",
  },


  SUBSCRIPTION: {
    CREATED: "subscription.created",
    UPDATED: "subscription:updated",
    CANCELED: "subscription:canceled",
  },
};

/**
 * Event Schema Documentation
 * ==========================
 * Each event can have specific payload structure
 * This helps with type checking and documentation
 */
export const EVENT_SCHEMAS = {
  // Workspace
  [EVENTS.WORKSPACE.UPDATED]: {
    workspaceId: "string",
    name: "string?",
    description: "string?",
    updatedAt: "timestamp",
  },
  [EVENTS.WORKSPACE.MEMBERS_UPDATED]: {
    workspaceId: "string",
    members: "array",
    updatedAt: "timestamp",
  },

  // Page
  [EVENTS.PAGE.ANALYSIS_PROGRESS]: {
    pageId: "string",
    workspaceId: "string",
    progress: "number (0-100)",
    status: "string",
  },
  [EVENTS.PAGE.ANALYSIS_COMPLETED]: {
    pageId: "string",
    workspaceId: "string",
    analysisData: "object",
    completedAt: "timestamp",
  },

  // Usage
  [EVENTS.USAGE.AI_CREDITS_UPDATED]: {
    userId: "string",
    creditsRemaining: "number",
    creditsUsed: "number",
    totalCredits: "number",
  },

  // Notifications
  [EVENTS.NOTIFICATION.NEW]: {
    notificationId: "string",
    type: "string",
    title: "string",
    message: "string",
    createdAt: "timestamp",
  },
};
