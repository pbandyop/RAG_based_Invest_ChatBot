"""
Build FAISS index + chunk metadata from a P1-S4 normalized run directory.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from phase2.chunking import build_chunks_from_run


class Phase2BuildError(RuntimeError):
    """Failed to build Phase 2 bundle."""


def build_phase2_index_bundle(
    normalized_run_dir: Path,
    index_out_dir: Path,
    *,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
    max_chunk_tokens: int = 480,
    overlap_tokens: int = 80,
    min_chunk_chars: int = 32,
    encode_batch_size: int = 16,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Load SentenceTransformer, chunk all *.normalized.json, embed, write FAISS + metadata.

    index_out_dir: e.g. data/phase2/index/{run_id}/
    """
    try:
        import faiss  # noqa: WPS433 — runtime dep
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise Phase2BuildError(
            "Install Phase 2 deps: pip install -r requirements.txt",
        ) from e

    index_out_dir = Path(index_out_dir)
    if index_out_dir.exists() and any(index_out_dir.iterdir()) and not overwrite:
        raise Phase2BuildError(
            f"Output dir not empty (use --overwrite): {index_out_dir}",
        )
    index_out_dir.mkdir(parents=True, exist_ok=True)

    normalized_run_dir = Path(normalized_run_dir)
    model = SentenceTransformer(embedding_model)
    tokenizer = model.tokenizer

    chunks = build_chunks_from_run(
        normalized_run_dir,
        tokenizer,
        max_chunk_tokens=max_chunk_tokens,
        overlap_tokens=overlap_tokens,
        min_chunk_chars=min_chunk_chars,
        tokenizer_max_length=int(getattr(model, "max_seq_length", 512) or 512),
    )
    if not chunks:
        raise Phase2BuildError("No chunks produced; check normalized_run_dir and text fields.")

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=encode_batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    embs = np.asarray(embeddings, dtype=np.float32)
    dim = embs.shape[1]

    index = faiss.IndexFlatIP(dim)
    index.add(embs)

    faiss_path = index_out_dir / "index.faiss"
    meta_path = index_out_dir / "chunk_metadata.json"
    chunks_path = index_out_dir / "chunks.jsonl"
    manifest_path = index_out_dir / "manifest.json"

    faiss.write_index(index, str(faiss_path))
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with chunks_path.open("w", encoding="utf-8") as f:
        for row in chunks:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fingerprint = hashlib.sha256()
    for row in chunks:
        fingerprint.update(row["chunk_id"].encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(row["text"].encode("utf-8", errors="replace"))
        fingerprint.update(b"\n")
    fp_hex = fingerprint.hexdigest()

    manifest: dict[str, Any] = {
        "phase": "P2",
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "embedding_model": embedding_model,
        "max_chunk_tokens": max_chunk_tokens,
        "overlap_tokens": overlap_tokens,
        "min_chunk_chars": min_chunk_chars,
        "normalized_source_dir": str(normalized_run_dir.resolve()),
        "index_out_dir": str(index_out_dir.resolve()),
        "chunk_count": len(chunks),
        "vector_dim": dim,
        "faiss_index_type": "IndexFlatIP",
        "embedding_normalize": True,
        "chunk_fingerprint_sha256": fp_hex,
    }
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return {
        "manifest": manifest,
        "paths": {
            "faiss": str(faiss_path),
            "chunk_metadata": str(meta_path),
            "chunks_jsonl": str(chunks_path),
            "manifest": str(manifest_path),
        },
    }
