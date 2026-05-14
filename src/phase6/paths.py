from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Repository root (parent of ``src/``)."""
    return Path(__file__).resolve().parents[2]


def latest_phase2_index_dir(repo: Path) -> Path | None:
    base = repo / "data" / "phase2" / "index"
    if not base.is_dir():
        return None
    dirs = [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").is_file()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def resolve_phase2_index_dir(repo: Path) -> Path:
    """
    Phase 2 bundle directory containing ``manifest.json``.

    Override with env ``PHASE6_INDEX_DIR`` (absolute or repo-relative path).
    """
    raw = (os.environ.get("PHASE6_INDEX_DIR") or "").strip()
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (repo / p).resolve()
        if not p.is_dir() or not (p / "manifest.json").is_file():
            raise FileNotFoundError(f"PHASE6_INDEX_DIR is not a valid index bundle: {p}")
        return p
    found = latest_phase2_index_dir(repo)
    if found is None:
        raise FileNotFoundError(
            "No Phase 2 index under data/phase2/index/. Build with scripts/run_phase2_build_index.py "
            "or set PHASE6_INDEX_DIR.",
        )
    return found
