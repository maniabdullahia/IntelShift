import appEvents from "../events/appEvents.js";

function registerPageListeners() {
    appEvents.on("page.created", async ({ pageId }) => { });
    appEvents.on("page.updated", async ({ pageId }) => { });
    appEvents.on("page.deleted", async ({ pageId }) => { });
    appEvents.on("page.scan.started", async ({ pageId }) => { });
    appEvents.on("page.scan.completed", async ({ pageId }) => { });
    appEvents.on("page.scan.failed", async ({ pageId }) => { });
}

export default registerPageListeners;