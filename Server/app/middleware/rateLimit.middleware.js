// In-memory sliding-window rate limiter (no extra dependency).
//
// Keyed by the authenticated user when there is one, else by client IP. One API
// process today, so in-memory is enough; if the API is ever scaled to several
// processes, move the buckets to Redis.
//
// Behind nginx, set TRUST_PROXY=1 (index.js) so req.ip is the real client.

const buckets = new Map(); // key -> number[] (timestamps, ms)
const MAX_BUCKETS = 20000;

const prune = (now, windowMs) => {
    if (buckets.size <= MAX_BUCKETS) return;
    for (const [k, q] of buckets) {
        if (!q.length || now - q[q.length - 1] > windowMs) buckets.delete(k);
    }
};

/**
 * @param {object} opts
 * @param {string} opts.name     bucket namespace (so limits don't share counters)
 * @param {number} opts.max      requests allowed per window
 * @param {number} [opts.windowMs=60000]
 */
export const rateLimit = ({ name, max, windowMs = 60_000 }) => (req, res, next) => {
    if (process.env.DISABLE_RATE_LIMIT === "1") return next();
    const who = req.user?.id || req.user?.userId || req.user?._id || req.ip || "unknown";
    const key = `${name}:${who}`;
    const now = Date.now();
    const q = (buckets.get(key) || []).filter((t) => now - t < windowMs);
    if (q.length >= max) {
        const retryAfter = Math.max(1, Math.ceil((windowMs - (now - q[0])) / 1000));
        res.set("Retry-After", String(retryAfter));
        return res.status(429).json({
            message: `Too many requests. Please wait ${retryAfter}s and try again.`,
            code: "RATE_LIMITED",
            retryAfterSeconds: retryAfter,
        });
    }
    q.push(now);
    buckets.set(key, q);
    prune(now, windowMs);
    next();
};

export default rateLimit;
