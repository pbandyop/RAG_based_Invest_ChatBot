from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from phase2.retrieve import SearchHit

_STOP = frozenset(
    "a an the is are was were be been being to of and or for in on at by it as if with this that "
    "what which how when where who from".split(),
)


def _is_plausible_sentence(p: str) -> bool:
    if len(p) < 18:
        return False
    low = p.lower()
    collapsed = re.sub(r"\s+", "", low)
    if "@type" in collapsed or "schema.org" in collapsed:
        return False
    if "<" in p or ">" in p:
        return False
    if "br/" in collapsed or "/p" in collapsed:
        return False
    if low.count('"') > 12:
        return False
    if '":"' in collapsed or '"name"' in collapsed:
        return False
    letters = sum(c.isalpha() for c in p)
    ratio = letters / max(len(p), 1)
    if ratio > 0.40:
        return True
    # Groww NAV / scheme AUM rows are digit-heavy but factual (not JSON payloads).
    if re.search(r"\bnav\s*:", low) or re.search(r"\bfund\s+size\s*\(\s*aum\s*\)", low) or re.search(r"\btotal\s+aum\b", low):
        return ratio > 0.16 and len(p) >= 20
    return False


def _extractive_priority_nav_aum(blob: str, query: str) -> list[str]:
    """Pull scheme NAV / fund-size lines when the question asks for them (Groww crawl shape)."""
    out: list[str] = []
    q = (query or "").lower()
    if re.search(r"\b(nav|n\.a\.v\.)\b", q):
        m = re.search(r"\bnav\s*:\s*.+?min\.", blob, re.IGNORECASE | re.DOTALL)
        if not m:
            m = re.search(r"\bnav\s*:\s*.{12,240}", blob, re.IGNORECASE | re.DOTALL)
        if m:
            s = re.sub(r"\s+", " ", m.group(0)).strip()
            if not s.endswith("."):
                s += "."
            out.append(s)
    if re.search(r"\b(aum|assets under management|fund size)\b", q):
        m = re.search(
            r"\bfund\s+size\s*\(\s*aum\s*\)\s*₹[\d,\s\.]+\s*cr\b",
            blob,
            re.IGNORECASE,
        )
        if m:
            s = re.sub(r"\s+", " ", m.group(0)).strip()
            if not s.endswith("."):
                s += "."
            out.append(s)
    return out


def _prepare_blob(contexts: list[str]) -> str:
    pieces: list[str] = []
    for c in contexts:
        c = re.sub(r"<[^>]{0,800}>", " ", c)
        c = re.sub(r"^#+\s*", "", c, flags=re.MULTILINE)
        c = c.replace("\\n", " ").replace("\n", " ")
        c = re.sub(r"\s+", " ", c).strip()
        if c:
            pieces.append(c)
    return " ".join(pieces)


def _phrases_from_query(q: str) -> list[str]:
    toks = [t for t in re.findall(r"[a-z0-9]+", q.lower()) if t not in _STOP and len(t) > 2]
    phrases: list[str] = []
    for i in range(len(toks) - 1):
        phrases.append(f"{toks[i]} {toks[i + 1]}")
    phrases.extend(toks)
    uniq: list[str] = []
    seen: set[str] = set()
    for p in sorted(phrases, key=len, reverse=True):
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def _snippet_around_phrase(blob: str, phrase: str) -> str | None:
    esc = re.escape(phrase)
    pat = re.compile(rf"([^.]{{0,100}}{esc}[^.]{{0,360}}\.)", re.IGNORECASE)
    m = pat.search(blob)
    if not m:
        return None
    s = re.sub(r"\s+", " ", m.group(1)).strip()
    return s if _is_plausible_sentence(s) else None


def _extractive_from_contexts(query: str, contexts: list[str], max_sentences: int = 3) -> str:
    blob = _prepare_blob(contexts)
    picked: list[str] = []

    for s in _extractive_priority_nav_aum(blob, query):
        if s and _is_plausible_sentence(s) and s not in picked:
            picked.append(s)
        if len(picked) >= max_sentences:
            return " ".join(picked)

    for ph in _phrases_from_query(query):
        sn = _snippet_around_phrase(blob, ph)
        if sn and sn not in picked:
            picked.append(sn)
        if len(picked) >= max_sentences:
            return " ".join(picked)

    for pat in (
        r"([^.]{0,80}\b\d{1,2}(?:\.\d+)?\s*%[^.]{0,200}\.)",
        r"([^.]{0,80}\b₹\s*[\d,]+[^.]{0,220}\.)",
        r"([^.]{0,120}\block[- ]?in[^.]{0,200}\.)",
    ):
        m = re.search(pat, blob, re.IGNORECASE)
        if m:
            s = re.sub(r"\s+", " ", m.group(1)).strip()
            if _is_plausible_sentence(s) and s not in picked:
                picked.append(s)
        if len(picked) >= max_sentences:
            return " ".join(picked)

    parts = [s.strip() for s in blob.split(". ") if s.strip()]
    for i in range(len(parts) - 1):
        parts[i] = parts[i] + "."
    qwords = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in _STOP and len(w) > 1}
    scored: list[tuple[int, str]] = []
    for p in parts:
        p = p.strip()
        if not _is_plausible_sentence(p):
            continue
        if p.lower().startswith("http"):
            continue
        words = {w for w in re.findall(r"[a-z0-9]+", p.lower()) if w not in _STOP}
        overlap = len(qwords & words)
        scored.append((overlap + (1 if re.search(r"\d", p) else 0), p))
    scored.sort(key=lambda x: (-x[0], len(x[1])))
    for _, p in scored:
        if p not in picked:
            picked.append(p)
        if len(picked) >= max_sentences:
            break

    return " ".join(picked[:max_sentences]).strip()


def contexts_from_hits(hits: list[SearchHit], *, max_chunks: int) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    ids: list[str] = []
    for h in hits[:max_chunks]:
        t = h.text.strip()
        if not t:
            continue
        texts.append(t)
        ids.append(h.chunk_id)
    return texts, ids


_GROQ_OPENAI_COMPAT_BASE = "https://api.groq.com/openai/v1"
_dotenv_loaded = False


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _ensure_dotenv_loaded() -> None:
    """Load ``<repo>/.env`` once (optional ``python-dotenv``)."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def try_groq_json_answer(
    *,
    query: str,
    evidence_blocks: list[str],
    allowlist_urls: list[str],
    model: str,
    base_url: str | None = None,
    extra_user_instructions: str | None = None,
) -> dict[str, Any] | None:
    """
    Architecture §6.3: low temperature, JSON-only, allowlisted citation, facts-only system prompt.

    Uses **Groq** via the OpenAI-compatible Chat Completions API (see Groq console docs).
    Set ``GROQ_API_KEY`` (environment or a repo-root ``.env`` via python-dotenv);
    optional ``base_url`` defaults to Groq's OpenAI-compatible endpoint.
    """
    _ensure_dotenv_loaded()
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None

    endpoint = (base_url or "").strip() or _GROQ_OPENAI_COMPAT_BASE
    client = OpenAI(api_key=key, base_url=endpoint)
    allow_bullets = "\n".join(f"- {u}" for u in allowlist_urls)
    evidence = "\n\n---\n\n".join(evidence_blocks[:8])
    system = (
        "You are a facts-only mutual fund FAQ assistant for a pilot corpus. "
        "Use ONLY the evidence excerpts. Do not give investment advice, fund comparisons, rankings, "
        "or predictions. Do not fabricate past returns, CAGR, or performance narratives; if the user asks about performance, "
        "answer only with neutral factual attributes present in evidence (e.g. expense ratio). "
        "When the evidence explicitly states snapshot NAV (net asset value) or scheme-level fund size (AUM in ₹ cr), "
        "include those figures in the answer — they are factual attributes, not return claims. "
        "Otherwise say evidence is insufficient. "
        "Do not repeat promotional or suitability language from the source. "
        "Output a single JSON object with keys: "
        "answer (string, at most 3 short sentences), "
        "citation_url (exactly one string copied verbatim from the allowlist), "
        "scheme_id (string pilot id from evidence metadata when clear, else null). "
        "Do not include a 'last updated' line in answer; the application adds the footer. "
        "No markdown, no extra keys."
    )
    user = (
        f"USER_QUESTION:\n{query}\n\nALLOWLIST (citation_url must be one of these, verbatim):\n{allow_bullets}\n\n"
        f"EVIDENCE (excerpts from official crawl):\n{evidence}\n"
    )
    if extra_user_instructions:
        user += f"\nADDITIONAL_INSTRUCTIONS:\n{extra_user_instructions}\n"

    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
