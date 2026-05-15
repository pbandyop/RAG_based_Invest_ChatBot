#!/usr/bin/env python3
"""
Phase 6 — HTTP API server (architecture §9.1 ``POST /query``).

Serves Phase 5 static UI at ``/ui/`` (``GET /`` redirects there). Meta: ``/meta/schemes``, ``/meta/disclaimer``.

Usage:
  pip install -r requirements.txt
  set PYTHONPATH=src
  python scripts/run_phase6_server.py

Env:
  PHASE6_INDEX_DIR — optional override for Phase 2 bundle path
  PHASE6_CORS_ORIGINS — optional comma-separated origins (overrides config/phase6/defaults.json)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        r = getattr(stream, "reconfigure", None)
        if callable(r):
            try:
                r(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    defaults_path = ROOT / "config" / "phase6" / "defaults.json"
    host = "127.0.0.1"
    port = 8765
    if defaults_path.is_file():
        with defaults_path.open(encoding="utf-8") as f:
            d = json.load(f)
        host = str(d.get("host", host))
        port = int(d.get("port", port))

    import uvicorn

    uvicorn.run(
        "phase6.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
