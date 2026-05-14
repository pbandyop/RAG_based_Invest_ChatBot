from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phase3.url_normalize import normalize_citation_url


@dataclass
class Phase0RuntimeConfig:
    citation_urls_normalized: set[str]
    scheme_id_to_citation: dict[str, str]
    refusal_config: dict[str, Any]


def load_phase0_runtime(repo_root: Path) -> Phase0RuntimeConfig:
    repo_root = Path(repo_root)
    allow_path = repo_root / "config" / "phase0" / "citation_allowlist.json"
    schemes_path = repo_root / "config" / "phase0" / "schemes.json"
    refusal_path = repo_root / "config" / "phase0" / "refusal_and_education.json"

    with allow_path.open(encoding="utf-8") as f:
        allow = json.load(f)
    with schemes_path.open(encoding="utf-8") as f:
        schemes_doc = json.load(f)
    with refusal_path.open(encoding="utf-8") as f:
        refusal = json.load(f)

    urls = {normalize_citation_url(u) for u in allow.get("urls", [])}
    sid_map: dict[str, str] = {}
    for row in schemes_doc.get("schemes", []):
        sid = str(row.get("scheme_id") or "")
        cu = normalize_citation_url(str(row.get("citation_url") or ""))
        if sid and cu:
            sid_map[sid] = cu

    return Phase0RuntimeConfig(
        citation_urls_normalized=urls,
        scheme_id_to_citation=sid_map,
        refusal_config=refusal,
    )
