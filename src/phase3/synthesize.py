from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from phase2.retrieve import SearchHit
from phase3.grounding import (
    fund_manager_focus_query,
    nav_focus_only_query,
    polish_answer_text,
    prefer_fact_span,
    truncate_to_max_sentences,
)

_log = logging.getLogger(__name__)

_STOP = frozenset(
    "a an the is are was were be been being to of and or for in on at by it as if with this that "
    "what which how when where who from".split(),
)

# Groww scheme-page hero: ``nav : 14 may'26 ₹1, 436. 63 min. for sip …``
_GROWW_NAV_HERO_RE = re.compile(
    r"\bnav\s*:\s*"
    r"(\d{1,2}\s+[a-z]{3}\s*'?\s*\d{2,4})"
    r"\s*₹\s*([\d,\s\.]+)",
    re.IGNORECASE,
)

_MONTH_ABBR_TO_NAME = {
    "jan": "January",
    "feb": "February",
    "mar": "March",
    "apr": "April",
    "may": "May",
    "jun": "June",
    "jul": "July",
    "aug": "August",
    "sep": "September",
    "oct": "October",
    "nov": "November",
    "dec": "December",
}


@dataclass(frozen=True)
class NavFact:
    """NAV value and as-of date parsed from a Groww scheme-page hero line in EVIDENCE."""

    amount_inr: str
    as_of_display: str
    source_line: str


@dataclass(frozen=True)
class FundManagementFact:
    """Fund manager name(s) from Groww Fund Management (``fund_manager_details`` / person_name)."""

    names: tuple[str, ...]


# Groww JSON in crawl: ``" person _ name " : " amar kalkundrikar "`` inside ``fund_manager_details``.
_PERSON_NAME_IN_DETAILS_RE = re.compile(
    r'person\s*_\s*name\s*"\s*:\s*"\s*([a-z][a-z\s\.\-]{1,80}?)\s*"',
    re.IGNORECASE,
)


def _normalize_inr_amount(raw: str) -> str:
    """Collapse Groww spacing (``1, 436. 33``) and format as ``₹1,436.33``."""
    compact = re.sub(r"\s+", "", (raw or "").strip()).lstrip("₹")
    num = re.sub(r"[^\d.]", "", compact)
    if not num:
        return ""
    try:
        return f"₹{float(num):,.2f}"
    except ValueError:
        return f"₹{compact}" if compact else ""


def _groww_nav_as_of_display(raw: str) -> str | None:
    """``14 may'26`` / ``15 - may - 2026`` → ``14 May 2026`` (scheme as-of, not ``fetched_at``)."""
    t = re.sub(r"[-\s]+", " ", (raw or "").strip().lower())
    t = t.replace("'", " ")
    m = re.match(r"(\d{1,2})\s+([a-z]{3})\s*(\d{2,4})", t)
    if not m:
        return None
    day = int(m.group(1))
    mon_key = m.group(2)[:3]
    month_name = _MONTH_ABBR_TO_NAME.get(mon_key)
    if not month_name:
        return None
    year = int(m.group(3))
    if year < 100:
        year += 2000
    return f"{day} {month_name} {year}"


def _nav_as_of_sort_key(display: str) -> tuple[int, int, int]:
    """Sort key for picking the newest NAV as-of date in evidence."""
    parts = (display or "").split()
    if len(parts) != 3:
        return (0, 0, 0)
    day = int(parts[0]) if parts[0].isdigit() else 0
    year = int(parts[2]) if parts[2].isdigit() else 0
    month_name = parts[1].lower()
    month_num = 0
    for i, full in enumerate(_MONTH_ABBR_TO_NAME.values(), start=1):
        if full.lower() == month_name:
            month_num = i
            break
    return (year, month_num, day)


# Groww page JSON: ``"nav" : 1436.329, "nav_date" : "15 - may - 2026"``
_NAV_JSON_PAIR_RE = re.compile(
    r'"nav\s*"\s*:\s*([\d.\s,]+)\s*,\s*"nav\s*_\s*date\s*"\s*:\s*"\s*([^"]+?)\s*"',
    re.IGNORECASE,
)

# Schema / FAQ prose (lower priority than hero or JSON).
_NAV_PROSE_RE = re.compile(
    r"\bthe\s+nav\b[^.]{0,220}?₹\s*([\d,\s\.]+)\s+as\s+of\s+(\d{1,2}\s+[a-z]{3,9}\s+\d{4})",
    re.IGNORECASE,
)
# Groww about blurb: ``Latest NAV as of 18 May 2026 is ₹1,430.78``
_NAV_PROSE_AS_OF_IS_RE = re.compile(
    r"\b(?:latest\s+)?nav\b[^.]{0,160}?\bas\s+of\s+(\d{1,2}\s+[a-z]{3,9}\s+\d{4})\s+is\s+₹\s*([\d,\s\.]+)",
    re.IGNORECASE,
)


def _nav_fact_from_match(m: re.Match[str]) -> NavFact | None:
    as_of_display = _groww_nav_as_of_display(m.group(1))
    amount_inr = _normalize_inr_amount(m.group(2))
    if not as_of_display or not amount_inr:
        return None
    source_line = re.sub(r"\s+", " ", m.group(0)).strip()
    return NavFact(amount_inr=amount_inr, as_of_display=as_of_display, source_line=source_line)


def _nav_facts_from_blob(blob: str) -> tuple[list[NavFact], list[NavFact], list[NavFact]]:
    """Return (hero, json_pair, prose) NAV facts found in one text blob."""
    heroes: list[NavFact] = []
    json_pairs: list[NavFact] = []
    prose: list[NavFact] = []

    for m in _GROWW_NAV_HERO_RE.finditer(blob):
        fact = _nav_fact_from_match(m)
        if fact:
            heroes.append(fact)

    for m in _NAV_JSON_PAIR_RE.finditer(blob):
        as_of = _groww_nav_as_of_display(m.group(2))
        amount = _normalize_inr_amount(m.group(1))
        if as_of and amount:
            src = re.sub(r"\s+", " ", m.group(0)).strip()
            json_pairs.append(NavFact(amount_inr=amount, as_of_display=as_of, source_line=src))

    for m in _NAV_PROSE_RE.finditer(blob):
        as_of = _groww_nav_as_of_display(m.group(2))
        amount = _normalize_inr_amount(m.group(1))
        if as_of and amount:
            src = re.sub(r"\s+", " ", m.group(0)).strip()
            prose.append(NavFact(amount_inr=amount, as_of_display=as_of, source_line=src))

    for m in _NAV_PROSE_AS_OF_IS_RE.finditer(blob):
        as_of = _groww_nav_as_of_display(m.group(1))
        amount = _normalize_inr_amount(m.group(2))
        if as_of and amount:
            src = re.sub(r"\s+", " ", m.group(0)).strip()
            prose.append(NavFact(amount_inr=amount, as_of_display=as_of, source_line=src))

    return heroes, json_pairs, prose


def _pick_latest_nav(facts: list[NavFact]) -> NavFact | None:
    if not facts:
        return None
    return max(facts, key=lambda f: _nav_as_of_sort_key(f.as_of_display))


def extract_nav_fact_from_contexts(contexts: list[str]) -> NavFact | None:
    """
    Parse NAV from Groww scheme-page evidence.

    Priority: visible hero ``nav : <date> ₹…`` (newest date if several), then JSON
    ``nav`` + ``nav_date``, then FAQ prose. Ignores stale FAQ if a newer hero exists.
    """
    heroes: list[NavFact] = []
    json_pairs: list[NavFact] = []
    prose: list[NavFact] = []

    for c in contexts:
        blob = _prepare_blob([c])
        h, j, p = _nav_facts_from_blob(blob)
        heroes.extend(h)
        json_pairs.extend(j)
        prose.extend(p)

    picked = _pick_latest_nav(heroes)
    if picked:
        return picked
    picked = _pick_latest_nav(json_pairs)
    if picked:
        return picked
    return _pick_latest_nav(prose)


def extract_nav_fact_from_hits(hits: list[Any]) -> NavFact | None:
    """Parse NAV from all retrieved chunks (not only the first context slice)."""
    texts = [str(h.text or "") for h in hits if str(h.text or "").strip()]
    return extract_nav_fact_from_contexts(texts)


def _normalize_person_name(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip().lower())
    if not s:
        return ""
    return " ".join(part.capitalize() for part in s.split())


def extract_fund_managers_from_contexts(contexts: list[str]) -> FundManagementFact | None:
    """
    Parse manager names from Groww Fund Management JSON (``person_name`` in crawl chunks).

    Ignores stale top-level ``fund_manager`` strings (e.g. old single-name metadata).
    """
    ordered: list[str] = []
    seen: set[str] = set()

    for c in contexts:
        blob = _prepare_blob([c])
        for m in _PERSON_NAME_IN_DETAILS_RE.finditer(blob):
            name = _normalize_person_name(m.group(1))
            key = name.lower()
            if len(name) < 4 or key in seen:
                continue
            seen.add(key)
            ordered.append(name)

    if ordered:
        if len(ordered) > 1:
            ordered = sorted(ordered, key=str.lower)
        return FundManagementFact(names=tuple(ordered))

    # Fallback: compare-section bios (``education mr. kalkundrikar`` / ``education mr. dhruv``).
    blob = _prepare_blob(contexts)
    for m in re.finditer(
        r"\beducation\s+mr\.?\s+([a-z][a-z\-]{2,40})\b",
        blob,
        re.IGNORECASE,
    ):
        fragment = m.group(1).lower()
        if fragment in ("dhruv",):
            name = "Dhruv Muchhal"
        elif "kalkundrikar" in fragment or fragment in ("kalkundrikar", "amar"):
            name = "Amar Kalkundrikar"
        else:
            name = _normalize_person_name(fragment)
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            ordered.append(name)

    if ordered:
        return FundManagementFact(names=tuple(ordered))
    return None


def fund_label_for_answer(
    *,
    query: str,
    scheme_id: str | None,
    schemes: list[dict[str, Any]],
) -> str:
    q = query or ""
    for pat in (
        r"\b(?:nav|n\.a\.v\.)\b.*?\b(?:of|for)\s+(.+?)(?:\?|$)",
        r"\bfund\s+managers?\b.*?\b(?:of|for)\s+(.+?)(?:\?|$)",
        r"\bwho\s+manages\b\s+(.+?)(?:\?|$)",
    ):
        m = re.search(pat, q, re.IGNORECASE | re.DOTALL)
        if m:
            label = m.group(1).strip().rstrip("?.,")
            if label:
                return label
    if scheme_id:
        for row in schemes:
            if str(row.get("scheme_id") or "") == scheme_id:
                dn = str(row.get("display_name") or "").strip()
                if dn:
                    return dn
    return "the fund"


def fund_label_for_nav_answer(
    *,
    query: str,
    scheme_id: str | None,
    schemes: list[dict[str, Any]],
) -> str:
    return fund_label_for_answer(query=query, scheme_id=scheme_id, schemes=schemes)


def format_nav_answer(fund_label: str, fact: NavFact) -> str:
    label = (fund_label or "the fund").strip()
    return f"The NAV of {label} is {fact.amount_inr} as of {fact.as_of_display}."


def format_fund_manager_answer(fund_label: str, fact: FundManagementFact) -> str:
    label = (fund_label or "the fund").strip()
    names = fact.names
    if not names:
        return ""
    if len(names) == 1:
        return f"The fund manager of {label} is {names[0]}."
    if len(names) == 2:
        return f"The fund managers of {label} are {names[0]} and {names[1]}."
    body = ", ".join(names[:-1]) + f", and {names[-1]}"
    return f"The fund managers of {label} are {body}."


def shape_answer_for_query(
    query: str,
    answer_text: str,
    *,
    nav_fact: NavFact | None = None,
    manager_fact: FundManagementFact | None = None,
    fund_label: str | None = None,
) -> str:
    """Truncate, polish, intent-based span; grounded fund-manager facts may override LLM prose."""
    label = fund_label or "the fund"
    if fund_manager_focus_query(query) and manager_fact is not None and manager_fact.names:
        return format_fund_manager_answer(label, manager_fact)
    out = truncate_to_max_sentences(answer_text, 3)
    out = polish_answer_text(out)
    out = prefer_fact_span(out, query)
    if nav_focus_only_query(query):
        out = truncate_to_max_sentences(out, 1)
    return out


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
    # Groww NAV / scheme AUM / expense ratio rows can be digit-heavy but factual.
    if re.search(r"\bnav\s*:", low) or re.search(r"\bfund\s+size\s*\(\s*aum\s*\)", low) or re.search(r"\btotal\s+aum\b", low):
        return ratio > 0.16 and len(p) >= 20
    if re.search(r"\b(expense\s+ratio|ter)\b", low) and re.search(r"\d[\d.,]*\s*%", p):
        return ratio > 0.12 and len(p) >= 14
    return False


def _extractive_priority_expense_ratio(blob: str, query: str) -> list[str]:
    """Pull expense ratio / TER lines when the question asks for them (Groww crawl shape)."""
    q = (query or "").lower()
    if "expense" not in q or "ratio" not in q:
        return []
    out: list[str] = []
    # Groww inserts spaces inside decimals (``0. 75 %``); older ``[^.]`` patterns stopped at the dot.
    for pat in (
        r"\b(?:total\s+)?expense\s+ratio\s*:?\s+[\d\s.,]+%",
        r"\blower\s+expense\s+ratio\s*:?\s+[\d\s.,]+%",
        r"\bter\s*:?\s+[\d\s.,]+%",
    ):
        for m in re.finditer(pat, blob, re.IGNORECASE):
            span = m.group(0)
            if "expense _ ratio" in span:
                continue
            s = re.sub(r"\s+", " ", span).strip()
            digits = re.sub(r"\s+", "", s)
            if not re.search(r"\d", digits):
                continue
            if not s.endswith("."):
                s += "."
            if _is_plausible_sentence(s) and s not in out:
                out.append(s)
            if len(out) >= 3:
                return out
    return out


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


def _extractive_priority_fund_manager(blob: str, query: str) -> list[str]:
    """Pull manager answer when the question asks (Fund Management names from crawl)."""
    if not fund_manager_focus_query(query):
        return []
    fact = extract_fund_managers_from_contexts([blob])
    if fact and fact.names:
        return [format_fund_manager_answer("the fund", fact)]
    out: list[str] = []
    for pat in (
        r"\b[^.]{10,520}\b(current\s+)?fund\s+manager\b[^.]{0,460}\.",
        r"\b[^.]{20,620}also manages these schemes[^.]{0,560}\.",
    ):
        for m in re.finditer(pat, blob, re.IGNORECASE | re.DOTALL):
            s = re.sub(r"\s+", " ", m.group(0)).strip()
            if _is_plausible_sentence(s) and s not in out:
                out.append(s)
            if len(out) >= 3:
                return out
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


def _extractive_nav_only(blob: str) -> str | None:
    """Single Groww-style NAV line; avoids pulling SIP/AUM from the same hero blob."""
    m = re.search(r"\bnav\s*:\s*.+?₹[\d,\s\.]+", blob, re.IGNORECASE | re.DOTALL)
    if m:
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        if not s.endswith("."):
            s += "."
        if _is_plausible_sentence(s):
            return s
    m = re.search(r"\bnav\s*:\s*[^.]{8,120}\.", blob, re.IGNORECASE | re.DOTALL)
    if m:
        s = re.sub(r"\s+", " ", m.group(0)).strip()
        low = s.lower()
        if any(x in low for x in ("fund size", "aum", "expense", "sip")):
            return None
        if _is_plausible_sentence(s):
            return s
    return None


def _extractive_from_contexts(query: str, contexts: list[str], max_sentences: int = 3) -> str:
    blob = _prepare_blob(contexts)

    if nav_focus_only_query(query):
        only = _extractive_nav_only(blob)
        if only:
            return only

    picked: list[str] = []

    for s in _extractive_priority_expense_ratio(blob, query):
        if s and _is_plausible_sentence(s) and s not in picked:
            picked.append(s)
        if len(picked) >= max_sentences:
            return " ".join(picked)

    for s in _extractive_priority_nav_aum(blob, query):
        if s and _is_plausible_sentence(s) and s not in picked:
            picked.append(s)
        if len(picked) >= max_sentences:
            return " ".join(picked)

    for s in _extractive_priority_fund_manager(blob, query):
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
    # ``override=True``: a defined-but-empty ``GROQ_API_KEY`` in the process env must not
    # block values from the repo-root ``.env`` (python-dotenv default is no override).
    load_dotenv(_REPO_ROOT / ".env", override=True)


def _normalize_groq_api_key() -> str | None:
    """Return stripped API key from the environment after loading repo ``.env``."""
    _ensure_dotenv_loaded()
    raw = (os.environ.get("GROQ_API_KEY") or "").strip()
    if raw.startswith("\ufeff"):
        raw = raw.lstrip("\ufeff")
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()
    return raw or None


def _groq_retry_after_seconds(error_body: str) -> float | None:
    """Parse Groq / OpenAI-style rate-limit hint (seconds or minutes+seconds)."""
    t = (error_body or "")[:1200]
    m = re.search(r"try again in (\d+)\s*m\s*([\d.]+)\s*s", t, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.search(r"try again in ([\d.]+)\s*s", t, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return None


def _groq_chat_completions_http(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    json_object_mode: bool,
) -> str:
    """OpenAI-compatible ``/v1/chat/completions`` POST (stdlib only; no ``openai`` package)."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "messages": messages,
    }
    if json_object_mode:
        payload["response_format"] = {"type": "json_object"}
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Groq is behind Cloudflare; the default ``Python-urllib/x.y`` UA is often blocked (HTTP 403).
        "User-Agent": "OpenAI/Python 1.0 (NextLeapGroww/phase3; +https://github.com/pbandyop/RAG_based_Invest_ChatBot)",
    }
    max_attempts = 3
    last_detail = ""
    for attempt in range(max_attempts):
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_detail = e.read().decode("utf-8", errors="replace")[:800]
            _log.warning("Groq HTTP %s %s: %s", e.code, url, last_detail)
            if e.code == 429 and attempt < max_attempts - 1:
                hint = _groq_retry_after_seconds(last_detail)
                if hint is not None and hint > 90:
                    _log.warning(
                        "Groq rate limit retry-after is %.0fs (>90s); skipping extra HTTP retries for model=%s",
                        hint,
                        model,
                    )
                    raise
                wait = 3.0 if hint is None else min(max(hint, 1.0), 20.0)
                _log.info("Groq 429: sleeping %.1fs then HTTP retry %s/%s", wait, attempt + 2, max_attempts)
                time.sleep(wait)
                continue
            raise
        else:
            choices = body.get("choices") or []
            if not choices:
                raise ValueError("Groq response missing choices")
            msg = (choices[0].get("message") or {}) if isinstance(choices[0], dict) else {}
            return str(msg.get("content") or "").strip()
    raise RuntimeError("Groq HTTP: unexpected retry loop exit")


def groq_api_configured() -> bool:
    """True when a Groq API key is available (env or repo-root ``.env`` via dotenv)."""
    return _normalize_groq_api_key() is not None


def try_groq_json_answer(
    *,
    query: str,
    evidence_blocks: list[str],
    allowlist_urls: list[str],
    model: str,
    base_url: str | None = None,
    extra_user_instructions: str | None = None,
    nav_fact: NavFact | None = None,
    manager_fact: FundManagementFact | None = None,
    fund_label: str | None = None,
) -> dict[str, Any] | None:
    """
    Architecture §6.3: low temperature, JSON-only, allowlisted citation, facts-only system prompt.

    Uses **Groq** via the OpenAI-compatible Chat Completions API (see Groq console docs).
    Set ``GROQ_API_KEY`` (environment or a repo-root ``.env`` via python-dotenv);
    optional ``base_url`` defaults to Groq's OpenAI-compatible endpoint.
    """
    _ensure_dotenv_loaded()
    key = _normalize_groq_api_key()
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None  # type: ignore[misc, assignment]

    endpoint = (base_url or "").strip() or _GROQ_OPENAI_COMPAT_BASE
    allow_bullets = "\n".join(f"- {u}" for u in allowlist_urls)
    evidence = "\n\n---\n\n".join(evidence_blocks[:8])
    system = (
        "You are a facts-only mutual fund FAQ assistant (RAG). Your only source is the EVIDENCE block below — "
        "plain text and embedded JSON fragments from a fixed crawl. Do not use outside knowledge, the open web, "
        "or guesses. Do not give investment advice, fund comparisons, rankings, or predictions. "
        "Do not invent numbers, dates, names, or policies. "
        "If the USER_QUESTION asks about past returns, CAGR, or performance stories, only repeat neutral factual "
        "lines that literally appear in EVIDENCE (e.g. stated ratios or labels); never fabricate performance. "
        "Answer policy: Read the USER_QUESTION and decide what factual information is being requested. "
        "If one or more EVIDENCE excerpts clearly contain that information (including facts buried inside JSON-like "
        "strings, manager names, AMC lines, NAV, AUM, fees, loads, lock-in, registrar, etc.), answer in at most "
        "three short neutral sentences using only those supported facts. "
        "**NAV-only:** If the USER_QUESTION asks only for NAV / N.A.V. and does not ask for other statistics "
        "(AUM, fund size, expense ratio, minimum SIP, TER, etc.), the answer must state only the NAV fact from "
        "EVIDENCE — typically one short sentence — and must not add AUM, SIP minimums, expense ratio, or other "
        "hero stats even when they appear in the same excerpt. "
        "For NAV, the as-of date must be the date printed next to ``nav :`` on the scheme page in EVIDENCE "
        "(e.g. ``14 may'26``), not today's date, not ``fetched_at`` metadata, and not invented dates. "
        "The NAV amount must match the ₹ figure on that same ``nav :`` line. "
        "**Fund manager:** For who manages a scheme, use names from the Groww **Fund Management** section in "
        "EVIDENCE — the ``fund_manager_details`` list with ``person_name`` entries. List every current manager "
        "shown there. Do **not** use stale top-level ``fund_manager`` metadata strings if ``fund_manager_details`` "
        "or Fund Management headings list different people. "
        "If the USER_QUESTION names a term or concept that does not appear in EVIDENCE (for example an unknown "
        "abbreviation or attribute), do not answer with a different fact from EVIDENCE (such as fund manager or NAV). "
        "If the requested information does not appear in any excerpt (or only appears in a way you cannot state "
        "faithfully without adding unsupported detail), respond with a single sentence that the evidence is "
        "insufficient — e.g. that the retrieved corpus does not contain enough to answer. "
        "Do not copy long marketing or suitability wording from the source. "
        "Output a single JSON object with keys: "
        "answer (string, at most 3 short sentences), "
        "citation_url (exactly one string copied verbatim from the allowlist), "
        "scheme_id (string pilot id from evidence metadata when clear, else null). "
        "Do not include a 'last updated' line in answer; the application adds the footer. "
        "No markdown, no extra keys."
    )
    user = (
        f"USER_QUESTION:\n{query}\n\n"
        "RAG_TASK: The EVIDENCE block below was retrieved from a vector index over the pilot corpus (embedding "
        "search over scheme-page chunks). Write the answer by combining the USER_QUESTION with only facts supported "
        "by that EVIDENCE — paraphrase or quote short spans; do not use general web knowledge or invent details.\n\n"
        f"ALLOWLIST (citation_url must be one of these, verbatim):\n{allow_bullets}\n\n"
        f"EVIDENCE (retrieved excerpts):\n{evidence}\n"
    )
    if nav_focus_only_query(query):
        user += (
            "\nFOCUS_NAV_ONLY: The user asked about NAV only. Reply with only the NAV in one short sentence. "
            "Use the as-of date from the scheme-page ``nav : …`` line in EVIDENCE (not fetched_at). "
            "Omit AUM, minimum SIP, expense ratio, and every other statistic.\n"
        )
        if nav_fact is not None:
            label = (fund_label or "the fund").strip()
            user += (
                f"\nCANONICAL_NAV_FROM_SCHEME_PAGE (use this NAV amount and as-of date exactly; do not change digits or date):\n"
                f"The NAV of {label} is {nav_fact.amount_inr} as of {nav_fact.as_of_display}.\n"
                f"Parsed from evidence line: {nav_fact.source_line}\n"
            )
    if fund_manager_focus_query(query):
        user += (
            "\nFOCUS_FUND_MANAGER: The user asked who manages the fund. Use only the Fund Management section "
            "(``fund_manager_details`` / ``person_name``). Ignore outdated single ``fund_manager`` JSON fields "
            "when details list other names.\n"
        )
        if manager_fact is not None and manager_fact.names:
            label = (fund_label or "the fund").strip()
            canonical = format_fund_manager_answer(label, manager_fact)
            names_line = ", ".join(manager_fact.names)
            user += (
                f"\nCANONICAL_FUND_MANAGEMENT (use these manager name(s) exactly; include all listed):\n"
                f"{canonical}\n"
                f"Managers from Fund Management evidence: {names_line}\n"
            )
    if extra_user_instructions:
        user += f"\nADDITIONAL_INSTRUCTIONS:\n{extra_user_instructions}\n"

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    raw = ""
    if OpenAI is not None:
        try:
            client = OpenAI(api_key=key, base_url=endpoint)
            _log.info("Groq chat.completions (openai SDK) model=%s endpoint=%s", model, endpoint)
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=messages,
            )
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            _log.warning("Groq OpenAI SDK failed (%s): %s; falling back to HTTP", type(e).__name__, e)

    if not raw:
        try:
            _log.info("Groq chat.completions (urllib HTTP) model=%s endpoint=%s", model, endpoint)
            raw = _groq_chat_completions_http(
                api_key=key,
                base_url=endpoint,
                model=model,
                messages=messages,
                json_object_mode=True,
            )
        except Exception as e:
            _log.warning("Groq HTTP chat.completions failed (%s): %s", type(e).__name__, e)
            return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Model occasionally returns JSON wrapped in fences or prose; retry once without json_object mode.
    raw_retry = ""
    if OpenAI is not None:
        try:
            client = OpenAI(api_key=key, base_url=endpoint)
            _log.info("Groq retry without json_object mode (openai SDK) model=%s", model)
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=messages
                + [
                    {
                        "role": "user",
                        "content": "Your previous reply was not valid JSON. Reply with ONE raw JSON object only, same keys as before.",
                    }
                ],
            )
            raw_retry = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            _log.warning("Groq JSON retry (SDK) failed (%s): %s", type(e).__name__, e)
    if not raw_retry:
        try:
            _log.info("Groq retry without json_object mode (urllib HTTP) model=%s", model)
            raw_retry = _groq_chat_completions_http(
                api_key=key,
                base_url=endpoint,
                model=model,
                messages=messages
                + [
                    {
                        "role": "user",
                        "content": "Your previous reply was not valid JSON. Reply with ONE raw JSON object only, same keys as before.",
                    }
                ],
                json_object_mode=False,
            )
        except Exception as e:
            _log.warning("Groq JSON retry (HTTP) failed (%s): %s", type(e).__name__, e)
            raw_retry = ""
    if raw_retry:
        try:
            return json.loads(raw_retry)
        except json.JSONDecodeError:
            _log.warning("Groq returned non-JSON after retry; first 240 chars: %s", raw_retry[:240])
    else:
        _log.warning("Groq returned non-JSON; first 240 chars: %s", raw[:240])
    return None
