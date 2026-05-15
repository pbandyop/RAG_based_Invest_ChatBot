from __future__ import annotations

import re

from phase3.url_normalize import normalize_citation_url

_FORBIDDEN = re.compile(
    r"\b(you should|i recommend|we recommend|best fund|better fund|"
    r"will outperform|guaranteed return|sure winner)\b",
    re.IGNORECASE,
)

_NAV_WORD = re.compile(r"\b(nav|n\.a\.v\.)\b", re.IGNORECASE)
# If the user also asks for these, the answer may include multiple hero stats.
_OTHER_STAT_WORDS = re.compile(
    r"\b(aum|assets\s+under\s+management|fund\s+size|expense|"
    r"\bratio\b|\bter\b|sip|systematic|exit\s+load|benchmark|"
    r"lock[- ]?in|tax|return|performance|cagr|yield|rating)\b",
    re.IGNORECASE,
)


def nav_focus_only_query(query: str) -> bool:
    """
    True when the question is NAV-centric and does not ask for other scheme stats
    (AUM, expense, SIP, etc.). Used to keep answers tight for RAG output.
    """
    q = query or ""
    if not _NAV_WORD.search(q):
        return False
    if _OTHER_STAT_WORDS.search(q):
        return False
    return True


def sentence_count(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    parts = re.split(r"(?<=[.!?])\s+", t)
    return len([p for p in parts if p.strip()])


def prefer_fact_span(answer: str, query: str) -> str:
    """When possible, keep a tight span matching the user's factual intent."""
    a = (answer or "").strip()
    q = (query or "").lower()
    if not a:
        return a
    if "expense" in q and "ratio" in q:
        for pat in (
            r"([^.]{0,200}total\s+expense\s+ratio[^.]{0,360}\d[\d.,]*\s*%[^.]{0,160}\.)",
            r"([^.]{0,200}expense\s+ratio[^.]{0,380}\d[\d.,]*\s*%[^.]{0,160}\.)",
            r"([^.]{0,200}\bter\b[^.]{0,280}\d[\d.,]*\s*%[^.]{0,160}\.)",
        ):
            m = re.search(pat, a, re.IGNORECASE | re.DOTALL)
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip()
    if "exit" in q and "load" in q:
        m = re.search(r"([^.]{0,120}exit\s+load[^.]{0,320}\.)", a, re.IGNORECASE | re.DOTALL)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    if "minimum" in q and "sip" in q:
        m = re.search(r"([^.]{0,120}minimum[^.]{0,320}sip[^.]{0,220}\.)", a, re.IGNORECASE | re.DOTALL)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    if "lock" in q:
        m = re.search(r"([^.]{0,120}lock[^.]{0,260}\.)", a, re.IGNORECASE | re.DOTALL)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    if re.search(r"\b(nav|n\.a\.v\.)\b", q):
        if nav_focus_only_query(q):
            m = re.search(r"\bnav\s*:\s*.+?₹[\d,\s\.]+", a, re.IGNORECASE | re.DOTALL)
            if m:
                s = re.sub(r"\s+", " ", m.group(0)).strip()
                if not s.endswith("."):
                    s += "."
                return s
            m = re.search(r"\bnav\s*:\s*[^.]{8,120}\.", a, re.IGNORECASE | re.DOTALL)
            if m:
                s = re.sub(r"\s+", " ", m.group(0)).strip()
                low = s.lower()
                if "fund size" not in low and "aum" not in low and "expense" not in low and "sip" not in low:
                    return s
        m = re.search(r"(\bnav\s*:\s*.+?min\.)", a, re.IGNORECASE | re.DOTALL)
        if m:
            frag = re.sub(r"\s+", " ", m.group(1)).strip()
            if nav_focus_only_query(q):
                frag_l = frag.lower()
                if "fund size" in frag_l or "sip" in frag_l or "aum" in frag_l or "expense" in frag_l:
                    m2 = re.search(r"\bnav\s*:\s*.+?₹[\d,\s\.]+", a, re.IGNORECASE | re.DOTALL)
                    if m2:
                        s2 = re.sub(r"\s+", " ", m2.group(0)).strip()
                        return s2 + ("." if not s2.endswith(".") else "")
            return frag
        m = re.search(r"(\bnav\s*:\s*.{12,280}\.)", a, re.IGNORECASE | re.DOTALL)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    if re.search(r"\b(aum|assets under management|fund size)\b", q):
        m = re.search(
            r"(\bfund\s+size\s*\(\s*aum\s*\)\s*₹[\d,\s\.]+\s*cr\b\.?)",
            a,
            re.IGNORECASE,
        )
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    if re.search(r"\b(fund\s+management|fund\s+manager|who\s+manages)\b", q):
        m = re.search(
            r"([^.]{0,100}\b(current\s+)?fund\s+manager\b[^.]{0,480}\.)",
            a,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return a


def polish_answer_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^#+\s*", "", t)
    t = re.sub(r"\\+\s*n", " ", t, flags=re.IGNORECASE)
    t = re.sub(r'"\s+', "", t)
    t = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Start at first letter to drop stray punctuation / quotes
    m = re.search(r"[A-Za-z₹]", t)
    if m:
        t = t[m.start() :]
    return t


def truncate_to_max_sentences(text: str, max_sentences: int = 3) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", t)
    acc: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        acc.append(p)
        if len(acc) >= max_sentences:
            break
    return " ".join(acc)


def grounding_ok(
    *,
    answer: str,
    citation_url: str,
    allowlist: set[str],
    scheme_id: str | None,
    scheme_id_to_citation: dict[str, str],
) -> tuple[bool, str | None]:
    if _FORBIDDEN.search(answer):
        return False, "forbidden_phrase"
    if sentence_count(answer) > 3:
        return False, "too_many_sentences"
    cu = normalize_citation_url(citation_url)
    if cu not in allowlist:
        return False, "citation_not_allowlisted"
    if scheme_id:
        expected = scheme_id_to_citation.get(scheme_id)
        if expected and normalize_citation_url(expected) != cu:
            return False, "citation_scheme_mismatch"
    return True, None
