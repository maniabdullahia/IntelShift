// SSRF guard for user-supplied URLs.
//
// Every store / competitor / page URL a user submits is later fetched by the
// crawler. Without this, "http://127.0.0.1:27017" or the cloud metadata address
// (169.254.169.254) would be fetched — and /debug-fetch or an analysis result
// would hand the response back. We resolve the host and reject loopback,
// private, link-local, CGNAT, multicast and reserved ranges, non-http(s)
// schemes and URLs with embedded credentials. The Python service repeats the
// check (python/website_analyzer_app/level1_detector/net_guard.py), including
// after redirects.
//
// ALLOW_PRIVATE_URLS=1 disables the guard (local testing against a dev store).

import dns from "dns/promises";
import net from "net";

const DNS_TTL_MS = 10 * 60 * 1000;
const cache = new Map(); // host -> { at, ok }

const BLOCKED_HOSTS = new Set(["localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"]);

const ipv4ToInt = (ip) => ip.split(".").reduce((acc, o) => (acc << 8) + Number(o), 0) >>> 0;
const inV4 = (ip, cidr) => {
    const [base, bits] = cidr.split("/");
    const mask = bits === "0" ? 0 : (~0 << (32 - Number(bits))) >>> 0;
    return (ipv4ToInt(ip) & mask) === (ipv4ToInt(base) & mask);
};
const V4_BLOCKED = [
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16",
    "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24", "192.168.0.0/16", "198.18.0.0/15",
    "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4",
];

export const isPublicIp = (ip) => {
    if (net.isIPv4(ip)) return !V4_BLOCKED.some((c) => inV4(ip, c));
    if (net.isIPv6(ip)) {
        const v = ip.toLowerCase();
        const mapped = v.match(/^::ffff:(\d+\.\d+\.\d+\.\d+)$/);
        if (mapped) return isPublicIp(mapped[1]);
        if (v === "::" || v === "::1") return false;
        if (/^(fc|fd)/.test(v)) return false; // unique local
        if (/^fe[89ab]/.test(v)) return false; // link local
        if (/^ff/.test(v)) return false; // multicast
        return true;
    }
    return false;
};

const hostIsPublic = async (host) => {
    const h = String(host || "").toLowerCase().replace(/\.$/, "").replace(/^\[|\]$/g, "");
    if (!h || BLOCKED_HOSTS.has(h) || h.endsWith(".localhost") || h.endsWith(".internal")) return false;
    if (net.isIP(h)) return isPublicIp(h);
    const hit = cache.get(h);
    if (hit && Date.now() - hit.at < DNS_TTL_MS) return hit.ok;
    let ok;
    try {
        const addrs = await dns.lookup(h, { all: true });
        ok = addrs.length > 0 && addrs.every((a) => isPublicIp(a.address));
    } catch {
        // NXDOMAIN / transient DNS failure: a name that doesn't resolve can't
        // reach an internal service, and the Python fetcher re-checks at fetch
        // time. Allow (and don't cache) so a DNS blip never blocks a real store.
        return true;
    }
    cache.set(h, { at: Date.now(), ok });
    return ok;
};

export const isPublicUrl = async (raw) => {
    if (process.env.ALLOW_PRIVATE_URLS === "1") return true;
    let u;
    try {
        const s = String(raw || "").trim();
        u = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(s) ? s : `https://${s}`);
    } catch {
        return true; // not a URL — format validation elsewhere decides
    }
    if (u.protocol !== "http:" && u.protocol !== "https:") return false;
    if (u.username || u.password) return false;
    return hostIsPublic(u.hostname);
};

// Body keys whose (possibly bare-domain) string value is a URL to check.
const URL_KEYS = new Set(["url", "websiteurl", "storeurl", "competitorurl", "workspaceurl", "homepageurl"]);
const MAX_URLS_CHECKED = 300;

const collectUrls = (value, key, out, depth = 0) => {
    if (out.size >= MAX_URLS_CHECKED || depth > 6 || value == null) return;
    if (typeof value === "string") {
        const s = value.trim();
        if (/^https?:\/\//i.test(s) || (key && URL_KEYS.has(key.toLowerCase()) && s && !/\s/.test(s))) out.add(s);
        return;
    }
    if (Array.isArray(value)) {
        for (const v of value) collectUrls(v, key, out, depth + 1);
        return;
    }
    if (typeof value === "object") {
        for (const [k, v] of Object.entries(value)) collectUrls(v, k, out, depth + 1);
    }
};

/** Express middleware: reject a mutating request carrying any non-public URL. */
export const urlGuard = async (req, res, next) => {
    if (!["POST", "PUT", "PATCH"].includes(req.method) || !req.body || typeof req.body !== "object") return next();
    try {
        const urls = new Set();
        collectUrls(req.body, null, urls);
        for (const u of urls) {
            if (!(await isPublicUrl(u))) {
                return res.status(400).json({ message: "That URL isn't a public website. Please enter your store's public address.", code: "UNSAFE_URL" });
            }
        }
    } catch (err) {
        console.warn("urlGuard check failed (allowing):", err?.message || err);
    }
    next();
};

export default urlGuard;
