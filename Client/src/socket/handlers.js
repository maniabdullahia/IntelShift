
/**
 * Socket Event Handlers
 * =====================
 * Centralized place to register all socket event handlers
 * Organized by domain/feature for better maintainability
 * 
 * Each handler is responsible for:
 * 1. Listening to socket events
 * 2. Processing the data
 * 3. Updating stores/state
 * 4. Triggering side effects if needed
 * 
 * Import this file in your main App.jsx to initialize handlers
 */

import eventManager from "./eventManager";
import { EVENTS } from "./events";

// Import stores to update state when events arrive
import useWorkspaceStore from "../store/workspace.store";
import useAuthStore from "../store/auth.store";
import useNotificationStore from "../store/notification.store";

const { syncUser } = useAuthStore.getState();

/**
 * WORKSPACE HANDLERS
 */
const setupWorkspaceHandlers = () => {
    /**
     * Handle workspace update event
     * Triggered when workspace settings or data changes
     */
    eventManager.on(EVENTS.WORKSPACE.UPDATED, (data) => {
        console.log("🔄 [Handler] WORKSPACE.UPDATED:", data);
        // Re-sync from the server rather than calling the store's updateWorkspace
        // action, which itself PUTs to the API (that would echo the change back).
        try {
            useWorkspaceStore.getState().syncWorkspace();
        } catch (error) {
            console.error("❌ [Handler] Error syncing workspace:", error);
        }
    });

    /**
     * Handle workspace members update
     * Triggered when team members are added/removed/updated
     */
    eventManager.on(EVENTS.WORKSPACE.MEMBERS_UPDATED, (data) => {
        // No members feature in the store yet — refresh from the server so any
        // membership change is reflected without a dedicated action.
        console.log("👥 [Handler] WORKSPACE.MEMBERS_UPDATED:", data);
        useWorkspaceStore.getState().syncWorkspace();
    });

    /**
     * Handle workspace deletion
     */
    eventManager.on(EVENTS.WORKSPACE.DELETED, (data) => {
        console.log("🗑️ [Handler] WORKSPACE.DELETED:", data);
        // Clear local workspace state and send the user back to the dashboard.
        useWorkspaceStore.getState().clearStorage();
        window.location.href = "/dashboard";
    });

    /**
     * Handle workspace settings change
     */
    eventManager.on(EVENTS.WORKSPACE.SETTINGS_CHANGED, (data) => {
        console.log("⚙️ [Handler] WORKSPACE.SETTINGS_CHANGED:", data);
        useWorkspaceStore.getState().syncWorkspace();
    });

    /**
     * Handle workspace data sync
     */
    eventManager.on(EVENTS.WORKSPACE.DATA_SYNCED, (data) => {
        console.log("🔃 [Handler] WORKSPACE.DATA_SYNCED:", data);
        useWorkspaceStore.getState().syncWorkspace();
    });

    eventManager.on(EVENTS.WORKSPACE.ANALYSIS_STARTED, (data) => {
        
        useWorkspaceStore.getState().updateWorkspaceStatus(data.status);
        // Update store or UI to show loading state
    });

    eventManager.on(EVENTS.WORKSPACE.ANALYSIS_FAILED, (data) => {
       
        useWorkspaceStore.getState().updateWorkspaceStatus(data.status);
        // Show error notification
        // Log error for debugging
    });

    /**
     * Handle workspace analysis progress
     */
    eventManager.on(EVENTS.WORKSPACE.ANALYSIS_PROGRESS, (data) => {
       
        
    });

    /**
     * Handle workspace analysis completion
     */
    eventManager.on(EVENTS.WORKSPACE.ANALYSIS_COMPLETED, (data) => {
       console.log("Workspace Analysis Completed: ", data)
        useWorkspaceStore.getState().updateWorkspaceStatus(data.status);
    });
};

/**
 * PAGE HANDLERS
 */
const setupPageHandlers = () => {
    /**
     * Handle page analysis started
     */
    eventManager.on(EVENTS.PAGE.ANALYSIS_STARTED, (data) => {
        console.log("📄 [Handler] PAGE.ANALYSIS_STARTED:", data);
        try {
            useWorkspaceStore.getState().updatePageStatus(data.competitorId, data.pageId, data.status);
            console.log("✅ [Handler] Page status updated:", { competitorId: data.competitorId, pageId: data.pageId, status: data.status });
        } catch (error) {
            console.error("❌ [Handler] Error updating page status:", error);
        }
    });

    /**
     * Handle page analysis progress
     * Real-time progress updates during analysis
     */
    eventManager.on(EVENTS.PAGE.ANALYSIS_PROGRESS, (data) => {
       
        // Update progress bar, UI state, etc.
    });

    /**
     * Handle page analysis completed
     */
    eventManager.on(EVENTS.PAGE.ANALYSIS_COMPLETED, (data) => {
        console.log("✅ [Handler] PAGE.ANALYSIS_COMPLETED:", data);
        try {
            useWorkspaceStore.getState().updatePageStatus(data.competitorId, data.pageId, data.status);
            console.log("✅ [Handler] Page analysis marked as completed");
        } catch (error) {
            console.error("❌ [Handler] Error completing page analysis:", error);
        }
    });

    /**
     * Handle page analysis failed
     */
    eventManager.on(EVENTS.PAGE.ANALYSIS_FAILED, (data) => {
        
        useWorkspaceStore.getState().updatePageStatus(data.competitorId, data.pageId, data.status);
        // Show error notification
        // Log error for debugging
    });

    /**
     * Handle page update
     */
    eventManager.on(EVENTS.PAGE.UPDATED, (data) => {
       
        // Update page data in store
    });

    /**
     * Handle page deletion
     */
    eventManager.on(EVENTS.PAGE.DELETED, (data) => {
       
        // Remove page from store
        // Redirect if viewing deleted page
    });
};

/**
 * COMPETITOR HANDLERS
 */
const setupCompetitorHandlers = () => {
    /**
     * Handle competitor added
     */
    eventManager.on(EVENTS.COMPETITOR.ADDED, (data) => {
        
        // Add to competitors list
        // Show notification
    });

    /**
     * Handle competitor updated
     */
    eventManager.on(EVENTS.COMPETITOR.UPDATED, (data) => {
       
        // Update competitor data
        // Refresh competitor comparison UI
    });

    /**
     * Handle competitor analysis started
     */
    eventManager.on(EVENTS.COMPETITOR.ANALYSIS_STARTED, (data) => {
        console.log("🏢 [Handler] COMPETITOR.ANALYSIS_STARTED:", data);
        try {
            useWorkspaceStore.getState().updateCompetitorStatus(data.competitorId, data.status);
            console.log("✅ [Handler] Competitor status updated to:", data.status);
        } catch (error) {
            console.error("❌ [Handler] Error updating competitor status:", error);
        }
    });

    /**
     * Handle competitor analysis completed
     */
    eventManager.on(EVENTS.COMPETITOR.ANALYSIS_COMPLETED, (data) => {
        console.log("🏆 [Handler] COMPETITOR.ANALYSIS_COMPLETED:", data);
        try {
            useWorkspaceStore.getState().updateCompetitorStatus(data.competitorId, data.status);
            console.log("✅ [Handler] Competitor analysis marked as completed");
        } catch (error) {
            console.error("❌ [Handler] Error completing competitor analysis:", error);
        }
    });

    /**
     * Handle competitor deleted
     */
    eventManager.on(EVENTS.COMPETITOR.DELETED, (data) => {
       
        // Remove from list
    });

    /**
     * Handle competitor analysis started
     */
    eventManager.on(EVENTS.COMPETITOR.ANALYSIS_STARTED, (data) => {
      
        useWorkspaceStore.getState().updateCompetitorStatus(data.competitorId, data.status);
    });

    /**
     * Handle competitor analysis completed
     */

    eventManager.on(EVENTS.COMPETITOR.ANALYSIS_COMPLETED, (data) => {
       
        useWorkspaceStore.getState().updateCompetitorStatus(data.competitorId, data.status);
        // Show notification
        // Refresh competitor data
    });

    /**
     * Handle competitor analysis failed
     */
    eventManager.on(EVENTS.COMPETITOR.ANALYSIS_FAILED, (data) => {
       
        useWorkspaceStore.getState().updateCompetitorStatus(data.competitorId, data.status);
        // Show error notification
        // Log error for debugging
    });


};

/**
 * USER HANDLERS
 */
const setupUserHandlers = () => {
    /**
     * Handle user profile update
     */
    eventManager.on(EVENTS.USER.PROFILE_UPDATED, (data) => {
        console.log("👤 [Handler] USER.PROFILE_UPDATED:", data);
        // User data lives in the auth store (there is no separate user store).
        // Re-sync to pull the latest profile from the server.
        useAuthStore.getState().syncUser();
    });

    /**
     * Handle user preferences change
     */
    eventManager.on(EVENTS.USER.PREFERENCES_CHANGED, (data) => {
        console.log("👤 [Handler] USER.PREFERENCES_CHANGED:", data);
        useAuthStore.getState().syncUser();
    });

    /**
     * Handle user activity log
     */
    eventManager.on(EVENTS.USER.ACTIVITY_LOG, (data) => {
        
        // Log activity for audit trail
    });

        /**
         * Handle user subscription created
         * Triggered when a new subscription is created for the user
         */
    eventManager.on(EVENTS.USER.SUBSCRIPTION_CREATED, (data) => {
        console.log("Received user.subscription.created event:", data);
    })
};

/**
 * NOTIFICATION HANDLERS
 */
const setupNotificationHandlers = () => {
    /**
     * Handle new notification
     */
    eventManager.on(EVENTS.NOTIFICATION.NEW, (data) => {
        console.log("🔔 [Handler] NOTIFICATION.NEW:", data);
        // Push into the shared store so the header bell updates instantly.
        useNotificationStore.getState().addOne({
            title: data?.title,
            body: data?.body,
            link: data?.link || "/dashboard",
            type: data?.type,
        });
    });

    /**
     * Handle notification dismissed
     */
    eventManager.on(EVENTS.NOTIFICATION.DISMISSED, (data) => {
       
    });

    /**
     * Handle notification marked as read
     */
    eventManager.on(EVENTS.NOTIFICATION.READ, (data) => {
       
    });
};

/**
 * USAGE & BILLING HANDLERS
 */
const setupUsageHandlers = () => {
    /**
     * Handle AI credits updated
     */
    eventManager.on(EVENTS.USAGE.AI_CREDITS_UPDATED, (data) => {
       
        // Update credits display
        // Update store
    });

    /**
     * Handle AI analysis tracked
     */
    eventManager.on(EVENTS.USAGE.AI_ANALYSIS_TRACKED, (data) => {
       
        // Update usage stats
    });

    /**
     * Handle quota warning
     */
    eventManager.on(EVENTS.USAGE.QUOTA_WARNING, (data) => {
        console.log("⚠️  Quota warning:", data);
        // Show warning notification
        // Suggest upgrade
    });
};

/**
 * ADMIN HANDLERS
 */
const setupAdminHandlers = () => {
    /**
     * Handle user activity in admin panel
     */
    eventManager.on(EVENTS.ADMIN.USER_ACTIVITY, (data) => {
       
        // Update admin dashboard
    });

    /**
     * Handle system alert
     */
    eventManager.on(EVENTS.ADMIN.SYSTEM_ALERT, (data) => {
        
        // Show alert in admin panel
    });

    /**
     * Handle analytics update
     */
    eventManager.on(EVENTS.ADMIN.ANALYTICS_UPDATE, (data) => {
      
        // Refresh analytics dashboard
    });
};

const setupSubscriptionHandlers = () => {


    /**
     * Handle subscription created
     */

    eventManager.on(EVENTS.SUBSCRIPTION.CREATED, () => {
        console.log("Subscription created event received. Syncing user data...");
        syncUser();
        // window.location.href = '/onboarding'; 
    });
}

/**
 * Initialize all handlers
 * Call this function from your main App.jsx on mount
 * 
 * Example:
 *   import { initializeSocketHandlers } from './socket/handlers'
 *   useEffect(() => {
 *     initializeSocketHandlers()
 *     return () => eventManager.clear()
 *   }, [])
 */
export const initializeSocketHandlers = () => {
    // console.log("🚀 [Init] Initializing socket handlers...");
    eventManager.clear(); // Clear existing handlers to avoid duplicates

    setupWorkspaceHandlers();
    // console.log("✅ [Init] Workspace handlers initialized");
    
    setupPageHandlers();
    // console.log("✅ [Init] Page handlers initialized");
    
    setupCompetitorHandlers();
    // console.log("✅ [Init] Competitor handlers initialized");
    
    setupUserHandlers();
    // console.log("✅ [Init] User handlers initialized");
    
    setupNotificationHandlers();
    // console.log("✅ [Init] Notification handlers initialized");
    
    setupUsageHandlers();
    // console.log("✅ [Init] Usage handlers initialized");
    
    setupAdminHandlers();
    // console.log("✅ [Init] Admin handlers initialized");
    
    setupSubscriptionHandlers();
    console.log("✅ [Init] Subscription handlers initialized");
    console.log("🎉 [Init] All socket handlers ready!");
};

export default {
    setupWorkspaceHandlers,
    setupPageHandlers,
    setupCompetitorHandlers,
    setupUserHandlers,
    setupNotificationHandlers,
    setupUsageHandlers,
    setupAdminHandlers,
};
