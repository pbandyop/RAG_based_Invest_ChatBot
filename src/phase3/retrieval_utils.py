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


def prioritize_hero_stat_chunks(hits: list[SearchHit], query: str) -> list[SearchHit]:
    """
    Move likely hero-stat or fund-manager JSON chunks earlier so ``contexts_from_hits`` / LLM paths
    see NAV / AUM / expense / manager facts before noisy nav-menu text.
    """
    q = (query or "").lower()
    if not hits:
        return hits

    def tier(h: SearchHit) -> int:
        t = (h.text or "").lower()
        if "expense" in q and "ratio" in q:
            if "expense _ ratio" in t:
                return 0
            if "fund size" in t and "aum" in t and "expense" in t and "ratio" in t and "%" in t:
                return 4
            if "expense" in t and "ratio" in t and "%" in t:
                return 3
            if "expense" in t and "ratio" in t:
                return 2
        if re.search(r"\b(nav|n\.a\.v\.)\b", q) and "nav" in t and ":" in t and "min." in t:
            return 3
        if re.search(r"\b(aum|fund size)\b", q) and "fund size" in t and "aum" in t:
            return 3
        if re.search(
            r"\b(fund\s+management|fund\s+manager|manager\s+details|who\s+manages|registrar|fund\s+house)\b",
            q,
        ):
            if "fund _ manager _ details" in t:
                return 4
            if re.search(r"\b(current\s+)?fund\s+manager\b", t):
                return 4
            if "fund _ manager" in t and ("person _ name" in t or "education" in t):
                return 3
            if "also manages these schemes" in t and ("education" in t or "experience" in t):
                return 3
            if "fund _ manager" in t or "amc _ info" in t or "person _ name" in t:
                return 2
            if "registrar" in t and ("cams" in t or "kfin" in t):
                return 2
        return 0

    return sorted(hits, key=lambda h: (-tier(h), -h.score))


_SLUG_STOPWORDS = frozenset(
    "hdfc fund direct growth plan the a an of for in on to and or g p v r www http https com in "
    "mutual funds what which is are was how much about tell please scheme mf".split()
)

_STAT_ANCHOR_QUERY = "NAV ₹ fund size AUM expense ratio TER minimum SIP"

_MANAGER_ANCHOR_QUERY = (
    "fund manager fund management current manager education experience "
    "also manages these schemes registrar portfolio fund house"
)

_QUERY_WANTS_MANAGER = re.compile(
    r"\b(fund\s+management|fund\s+manager|who\s+manages|portfolio\s+manager|"
    r"fund\s+house|registrar|transfer\s+agent|amc\s+team)\b",
    re.IGNORECASE,
)


def _chunk_has_manager_signal(text: str) -> bool:
    """Heuristic for Groww prose + spaced JSON keys in chunked crawl text."""
    t = (text or "").lower()
    if re.search(r"\b(current\s+)?fund\s+manager\b", t):
        return True
    if "fund _ manager _ details" in t or "fund _ manager" in t:
        return True
    if "also manages these schemes" in t and ("education" in t or "experience" in t):
        return True
    if "registrar" in t and ("cams" in t or "kfin" in t):
        return True
    return False


def infer_scheme_id_from_query(query: str, schemes: list[dict[str, Any]]) -> str | None:
    """
    Infer ``scheme_id`` from fund wording in the question (Groww URL slug tokens).
    Returns None when no scheme meets a 2/3 token-coverage bar or top scores tie.
    """
    if not schemes:
        return None
    q = (query or "").strip().lower()
    if not q:
        return None
    q_tokens = set(re.findall(r"[a-z0-9]+", q))

    candidates: list[tuple[int, str]] = []
    for row in schemes:
        sid = str(row.get("scheme_id") or "")
        url = str(row.get("citation_url") or "").strip()
        if not sid or not url:
            continue
        slug = url.rstrip("/").split("/")[-1].lower().replace("-", " ")
        raw_toks = [t for t in re.findall(r"[a-z0-9]+", slug) if t not in _SLUG_STOPWORDS and len(t) >= 2]
        if not raw_toks:
            continue
        tokens: list[str] = []
        seen: set[str] = set()
        for t in raw_toks:
            if t not in seen:
                seen.add(t)
                tokens.append(t)
        n = len(tokens)
        score = sum(1 for t in tokens if t in q_tokens)
        if n == 0 or score * 3 < n * 2:
            continue
        candidates.append((score, sid))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], len(x[1])))
    top_score, top_sid = candidates[0]
    if len(candidates) > 1 and candidates[1][0] == top_score:
        return None
    return top_sid


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
    if not re.search(
        r"\b(nav|n\.a\.v\.|aum|assets under management|fund size|expense\s+ratio|ter)\b",
        (query or "").lower(),
    ):
        return []
    raw = bundle.search(_STAT_ANCHOR_QUERY, k=60)
    ranked = dedupe_hits_by_source_url(raw)
    cand = substantive_hits(ranked, min_chars=min_chars)
    return [h for h in cand if str(h.metadata.get("scheme_id") or "") == sid]


def same_scheme_manager_fallback(
    bundle: Any,
    scheme_id: str,
    query: str,
    *,
    min_chars: int,
) -> list[SearchHit]:
    """
    When the embedding query misses on-page manager / registrar prose, anchor-search
    manager-rich lexicon and keep same-scheme chunks (do not URL-dedupe: one URL per scheme).
    """
    sid = scheme_id.strip()
    if not sid or not _QUERY_WANTS_MANAGER.search(query or ""):
        return []
    raw = bundle.search(_MANAGER_ANCHOR_QUERY, k=60)
    cand = substantive_hits(raw, min_chars=min_chars)
    out = [h for h in cand if str(h.metadata.get("scheme_id") or "") == sid]
    out.sort(key=lambda h: -h.score)
    return out


def merge_stat_anchor_hits(
    bundle: Any,
    hits: list[SearchHit],
    scheme_id: str,
    query: str,
    *,
    extra_k: int = 48,
) -> list[SearchHit]:
    """
    When the user asks for NAV / scheme AUM / expense ratio, the paraphrased query can miss the page-hero chunk.
    Pull extra same-scheme hits from a compact lexical anchor search and merge (dedupe by chunk_id).
    """
    q = (query or "").lower()
    if not scheme_id.strip():
        return hits
    if not re.search(
        r"\b(nav|n\.a\.v\.|aum|assets under management|fund size|expense\s+ratio|ter)\b",
        q,
    ):
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
        has_stat = (
            "nav" in t
            or "aum" in t
            or "fund size" in t
            or ("expense" in t and "ratio" in t)
            or (re.search(r"\bter\b", t) and "%" in t)
        )
        if not has_stat:
            continue
        if h.chunk_id not in seen:
            seen[h.chunk_id] = h

    merged = list(seen.values())
    merged.sort(key=lambda x: -x.score)
    return merged


def merge_manager_anchor_hits(
    bundle: Any,
    hits: list[SearchHit],
    scheme_id: str,
    query: str,
    *,
    extra_k: int = 48,
) -> list[SearchHit]:
    """Augment retrieval with same-scheme manager / registrar excerpts when the question asks."""
    if not scheme_id.strip() or not _QUERY_WANTS_MANAGER.search(query or ""):
        return hits

    seen: dict[str, SearchHit] = {h.chunk_id: h for h in hits}
    try:
        raw2 = bundle.search(_MANAGER_ANCHOR_QUERY, k=extra_k)
    except Exception:
        return hits

    for h in raw2:
        if str(h.metadata.get("scheme_id") or "") != scheme_id.strip():
            continue
        if not _chunk_has_manager_signal(h.text or ""):
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
