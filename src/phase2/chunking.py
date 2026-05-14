"""
Token-based chunking for P1-S4 normalized documents (architecture §5.1).

Prefers paragraph boundaries (`\\n\\n`); long paragraphs use a sliding token window.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol


class SupportsChunkTokenize(Protocol):
    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]: ...

    def decode(self, token_ids: list[int], skip_special_tokens: bool = True) -> str: ...


def _clamp_token_window(*, max_chunk_tokens: int, overlap_tokens: int, tokenizer_max_length: int | None) -> tuple[int, int]:
    cap = int(tokenizer_max_length) if tokenizer_max_length is not None else 512
    # Leave headroom for special tokens when the embedding model re-tokenizes chunk text.
    cap = max(32, cap - 4)
    m = max(32, min(int(max_chunk_tokens), cap))
    o = max(0, min(int(overlap_tokens), m - 1))
    return m, o


def _chunk_paragraph_hf(
    tokenizer: Any,
    para: str,
    *,
    max_chunk_tokens: int,
    overlap_tokens: int,
    min_chunk_chars: int,
) -> list[str]:
    """
    Sliding windows via HuggingFace `return_overflowing_tokens` (no unbounded full-doc encode).
    """
    overlap_tokens = min(overlap_tokens, max_chunk_tokens - 1)
    enc = tokenizer(
        para,
        max_length=max_chunk_tokens,
        stride=overlap_tokens,
        truncation=True,
        return_overflowing_tokens=True,
        return_attention_mask=False,
        add_special_tokens=False,
        padding=False,
    )
    id_groups = enc.get("input_ids") or []
    if id_groups and isinstance(id_groups[0], int):
        id_groups = [id_groups]
    out: list[str] = []
    for ids in id_groups:
        if not ids:
            continue
        piece = tokenizer.decode(ids, skip_special_tokens=True).strip()
        if len(piece) >= min_chunk_chars:
            out.append(piece)
    return out


def _chunk_paragraph_fallback_ids(
    tokenizer: SupportsChunkTokenize,
    para: str,
    *,
    max_chunk_tokens: int,
    overlap_tokens: int,
    min_chunk_chars: int,
) -> list[str]:
    """
    Token-id sliding window on short segments only (Protocol / non-HF tokenizers).
    Splits by characters first so `encode` is never applied to huge strings.
    """
    max_chars = max(max_chunk_tokens * 4, max_chunk_tokens)
    chunks: list[str] = []
    step = max(1, max_chunk_tokens - overlap_tokens)
    for seg_start in range(0, len(para), max_chars):
        seg = para[seg_start : seg_start + max_chars]
        ids = tokenizer.encode(seg, add_special_tokens=False)
        if not ids:
            continue
        i = 0
        while i < len(ids):
            window = ids[i : i + max_chunk_tokens]
            piece = tokenizer.decode(window, skip_special_tokens=True).strip()
            if len(piece) >= min_chunk_chars:
                chunks.append(piece)
            if i + max_chunk_tokens >= len(ids):
                break
            i += step
    return chunks


def chunk_text_for_embedding(
    text: str,
    tokenizer: SupportsChunkTokenize,
    *,
    max_chunk_tokens: int = 480,
    overlap_tokens: int = 80,
    min_chunk_chars: int = 32,
    tokenizer_max_length: int | None = None,
) -> list[str]:
    """
    Split text into chunks suitable for embedding (<= max_chunk_tokens each).
    overlap_tokens controls sliding window stride for oversized paragraphs.
    """
    text = (text or "").strip()
    if not text:
        return []

    max_chunk_tokens, overlap_tokens = _clamp_token_window(
        max_chunk_tokens=max_chunk_tokens,
        overlap_tokens=overlap_tokens,
        tokenizer_max_length=tokenizer_max_length,
    )
    chunks: list[str] = []

    # Prefer paragraph splits (markdown / normalized layout uses blank lines)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 1 and "\n\n" not in text:
        paragraphs = [text]

    for para in paragraphs:
        if not para.strip():
            continue
        used_hf = False
        call = getattr(tokenizer, "__call__", None)
        if callable(call):
            try:
                chunks.extend(
                    _chunk_paragraph_hf(
                        tokenizer,
                        para,
                        max_chunk_tokens=max_chunk_tokens,
                        overlap_tokens=overlap_tokens,
                        min_chunk_chars=min_chunk_chars,
                    ),
                )
                used_hf = True
            except TypeError:
                used_hf = False
        if not used_hf:
            chunks.extend(
                _chunk_paragraph_fallback_ids(
                    tokenizer,
                    para,
                    max_chunk_tokens=max_chunk_tokens,
                    overlap_tokens=overlap_tokens,
                    min_chunk_chars=min_chunk_chars,
                ),
            )

    return chunks


def load_normalized_document(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def iter_normalized_documents(normalized_run_dir: Path) -> list[Path]:
    if not normalized_run_dir.is_dir():
        raise FileNotFoundError(f"normalized run dir not found: {normalized_run_dir}")
    return sorted(normalized_run_dir.glob("*.normalized.json"))


def build_chunks_from_run(
    normalized_run_dir: Path,
    tokenizer: SupportsChunkTokenize,
    *,
    max_chunk_tokens: int = 480,
    overlap_tokens: int = 80,
    min_chunk_chars: int = 32,
    tokenizer_max_length: int | None = None,
    text_field: str = "combined_text_for_chunking",
) -> list[dict[str, Any]]:
    """
    Returns flat list of chunk dicts with text + metadata (pre-embedding).
    """
    run_id = normalized_run_dir.name
    all_chunks: list[dict[str, Any]] = []
    for path in iter_normalized_documents(normalized_run_dir):
        doc = load_normalized_document(path)
        body = str(doc.get(text_field) or "").strip()
        if not body:
            body = str(doc.get("plain_text") or "").strip()
        if not body:
            continue

        pieces = chunk_text_for_embedding(
            body,
            tokenizer,
            max_chunk_tokens=max_chunk_tokens,
            overlap_tokens=overlap_tokens,
            min_chunk_chars=min_chunk_chars,
            tokenizer_max_length=tokenizer_max_length,
        )
        base = path.name[: -len(".normalized.json")]
        for i, text in enumerate(pieces):
            chunk_id = f"{run_id}__{base}__c{i:04d}"
            all_chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": text,
                    "canonical_url": doc.get("canonical_url"),
                    "requested_url": doc.get("requested_url"),
                    "scheme_id": doc.get("scheme_id"),
                    "document_type": doc.get("document_type"),
                    "fetched_at_utc": doc.get("fetched_at_utc"),
                    "truncated": doc.get("truncated"),
                    "content_sha256": doc.get("content_sha256"),
                    "combined_text_sha256": doc.get("combined_text_sha256"),
                    "source_normalized_file": path.name,
                    "chunk_index_in_doc": i,
                    "language": "en",
                },
            )
    return all_chunks
