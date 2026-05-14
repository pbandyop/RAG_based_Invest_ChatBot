from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Phase3Response:
    """
    Structured runtime answer (architecture §6 + §9.1 POST /query shape).

    ``evidence`` carries retrieval rows with ``source_url`` and ``fetched_at`` per §6.1.
    """

    refusal: bool
    answer: str
    citation_url: str | None
    last_updated: str | None
    footer_line: str | None
    scheme_id: str | None
    educational_url: str | None
    educational_label: str | None
    refusal_template_key: str | None
    needs_scheme_clarification: bool
    clarification_message: str | None
    generator_route: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    retrieval_scores: list[float] = field(default_factory=list)
    chunk_ids_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "refusal": self.refusal,
            "answer": self.answer,
            "citation_url": self.citation_url,
            "last_updated": self.last_updated,
            "footer_line": self.footer_line,
            "scheme_id": self.scheme_id,
            "educational_url": self.educational_url,
            "educational_label": self.educational_label,
            "refusal_template_key": self.refusal_template_key,
            "needs_scheme_clarification": self.needs_scheme_clarification,
            "clarification_message": self.clarification_message,
            "generator_route": self.generator_route,
            "evidence": self.evidence,
            "retrieval_scores": self.retrieval_scores,
            "chunk_ids_used": self.chunk_ids_used,
        }
