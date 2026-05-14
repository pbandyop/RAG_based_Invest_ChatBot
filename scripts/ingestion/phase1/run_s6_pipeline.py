#!/usr/bin/env python3
"""
CLI — P1-S6: orchestrate P1-S1 → S2/S3 → S4 → (optional S5) and write ``p1_pipeline_report.json``.

Forwards optional fetch flags to ``run_s2_s3_fetch_and_store.py`` (e.g. ``--insecure-ssl`` dev only).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ingestion.phase1.s6_runner_handoff.pipeline import (  # noqa: E402
    run_manifest_pipeline,
    write_pipeline_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="P1-S6: full manifest → normalized pipeline + handoff report")
    parser.add_argument(
        "--skip-s1",
        action="store_true",
        help="Do not run P1-S1; use --crawl-plan or latest crawl_plan__*.json",
    )
    parser.add_argument(
        "--crawl-plan",
        type=Path,
        default=None,
        help="Explicit crawl plan (used with --skip-s1 or after S1)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Phase 0 manifest path (forwarded to P1-S1 when S1 runs)",
    )
    parser.add_argument(
        "--skip-s5",
        action="store_true",
        help="Skip P1-S5 pass",
    )
    parser.add_argument(
        "--playwright-s5",
        action="store_true",
        help="Enable Playwright augmentation in P1-S5 (allowlisted URLs only)",
    )
    parser.add_argument(
        "--s5-force",
        action="store_true",
        help="Forward --force to P1-S5",
    )
    parser.add_argument(
        "--s5-playwright-timeout-ms",
        type=int,
        default=60_000,
        help="Playwright timeout forwarded to P1-S5",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Pass --overwrite to P1-S4",
    )
    parser.add_argument(
        "--skip-robots",
        action="store_true",
        help="Forward to P1-S2/S3 (dev only)",
    )
    parser.add_argument(
        "--insecure-ssl",
        action="store_true",
        help="Forward to P1-S2/S3 (dev only)",
    )
    args = parser.parse_args()
    fetch_extra: list[str] = []
    if args.skip_robots:
        fetch_extra.append("--skip-robots")
    if args.insecure_ssl:
        fetch_extra.append("--insecure-ssl")

    result = run_manifest_pipeline(
        ROOT,
        skip_s1=args.skip_s1,
        crawl_plan_path=args.crawl_plan,
        manifest_path=args.manifest,
        skip_s5=args.skip_s5,
        s5_playwright=args.playwright_s5,
        s5_playwright_timeout_ms=args.s5_playwright_timeout_ms,
        s4_overwrite=args.overwrite,
        s5_force=args.s5_force,
        fetch_extra_args=fetch_extra,
    )

    report_path = write_pipeline_report(
        ROOT,
        result,
        skip_s5=args.skip_s5,
        s4_overwrite=args.overwrite,
    )

    print("P1-S6 pipeline finished")
    print(f"  run_id:           {result.run_id}")
    print(f"  crawl plan:       {result.crawl_plan_path}")
    print(f"  step exit codes:  {result.step_exit_codes}")
    print(f"  pipeline report:  {report_path}")
    if result.warnings:
        for w in result.warnings:
            print(f"  warning: {w}", file=sys.stderr)
    if result.errors:
        for e in result.errors:
            print(f"  error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
