#!/usr/bin/env python3
"""
Patch tracked pilot index chunks with live Groww NAV (18 May 2026).

Static P1 HTTP crawl often embeds a stale hero NAV; this updates hero lines and
adds an about-blurb sentence so Phase 3 picks the newest as-of date.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "data" / "phase2" / "index" / "groww-hdfc-pilot-v1__422a8bf8c13836c8"
CHUNKS = INDEX_DIR / "chunks.jsonl"
META = INDEX_DIR / "chunk_metadata.json"

# (stale hero substring, fresh hero substring, prose tail for chunking)
_PATCHES: tuple[tuple[str, str, str], ...] = (
    (
        "nav : 15 may'26 ₹1, 436. 33",
        "nav : 18 may'26 ₹1, 430. 78",
        "latest nav as of 18 may 2026 is ₹1, 430. 78",
    ),
    (
        "nav : 15 may'26 ₹2, 128. 27",
        "nav : 18 may'26 ₹2, 123. 92",
        "latest nav as of 18 may 2026 is ₹2, 123. 92",
    ),
    (
        "nav : 15 may'26 ₹253. 25",
        "nav : 18 may'26 ₹251. 30",
        "latest nav as of 18 may 2026 is ₹251. 30",
    ),
    (
        "nav : 15 may'26 ₹1, 175. 45",
        "nav : 18 may'26 ₹1, 174. 37",
        "latest nav as of 18 may 2026 is ₹1, 174. 37",
    ),
    (
        "nav : 15 may'26 ₹218. 42",
        "nav : 18 may'26 ₹217. 98",
        "latest nav as of 18 may 2026 is ₹217. 98",
    ),
)


def _patch_text(text: str) -> tuple[str, int, int]:
    hero_replacements = 0
    prose_added = 0
    for stale, fresh, prose in _PATCHES:
        if stale in text:
            text = text.replace(stale, fresh)
            hero_replacements += 1
        if fresh in text and prose not in text.lower():
            text = f"{text} {prose}."
            prose_added += 1
    return text, hero_replacements, prose_added


def main() -> int:
    if not CHUNKS.is_file() or not META.is_file():
        print(f"Missing index bundle under {INDEX_DIR}", file=sys.stderr)
        return 1

    hero_total = 0
    prose_total = 0

    lines = CHUNKS.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        row["text"], h, p = _patch_text(str(row.get("text") or ""))
        hero_total += h
        prose_total += p
        out.append(json.dumps(row, ensure_ascii=False))
    CHUNKS.write_text("\n".join(out) + "\n", encoding="utf-8")

    with META.open(encoding="utf-8") as f:
        meta = json.load(f)
    for row in meta:
        row["text"], h, p = _patch_text(str(row.get("text") or ""))
        hero_total += h
        prose_total += p
    with META.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Patched {INDEX_DIR.name}: hero_replacements={hero_total} prose_added={prose_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
