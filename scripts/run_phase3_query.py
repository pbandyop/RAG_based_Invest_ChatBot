#!/usr/bin/env python3
"""
Phase 3: run the facts-only RAG pipeline (retrieve → synthesize → grounding).

Requires a Phase 2 index under data/phase2/index/<run_id>/.
Optional: GROQ_API_KEY for Groq LLM synthesis; otherwise extractive fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

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
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass

    parser = argparse.ArgumentParser(description="Phase 3: grounded FAQ answer")
    parser.add_argument("--query", type=str, required=True)
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Phase 2 bundle directory (default: latest under data/phase2/index/)",
    )
    parser.add_argument(
        "--scheme-id",
        type=str,
        default=None,
        help="Pilot scheme_id from config/phase0/schemes.json (recommended for precision)",
    )
    parser.add_argument("--json", action="store_true", help="Print Phase3Response as JSON only")
    args = parser.parse_args()

    idx = args.index_dir or _latest_index_dir()
    if idx is None:
        print("No Phase 2 index found. Build with scripts/run_phase2_build_index.py", file=sys.stderr)
        return 1

    engine = FaqRagEngine(ROOT, idx)
    out = engine.answer(args.query, scheme_id=args.scheme_id)

    if args.json:
        print(json.dumps(out.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if out.refusal:
        print("REFUSAL")
        print(out.answer)
        if out.educational_url:
            print(f"Educational: {out.educational_label} — {out.educational_url}")
        return 0

    if out.needs_scheme_clarification:
        print("CLARIFICATION")
        print(out.answer)
        return 0

    print(out.answer)
    print()
    print(f"Source: {out.citation_url}")
    if out.last_updated:
        print(f"last_updated (ISO date): {out.last_updated}")
    print(out.footer_line or "")
    print(f"(generator={out.generator_route} top_scores={out.retrieval_scores[:3]!r})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
