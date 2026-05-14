"""
P1-S1 — Manifest binding (Phase 1.1).

Loads Phase 0 manifest, filters included_in_crawl, validates pilot URL rules,
produces a deterministic run id and crawl plan JSON for downstream subphases.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


class BindingError(ValueError):
    """Invalid manifest or URL row for crawl binding."""


ALLOWED_HOST = "groww.in"


def canonical_url(url: str) -> str:
    """Strip fragment and trailing slash for stable identity (path/query preserved)."""
    p = urlparse(url.strip())
    if not p.scheme or not p.netloc:
        return url.strip()
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return p._replace(path=path, fragment="").geturl()


def validate_crawl_url(url: str, row_index: int) -> None:
    u = url.strip()
    if not u:
        raise BindingError(f"manifest.urls[{row_index}]: empty url")
    parsed = urlparse(u)
    if parsed.scheme != "https":
        raise BindingError(
            f"manifest.urls[{row_index}]: url must use https (got scheme={parsed.scheme!r})"
        )
    host = (parsed.hostname or "").lower()
    if host != ALLOWED_HOST:
        raise BindingError(
            f"manifest.urls[{row_index}]: hostname must be {ALLOWED_HOST!r} (got {host!r})"
        )


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise BindingError(f"Manifest not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, Mapping):
        raise BindingError("Manifest root must be a JSON object")
    if "urls" not in data or not isinstance(data["urls"], list):
        raise BindingError("Manifest must contain a 'urls' array")
    return dict(data)


def _row_must_have(row: Mapping[str, Any], key: str, idx: int) -> Any:
    if key not in row:
        raise BindingError(f"manifest.urls[{idx}]: missing key {key!r}")
    return row[key]


def build_crawl_plan(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """
    Filter urls with included_in_crawl=true, validate, stable order (priority asc, url asc).
    Returns a dict suitable for JSON serialization (crawl plan + run metadata).
    """
    urls_raw = manifest.get("urls")
    if not isinstance(urls_raw, list):
        raise BindingError("manifest.urls must be a list")

    manifest_id = str(manifest.get("manifest_id") or "unknown_manifest")
    manifest_version = str(manifest.get("version") or "0")

    eligible: list[tuple[int, str, dict[str, Any]]] = []
    for idx, row in enumerate(urls_raw):
        if not isinstance(row, Mapping):
            raise BindingError(f"manifest.urls[{idx}] must be an object")
        if row.get("included_in_crawl") is not True:
            continue
        url = str(_row_must_have(row, "url", idx))
        validate_crawl_url(url, idx)
        allowed = row.get("allowed_use")
        if not isinstance(allowed, list) or "ingest" not in allowed:
            raise BindingError(
                f"manifest.urls[{idx}]: included_in_crawl rows must list 'ingest' in allowed_use"
            )
        priority = row.get("priority")
        if not isinstance(priority, int):
            raise BindingError(f"manifest.urls[{idx}]: priority must be an integer")
        canon = canonical_url(url)
        item = {k: v for k, v in row.items()}
        item["url"] = url.strip()
        item["canonical_url"] = canon
        eligible.append((priority, canon, item))

    eligible.sort(key=lambda t: (t[0], t[1]))
    ordered_items = [t[2] for t in eligible]

    fingerprint_payload = {
        "manifest_id": manifest_id,
        "manifest_version": manifest_version,
        "canonical_urls": [t[1] for t in eligible],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    run_id = f"{manifest_id}__{fingerprint[:16]}"

    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "p1_subphase": "P1-S1",
        "run_id": run_id,
        "plan_fingerprint_sha256": fingerprint,
        "generated_at_utc": generated_at,
        "manifest_id": manifest_id,
        "manifest_version": manifest_version,
        "manifest_path_note": "bind from config/phase0/manifest.json at generation time",
        "url_count": len(ordered_items),
        "urls": ordered_items,
    }


def write_crawl_plan(plan: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = plan["run_id"]
    safe_name = "".join(c if c.isalnum() or c in "-._" else "_" for c in run_id)
    out_path = out_dir / f"crawl_plan__{safe_name}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path


def build_crawl_plan_from_path(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    return build_crawl_plan(manifest)


def load_crawl_plan(path: Path) -> dict[str, Any]:
    """Load a P1-S1 crawl plan JSON from disk."""
    if not path.is_file():
        raise BindingError(f"Crawl plan not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, Mapping):
        raise BindingError("Crawl plan root must be a JSON object")
    for key in ("run_id", "urls"):
        if key not in data:
            raise BindingError(f"Crawl plan missing {key!r}")
    if not isinstance(data["urls"], list):
        raise BindingError("Crawl plan urls must be a list")
    return dict(data)
