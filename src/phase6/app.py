from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from phase6.paths import repo_root, resolve_phase2_index_dir

try:
    from dotenv import load_dotenv

    load_dotenv(repo_root() / ".env", override=True)
except ImportError:
    pass

from phase3.engine import FaqRagEngine

logger = logging.getLogger("phase6.api")

# §9.2 — do not log full user queries; avoid obvious PII-like patterns in log lines.
_PII_LOG_SCRUB = re.compile(
    r"\b([A-Z]{5}[0-9]{4}[A-Z]|\d{4}\s?\d{4}\s?\d{4})\b",
    re.IGNORECASE,
)


def _scrub_for_log(text: str, max_len: int = 24) -> str:
    t = _PII_LOG_SCRUB.sub("[redacted]", (text or "").replace("\n", " ").strip())
    if len(t) > max_len:
        return t[: max_len - 3] + "..."
    return t or "(empty)"


def _load_phase6_defaults(repo: Path) -> dict[str, Any]:
    p = repo / "config" / "phase6" / "defaults.json"
    if not p.is_file():
        return {"host": "127.0.0.1", "port": 8765, "cors_origins": [], "max_queries_per_ip_per_minute": 60}
    with p.open(encoding="utf-8") as f:
        return json.load(f)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    scheme_id: str | None = Field(default=None, max_length=256)


class _RateLimiter:
    """Simple per-IP sliding window (E6.7 baseline)."""

    def __init__(self, max_per_minute: int) -> None:
        self._max = max(1, max_per_minute)
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        window = 60.0
        bucket = self._hits[client_ip]
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= self._max:
            raise HTTPException(status_code=429, detail="Rate limit exceeded; retry later.")
        bucket.append(now)


def create_app() -> FastAPI:
    repo = repo_root()
    defaults = _load_phase6_defaults(repo)
    index_dir = resolve_phase2_index_dir(repo)
    engine = FaqRagEngine(repo, index_dir)
    limiter = _RateLimiter(int(defaults.get("max_queries_per_ip_per_minute", 60)))

    manifest: dict[str, Any] = {}
    mf = index_dir / "manifest.json"
    if mf.is_file():
        with mf.open(encoding="utf-8") as f:
            manifest = json.load(f)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine
        app.state.repo_root = repo
        app.state.index_dir = index_dir
        app.state.manifest = manifest
        app.state.rate_limiter = limiter
        logger.info(
            "startup index_dir=%s chunk_count=%s",
            index_dir.name,
            manifest.get("chunk_count"),
        )
        yield

    app = FastAPI(
        title="Mutual Fund FAQ Assistant (pilot)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Browsers on Vercel hit Railway directly (cross-origin). Wildcard CORS is safe here: no cookies /
    # credentials; secrets stay on the server. A strict allow-list breaks preview URLs (*.vercel.app)
    # unless every origin is configured.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "index": {
                "dir": app.state.index_dir.name,
                "built_at_utc": manifest.get("built_at_utc"),
                "chunk_count": manifest.get("chunk_count"),
                "embedding_model": manifest.get("embedding_model"),
                "chunk_fingerprint_sha256": manifest.get("chunk_fingerprint_sha256"),
            },
        }

    @app.get("/ui/health")
    def ui_health_redirect() -> RedirectResponse:
        """`/ui/` serves static assets only; API health is at `/health`."""
        return RedirectResponse(url="/health", status_code=307)

    @app.get("/version")
    def version() -> dict[str, str]:
        return {"api": "1.0.0", "phase": "phase6-pilot"}

    @app.get("/meta/schemes")
    def meta_schemes() -> dict[str, Any]:
        p = repo / "config" / "phase0" / "schemes.json"
        if not p.is_file():
            raise HTTPException(status_code=404, detail="config/phase0/schemes.json not found")
        with p.open(encoding="utf-8") as f:
            return json.load(f)

    @app.get("/meta/disclaimer")
    def meta_disclaimer() -> dict[str, str]:
        p = repo / "config" / "phase0" / "refusal_and_education.json"
        text = "Facts-only. No investment advice."
        if p.is_file():
            with p.open(encoding="utf-8") as f:
                d = json.load(f)
            text = str(d.get("ui_disclaimer_snippet") or text)
        return {"text": text}

    @app.post("/query")
    async def query(req: QueryRequest, request: Request) -> dict[str, Any]:
        client = request.client.host if request.client else "unknown"
        app.state.rate_limiter.check(client)

        t0 = time.perf_counter()
        try:
            out = await asyncio.to_thread(
                app.state.engine.answer,
                req.query.strip(),
                req.scheme_id,
            )
        except Exception:
            logger.exception("query_engine_error query_len=%d scheme_id=%s", len(req.query), req.scheme_id)
            raise HTTPException(status_code=500, detail="Internal error during query.") from None

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        payload = out.to_dict()

        # E6.1 — avoid HTTP 200 with empty answer when not refusal / not clarification.
        if not out.refusal and not out.needs_scheme_clarification:
            if not (payload.get("answer") or "").strip():
                logger.error("invalid_empty_answer query_prefix=%s", _scrub_for_log(req.query, 48))
                raise HTTPException(status_code=500, detail="Invalid engine response (empty answer).")

        top_scores = (out.retrieval_scores or [])[:5]
        logger.info(
            "query_complete refusal=%s clarify=%s scheme_id=%s query_len=%d latency_ms=%.1f top_scores=%s query_prefix=%s",
            out.refusal,
            out.needs_scheme_clarification,
            out.scheme_id,
            len(req.query),
            elapsed_ms,
            top_scores,
            _scrub_for_log(req.query, 32),
        )
        return payload

    public_dir = (repo / "src" / "phase5" / "public").resolve()
    if (public_dir / "index.html").is_file():

        @app.get("/")
        def index_redirect() -> RedirectResponse:
            return RedirectResponse(url="/ui/", status_code=302)

        app.mount(
            "/ui",
            StaticFiles(directory=str(public_dir), html=True),
            name="phase5_ui",
        )
    else:
        logger.warning("Phase 5 UI missing: %s", public_dir)

    return app


# Uvicorn entry: ``uvicorn phase6.app:app`` with ``PYTHONPATH=src``
app = create_app()
