import { test } from "node:test";
import assert from "node:assert/strict";
import { isPublicUrl, isPublicIp, urlGuard } from "../utils/urlGuard.js";
import { redactForLog } from "../utils/redact.js";
import { rateLimit } from "../app/middleware/rateLimit.middleware.js";

test("private / internal URLs are rejected", async () => {
    for (const u of ["http://127.0.0.1:8000", "localhost:27017", "http://169.254.169.254/latest", "http://[::1]/",
        "http://10.2.3.4", "http://192.168.1.10", "http://100.64.0.1", "ftp://shop.com", "http://a:b@shop.com",
        "http://db.internal/"]) {
        assert.equal(await isPublicUrl(u), false, u);
    }
    assert.equal(await isPublicUrl("http://93.184.216.34/"), true);
    assert.equal(isPublicIp("::ffff:127.0.0.1"), false);
    assert.equal(isPublicIp("8.8.8.8"), true);
});

const runMw = (mw, req) => new Promise((resolve) => {
    const res = {
        statusCode: 200, headers: {},
        status(c) { this.statusCode = c; return this; },
        set(k, v) { this.headers[k] = v; return this; },
        json(b) { resolve({ blocked: true, code: this.statusCode, body: b }); },
    };
    mw(req, res, () => resolve({ blocked: false }));
});

test("urlGuard blocks nested internal URLs in bodies, passes normal ones", async () => {
    const bad = await runMw(urlGuard, { method: "POST", body: { competitors: [{ url: "http://127.0.0.1:5000" }] } });
    assert.equal(bad.blocked, true);
    assert.equal(bad.code, 400);
    const ok = await runMw(urlGuard, { method: "POST", body: { name: "x", email: "a@b.com", selectedPages: ["http://93.184.216.34/p"] } });
    assert.equal(ok.blocked, false);
    const get = await runMw(urlGuard, { method: "GET", body: { url: "http://127.0.0.1" } });
    assert.equal(get.blocked, false);
});

test("redactForLog masks secrets and truncates big strings", () => {
    const out = redactForLog({ email: "a@b.com", password: "hunter2", nested: { refreshToken: "t", apiKey: "k" }, img: "x".repeat(5000) });
    assert.equal(out.password, "[REDACTED]");
    assert.equal(out.nested.refreshToken, "[REDACTED]");
    assert.equal(out.nested.apiKey, "[REDACTED]");
    assert.ok(out.img.length < 300);
    assert.equal(out.email, "a@b.com");
});

test("rateLimit returns 429 after max requests per user", async () => {
    const mw = rateLimit({ name: `t${Date.now()}`, max: 2, windowMs: 60_000 });
    const req = { user: { id: "u1" }, ip: "1.1.1.1" };
    assert.equal((await runMw(mw, req)).blocked, false);
    assert.equal((await runMw(mw, req)).blocked, false);
    const third = await runMw(mw, req);
    assert.equal(third.blocked, true);
    assert.equal(third.code, 429);
    assert.equal((await runMw(mw, { user: { id: "u2" } })).blocked, false); // separate bucket
});
