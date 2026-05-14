#!/usr/bin/env python3
"""
CLI — P1-S5: low-yield / JS-heavy follow-up on P1-S4 normalized JSON.

Annotates ``p1_s5`` on each ``*.normalized.json``. Optional ``--playwright`` augments
allowlisted Groww scheme URLs only (Phase 0 citation allowlist).

Requires (optional): ``pip install playwright`` and ``playwright install chromium``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ingestion.phase1.s5_js_fallback import run_s5_on_normalized_dir  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="P1-S5: low-yield flags / optional Playwright augmentation")
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Normalized + raw run folder name (default: latest under data/phase1/normalized/)",
    )
    parser.add_argument(
        "--normalized-root",
        type=Path,
        default=ROOT / "data" / "phase1" / "normalized",
        help="Root containing {run_id}/ normalized JSON",
    )
    parser.add_argument(
        "--playwright",
        action="store_true",
        help="Run headless Chromium goto only for URLs on config/phase0/citation_allowlist.json",
    )
    parser.add_argument(
        "--playwright-timeout-ms",
        type=int,
        default=60_000,
        help="Navigation timeout for Playwright goto",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run S5 even if p1_s5 already shows augmented_playwright",
    )
    args = parser.parse_args()

    norm_root = args.normalized_root
    if args.run_id:
        run_dir = norm_root / args.run_id
    else:
        if not norm_root.is_dir():
            print("No normalized root.", file=sys.stderr)
            return 1
        dirs = sorted([p for p in norm_root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        if not dirs:
            print("No normalized run directories. Run P1-S4 first.", file=sys.stderr)
            return 1
        run_dir = dirs[0]

    if not run_dir.is_dir():
        print(f"Run dir not found: {run_dir}", file=sys.stderr)
        return 1

    summary = run_s5_on_normalized_dir(
        ROOT,
        run_dir,
        use_playwright=args.playwright,
        playwright_timeout_ms=args.playwright_timeout_ms,
        force=args.force,
    )

    report_path = run_dir / "s5_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")

    c = summary["counts"]
    print("P1-S5 complete")
    print(f"  run dir:       {run_dir}")
    print(f"  files_seen:    {c['files_seen']}")
    print(f"  augmented:     {c['augmented_playwright']}")
    print(f"  flagged:       {c['flagged_or_review']}")
    print(f"  s5 report:     {report_path}")
    if summary.get("errors"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
