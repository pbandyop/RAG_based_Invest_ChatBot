"""
P1-S6 — manifest runner and Phase 2 handoff (architecture §4.1).

Orchestrates P1-S1 → S2/S3 → S4 → (optional S5) via the existing CLIs and writes ``p1_pipeline_report.json``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class PipelineResult:
    run_id: str
    crawl_plan_path: Path | None = None
    step_exit_codes: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _latest_crawl_plan(crawl_plans_dir: Path) -> Path | None:
    if not crawl_plans_dir.is_dir():
        return None
    candidates = sorted(
        crawl_plans_dir.glob("crawl_plan__*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _read_run_id(plan_path: Path) -> str:
    with plan_path.open(encoding="utf-8") as f:
        plan = json.load(f)
    return str(plan.get("run_id") or "")


def _run_step(
    label: str,
    cmd: list[str],
    *,
    cwd: Path,
    result: PipelineResult,
    treat_nonzero_as_error: bool,
) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd))  # noqa: S603 — argv built by runner from fixed script paths
    code = int(proc.returncode)
    result.step_exit_codes[label] = code
    if code != 0 and treat_nonzero_as_error:
        result.errors.append(f"{label} exited with code {code}")
    elif code != 0:
        result.warnings.append(f"{label} exited with code {code} (continuing pipeline)")


def run_manifest_pipeline(
    repo_root: Path,
    *,
    skip_s1: bool = False,
    crawl_plan_path: Path | None = None,
    manifest_path: Path | None = None,
    skip_s5: bool = False,
    s5_playwright: bool = False,
    s5_playwright_timeout_ms: int = 60_000,
    s4_overwrite: bool = False,
    s5_force: bool = False,
    fetch_extra_args: list[str] | None = None,
) -> PipelineResult:
    """
    Run subphases in order. Uses the same Python interpreter as the caller.
    """
    repo_root = Path(repo_root).resolve()
    py = sys.executable
    scripts = repo_root / "scripts" / "ingestion" / "phase1"
    crawl_plans_dir = repo_root / "data" / "phase1" / "crawl_plans"
    fetch_extra_args = list(fetch_extra_args or [])

    result = PipelineResult(run_id="")

    if not skip_s1:
        cmd_s1 = [py, str(scripts / "run_s1_manifest_binding.py")]
        if manifest_path is not None:
            cmd_s1.extend(["--manifest", str(manifest_path)])
        _run_step("P1-S1", cmd_s1, cwd=repo_root, result=result, treat_nonzero_as_error=True)
        if result.errors:
            return result

    plan_path = crawl_plan_path or _latest_crawl_plan(crawl_plans_dir)
    if plan_path is None or not plan_path.is_file():
        result.errors.append("No crawl plan found after P1-S1 (expected crawl_plan__*.json).")
        return result

    result.crawl_plan_path = plan_path
    result.run_id = _read_run_id(plan_path)
    if not result.run_id:
        result.errors.append("Crawl plan missing run_id")
        return result

    cmd_s23 = [py, str(scripts / "run_s2_s3_fetch_and_store.py"), "--crawl-plan", str(plan_path)]
    cmd_s23.extend(fetch_extra_args)
    _run_step("P1-S2_P1-S3", cmd_s23, cwd=repo_root, result=result, treat_nonzero_as_error=False)

    cmd_s4 = [
        py,
        str(scripts / "run_s4_normalize.py"),
        "--run-id",
        result.run_id,
    ]
    if s4_overwrite:
        cmd_s4.append("--overwrite")
    _run_step("P1-S4", cmd_s4, cwd=repo_root, result=result, treat_nonzero_as_error=True)
    if result.errors:
        return result

    if not skip_s5:
        cmd_s5 = [
            py,
            str(scripts / "run_s5_low_yield.py"),
            "--run-id",
            result.run_id,
        ]
        if s5_playwright:
            cmd_s5.append("--playwright")
        if s5_force:
            cmd_s5.append("--force")
        cmd_s5.extend(["--playwright-timeout-ms", str(s5_playwright_timeout_ms)])
        _run_step("P1-S5", cmd_s5, cwd=repo_root, result=result, treat_nonzero_as_error=False)

    return result


def write_pipeline_report(
    repo_root: Path,
    result: PipelineResult,
    *,
    skip_s5: bool,
    s4_overwrite: bool,
) -> Path:
    """Merge pointers into ``data/phase1/runs/{run_id}/p1_pipeline_report.json``."""
    repo_root = Path(repo_root).resolve()
    run_id = result.run_id
    runs_dir = repo_root / "data" / "phase1" / "runs" / run_id
    runs_dir.mkdir(parents=True, exist_ok=True)

    norm_dir = repo_root / "data" / "phase1" / "normalized" / run_id
    fetch_report = runs_dir / "fetch_report.json"
    normalize_report = norm_dir / "normalize_report.json"
    s5_report = norm_dir / "s5_report.json"

    ready = not result.errors and norm_dir.is_dir()

    payload: dict[str, Any] = {
        "p1_subphases": (["P1-S1", "P1-S2", "P1-S3", "P1-S4"] + ([] if skip_s5 else ["P1-S5"])),
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "crawl_plan_path": str(result.crawl_plan_path.resolve()) if result.crawl_plan_path else None,
        "fetch_report_path": str(fetch_report.resolve()) if fetch_report.is_file() else None,
        "normalized_dir": str(norm_dir.resolve()) if norm_dir.is_dir() else None,
        "normalize_report_path": str(normalize_report.resolve()) if normalize_report.is_file() else None,
        "s5_report_path": str(s5_report.resolve()) if s5_report.is_file() else None,
        "ready_for_phase2": bool(ready),
        "step_exit_codes": dict(result.step_exit_codes),
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "handoff": {
            "phase2_index_cli": "python scripts/run_phase2_build_index.py --normalized-dir data/phase1/normalized/"
            + run_id
            + (" --overwrite" if s4_overwrite else ""),
        },
    }

    out_path = runs_dir / "p1_pipeline_report.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path
