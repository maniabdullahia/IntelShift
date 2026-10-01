"""API-key authentication + rate limiting for CompIntel APIs.

Zero external dependencies. Controlled entirely by environment variables:

    COMPINTEL_API_KEY            shared secret. If unset, auth is DISABLED
                                 (dev mode) and a warning is printed.
    COMPINTEL_API_KEYS           comma-separated list of additional accepted
                                 keys. Each key gets its OWN rate-limit bucket,
                                 so one noisy client cannot starve the others.
    COMPINTEL_SERVICE_KEYS       comma-separated keys that skip rate limiting
                                 entirely. Use for your own trusted backend,
                                 which fans out many analyze calls per workspace
                                 and must not be throttled as if it were a
                                 single end user.

    RATE_LIMIT_PER_MINUTE        default 60  - normal endpoints
    HEAVY_RATE_LIMIT_PER_MINUTE  default 30  - expensive endpoints (analysis,
                                 full runs, OpenAI insight generation)

    TRUST_PROXY_HEADERS          "1" to read the client IP from
                                 X-Forwarded-For / X-Real-IP. Only enable this
                                 behind a proxy you control - the header is
                                 trivially spoofable otherwise.

Clients authenticate with the header:   X-API-Key: <key>
(or ?api_key=<key> query param for quick manual tests).

Rate limits are keyed on the API key when authentication is enabled, and fall
back to the client IP only in dev mode. This matters: a server-to-server caller
(your Node backend) presents one IP for every end user, so IP-keyed limits
would collapse the whole application into a single bucket.

Usage in an API file - call BEFORE adding CORSMiddleware, so CORS headers are
also applied to 401/429 responses:

    from api_security import install_security
    app = FastAPI(...)
    install_security(app, service_name="unified-api")
    app.add_middleware(CORSMiddleware, ...)
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Set, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}

HEAVY_PATH_PREFIXES = (
    "/api/v1/analyze",          # unified: analyze-page / analyze-pages
    "/api/v1/full-run",         # also covers /api/v1/full-run-multi
    "/api/v1/generate-insights",
    "/analyze",                 # standalone analyzer API
)

# Buckets are pruned once the dict exceeds this many entries, so a long-running
# process cannot accumulate one deque per distinct caller forever.
_MAX_TRACKED_BUCKETS = 10_000


def _split_env_list(name: str) -> Set[str]:
    raw = os.getenv(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _fingerprint(value: str) -> str:
    """Short, stable, non-reversible bucket id for a key.

    The raw secret never becomes a dict key, so it cannot leak through a
    debugger, a heap dump, or an accidental log of the buckets mapping.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def install_security(app, service_name: str = "api") -> None:
    primary_key = os.getenv("COMPINTEL_API_KEY", "").strip()

    valid_keys: Set[str] = _split_env_list("COMPINTEL_API_KEYS")
    if primary_key:
        valid_keys.add(primary_key)

    service_keys: Set[str] = _split_env_list("COMPINTEL_SERVICE_KEYS")
    # A service key is also a valid credential - no need to list it twice.
    valid_keys |= service_keys

    rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    heavy_limit = int(os.getenv("HEAVY_RATE_LIMIT_PER_MINUTE", "30"))
    trust_proxy = os.getenv("TRUST_PROXY_HEADERS", "").strip().lower() in {"1", "true", "yes"}

    auth_enabled = bool(valid_keys)

    if not auth_enabled:
        print(f"[{service_name}] WARNING: COMPINTEL_API_KEY is not set - "
              "API authentication is DISABLED (dev mode). "
              "Set it before exposing this API publicly.")
        print(f"[{service_name}] NOTE: rate limits will fall back to per-IP "
              "keying. If a backend proxies calls on behalf of many users they "
              "will all share one bucket.")

    if service_keys:
        print(f"[{service_name}] {len(service_keys)} service key(s) loaded - "
              "these bypass rate limiting.")

    window = 60.0
    buckets: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
    lock = threading.Lock()

    def _client_ip(request: Request) -> str:
        if trust_proxy:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                # Left-most entry is the original client.
                return forwarded.split(",")[0].strip()
            real_ip = request.headers.get("x-real-ip", "").strip()
            if real_ip:
                return real_ip
        return request.client.host if request.client else "unknown"

    def _prune_locked(now: float) -> None:
        """Drop buckets whose entire window has expired. Caller holds the lock."""
        if len(buckets) <= _MAX_TRACKED_BUCKETS:
            return
        stale = [key for key, q in buckets.items() if not q or now - q[-1] > window]
        for key in stale:
            del buckets[key]

    @app.middleware("http")
    async def _security_middleware(request: Request, call_next):
        path = request.url.path

        # CORS preflight and public paths always pass.
        if request.method == "OPTIONS" or path in EXEMPT_PATHS:
            return await call_next(request)

        provided = (
            request.headers.get("x-api-key")
            or request.query_params.get("api_key")
            or ""
        ).strip()

        # --- Authentication -------------------------------------------------
        if auth_enabled and provided not in valid_keys:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "error": "Invalid or missing API key. Send it in the X-API-Key header.",
                },
            )

        # --- Trusted server-to-server callers skip the limiter ---------------
        if provided and provided in service_keys:
            return await call_next(request)

        # Dev mode (no keys configured): the local Node backend calls from
        # loopback and fans out many analyze calls per workspace — never throttle
        # it, or a normal local run starts failing with 429s.
        if not auth_enabled and _client_ip(request) in {"127.0.0.1", "::1", "localhost"}:
            return await call_next(request)

        # --- Rate limiting (sliding 60s window) ------------------------------
        # Key on the credential when we have one; fall back to IP in dev mode.
        identity = f"key:{_fingerprint(provided)}" if provided else f"ip:{_client_ip(request)}"

        is_heavy = any(path.startswith(p) for p in HEAVY_PATH_PREFIXES)
        limit = heavy_limit if is_heavy else rate_limit
        scope = "heavy" if is_heavy else "standard"
        bucket_key = (identity, scope)

        now = time.time()
        with lock:
            q = buckets[bucket_key]
            while q and now - q[0] > window:
                q.popleft()

            if len(q) >= limit:
                retry_after = max(1, int(window - (now - q[0])) + 1)
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": f"Rate limit exceeded ({limit} requests/minute for "
                                 f"{scope} endpoints). Retry in {retry_after}s.",
                        "scope": scope,
                        "limit": limit,
                        "retryAfterSeconds": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(now + retry_after)),
                    },
                )

            q.append(now)
            remaining = limit - len(q)
            reset_at = int(q[0] + window)
            _prune_locked(now)

        response = await call_next(request)

        # Let well-behaved clients pace themselves instead of discovering the
        # limit by being rejected mid-run.
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(reset_at)

        return response
