#!/usr/bin/env python3
"""
Commit and push the Phase 2 index bundle produced by corpus_refresh CI.

Used after ingest-and-index so Railway (GitHub deploy) picks up the new FAISS bundle.
Exits 0 with no commit when the bundle is unchanged.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_ROOT = ROOT / "data" / "phase2" / "index"


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT, text=True, check=check, capture_output=True)


def _latest_index_dir() -> Path:
    if not INDEX_ROOT.is_dir():
        raise FileNotFoundError(f"Missing index root: {INDEX_ROOT}")
    candidates = [
        p for p in INDEX_ROOT.iterdir() if p.is_dir() and (p / "manifest.json").is_file()
    ]
    if not candidates:
        raise FileNotFoundError(f"No index bundle with manifest.json under {INDEX_ROOT}")
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def main() -> int:
    bundle = _latest_index_dir()
    rel = bundle.relative_to(ROOT).as_posix()

    manifest_path = bundle / "manifest.json"
    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)
    built_at = manifest.get("built_at_utc", "unknown")
    chunk_count = manifest.get("chunk_count", "?")
    fingerprint = manifest.get("chunk_fingerprint_sha256", "")[:12]

    _run(["git", "add", "--", rel])

    status = _run(["git", "diff", "--cached", "--quiet"], check=False)
    if status.returncode == 0:
        print(f"No index changes to commit under {rel}", flush=True)
        return 0

    run_id = os.environ.get("GITHUB_RUN_ID", "")
    event = os.environ.get("GITHUB_EVENT_NAME", "ci")
    msg = (
        f"chore(corpus): refresh Phase 2 index ({bundle.name})\n\n"
        f"built_at_utc: {built_at}\n"
        f"chunk_count: {chunk_count}\n"
        f"chunk_fingerprint: {fingerprint}…\n"
        f"workflow: {event} run {run_id}".strip()
    )

    _run(["git", "commit", "-m", msg])

    branch = os.environ.get("PUBLISH_BRANCH", "main").strip() or "main"
    _run(["git", "pull", "--rebase", "origin", branch], check=False)

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    remote_url = os.environ.get("GIT_REMOTE_URL", "").strip()
    if not remote_url and token:
        repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        if repo:
            remote_url = f"https://x-access-token:{token}@github.com/{repo}.git"

    if remote_url:
        _run(["git", "push", remote_url, f"HEAD:{branch}"])
    else:
        _run(["git", "push", "origin", branch])

    print(f"Pushed refreshed index {rel} to {branch}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        if e.stdout:
            print(e.stdout, file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        raise SystemExit(e.returncode) from e
