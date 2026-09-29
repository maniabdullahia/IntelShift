"""Change Detection API.

Run:
    uvicorn api:app --reload --port 8003

Endpoint:
    POST /diff-snapshots   { "previousSnapshot": {...}, "currentSnapshot": {...}, "settings": {...} }
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app.detector import detect_changes

app = FastAPI(title="Same-Site Change Detection", version="1.0.0")

# API-key auth + rate limiting (see api_security.py; env: COMPINTEL_API_KEY,
# RATE_LIMIT_PER_MINUTE, HEAVY_RATE_LIMIT_PER_MINUTE). Installed BEFORE CORS
# so 401/429 responses also carry CORS headers.
from api_security import install_security
install_security(app, service_name="change-detection-api")

# CORS: comma-separated origins via CORS_ORIGINS env var.
# Default covers local React dev (CRA :3000, Vite :5173).
# Set CORS_ORIGINS=https://yourapp.com in production, or "*" for open access
# (credentials are automatically disabled for "*").
import os as _os
_cors_origins = [
    o.strip() for o in _os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DiffSnapshotsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    previousSnapshot: Dict[str, Any]
    currentSnapshot: Dict[str, Any]
    settings: Optional[Dict[str, Any]] = Field(default=None)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "service": "change-detection", "version": "1.0.0"}


@app.post("/diff-snapshots")
def diff_snapshots(payload: DiffSnapshotsRequest) -> Dict[str, Any]:
    try:
        return detect_changes(payload.previousSnapshot, payload.currentSnapshot, payload.settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(exc)})
