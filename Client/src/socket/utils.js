/**
 * Socket Utilities
 * ================
 * Helper functions for common socket operations
 * These utilities can be used throughout the app
 */

import socket from "../services/socket";
import eventManager from "./eventManager";
import { EVENTS } from "./events";

/**
 * Listen to an event with automatic cleanup
 * Useful for temporary listeners that should be removed when component unmounts
 * 
 * @param {string} eventName - Event name from EVENTS constant
 * @param {function} callback - Handler function
 * @returns {function} Cleanup function to call on unmount
 * 
 * Example:
 *   const cleanup = listenOnce(EVENTS.PAGE.ANALYSIS_COMPLETED, (data) => {
 *     console.log('Analysis done:', data)
 *   })
 *   // Later: cleanup()
 */
export const listenOnce = (eventName, callback) => {
  return eventManager.on(eventName, callback);
};

/**
 * Emit an event to the server
 * 
 * @param {string} eventName - Event name
 * @param {object} data - Data to send
 * 
 * Example:
 *   emitEvent("workspace:join", { workspaceId: "123" })
 */
export const emitEvent = (eventName, data = {}) => {
  socket.emit(eventName, data);
};

/**
 * Wait for an event with timeout
 * Useful for request-response patterns
 * 
 * @param {string} eventName - Event name to wait for
 * @param {number} timeout - Timeout in ms (default: 10000)
 * @returns {Promise} Resolves with event data or rejects on timeout
 * 
 * Example:
 *   try {
 *     const result = await waitForEvent(EVENTS.PAGE.ANALYSIS_COMPLETED, 30000)
 *     console.log('Got result:', result)
 *   } catch (err) {
 *     console.error('Timeout waiting for event')
 *   }
 */
export const waitForEvent = (eventName, timeout = 10000) => {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      unsubscribe();
      reject(new Error(`Timeout waiting for event: ${eventName}`));
    }, timeout);

    const unsubscribe = eventManager.on(eventName, (data) => {
      clearTimeout(timer);
      unsubscribe();
      resolve(data);
    });
  });
};

/**
 * Emit an event and wait for response
 * Implements request-response pattern over sockets
 * 
 * @param {string} eventName - Event name to emit
 * @param {object} data - Data to send
 * @param {string} responseEventName - Event name to listen for response
 * @param {number} timeout - Timeout in ms (default: 10000)
 * @returns {Promise} Resolves with response data
 * 
 * Example:
 *   try {
 *     const workspace = await emitAndWait(
 *       "workspace:fetch",
 *       { workspaceId: "123" },
 *       "workspace:fetched",
 *       5000
 *     )
 *     console.log('Got workspace:', workspace)
 *   } catch (err) {
 *     console.error('Request failed:', err)
 *   }
 */
export const emitAndWait = (
  eventName,
  data = {},
  responseEventName,
  timeout = 10000
) => {
  return new Promise((resolve, reject) => {
    // Set up listener first
    const unsubscribe = eventManager.once(responseEventName, (response) => {
      clearTimeout(timer);
      resolve(response);
    });

    // Then emit the event
    socket.emit(eventName, data);

    // Handle timeout
    const timer = setTimeout(() => {
      unsubscribe();
      reject(new Error(`Timeout waiting for response: ${responseEventName}`));
    }, timeout);
  });
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
 * Get socket connection status
 * 
 * @returns {object} { connected: boolean, id: string }
 */
export const getSocketStatus = () => {
  return {
    connected: socket.connected,
    id: socket.id,
  };
};

/**
 * Batch emit multiple events
 * Useful for bulk operations
 * 
 * @param {array} events - Array of { eventName, data }
 * 
 * Example:
 *   batchEmit([
 *     { eventName: "page:update", data: { pageId: "1", ... } },
 *     { eventName: "page:update", data: { pageId: "2", ... } }
 *   ])
 */
export const batchEmit = (events) => {
  events.forEach(({ eventName, data }) => {
    socket.emit(eventName, data);
  });
};

/**
 * Batch listen to multiple events
 * Useful for subscribing to multiple events at once
 * 
 * @param {object} eventHandlers - { eventName: handler }
 * @returns {function} Cleanup function to unsubscribe from all
 * 
 * Example:
 *   const cleanup = batchListen({
 *     [EVENTS.PAGE.UPDATED]: (data) => console.log('Page updated', data),
 *     [EVENTS.PAGE.DELETED]: (data) => console.log('Page deleted', data)
 *   })
 *   // Later: cleanup()
 */
export const batchListen = (eventHandlers) => {
  const unsubscribers = Object.entries(eventHandlers).map(
    ([eventName, handler]) => eventManager.on(eventName, handler)
  );

  return () => {
    unsubscribers.forEach((unsub) => unsub());
  };
};

/**
 * Create a scoped event listener
 * Useful for components that need to listen to namespaced events
 * 
 * @param {string} scope - Scope prefix (e.g., "workspace:123")
 * @returns {object} { on, off, emit, once, clear }
 * 
 * Example:
 *   const workspaceEvents = createScope("workspace:123")
 *   workspaceEvents.on("updated", handler)
 *   // Listens to "workspace:123:updated"
 */
export const createScope = (scope) => {
  const prefix = `${scope}:`;

  return {
    on: (eventName, callback) => {
      return eventManager.on(`${prefix}${eventName}`, callback);
    },
    off: (eventName, callback) => {
      eventManager.off(`${prefix}${eventName}`, callback);
    },
    emit: (eventName, data) => {
      socket.emit(`${prefix}${eventName}`, data);
    },
    once: (eventName, callback) => {
      return eventManager.once(`${prefix}${eventName}`, callback);
    },
    clear: () => {
      // Remove all listeners with this prefix
      eventManager.getRegisteredEvents().forEach((event) => {
        if (event.startsWith(prefix)) {
          socket.off(event);
        }
      });
    },
  };
};

/**
 * Debounce socket events
 * Useful for high-frequency events to avoid overwhelming the handler
 * 
 * @param {string} eventName - Event name
 * @param {function} callback - Handler function
 * @param {number} delay - Debounce delay in ms (default: 300)
 * @returns {function} Cleanup function
 * 
 * Example:
 *   const cleanup = debounceEvent(
 *     EVENTS.PAGE.ANALYSIS_PROGRESS,
 *     (data) => updateProgressBar(data),
 *     500
 *   )
 */
export const debounceEvent = (eventName, callback, delay = 300) => {
  let timeout;

  return eventManager.on(eventName, (data) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      callback(data);
    }, delay);
  });
};

/**
 * Throttle socket events
 * Useful for rate-limiting event handlers
 * 
 * @param {string} eventName - Event name
 * @param {function} callback - Handler function
 * @param {number} limit - Throttle limit in ms (default: 300)
 * @returns {function} Cleanup function
 * 
 * Example:
 *   const cleanup = throttleEvent(
 *     EVENTS.WORKSPACE.DATA_SYNCED,
 *     (data) => console.log('Synced:', data),
 *     1000
 *   )
 */
export const throttleEvent = (eventName, callback, limit = 300) => {
  let inThrottle = false;

  return eventManager.on(eventName, (data) => {
    if (!inThrottle) {
      callback(data);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  });
};

export default {
  listenOnce,
  emitEvent,
  waitForEvent,
  emitAndWait,
  isSocketConnected,
  getSocketStatus,
  batchEmit,
  batchListen,
  createScope,
  debounceEvent,
  throttleEvent,
};
