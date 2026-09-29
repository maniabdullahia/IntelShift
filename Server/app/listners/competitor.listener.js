import appEvents from "../events/appEvents.js";

function registerCompetitorListeners() {
    appEvents.on("competitor.created", async ({ competitorId }) => { });
    appEvents.on("competitor.updated", async ({ competitorId }) => { });
    appEvents.on("competitor.deleted", async ({ competitorId }) => { });
    appEvents.on("competitor.scan.started", async ({ competitorId }) => { });
    appEvents.on("competitor.scan.completed", async ({ competitorId }) => { });
    appEvents.on("competitor.scan.failed", async ({ competitorId }) => { });
}

export default registerCompetitorListeners;