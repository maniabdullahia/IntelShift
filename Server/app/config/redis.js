// redis.js

import IORedis from "ioredis";

// Shared BullMQ connection. maxRetriesPerRequest MUST be null for BullMQ.
const connection = new IORedis({
  host: "127.0.0.1",
  port: 6379,

  maxRetriesPerRequest: null,
  // Keep trying to reconnect instead of giving up (capped backoff).
  retryStrategy: (times) => Math.min(times * 200, 5000),
});

// Without an 'error' listener, ioredis re-throws connection errors as UNHANDLED,
// which crashes the whole Node process when Redis is briefly down. Log + keep the
// process alive so it recovers when Redis comes back.
connection.on("error", (err) => {
  console.error("[redis] connection error:", err?.code || err?.message || err);
});

/**
 * Create a resilient standalone client for pub/sub (NOT BullMQ queues). Same
 * reconnect behaviour + an error handler so a Redis outage degrades (no realtime
 * socket updates) instead of hard-crashing the server.
 */
export const createRedis = (label = "redis") => {
  const client = new IORedis({
    host: "127.0.0.1",
    port: 6379,
    maxRetriesPerRequest: null,
    retryStrategy: (times) => Math.min(times * 200, 5000),
  });
  client.on("error", (err) => {
    console.error(`[${label}] connection error:`, err?.code || err?.message || err);
  });
  return client;
};

export default connection;
