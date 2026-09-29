/**
 * Socket Event Manager
 * ====================
 * Manages all socket event listeners and handlers
 * Provides a clean API for registering and unregistering handlers
 * 
 * Usage:
 *   eventManager.on(EVENTS.WORKSPACE.UPDATED, (data) => {...})
 *   eventManager.off(EVENTS.WORKSPACE.UPDATED, handlerFunction)
 */

import socket from "../services/socket";

class EventManager {
  constructor() {
    this.handlers = new Map(); // Map<eventName, Set<handler>>
    this.isInitialized = false;
  }

  /**
   * Register an event handler
   * @param {string} eventName - Event name from EVENTS constant
   * @param {function} callback - Handler function
   * @returns {function} Unsubscribe function
   */
  on(eventName, callback) {
    if (!this.handlers.has(eventName)) {
      this.handlers.set(eventName, new Set());

      // Listen on socket for this event
      socket.on(eventName, (data) => {
        console.log(`[Socket Event] Received '${eventName}':`, data);
        const handlers = this.handlers.get(eventName);
        if (handlers && handlers.size > 0) {
          console.log(`   ↳ ${handlers.size} handler(s) executing...`);
          handlers.forEach((handler) => {
            try {
              handler(data);
            } catch (error) {
              console.error(
                `❌ Error in handler for event '${eventName}':`,
                error
              );
            }
          });
        } else {
          console.warn(`   ⚠️  No handlers registered for '${eventName}'`);
        }
      });
    }

    // Add handler to the set
    const handlers = this.handlers.get(eventName);
    handlers.add(callback);

    // Return unsubscribe function
    return () => this.off(eventName, callback);
  }

  /**
   * Unregister an event handler
   * @param {string} eventName - Event name from EVENTS constant
   * @param {function} callback - Handler function to remove
   */
  off(eventName, callback) {
    const handlers = this.handlers.get(eventName);
    if (handlers) {
      handlers.delete(callback);
      if (handlers.size === 0) {
        this.handlers.delete(eventName);
        socket.off(eventName);
      }
    }
  }

  /**
   * Register a handler that only fires once
   * @param {string} eventName - Event name from EVENTS constant
   * @param {function} callback - Handler function
   */
  once(eventName, callback) {
    const unsubscribe = this.on(eventName, (...args) => {
      callback(...args);
      unsubscribe();
    });
    return unsubscribe;
  }

  /**
   * Emit an event to the server
   * @param {string} eventName - Event name
   * @param {*} data - Data to send
   */
  emit(eventName, data = {}) {
    socket.emit(eventName, data);
  }

  /**
   * Clear all registered handlers
   */
  clear() {
    this.handlers.forEach((handlers, eventName) => {
      socket.off(eventName);
    });
    this.handlers.clear();
  }

  /**
   * Get all registered event names
   * @returns {string[]} Array of event names
   */
  getRegisteredEvents() {
    return Array.from(this.handlers.keys());
  }

  /**
   * Check if an event has listeners
   * @param {string} eventName - Event name
   * @returns {boolean}
   */
  hasListeners(eventName) {
    const handlers = this.handlers.get(eventName);
    return handlers && handlers.size > 0;
  }

  /**
   * Get number of listeners for an event
   * @param {string} eventName - Event name
   * @returns {number}
   */
  listenerCount(eventName) {
    const handlers = this.handlers.get(eventName);
    return handlers ? handlers.size : 0;
  }
}

export default new EventManager();
