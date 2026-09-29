from __future__ import annotations

import json
from typing import Any, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.merger import merge_page_jsons

app = FastAPI(title="Competitor Intelligence JSON Merger", version="1.1.0")

# API-key auth + rate limiting (see api_security.py; env: COMPINTEL_API_KEY,
# RATE_LIMIT_PER_MINUTE, HEAVY_RATE_LIMIT_PER_MINUTE). Installed BEFORE CORS
# so 401/429 responses also carry CORS headers.
from api_security import install_security
install_security(app, service_name="merger-api")

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


class MergeJsonRequest(BaseModel):
    """
    Request body for merging page JSON objects directly.

    Example:
    {
      "pages": [
        { "url": "https://example.com", "pageType": "homepage", ... },
        { "url": "https://example.com/products", "pageType": "collection", ... }
      ]
    }
    """

    pages: List[dict[str, Any]] = Field(..., min_length=1)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/merge")
def merge_json_body(payload: MergeJsonRequest):
    """
    Preferred SaaS endpoint.
    Accepts JSON directly in the request body and returns merged JSON directly.
    No JSON files are uploaded or saved.
    """

    page_jsons = payload.pages

    if not page_jsons:
        raise HTTPException(status_code=400, detail="Send at least one page JSON object in pages[].")

    for index, page in enumerate(page_jsons):
        if not isinstance(page, dict):
            raise HTTPException(
                status_code=400,
                detail=f"pages[{index}] must be a JSON object.",
            )

    snapshot = merge_page_jsons(page_jsons)
    return JSONResponse(snapshot)


@app.post("/merge-files")
async def merge_uploaded_jsons(files: List[UploadFile] = File(...)):
    """
    Optional legacy/testing endpoint.
    Accepts uploaded .json files and returns merged JSON directly.
    """

    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one JSON file.")

    page_jsons = []
    errors = []

    for file in files:
        try:
            raw = await file.read()
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                errors.append(f"{file.filename}: root JSON must be an object")
                continue
            page_jsons.append(data)
        except Exception as exc:
            errors.append(f"{file.filename}: {exc}")

    if not page_jsons:
        raise HTTPException(
            status_code=400,
            detail={"message": "No valid JSON files found.", "errors": errors},
        )

    snapshot = merge_page_jsons(page_jsons)

    if errors:
        snapshot.setdefault("quality", {}).setdefault("warnings", []).extend(errors)

    return JSONResponse(snapshot)
