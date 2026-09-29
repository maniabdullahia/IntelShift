"""API-key authentication + rate limiting for CompIntel APIs.

Zero external dependencies. Controlled entirely by environment variables:

    COMPINTEL_API_KEY            shared secret. If unset, auth is DISABLED
                                 (dev mode) and a warning is printed.
    RATE_LIMIT_PER_MINUTE        default 60  - normal endpoints, per client IP
    HEAVY_RATE_LIMIT_PER_MINUTE  default 10  - expensive endpoints (analysis,
                                 full runs, OpenAI insight generation)

Clients authenticate with the header:   X-API-Key: <key>
(or ?api_key=<key> query param for quick manual tests).

Usage in an API file - call BEFORE adding CORSMiddleware, so CORS headers are
also applied to 401/429 responses:

    from api_security import install_security
    app = FastAPI(...)
    install_security(app, service_name="unified-api")
    app.add_middleware(CORSMiddleware, ...)
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}

HEAVY_PATH_PREFIXES = (
    "/api/v1/analyze",          # unified: analyze-page / analyze-pages
    "/api/v1/full-run",
    "/api/v1/generate-insights",
    "/analyze",                 # standalone analyzer API
)


def install_security(app, service_name: str = "api") -> None:
    api_key = os.getenv("COMPINTEL_API_KEY", "").strip()
    rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    heavy_limit = int(os.getenv("HEAVY_RATE_LIMIT_PER_MINUTE", "10"))

    if not api_key:
        print(f"[{service_name}] WARNING: COMPINTEL_API_KEY is not set - "
              "API authentication is DISABLED (dev mode). "
              "Set it before exposing this API publicly.")

    window = 60.0
    buckets: dict = defaultdict(deque)
    lock = threading.Lock()

    @app.middleware("http")
    async def _security_middleware(request: Request, call_next):
        path = request.url.path

        # CORS preflight and public paths always pass.
        if request.method == "OPTIONS" or path in EXEMPT_PATHS:
            return await call_next(request)

        # --- Authentication -------------------------------------------------
        if api_key:
            provided = (
                request.headers.get("x-api-key")
                or request.query_params.get("api_key")
                or ""
            )
            if provided != api_key:
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "error": "Invalid or missing API key. Send it in the X-API-Key header.",
                    },
                )

        # --- Rate limiting (per client IP, sliding 60s window) ---------------
        client = request.client.host if request.client else "unknown"
        is_heavy = any(path.startswith(p) for p in HEAVY_PATH_PREFIXES)
        limit = heavy_limit if is_heavy else rate_limit
        bucket_key = (client, "heavy" if is_heavy else "standard")

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
                                 f"{'heavy' if is_heavy else 'standard'} endpoints). "
                                 f"Retry in {retry_after}s.",
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

        return await call_next(request)
