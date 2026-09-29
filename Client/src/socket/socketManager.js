/**
 * Socket Manager
 * ==============
 * Manages socket connection lifecycle and room management
 * Integrates with the event system
 */

import socket from "../services/socket";
import eventManager from "./eventManager";
import { EVENTS } from "./events";

let isConnected = false;

/**
 * Connect to socket server
 * Also sets up automatic reconnection and error handling
 */
export const connectSocket = () => {
  if (!isConnected) {
    console.log("🔌 [Socket] Connecting to server...");

    // Set up connection listeners
    socket.on("connect", () => {
      isConnected = true;
      console.log("✅ [Socket] Connected successfully. ID:", socket.id);
      eventManager.emit(EVENTS.CONNECTION.CONNECTED, { socketId: socket.id });
    });

    socket.on("disconnect", () => {
      console.log("❌ [Socket] Disconnected from server");
      isConnected = false;
      eventManager.emit(EVENTS.CONNECTION.DISCONNECTED);
    });

    socket.on("connect_error", (error) => {
      console.error("❌ [Socket] Connection error:", error);
      eventManager.emit(EVENTS.CONNECTION.ERROR, { error: error.message });
    });

    socket.connect();
  } else {
    console.log("ℹ️  [Socket] Already connected, skipping connection");
  }
};

/**
 * Disconnect from socket server
 */
export const disconnectSocket = () => {
  if (socket.connected) {
    console.log("🔌 Disconnecting from socket server...");
    socket.disconnect();
    isConnected = false;
  }
};

/**
 * Check if socket is connected
 * 
 * @returns {boolean}
 */
export const isSocketConnected = () => {
  return socket.connected;
};

/**
 * Get socket ID
 * 
 * @returns {string|null}
 */
export const getSocketId = () => {
  return socket.id || null;
};

/**
 * Join a workspace room
 * All events sent to this workspace will be received
 * 
 * @param {string} workspaceId - Workspace ID
 */
export const joinWorkspace = (workspaceId) => {
  socket.emit("workspace:join", workspaceId);
};

/**
 * Leave a workspace room
 * 
 * @param {string} workspaceId - Workspace ID
 */
export const leaveWorkspace = (workspaceId) => {
  socket.emit("workspace:leave", workspaceId);
};

/**
 * Join admin room (for admin panel)
 */
export const joinAdminRoom = () => {

  socket.emit("admin:join");
};

/**
 * Join user personal room (for personal notifications)
 * 
 * @param {string} userId - User ID
 */
export const joinUserRoom = (userId) => {

  socket.emit("user:join", userId);
};

/**
 * Get current connection status
 * 
 * @returns {object} { connected, socketId }
 */
export const getConnectionStatus = () => {
  return {
    connected: isConnected,
    socketId: socket.id,
  };
};

export default {
  connectSocket,
  disconnectSocket,
  isSocketConnected,
  getSocketId,
  joinWorkspace,
  leaveWorkspace,
  joinAdminRoom,
  joinUserRoom,
  getConnectionStatus,
};