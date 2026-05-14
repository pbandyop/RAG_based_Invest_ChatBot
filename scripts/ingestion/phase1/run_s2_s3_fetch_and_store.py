#!/usr/bin/env python3
"""
CLI — P1-S2 + P1-S3: fetch each URL in a crawl plan and persist raw artifacts.

Requires a crawl plan from P1-S1 (`run_s1_manifest_binding.py`).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from ingestion.phase1.s1_manifest_binding import load_crawl_plan  # noqa: E402
from ingestion.phase1.s2_http_fetch import (  # noqa: E402
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_USER_AGENT,
    RobotsPolicy,
    fetch_url,
    unverified_ssl_context,
)
from ingestion.phase1.s3_raw_artifact_store import (  # noqa: E402
    StoreError,
    fetch_result_to_jsonable,
    store_fetch_result,
)


def _latest_crawl_plan(crawl_plans_dir: Path) -> Path | None:
    if not crawl_plans_dir.is_dir():
        return None
    candidates = sorted(
        crawl_plans_dir.glob("crawl_plan__*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P1-S2+P1-S3: fetch crawl plan URLs and store raw artifacts",
    )
    parser.add_argument(
        "--crawl-plan",
        type=Path,
        default=None,
        help="Path to crawl_plan__*.json (default: newest in data/phase1/crawl_plans/)",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=ROOT / "data" / "phase1" / "raw",
        help="Root directory for raw artifacts (run_id subfolders)",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=ROOT / "data" / "phase1" / "runs",
        help="Directory for fetch_report.json per run",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SEC,
        help="HTTP timeout seconds",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="Max response body bytes per URL",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Max fetch attempts per URL",
    )
    parser.add_argument(
        "--skip-robots",
        action="store_true",
        help="Do not load or enforce robots.txt (dev only)",
    )
    parser.add_argument(
        "--insecure-ssl",
        action="store_true",
        help="Disable TLS certificate verification (dev only; fixes some local Python/CA setups)",
    )
    args = parser.parse_args()

    crawl_plans_dir = ROOT / "data" / "phase1" / "crawl_plans"
    plan_path = args.crawl_plan or _latest_crawl_plan(crawl_plans_dir)
    if plan_path is None:
        print(
            "No crawl plan found. Run: python scripts/ingestion/phase1/run_s1_manifest_binding.py",
            file=sys.stderr,
        )
        return 1

    try:
        plan = load_crawl_plan(plan_path)
    except Exception as e:  # noqa: BLE001
        print(f"Failed to load crawl plan: {e}", file=sys.stderr)
        return 1

    run_id = str(plan["run_id"])
    urls = plan["urls"]

    ssl_ctx = unverified_ssl_context() if args.insecure_ssl else None

    robots: RobotsPolicy | None = None
    if not args.skip_robots:
        robots = RobotsPolicy(DEFAULT_USER_AGENT)
        robots.load(timeout=min(15.0, args.timeout), ssl_context=ssl_ctx)

    started = datetime.now(timezone.utc).isoformat()
    entries: list[dict] = []
    ok_count = 0
    fail_count = 0

    for ordinal, row in enumerate(urls, start=1):
        url = str(row.get("url") or "")
        if not url:
            entries.append({"ordinal": ordinal, "error": "missing url in plan row", "store": None})
            fail_count += 1
            continue
        try:
            result = fetch_url(
                url,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
                max_retries=args.max_retries,
                robots=robots,
                ssl_context=ssl_ctx,
            )
            store_info = store_fetch_result(
                run_id=run_id,
                ordinal=ordinal,
                plan_row=row,
                result=result,
                raw_root=args.raw_root,
            )
            if result.ok:
                ok_count += 1
            else:
                fail_count += 1
            entries.append(
                {
                    "ordinal": ordinal,
                    "url": url,
                    "fetch": fetch_result_to_jsonable(result),
                    "store": store_info,
                },
            )
        except StoreError as e:
            fail_count += 1
            entries.append(
                {
                    "ordinal": ordinal,
                    "url": url,
                    "error": f"StoreError: {e}",
                    "store": None,
                },
            )

    finished = datetime.now(timezone.utc).isoformat()
    report = {
        "p1_subphases": ["P1-S2", "P1-S3"],
        "run_id": run_id,
        "crawl_plan_path": str(plan_path.resolve()),
        "started_at_utc": started,
        "finished_at_utc": finished,
        "summary": {"ok": ok_count, "failed": fail_count, "total": len(urls)},
        "entries": entries,
    }

    report_dir = args.report_dir / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "fetch_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("P1-S2 fetch + P1-S3 store complete")
    print(f"  run_id:        {run_id}")
    print(f"  ok / failed:   {ok_count} / {fail_count}")
    print(f"  raw dir:       {args.raw_root / run_id}")
    print(f"  fetch report:  {report_path}")
    return 0 if fail_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
