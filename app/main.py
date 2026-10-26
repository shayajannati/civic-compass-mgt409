"""Civic Compass web app (FastAPI + Jinja2).

Run:  uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, directory, pipeline, safety, zipmap
from .llm import BudgetError, ContentFilterError, ModelError, SetupError

app = FastAPI(title="Civic Compass", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=config.ROOT / "app" / "static"), name="static")
templates = Jinja2Templates(directory=config.ROOT / "app" / "templates")

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method == "POST":
        size = int(request.headers.get("content-length") or 0)
        if size > config.MAX_BODY_BYTES:
            return JSONResponse({"error": "Request too large."}, status_code=413)
        ip = request.client.host if request.client else "?"
        q, now = _hits[ip], time.time()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= config.RATE_LIMIT_PER_MINUTE:
            return JSONResponse({"error": "Too many requests. Please wait a minute."}, status_code=429)
        q.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _env_status() -> dict:
    where = None
    if config.ENV_FILE:
        where = "repository folder" if config.ENV_FILE.parent == config.ROOT else "parent folder"
    return {"key_configured": bool(config.api_key()), "env_file": where, "model": config.MODEL_NAME}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html",
                                      {"categories": config.CATEGORIES, "env": _env_status()})


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request):
    agencies = directory.query_all_agencies()
    return templates.TemplateResponse(request, "sources.html",
                                      {"sources": directory.sources(), "agencies": agencies})


@app.get("/purpose", response_class=HTMLResponse)
def purpose_page(request: Request):
    return templates.TemplateResponse(request, "purpose.html", {})


@app.get("/api/zip/{zip5}")
def api_zip(zip5: str):
    """Display-only map data for a ZIP area (no model call, no address)."""
    if not safety.ZIP_RE.match(zip5):
        return JSONResponse({"error": "Please enter a valid 5-digit ZIP code."}, status_code=400)
    return zipmap.zip_map(zip5)


@app.get("/api/health")
def health():
    return {"status": "ok", **_env_status(), "sources": len(directory.sources())}


async def _json(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise pipeline.InputError("Malformed request.")
    if not isinstance(body, dict):
        raise pipeline.InputError("Malformed request.")
    return body


def _error(exc: Exception) -> JSONResponse:
    if isinstance(exc, pipeline.InputError):
        return JSONResponse({"error": str(exc)}, status_code=400)
    if isinstance(exc, SetupError):
        return JSONResponse({"error": str(exc), "setup": True}, status_code=503)
    if isinstance(exc, BudgetError):
        return JSONResponse({"error": str(exc)}, status_code=429)
    if isinstance(exc, ContentFilterError):
        return JSONResponse({"error": str(exc)}, status_code=422)
    if isinstance(exc, ModelError):
        return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse({"error": "Something went wrong. Please try again."}, status_code=500)


@app.post("/api/route")
async def api_route(request: Request):
    try:
        return pipeline.route(await _json(request))
    except Exception as exc:  # noqa: BLE001 — mapped to safe user-facing messages
        return _error(exc)


@app.post("/api/letter")
async def api_letter(request: Request):
    try:
        return pipeline.draft_letter(await _json(request))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
