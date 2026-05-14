"""Load Phase 2 bundle and run dense retrieval (for Phase 3 / smoke tests)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class SearchHit:
    rank: int
    score: float
    chunk_id: str
    text: str
    metadata: dict[str, Any]


class IndexBundle:
    """FAISS + SentenceTransformer query encoder + chunk metadata."""

    def __init__(self, bundle_dir: Path) -> None:
        self.bundle_dir = Path(bundle_dir)
        mf = self.bundle_dir / "manifest.json"
        if not mf.is_file():
            raise FileNotFoundError(f"missing manifest: {mf}")
        with mf.open(encoding="utf-8") as f:
            self.manifest: dict[str, Any] = json.load(f)

        import faiss  # noqa: WPS433
        from sentence_transformers import SentenceTransformer

        self._faiss = faiss
        self.model = SentenceTransformer(str(self.manifest["embedding_model"]))
        self.index = faiss.read_index(str(self.bundle_dir / "index.faiss"))
        with (self.bundle_dir / "chunk_metadata.json").open(encoding="utf-8") as f:
            self.chunks: list[dict[str, Any]] = json.load(f)
        if self.index.ntotal != len(self.chunks):
            raise ValueError(
                f"FAISS ntotal {self.index.ntotal} != metadata len {len(self.chunks)}",
            )

    def encode_query(self, query: str) -> np.ndarray:
        v = self.model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(v, dtype=np.float32)

    def search(self, query: str, k: int = 8) -> list[SearchHit]:
        q = self.encode_query(query)
        scores, idxs = self.index.search(q, min(k, self.index.ntotal))
        hits: list[SearchHit] = []
        for rank, (score, idx) in enumerate(zip(scores[0].tolist(), idxs[0].tolist())):
            if idx < 0:
                continue
            row = self.chunks[int(idx)]
            hits.append(
                SearchHit(
                    rank=rank,
                    score=float(score),
                    chunk_id=str(row["chunk_id"]),
                    text=str(row["text"]),
                    metadata={k: v for k, v in row.items() if k != "text"},
                ),
            )
        return hits


def load_index_bundle(bundle_dir: Path) -> IndexBundle:
    return IndexBundle(bundle_dir)
