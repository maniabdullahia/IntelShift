
/**
 * @readonly
 * @enum {string}
 */

export const EVENTS = Object.freeze({

    WORKSPACE_CREATED: "workspace.created",
    WORKSPACE_UPDATED: "workspace.updated",
    WORKSPACE_DELETED: "workspace.deleted",
    WORKSPACE_SCAN_STARTED: "workspace.scan.started",
    WORKSPACE_SCAN_COMPLETED: "workspace.scan.completed",
    WORKSPACE_SCAN_FAILED: "workspace.scan.failed",

    COMPETITOR_CREATED: "competitor.created",
    COMPETITOR_UPDATED: "competitor.updated",
    COMPETITOR_DELETED: "competitor.deleted",
    COMPETITOR_SCAN_STARTED: "competitor.scan.started",
    COMPETITOR_SCAN_COMPLETED: "competitor.scan.completed",
    COMPETITOR_SCAN_FAILED: "competitor.scan.failed",

    PAGE_CREATED: "page.created",
    PAGE_UPDATED: "page.updated",
    PAGE_DELETED: "page.deleted",
    PAGE_SCAN_STARTED: "page.scan.started",
    PAGE_SCAN_COMPLETED: "page.scan.completed",
    PAGE_SCAN_FAILED: "page.scan.failed",

    WORKSPACE_STATS_RECALC: "workspace.stats.recalc",
});

