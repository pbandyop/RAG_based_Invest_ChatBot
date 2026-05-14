#!/usr/bin/env python3
"""
Phase 3 golden checks (architecture §6.5): citation allowlist, footer on answers, refusal routing.

Usage:
  set PYTHONPATH=src
  python scripts/run_phase3_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phase3.engine import FaqRagEngine  # noqa: E402
from phase3.url_normalize import normalize_citation_url  # noqa: E402


def _latest_index_dir() -> Path | None:
    base = ROOT / "data" / "phase2" / "index"
    if not base.is_dir():
        return None
    dirs = [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").is_file()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def _load_allowlist() -> set[str]:
    p = ROOT / "config" / "phase0" / "citation_allowlist.json"
    with p.open(encoding="utf-8") as f:
        doc = json.load(f)
    return {normalize_citation_url(u) for u in doc.get("urls", [])}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        r = getattr(stream, "reconfigure", None)
        if callable(r):
            try:
                r(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass

    golden_path = ROOT / "config" / "phase3" / "golden_phase3.json"
    if not golden_path.is_file():
        print(f"Missing {golden_path}", file=sys.stderr)
        return 1

    idx = _latest_index_dir()
    if idx is None:
        print("No Phase 2 index under data/phase2/index/", file=sys.stderr)
        return 1

    with golden_path.open(encoding="utf-8") as f:
        g = json.load(f)

    allow = _load_allowlist()
    engine = FaqRagEngine(ROOT, idx)
    failed = 0

    for case in g.get("cases", []):
        cid = case.get("id", "?")
        q = str(case.get("query") or "")
        sid = case.get("scheme_id")
        expect = str(case.get("expect") or "answer")
        resp = engine.answer(q, scheme_id=sid if isinstance(sid, str) else None)

        if expect == "refusal":
            if not resp.refusal:
                print(f"FAIL {cid}: expected refusal, got answer (route={resp.generator_route})")
                failed += 1
            else:
                print(f"OK   {cid}: refusal ({resp.refusal_template_key})")
            continue

        if resp.refusal or resp.needs_scheme_clarification:
            print(f"FAIL {cid}: expected answer, got refusal={resp.refusal} clarify={resp.needs_scheme_clarification}")
            failed += 1
            continue

        cu = normalize_citation_url(str(resp.citation_url or ""))
        if cu not in allow:
            print(f"FAIL {cid}: citation not on allowlist: {resp.citation_url!r}")
            failed += 1
            continue

        if not resp.footer_line or "Last updated from sources:" not in (resp.footer_line or ""):
            print(f"FAIL {cid}: missing footer_line")
            failed += 1
            continue

        if not resp.last_updated:
            print(f"FAIL {cid}: missing last_updated")
            failed += 1
            continue

        host_need = case.get("citation_must_include_scheme_host")
        if host_need and host_need not in (resp.citation_url or ""):
            print(f"FAIL {cid}: citation host check {host_need!r}")
            failed += 1
            continue

        if not resp.evidence or not resp.evidence[0].get("source_url"):
            print(f"FAIL {cid}: evidence missing source_url (§6.1)")
            failed += 1
            continue

        print(f"OK   {cid}: citation ok, footer ok, evidence rows={len(resp.evidence)}")

    print(f"\nGolden summary: {failed} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
