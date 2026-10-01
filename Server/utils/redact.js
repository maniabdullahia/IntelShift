// Redaction for log output. Anything that can identify or authenticate a user
// is masked; long strings (base64 images, HTML snapshots) are truncated.

const SENSITIVE_KEY_RE = /pass(word)?|secret|token|authorization|cookie|api[-_]?key|otp|code|card|cvv|signature/i;
const MAX_STRING = 200;
const MAX_DEPTH = 4;

export const redactForLog = (value, depth = 0) => {
    if (value == null) return value;
    if (typeof value === "string") {
        return value.length > MAX_STRING ? `${value.slice(0, MAX_STRING)}…(${value.length} chars)` : value;
    }
    if (typeof value !== "object") return value;
    if (depth >= MAX_DEPTH) return Array.isArray(value) ? `[array(${value.length})]` : "[object]";
    if (Array.isArray(value)) {
        const head = value.slice(0, 10).map((v) => redactForLog(v, depth + 1));
        return value.length > 10 ? [...head, `…(+${value.length - 10} more)`] : head;
    }
    const out = {};
    for (const [k, v] of Object.entries(value)) {
        out[k] = SENSITIVE_KEY_RE.test(k) ? "[REDACTED]" : redactForLog(v, depth + 1);
    }
    return out;
};

export default redactForLog;
