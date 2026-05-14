"""Pilot Groww URL allowlist for P1-S5 headless augmentation (architecture §4.1 P1-S5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ingestion.phase1.s1_manifest_binding.manifest_binding import canonical_url


def load_citation_allowlist_urls(repo_root: Path) -> set[str]:
    path = Path(repo_root) / "config" / "phase0" / "citation_allowlist.json"
    with path.open(encoding="utf-8") as f:
        doc: dict[str, Any] = json.load(f)
    return {canonical_url(u) for u in doc.get("urls", []) if isinstance(u, str)}


def is_allowlisted_groww_url(url: str, allow: set[str]) -> bool:
    if not (url or "").strip():
        return False
    return canonical_url(url) in allow
