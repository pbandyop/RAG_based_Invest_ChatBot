from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from phase2.retrieve import SearchHit
from phase3.url_normalize import normalize_citation_url


def load_phase3_defaults(repo_root: Path) -> dict[str, Any]:
    p = Path(repo_root) / "config" / "phase3" / "defaults.json"
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def clean_chunk_text(text: str) -> str:
    t = (text or "").replace("\r\n", "\n")
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def substantive_hits(
    hits: list[SearchHit],
    *,
    min_chars: int,
) -> list[SearchHit]:
    out: list[SearchHit] = []
    for h in hits:
        if len(clean_chunk_text(h.text)) >= min_chars:
            out.append(h)
    return out


def dedupe_hits_by_source_url(hits: list[SearchHit]) -> list[SearchHit]:
    """
    Diversity pass (architecture §6.1): one best-scoring chunk per canonical/source URL.
    """
    best: dict[str, SearchHit] = {}
    key_order: list[str] = []
    for h in hits:
        raw = str(h.metadata.get("canonical_url") or h.metadata.get("requested_url") or "")
        key = normalize_citation_url(raw) if raw else h.chunk_id
        if key not in best:
            key_order.append(key)
            best[key] = h
        elif h.score > best[key].score:
            best[key] = h
    return [best[k] for k in key_order]


def hit_evidence_record(hit: SearchHit) -> dict[str, Any]:
    """Architecture §6.1: expose source_url + fetched_at with scores for API consumers."""
    meta = hit.metadata
    url = str(meta.get("canonical_url") or meta.get("requested_url") or "")
    return {
        "chunk_id": hit.chunk_id,
        "score": hit.score,
        "source_url": url,
        "fetched_at": meta.get("fetched_at_utc"),
        "scheme_id": meta.get("scheme_id"),
    }


def scheme_clarification_needed(
    hits: list[SearchHit],
    *,
    margin: float,
) -> tuple[bool, str | None]:
    if len(hits) < 2:
        return False, None
    s0, s1 = hits[0].score, hits[1].score
    id0 = str(hits[0].metadata.get("scheme_id") or "")
    id1 = str(hits[1].metadata.get("scheme_id") or "")
    if not id0 or not id1 or id0 == id1:
        return False, None
    if abs(s0 - s1) <= margin:
        msg = (
            "Retrieval found similar matches for more than one pilot scheme. "
            "Please choose a scheme (dropdown in the UI) or name the fund explicitly in your question."
        )
        return True, msg
    return False, None


_STAT_ANCHOR_QUERY = "NAV ₹ fund size AUM expense ratio minimum SIP"


def same_scheme_stat_fallback(
    bundle: Any,
    scheme_id: str,
    query: str,
    *,
    min_chars: int,
) -> list[SearchHit]:
    """
    If the user's question is short (e.g. \"What is NAV?\") the embedding query may not
    retrieve any chunk for the selected scheme; anchor-search the stat-rich lexicon instead.
    """
    sid = scheme_id.strip()
    if not sid:
        return []
    if not re.search(r"\b(nav|n\.a\.v\.|aum|assets under management|fund size)\b", (query or "").lower()):
        return []
    raw = bundle.search(_STAT_ANCHOR_QUERY, k=60)
    ranked = dedupe_hits_by_source_url(raw)
    cand = substantive_hits(ranked, min_chars=min_chars)
    return [h for h in cand if str(h.metadata.get("scheme_id") or "") == sid]


def merge_stat_anchor_hits(
    bundle: Any,
    hits: list[SearchHit],
    scheme_id: str,
    query: str,
    *,
    extra_k: int = 48,
) -> list[SearchHit]:
    """
    When the user asks for NAV / scheme AUM, the paraphrased query can miss the page-hero chunk.
    Pull extra same-scheme hits from a compact lexical anchor search and merge (dedupe by chunk_id).
    """
    q = (query or "").lower()
    if not scheme_id.strip():
        return hits
    if not re.search(r"\b(nav|n\.a\.v\.|aum|assets under management|fund size)\b", q):
        return hits

    seen: dict[str, SearchHit] = {h.chunk_id: h for h in hits}
    try:
        raw2 = bundle.search(_STAT_ANCHOR_QUERY, k=extra_k)
    except Exception:
        return hits

    for h in raw2:
        if str(h.metadata.get("scheme_id") or "") != scheme_id.strip():
            continue
        t = (h.text or "").lower()
        if "nav" not in t and "aum" not in t and "fund size" not in t:
            continue
        if h.chunk_id not in seen:
            seen[h.chunk_id] = h

    merged = list(seen.values())
    merged.sort(key=lambda x: -x.score)
    return merged


def max_fetched_at_iso(hits: list[SearchHit]) -> str | None:
    dates: list[datetime] = []
    for h in hits:
        raw = h.metadata.get("fetched_at_utc")
        if not raw:
            continue
        try:
            s = str(raw).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            dates.append(dt)
        except ValueError:
            continue
    if not dates:
        return None
    latest = max(dates)
    return latest.date().isoformat()
