"""Detect when a query asks for facts not present in retrieved pilot corpus evidence."""

from __future__ import annotations

import re
from typing import Any

from phase3.grounding import fund_manager_focus_query, nav_focus_only_query

# Attributes the pilot corpus is designed to answer (Groww scheme pages).
_PILOT_FACT_VOCAB = frozenset(
    """
    nav n.a.v expense ratio ter sip systematic minimum min lumpsum exit load lock lockin
    benchmark manager manages management aum assets size registrar transfer agent risk
    category elss tax saver lock-in inception launch custodian folio direct growth plan
    investment stamp duty sid isin amc rating returns annualised annualized performance
    portfolio holdings dividend benchmark index
    """.split()
)

_QUERY_STOP = frozenset(
    """
    a an the is are was were be been being to of and or for in on at by it as if with this that
    what which how when where who whom whose why tell me about give show please can could
    would should do does did will shall may might must fund mutual scheme plans plan
    hdfc groww pilot
    """.split()
)

_INSUFFICIENT_LLM_RE = re.compile(
    r"\b("
    r"do not contain|does not contain|don't contain|"
    r"not contain enough|insufficient evidence|"
    r"cannot find|can't find|could not find|"
    r"not enough (supported )?information|"
    r"unable to answer|"
    r"retrieved corpus does not"
    r")\b",
    re.IGNORECASE,
)

_FUND_MANAGER_ANSWER_RE = re.compile(
    r"\bfund managers?\b.*\bis\b|\bthe fund manager\b",
    re.IGNORECASE,
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]{2,4})?", (text or "").lower())


def _scheme_strip_patterns(schemes: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    for row in schemes:
        for raw in (
            str(row.get("display_name") or ""),
            str(row.get("category") or ""),
            *list(row.get("query_aliases") or []),
        ):
            t = raw.strip().lower()
            if len(t) >= 3:
                patterns.append(t)
    patterns.sort(key=len, reverse=True)
    return patterns


def extract_focus_terms(query: str, schemes: list[dict[str, Any]]) -> list[str]:
    """
  Terms the user asks about (excluding scheme names and question filler).

  Empty list means a broad scheme question (e.g. "tell me about HDFC Mid Cap").
  """
    q = (query or "").lower()
    for pat in _scheme_strip_patterns(schemes):
        q = q.replace(pat, " ")
    tokens = [t for t in _tokenize(q) if t not in _QUERY_STOP and len(t) >= 2]
    # Drop generic fund words left after alias strip
    tokens = [t for t in tokens if t not in {"mid", "cap", "large", "small", "focused", "flexi", "tax", "saver", "elss"}]
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def evidence_blob(contexts: list[str]) -> str:
    return "\n".join(contexts).lower()


def term_supported(term: str, blob: str) -> bool:
    if term in _PILOT_FACT_VOCAB:
        return True
    if term in blob:
        return True
    if len(term) >= 4 and term[:4] in blob:
        return True
    return False


def query_supported_by_evidence(
    query: str,
    contexts: list[str],
    schemes: list[dict[str, Any]],
) -> bool:
    """
    False when the user names a concept (e.g. "poda") that does not appear in evidence
    and is not a known pilot factual attribute.
    """
    if nav_focus_only_query(query) or fund_manager_focus_query(query):
        return True
    focus = extract_focus_terms(query, schemes)
    if not focus:
        return True
    blob = evidence_blob(contexts)
    return all(term_supported(t, blob) for t in focus)


def example_query_for_scheme(scheme_id: str | None, schemes: list[dict[str, Any]]) -> str:
    sid = (scheme_id or "").strip()
    for row in schemes:
        if str(row.get("scheme_id") or "") == sid:
            name = str(row.get("display_name") or "this fund").strip()
            return f"What is the NAV of {name}?"
    return "What is the NAV of HDFC Mid-Cap Fund Direct Growth?"


def format_insufficient_answer(
    *,
    query: str,
    scheme_id: str | None,
    schemes: list[dict[str, Any]],
) -> str:
    example = example_query_for_scheme(scheme_id, schemes)
    focus = extract_focus_terms(query, schemes)
    topic = " ".join(focus) if focus else "that topic"
    return (
        f"The Groww pilot corpus for this fund does not include information about “{topic}”, "
        f"so I cannot answer that reliably from the retrieved sources. "
        f"Try a factual question that appears on the scheme page, for example: “{example}”"
    )


def llm_answer_indicates_insufficient(answer: str) -> bool:
    return bool(_INSUFFICIENT_LLM_RE.search(answer or ""))


def answer_topic_mismatch(query: str, answer: str, schemes: list[dict[str, Any]]) -> bool:
    """
    Catch answers that discuss fund managers (or other topics) when the user asked for
    something else that is not in the corpus (e.g. "what is poda").
    """
    if fund_manager_focus_query(query) or nav_focus_only_query(query):
        return False
    a = (answer or "").strip()
    if not a:
        return False
    focus = extract_focus_terms(query, schemes)
    if not focus:
        return False
    if _FUND_MANAGER_ANSWER_RE.search(a) and not fund_manager_focus_query(query):
        return True
    low = a.lower()
    if not any(t in low for t in focus):
        # User asked about X but answer never mentions X
        if _FUND_MANAGER_ANSWER_RE.search(a) or re.search(r"\bnav\s+(of|is)\b", a, re.I):
            return True
    return False
