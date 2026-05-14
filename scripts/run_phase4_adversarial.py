#!/usr/bin/env python3
"""
Phase 4 gate (architecture §7.3): adversarial prompts → refusals or safe factual answers.

Requires Phase 2 index (same as Phase 3). Uses ``config/phase4/adversarial_prompts.json``.

Usage:
  set PYTHONPATH=src
  python scripts/run_phase4_adversarial.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phase3.engine import FaqRagEngine  # noqa: E402


def _latest_index_dir() -> Path | None:
    base = ROOT / "data" / "phase2" / "index"
    if not base.is_dir():
        return None
    dirs = [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").is_file()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        r = getattr(stream, "reconfigure", None)
        if callable(r):
            try:
                r(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass

    path = ROOT / "config" / "phase4" / "adversarial_prompts.json"
    if not path.is_file():
        print(f"Missing {path}", file=sys.stderr)
        return 1

    idx = _latest_index_dir()
    if idx is None:
        print("No Phase 2 index under data/phase2/index/", file=sys.stderr)
        return 1

    with path.open(encoding="utf-8") as f:
        doc = json.load(f)

    engine = FaqRagEngine(ROOT, idx)
    failed = 0

    for case in doc.get("cases", []):
        cid = case.get("id", "?")
        q = str(case.get("query") or "")
        expect = str(case.get("expect") or "refusal")
        want_tpl = case.get("refusal_template_key")
        no_edu = bool(case.get("no_educational_url"))
        sid = case.get("scheme_id")
        scheme_id = sid if isinstance(sid, str) and sid.strip() else None

        resp = engine.answer(q, scheme_id=scheme_id)

        if expect == "refusal":
            if not resp.refusal:
                print(f"FAIL {cid}: expected refusal, got answer (route={resp.generator_route})")
                failed += 1
                continue
            if want_tpl and resp.refusal_template_key != want_tpl:
                print(
                    f"FAIL {cid}: expected refusal_template_key={want_tpl!r}, "
                    f"got {resp.refusal_template_key!r}",
                )
                failed += 1
                continue
            if no_edu and (resp.educational_url or resp.educational_label):
                print(
                    f"FAIL {cid}: expected no educational URL for this refusal, "
                    f"got url={resp.educational_url!r}",
                )
                failed += 1
                continue
            print(f"OK   {cid}: refusal ({resp.refusal_template_key})")
            continue

        if expect == "answer":
            if resp.refusal or resp.needs_scheme_clarification:
                print(
                    f"FAIL {cid}: expected factual answer, "
                    f"refusal={resp.refusal} clarify={resp.needs_scheme_clarification}",
                )
                failed += 1
                continue
            if not (resp.answer or "").strip():
                print(f"FAIL {cid}: empty answer")
                failed += 1
                continue
            if not resp.citation_url:
                print(f"FAIL {cid}: missing citation_url")
                failed += 1
                continue
            print(f"OK   {cid}: answer (route={resp.generator_route})")
            continue

        print(f"FAIL {cid}: unknown expect={expect!r}", file=sys.stderr)
        failed += 1

    print(f"\nPhase 4 adversarial summary: {failed} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
