#!/usr/bin/env python3
"""
Run the same Python steps as ``.github/workflows/corpus_refresh.yml`` job ``ingest-and-index``
(minus checkout, pip install, and artifact upload).

From repo root after ``pip install -r requirements.txt``:

  python scripts/run_corpus_refresh_local.py

Env: sets ``PYTHONPATH`` to ``src/``. Optional ``HF_TOKEN`` in ``.env`` is picked up by
scripts that load dotenv (e.g. Phase 2).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    steps: list[list[str]] = [
        [sys.executable, str(ROOT / "scripts" / "validate_phase0.py")],
        [sys.executable, str(ROOT / "scripts" / "ingestion" / "phase1" / "run_s6_pipeline.py"), "--overwrite"],
        [sys.executable, str(ROOT / "scripts" / "run_phase2_build_index.py"), "--overwrite"],
    ]

    for cmd in steps:
        label = " ".join(cmd[1:])
        print(f"\n=== {label} ===\n", flush=True)
        r = subprocess.run(cmd, cwd=ROOT, env=env)
        if r.returncode != 0:
            print(f"\n=== FAILED (exit {r.returncode}): {label} ===\n", flush=True)
            return r.returncode

    print("\n=== Corpus refresh local run finished OK ===\n", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
