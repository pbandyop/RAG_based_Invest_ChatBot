"""Unit tests for pilot corpus support detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from phase3.corpus_support import (  # noqa: E402
    answer_topic_mismatch,
    extract_focus_terms,
    format_insufficient_answer,
    query_supported_by_evidence,
)


def _schemes() -> list[dict]:
    p = ROOT / "config" / "phase0" / "schemes.json"
    with p.open(encoding="utf-8") as f:
        doc = json.load(f)
    return list(doc.get("schemes") or [])


def test_poda_not_supported() -> None:
    schemes = _schemes()
    q = "What is poda of HDFC mid cap fund?"
    focus = extract_focus_terms(q, schemes)
    assert "poda" in focus
    contexts = ["The fund managers of HDFC Mid-Cap Fund are Chirag Setalvad."]
    assert not query_supported_by_evidence(q, contexts, schemes)


def test_nav_query_supported() -> None:
    schemes = _schemes()
    q = "What is the NAV of HDFC Mid-Cap Fund Direct Growth?"
    assert query_supported_by_evidence(q, ["nav : 1430.78"], schemes)


def test_manager_mismatch_detected() -> None:
    schemes = _schemes()
    q = "What is poda of HDFC mid cap fund?"
    ans = "The fund manager of HDFC Mid Cap Fund Direct Growth is Chirag Setalvad."
    assert answer_topic_mismatch(q, ans, schemes)


def test_insufficient_answer_has_example() -> None:
    schemes = _schemes()
    text = format_insufficient_answer(
        query="What is poda of HDFC mid cap fund?",
        scheme_id="hdfc_mid_cap_direct_growth",
        schemes=schemes,
    )
    assert "poda" in text.lower()
    assert "NAV" in text
