import { createRedis } from "../app/config/redis.js";
import { emitWorkspaceStatusUpdate, emitPageStatusUpdate, emitCompetitorStatusUpdate } from "../app/socket/emitter.js";

const sub = createRedis("socketSubscriber");

export const startSocketSubscriber = () => {
    sub.subscribe("socket-events");

    sub.on("message", (channel, message) => {
        const { event, data } = JSON.parse(message)

        const { workspaceId } = data;

        switch (event) {
            case "page.analysis.started":
                // console.log(`Page Analysis Started => ${data.pageId}`)
                emitPageStatusUpdate(workspaceId, data.competitorId, data.pageId, "analyzing")
                break;

            case "page.analysis.completed":
                // console.log(`Page Analysis Completed => ${data.pageId}`)
                emitPageStatusUpdate(workspaceId, data.competitorId, data.pageId, "completed")
                break;

            case "page.analysis.failed":
                // console.log(`Page Analysis Failed => ${data.pageId}`)
                emitPageStatusUpdate(workspaceId, data.competitorId, data.pageId, "failed")
                break;

            case "competitor.analysis.started":
                // console.log(`Competitor analysis started => ${data.competitorId}`)
                emitCompetitorStatusUpdate(workspaceId, data.competitorId, "analyzing")
                break;

            case "competitor.analysis.completed":
                // console.log(`Competitor analysis Completed => ${data.competitorId}`)
                emitCompetitorStatusUpdate(workspaceId, data.competitorId, "completed")
                break;

            case "competitor.analysis.failed":
                // console.log(`Competitor analysis Failed => ${data.competitorId}`)
                emitCompetitorStatusUpdate(workspaceId, data.competitorId, "failed")
                break;

            case "workspace.analysis.started":
                // console.log(`workspace analysis started => ${data.workspaceId}`)
                emitWorkspaceStatusUpdate(workspaceId, "analyzing")
                break;

            case "workspace.analysis.completed":
                // console.log(`workspace analysis Completd => ${data.workspaceId}`)
                emitWorkspaceStatusUpdate(workspaceId, "completed")
                break;

            case "workspace.analysis.failed":
                // console.log(`workspace analysis failed => ${data.workspaceId}`)
                emitWorkspaceStatusUpdate(workspaceId, "failed")
                break;

            default:
                console.log(`[SOCKET SUBSCRIBER] Unhandled Event ${event}`)


        }
    })
}