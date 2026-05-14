#!/usr/bin/env python3
"""
CLI — P1-S4: normalize HTML artifacts from P1-S3 into JSON for Phase 2 chunking.

Reads:  data/phase1/raw/{run_id}/fetch_*.meta.json + .body.html
Writes: data/phase1/normalized/{run_id}/fetch_*.normalized.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ingestion.phase1.s4_html_normalization import (  # noqa: E402
    NormalizationError,
    normalize_run,
)


def _latest_run_dir(raw_root: Path) -> Path | None:
    if not raw_root.is_dir():
        return None
    candidates = sorted(
        [p for p in raw_root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="P1-S4: HTML → normalized JSON documents")
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run id folder name under raw/ (default: latest mtime under data/phase1/raw/)",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=ROOT / "data" / "phase1" / "raw",
        help="Root containing {run_id}/ fetch artifacts",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "data" / "phase1" / "normalized",
        help="Root for normalized/{run_id}/ output",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .normalized.json files",
    )
    parser.add_argument(
        "--review-chars",
        type=int,
        default=None,
        help="needs_manual_review if combined chars below this (default: library default)",
    )
    parser.add_argument(
        "--review-words",
        type=int,
        default=None,
        help="needs_manual_review if combined words below this when chars also low",
    )
    args = parser.parse_args()

    run_id = args.run_id
    if not run_id:
        latest = _latest_run_dir(args.raw_root)
        if latest is None:
            print("No run directories under raw-root. Run P1-S2/S3 first.", file=sys.stderr)
            return 1
        run_dir = latest
        run_id = run_dir.name
    else:
        run_dir = args.raw_root / run_id
    out_dir = args.out_root / run_id

    kwargs = {"overwrite": args.overwrite}
    if args.review_chars is not None:
        kwargs["review_char_threshold"] = args.review_chars
    if args.review_words is not None:
        kwargs["review_word_threshold"] = args.review_words

    try:
        summary = normalize_run(run_dir, out_dir, **kwargs)
    except NormalizationError as e:
        print(f"Normalize failed: {e}", file=sys.stderr)
        return 1

    report_path = out_dir / "normalize_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("P1-S4 normalization complete")
    print(f"  run_id:          {run_id}")
    print(f"  written:         {summary['written_count']}")
    print(f"  skipped:         {len(summary['skipped'])}")
    print(f"  errors:          {len(summary['errors'])}")
    print(f"  out dir:         {out_dir}")
    print(f"  summary report:  {report_path}")
    if summary["errors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
