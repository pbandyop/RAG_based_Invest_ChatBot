"""
P1-S3 — Raw artifact store.

Writes immutable body + sidecar metadata under data/phase1/raw/{run_id}/.
Never overwrites an existing artifact prefix (new run_id or new ordinal).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from ingestion.phase1.s2_http_fetch.fetcher import FetchResult, body_extension, content_sha256


class StoreError(Exception):
    """Invalid path or serialization error."""


def _slug_fragment(url: str, max_len: int = 48) -> str:
    tail = url.rstrip("/").split("/")[-1] or "root"
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", tail)[:max_len]
    return safe or "page"


def store_fetch_result(
    *,
    run_id: str,
    ordinal: int,
    plan_row: Mapping[str, Any],
    result: FetchResult,
    raw_root: Path,
) -> dict[str, Any]:
    """
    Persist fetch outcome under raw_root / run_id /.

    On success (ok and body): writes fetch_{ordinal:05d}_{slug}.<ext> + .meta.json
    On failure: writes fetch_{ordinal:05d}_{slug}.error.json only
    """
    run_dir = raw_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    slug = _slug_fragment(result.canonical_url or result.requested_url)
    base = f"fetch_{ordinal:05d}_{slug}"

    meta: dict[str, Any] = {
        "p1_subphase_store": "P1-S3",
        "run_id": run_id,
        "ordinal": ordinal,
        "requested_url": result.requested_url,
        "canonical_url": result.canonical_url,
        "final_url": result.final_url,
        "status_code": result.status_code,
        "fetched_at_utc": result.fetched_at_utc,
        "last_modified": result.last_modified,
        "etag": result.etag,
        "content_type": result.content_type,
        "truncated": result.truncated,
        "fetch_attempts": result.attempts,
        "fetcher_version": result.fetcher_version,
        "ok": result.ok,
        "error": result.error,
        "robots_allowed": result.robots_allowed,
        "robots_note": result.robots_note,
        "content_sha256": content_sha256(result.body),
        "document_type": plan_row.get("document_type"),
        "scheme_id": plan_row.get("scheme_id"),
        "scheme_display_name": plan_row.get("scheme_display_name"),
        "citable": plan_row.get("citable"),
    }

    written: list[str] = []

    if result.ok and result.body is not None:
        ext = body_extension(result.content_type)
        body_path = run_dir / f"{base}.body.{ext}"
        if body_path.exists():
            raise StoreError(f"refusing to overwrite existing artifact: {body_path}")
        body_path.write_bytes(result.body)
        written.append(str(body_path.name))
        meta["body_file"] = body_path.name
        meta["body_bytes"] = len(result.body)
    else:
        meta["body_file"] = None
        meta["body_bytes"] = len(result.body) if result.body else 0

    meta_path = run_dir / f"{base}.meta.json"
    if meta_path.exists():
        raise StoreError(f"refusing to overwrite existing meta: {meta_path}")
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")
    written.append(str(meta_path.name))

    return {
        "ordinal": ordinal,
        "base": base,
        "run_dir": str(run_dir),
        "files": written,
        "ok": result.ok,
    }


def fetch_result_to_jsonable(result: FetchResult) -> dict[str, Any]:
    """Serialize FetchResult without body bytes (for aggregate reports)."""
    d = asdict(result)
    d.pop("body", None)
    d["body_sha256"] = content_sha256(result.body)
    d["body_size"] = len(result.body) if result.body else 0
    return d
