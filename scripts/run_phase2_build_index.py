#!/usr/bin/env python3
"""
Build Phase 2 index from P1-S4 normalized JSON (chunk → embed → FAISS).

Requires: pip install -r requirements.txt
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

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from phase2.pipeline import Phase2BuildError, build_phase2_index_bundle  # noqa: E402
from phase2.retrieve import load_index_bundle  # noqa: E402


def _latest_normalized_run(norm_root: Path) -> Path | None:
    if not norm_root.is_dir():
        return None
    dirs = [p for p in norm_root.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def main() -> int:
    # Windows consoles often default to cp1252; smoke output may include ₹ etc.
    for stream in (sys.stdout, sys.stderr):
        reconf = getattr(stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                pass

    parser = argparse.ArgumentParser(description="Phase 2: chunk, embed, build FAISS index")
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=None,
        help="P1-S4 run dir (default: latest under data/phase1/normalized/)",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Output bundle dir (default: data/phase2/index/<run_id>/)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="BAAI/bge-small-en-v1.5",
        help="sentence-transformers model id",
    )
    parser.add_argument("--max-chunk-tokens", type=int, default=480)
    parser.add_argument("--overlap-tokens", type=int, default=80)
    parser.add_argument("--min-chunk-chars", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="After build, run sample queries from config/phase2/golden_queries.json",
    )
    args = parser.parse_args()

    norm_root = ROOT / "data" / "phase1" / "normalized"
    norm_dir = args.normalized_dir or _latest_normalized_run(norm_root)
    if norm_dir is None:
        print("No normalized run found. Run P1-S4 first.", file=sys.stderr)
        return 1

    index_dir = args.index_dir or (ROOT / "data" / "phase2" / "index" / norm_dir.name)

    try:
        summary = build_phase2_index_bundle(
            norm_dir,
            index_dir,
            embedding_model=args.model,
            max_chunk_tokens=args.max_chunk_tokens,
            overlap_tokens=args.overlap_tokens,
            min_chunk_chars=args.min_chunk_chars,
            encode_batch_size=args.batch_size,
            overwrite=args.overwrite,
        )
    except Phase2BuildError as e:
        print(f"Phase 2 build failed: {e}", file=sys.stderr)
        return 1

    m = summary["manifest"]
    print("Phase 2 index build OK")
    print(f"  chunks:      {m['chunk_count']}")
    print(f"  vector_dim:  {m['vector_dim']}")
    print(f"  model:       {m['embedding_model']}")
    print(f"  index dir:   {index_dir}")

    if args.smoke:
        golden = ROOT / "config" / "phase2" / "golden_queries.json"
        if not golden.is_file():
            print(f"Smoke: missing {golden}", file=sys.stderr)
            return 0
        with golden.open(encoding="utf-8") as f:
            gdata = json.load(f)
        bundle = load_index_bundle(index_dir)
        for item in gdata.get("queries", []):
            q = item.get("query", "")
            k = int(item.get("k", 5))
            print(f"\n-- smoke: {q!r}")
            for hit in bundle.search(q, k=k):
                sid = hit.metadata.get("scheme_id")
                print(f"  [{hit.rank}] score={hit.score:.4f} scheme_id={sid!r}")
                print(f"      text: {hit.text[:200]!r}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
