import appEvents from "../events/appEvents.js";

function registerAnalysisListeners() {
    appEvents.on("analysis.started", async ({ pageId }) => { });
    appEvents.on("analysis.completed", async ({ pageId, analysisData }) => { });
    appEvents.on("analysis.failed", async ({ pageId }) => { });
}

export default registerAnalysisListeners;
