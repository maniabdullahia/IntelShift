import appEvents from "../events/appEvents.js";

function registerWorkspaceListeners() {
    appEvents.on("workspace.created", async ({ workspaceId }) => { });
    appEvents.on("workspace.updated", async ({ workspaceId }) => { });
    appEvents.on("workspace.deleted", async ({ workspaceId }) => { });
    appEvents.on("workspace.scan.started", async ({ workspaceId }) => { });
    appEvents.on("workspace.scan.completed", async ({ workspaceId }) => { });
    appEvents.on("workspace.scan.failed", async ({ workspaceId }) => { });
}

export default registerWorkspaceListeners;