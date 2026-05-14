from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GuardResult:
    """Phase 4 pre-retrieval guard outcome (architecture §7.1)."""

    refusal_template_key: str | None
    reason: str | None = None


_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR_LIKE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PII_VERB = re.compile(
    r"\b(share|send|verify|confirm)\s+(my\s+)?(pan|aadhaar|aadhar|otp|account\s+number|"
    r"bank\s+account|upi\s+pin|password)\b",
    re.IGNORECASE,
)

# E4.2 / policy boundary — do not retrieve on manipulation prompts.
_JAILBREAK = re.compile(
    r"\b(ignore (all |your )?(previous|prior|above) (instructions|rules)|"
    r"disregard (the )?(system|safety|content) (prompt|rules|policy)|"
    r"you are now (a |an )?(unrestricted|uncensored)|"
    r"pretend you are|bypass (your )?rules|"
    r"developer mode|jailbreak|DAN mode)\b",
    re.IGNORECASE,
)

# E4.5 — personalized tax / ITR guidance (not in-scope factual scheme FAQ).
_TAX_PERSONALIZED = re.compile(
    r"\b(how much tax (will|would|should) i|tax (i will|i'd) owe|"
    r"tax (on|for) my (income|salary|capital gains)|"
    r"for my (income )?bracket|my tax slab|"
    r"(should|must) i file (itr|returns)|"
    r"optimize my tax|tax advice for me)\b",
    re.IGNORECASE,
)

_ADVISORY = re.compile(
    r"\b(should i|shall i|must i|would you recommend|which fund is better|which scheme is better|"
    r"which is better|best fund|best mf|better than|outperform|beat the index|"
    r"is it a good idea to invest|where should i invest|recommend (a |the )?fund|"
    r"invest or not|good for my|suitable for me|hypothetically,? which (fund|scheme))\b",
    re.IGNORECASE,
)

# E4.4 / §7.1(3) — no return numbers or predictions from the assistant.
_PERFORMANCE = re.compile(
    r"\b(what return will|expected return|cagr|xirr|predict|forecast|"
    r"will (this|the) fund (beat|double|give)|next year'?s? return|"
    r"(past|last|previous) (year'?s? )?returns?|"
    r"\breturns? (in|for) (20\d{2}|last year|the last year)|"
    r"\bhow much did (it|this fund|the fund) return\b|"
    r"\b1[\s-]?year return\b|\b3[\s-]?year return\b|\bytd returns?\b)\b",
    re.IGNORECASE,
)


def evaluate_query_guard(query: str) -> GuardResult:
    """
    Layered rule guard before retrieval (architecture §7.1).

    Order: empty → PII patterns → jailbreak → personalized tax → advisory → performance.
    """
    q = (query or "").strip()
    if not q:
        return GuardResult("refusal_out_of_corpus", "empty")

    if _PAN.search(q) or _AADHAAR_LIKE.search(q) or _PII_VERB.search(q):
        return GuardResult("refusal_no_pii", "pii_pattern")

    if _JAILBREAK.search(q):
        return GuardResult("refusal_advisory", "policy_boundary")

    if _TAX_PERSONALIZED.search(q):
        return GuardResult("refusal_advisory", "tax_personalized")

    if _ADVISORY.search(q):
        return GuardResult("refusal_advisory", "advisory")

    if _PERFORMANCE.search(q):
        return GuardResult("refusal_performance_or_educational_pointer", "performance")

    return GuardResult(None)
