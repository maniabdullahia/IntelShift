/**
 * Socket Hooks
 * =============
 * React hooks for easy socket integration in components
 * 
 * Examples:
 *   const data = useSocketEvent(EVENTS.WORKSPACE.UPDATED)
 *   useSocketListener(EVENTS.PAGE.ANALYSIS_PROGRESS, (data) => {...})
 */

import { useEffect, useState, useCallback, useRef } from "react";
import eventManager from "./eventManager";
import { EVENTS } from "./events";

/**
 * Listen to a socket event in a component
 * Automatically cleans up on unmount
 * 
 * @param {string} eventName - Event name
 * @param {function} callback - Handler function
 * 
 * Example:
 *   useSocketListener(EVENTS.PAGE.ANALYSIS_COMPLETED, (data) => {
 *     setAnalysisData(data)
 *   })
 */
export const useSocketListener = (eventName, callback) => {
  useEffect(() => {
    const unsubscribe = eventManager.on(eventName, callback);
    return unsubscribe;
  }, [eventName, callback]);
};

/**
 * Store socket event data in component state
 * Automatically updates when event is received
 * 
 * @param {string} eventName - Event name
 * @param {*} initialValue - Initial state value
 * @returns {*} Event data
 * 
 * Example:
 *   const analysisData = useSocketEvent(EVENTS.PAGE.ANALYSIS_COMPLETED)
 */
export const useSocketEvent = (eventName, initialValue = null) => {
  const [data, setData] = useState(initialValue);

  useEffect(() => {
    const unsubscribe = eventManager.on(eventName, setData);
    return unsubscribe;
  }, [eventName]);

  return data;
};

/**
 * Listen to multiple socket events
 * 
 * @param {object} eventHandlers - { eventName: handler }
 * 
 * Example:
 *   useSocketListeners({
 *     [EVENTS.PAGE.UPDATED]: (data) => console.log('Page updated:', data),
 *     [EVENTS.PAGE.DELETED]: (data) => console.log('Page deleted:', data)
 *   })
 */
export const useSocketListeners = (eventHandlers) => {
  useEffect(() => {
    const unsubscribers = Object.entries(eventHandlers).map(
      ([eventName, handler]) => eventManager.on(eventName, handler)
    );

    return () => {
      unsubscribers.forEach((unsub) => unsub());
    };
  }, [eventHandlers]);
};

/**
 * Wait for a socket event to occur
 * Useful for triggering actions after specific events
 * 
 * @param {string} eventName - Event name
 * @param {function} onEvent - Callback when event arrives
 * @param {function} onError - Error callback
 * 
 * Example:
 *   useWaitForSocketEvent(
 *     EVENTS.PAGE.ANALYSIS_COMPLETED,
 *     (data) => showSuccessNotification(),
 *     (error) => showErrorNotification(error)
 *   )
 */
export const useWaitForSocketEvent = (eventName, onEvent, onError) => {
  const timeoutRef = useRef(null);

  useEffect(() => {
    const unsubscribe = eventManager.once(eventName, (data) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      onEvent(data);
    });

    timeoutRef.current = setTimeout(() => {
      unsubscribe();
      onError?.(new Error(`Timeout waiting for event: ${eventName}`));
    }, 30000);

    return () => {
      unsubscribe();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [eventName, onEvent, onError]);
};

/**
 * Debounce socket event handler
 * Useful for high-frequency events
 * 
 * @param {string} eventName - Event name
 * @param {function} callback - Handler function
 * @param {number} delay - Debounce delay in ms
 * 
 * Example:
 *   useDebounceSocketEvent(
 *     EVENTS.PAGE.ANALYSIS_PROGRESS,
 *     (data) => updateProgressBar(data),
 *     500
 *   )
 */
export const useDebounceSocketEvent = (eventName, callback, delay = 300) => {
  const timeoutRef = useRef(null);

  useEffect(() => {
    const unsubscribe = eventManager.on(eventName, (data) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        callback(data);
      }, delay);
    });

    return () => {
      unsubscribe();
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [eventName, callback, delay]);
};

/**
 * Throttle socket event handler
 * 
 * @param {string} eventName - Event name
 * @param {function} callback - Handler function
 * @param {number} limit - Throttle limit in ms
 * 
 * Example:
 *   useThrottleSocketEvent(
 *     EVENTS.WORKSPACE.DATA_SYNCED,
 *     (data) => console.log('Synced:', data),
 *     1000
 *   )
 */
export const useThrottleSocketEvent = (eventName, callback, limit = 300) => {
  const inThrottleRef = useRef(false);

  useEffect(() => {
    const unsubscribe = eventManager.on(eventName, (data) => {
      if (!inThrottleRef.current) {
        callback(data);
        inThrottleRef.current = true;
        setTimeout(() => {
          inThrottleRef.current = false;
        }, limit);
      }
    });

    return unsubscribe;
  }, [eventName, callback, limit]);
};

/**
 * Hook to emit a socket event
 * Returns a function that can be called to emit
 * 
 * @param {string} eventName - Event name
 * @returns {function} Function to emit event with data
 * 
 * Example:
 *   const emitAnalysis = useEmitSocketEvent("page:analyze")
 *   <button onClick={() => emitAnalysis({ pageId: "123" })}>
 *     Analyze
 *   </button>
 */
export const useEmitSocketEvent = (eventName) => {
  return useCallback(
    (data) => {
      eventManager.emit(eventName, data);
    },
    [eventName]
  );
};

/**
 * Hook for request-response socket pattern
 * Returns a function that emits and waits for response
 * 
 * @param {string} requestEventName - Event to emit
 * @param {string} responseEventName - Event to wait for
 * @param {number} timeout - Timeout in ms
 * @returns {function} Async function that emits and waits
 * 
 * Example:
 *   const fetchWorkspace = useSocketRequest("workspace:fetch", "workspace:fetched", 5000)
 *   const workspace = await fetchWorkspace({ workspaceId: "123" })
 */
export const useSocketRequest = (
  requestEventName,
  responseEventName,
  timeout = 10000
) => {
  return useCallback(
    (data) => {
      return new Promise((resolve, reject) => {
        const unsubscribe = eventManager.once(responseEventName, (response) => {
          clearTimeout(timer);
          resolve(response);
        });

        eventManager.emit(requestEventName, data);

        const timer = setTimeout(() => {
          unsubscribe();
          reject(new Error(`Request timeout: ${responseEventName}`));
        }, timeout);
      });
    },
    [requestEventName, responseEventName, timeout]
  );
};

/**
 * Hook to track socket connection status
 * 
 * @returns {object} { connected: boolean, socketId: string }
 * 
 * Example:
 *   const { connected, socketId } = useSocketStatus()
 *   {!connected && <p>Connecting...</p>}
 */
export const useSocketStatus = () => {
  const [status, setStatus] = useState({
    connected: false,
    socketId: null,
  });

  useEffect(() => {
    const handleConnect = () => {
      setStatus({
        connected: true,
        socketId: eventManager.socket?.id,
      });
    };

    const handleDisconnect = () => {
      setStatus({
        connected: false,
        socketId: null,
      });
    };

    eventManager.on(EVENTS.CONNECTION.CONNECTED, handleConnect);
    eventManager.on(EVENTS.CONNECTION.DISCONNECTED, handleDisconnect);

    return () => {
      eventManager.off(EVENTS.CONNECTION.CONNECTED, handleConnect);
      eventManager.off(EVENTS.CONNECTION.DISCONNECTED, handleDisconnect);
    };
  }, []);

  return status;
};

export default {
  useSocketListener,
  useSocketEvent,
  useSocketListeners,
  useWaitForSocketEvent,
  useDebounceSocketEvent,
  useThrottleSocketEvent,
  useEmitSocketEvent,
  useSocketRequest,
  useSocketStatus,
};
