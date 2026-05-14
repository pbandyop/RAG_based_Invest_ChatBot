#!/usr/bin/env python3
"""
CLI — P1-S1 manifest binding.

Writes crawl plan JSON under data/phase1/crawl_plans/ for P1-S2+.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root: scripts/ingestion/phase1 -> parents[3]
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ingestion.phase1.s1_manifest_binding import (  # noqa: E402
    BindingError,
    build_crawl_plan_from_path,
    write_crawl_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="P1-S1: build crawl plan from Phase 0 manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "config" / "phase0" / "manifest.json",
        help="Path to manifest.json",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "phase1" / "crawl_plans",
        help="Directory for crawl_plan__<run_id>.json",
    )
    args = parser.parse_args()

    try:
        plan = build_crawl_plan_from_path(args.manifest)
        out_path = write_crawl_plan(plan, args.out_dir)
    except BindingError as e:
        print(f"Binding failed: {e}", file=sys.stderr)
        return 1

    print("P1-S1 manifest binding OK")
    print(f"  run_id:           {plan['run_id']}")
    print(f"  urls in plan:     {plan['url_count']}")
    print(f"  fingerprint:      {plan['plan_fingerprint_sha256'][:24]}...")
    print(f"  crawl plan file:  {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
