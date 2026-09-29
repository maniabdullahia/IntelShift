import { createRedis } from "../app/config/redis.js";
import SocketGateway from "../app/socket/gateway.js";

const sub = createRedis("eventRouter");

/*
|--------------------------------------------------------------------------
| EVENT ROUTER (GENERIC)
|--------------------------------------------------------------------------
| Redis → SocketGateway
|--------------------------------------------------------------------------
*/

const handlers = {

  /*
  |--------------------------------------------------------------------------
  | PAGE EVENTS
  |--------------------------------------------------------------------------
  */

  "page.analysis.started": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "page.analysis.started",
      data
    );
  },

  "page.analysis.progress": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "page.analysis.progress",
      data
    );
  },

  "page.analysis.completed": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "page.analysis.completed",
      data
    );
  },

  "page.analysis.failed": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "page.analysis.failed",
      data
    );
  },

  /*
  |--------------------------------------------------------------------------
  | COMPETITOR EVENTS
  |--------------------------------------------------------------------------
  */

  "competitor.analysis.started": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "competitor.analysis.started",
      data
    );
  },

  "competitor.analysis.completed": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "competitor.analysis.completed",
      data
    );
  },

  "competitor.analysis.failed": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "competitor.analysis.failed",
      data
    );
  },

  /*
  |--------------------------------------------------------------------------
  | WORKSPACE EVENTS
  |--------------------------------------------------------------------------
  */

  "workspace.analysis.started": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "workspace.analysis.started",
      data
    );
  },

  "workspace.analysis.completed": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "workspace.analysis.completed",
      data
    );
  },

  "workspace.analysis.failed": (data) => {
    SocketGateway.workspace(
      data.workspaceId,
      "workspace.analysis.failed",
      data
    );
  },

  /*
  |--------------------------------------------------------------------------
  | NOTIFICATION EVENTS (per-user)
  |--------------------------------------------------------------------------
  */

  "notification.new": (data) => {
    if (!data?.userId) return;
    // Client listens on "notification:new" (see EVENTS.NOTIFICATION.NEW)
    SocketGateway.user(data.userId, "notification:new", data);
  },
};

/*
|--------------------------------------------------------------------------
| START SUBSCRIBER
|--------------------------------------------------------------------------
*/

export const startEventRouter = () => {

  sub.subscribe("socket-events");

  sub.on("message", (channel, message) => {

    const { event, data } = JSON.parse(message);

    const handler = handlers[event];

    if (!handler) {
      console.log("⚠️ Unhandled event:", event);
      return;
    }

    handler(data);
  });
};