from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from phase2.retrieve import IndexBundle, load_index_bundle
from phase3.grounding import fund_manager_focus_query, grounding_ok, nav_focus_only_query
from phase3.models import Phase3Response
from phase3.phase0_config import Phase0RuntimeConfig, load_phase0_runtime
from phase3.query_guard import GuardResult, evaluate_query_guard
from phase3.retrieval_utils import (
    dedupe_hits_by_source_url,
    hit_evidence_record,
    infer_scheme_id_from_query,
    load_phase3_defaults,
    max_fetched_at_iso,
    merge_manager_anchor_hits,
    merge_stat_anchor_hits,
    prioritize_hero_stat_chunks,
    query_is_pilot_scope,
    same_scheme_manager_fallback,
    same_scheme_stat_fallback,
    scheme_clarification_needed,
    substantive_hits,
)
from phase3.synthesize import (
    FundManagementFact,
    NavFact,
    _extractive_from_contexts,
    contexts_from_hits,
    extract_fund_managers_from_contexts,
    extract_nav_fact_from_contexts,
    fund_label_for_answer,
    groq_api_configured,
    shape_answer_for_query,
    try_groq_json_answer,
)
from phase3.url_normalize import normalize_citation_url

_log = logging.getLogger(__name__)

# Refusal classes: no user-visible URLs (architecture §1.1 — unsupported / PII).
_REFUSAL_NO_URL_TEMPLATES = frozenset({"refusal_out_of_corpus", "refusal_no_pii"})


class FaqRagEngine:
    """Phase 3 runtime (architecture §6): guard → retrieve → diversity → cite → synthesize → ground."""

    def __init__(
        self,
        repo_root: Path,
        index_bundle_dir: Path,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.bundle_dir = Path(index_bundle_dir)
        self.p0: Phase0RuntimeConfig = load_phase0_runtime(self.repo_root)
        self.defaults: dict[str, Any] = load_phase3_defaults(self.repo_root)
        if overrides:
            self.defaults = {**self.defaults, **overrides}
        self.bundle: IndexBundle = load_index_bundle(self.bundle_dir)

    def _refusal(self, template_key: str) -> Phase3Response:
        tpl = self.p0.refusal_config["templates"][template_key]
        body = str(tpl["body"])
        edu_url: str | None = None
        edu_label: str | None = None
        if template_key not in _REFUSAL_NO_URL_TEMPLATES:
            ek = str(tpl.get("educational_link_key") or "")
            if ek and ek in self.p0.refusal_config.get("educational_links", {}):
                link = self.p0.refusal_config["educational_links"][ek]
                edu_url = str(link["url"])
                edu_label = str(link["label"])
        return Phase3Response(
            refusal=True,
            answer=body,
            citation_url=None,
            last_updated=None,
            footer_line=None,
            scheme_id=None,
            educational_url=edu_url,
            educational_label=edu_label,
            refusal_template_key=template_key,
            needs_scheme_clarification=False,
            clarification_message=None,
            generator_route="guard",
            evidence=[],
        )

    def _apply_llm_dict(
        self,
        llm_obj: dict[str, Any],
        *,
        citation_url: str,
        sid: str,
    ) -> tuple[str, str, str]:
        """Returns (answer_text, citation_url, sid)."""
        answer_text = str(llm_obj.get("answer") or "").strip()
        cit = normalize_citation_url(str(llm_obj.get("citation_url") or ""))
        llm_sid = llm_obj.get("scheme_id")
        if isinstance(llm_sid, str) and llm_sid.strip():
            sid = llm_sid.strip()
        if cit in self.p0.citation_urls_normalized:
            citation_url = cit
        return answer_text, citation_url, sid

    def answer(self, query: str, scheme_id: str | None = None) -> Phase3Response:
        guard: GuardResult = evaluate_query_guard(query)
        if guard.refusal_template_key:
            return self._refusal(guard.refusal_template_key)

        explicit_sid = (scheme_id or "").strip()
        if not query_is_pilot_scope(
            query,
            self.p0.schemes,
            explicit_scheme_id=explicit_sid or None,
        ):
            return self._refusal("refusal_off_topic")

        k = int(self.defaults.get("retrieve_k", 12))
        min_score = float(self.defaults.get("min_retrieval_score", 0.12))
        margin = float(self.defaults.get("score_margin_for_scheme_clarification", 0.028))
        min_chars = int(self.defaults.get("substantive_chunk_min_chars", 40))
        max_ctx = int(self.defaults.get("max_context_chunks", 6))
        dedupe = bool(self.defaults.get("dedupe_by_canonical_url", True))

        inferred_sid = infer_scheme_id_from_query(query, self.p0.schemes) if not explicit_sid else None
        effective_sid = explicit_sid or (inferred_sid or "")

        raw_hits = self.bundle.search(query, k=k)
        # URL-level dedupe keeps one chunk per Groww page — fine when the question is open-ended
        # across schemes. When a scheme is already resolved, every on-page chunk shares the same
        # canonical URL; deduping then collapses the whole scheme to a single excerpt (often NAV
        # chrome) and hides fund-manager / SID / registrar blocks the LLM needs.
        if dedupe and not effective_sid:
            ranked = dedupe_hits_by_source_url(raw_hits)
        else:
            ranked = list(raw_hits)
        scores = [h.score for h in ranked[:5]]
        hits = substantive_hits(ranked, min_chars=min_chars)
        sid_filter = effective_sid
        if sid_filter:
            matching = [h for h in hits if str(h.metadata.get("scheme_id") or "") == sid_filter]
            if not matching:
                matching = same_scheme_stat_fallback(
                    self.bundle, sid_filter, query, min_chars=min_chars
                )
            if not matching:
                matching = same_scheme_manager_fallback(
                    self.bundle, sid_filter, query, min_chars=min_chars
                )
            if not matching:
                return self._refusal("refusal_out_of_corpus")
            hits = merge_stat_anchor_hits(self.bundle, matching, sid_filter, query)
            hits = merge_manager_anchor_hits(self.bundle, hits, sid_filter, query)
            hits = prioritize_hero_stat_chunks(hits, query)

        if not hits or hits[0].score < min_score:
            return self._refusal("refusal_out_of_corpus")

        need_clar, clar_msg = scheme_clarification_needed(hits, margin=margin)
        ev_pre = [hit_evidence_record(h) for h in hits[:max_ctx]]
        lu_pre = max_fetched_at_iso(hits[:max_ctx])
        scheme_resolved = bool(explicit_sid) or bool(inferred_sid)
        if need_clar and not scheme_resolved:
            if not query_is_pilot_scope(
                query,
                self.p0.schemes,
                explicit_scheme_id=explicit_sid or None,
            ):
                return self._refusal("refusal_off_topic")
            return Phase3Response(
                refusal=False,
                answer=clar_msg or "",
                citation_url=None,
                last_updated=lu_pre,
                footer_line=None,
                scheme_id=None,
                educational_url=None,
                educational_label=None,
                refusal_template_key=None,
                needs_scheme_clarification=True,
                clarification_message=clar_msg,
                generator_route="retrieval",
                evidence=ev_pre,
                retrieval_scores=scores,
                chunk_ids_used=[h.chunk_id for h in hits[:max_ctx]],
            )

        primary = hits[0]
        sid = str(primary.metadata.get("scheme_id") or "") or (scheme_id or "")
        if scheme_id and scheme_id.strip():
            sid = scheme_id.strip()

        citation_url = self.p0.scheme_id_to_citation.get(sid) or normalize_citation_url(
            str(primary.metadata.get("canonical_url") or primary.metadata.get("requested_url") or ""),
        )
        if citation_url not in self.p0.citation_urls_normalized:
            citation_url = self.p0.scheme_id_to_citation.get(sid, "")

        if not citation_url or normalize_citation_url(citation_url) not in self.p0.citation_urls_normalized:
            return self._refusal("refusal_out_of_corpus")

        citation_url = normalize_citation_url(citation_url)
        footer_date = max_fetched_at_iso(hits[:max_ctx])
        footer_line = (
            f"Last updated from sources: {footer_date}" if footer_date else "Last updated from sources: (unknown)"
        )
        evidence_rows = [hit_evidence_record(h) for h in hits[:max_ctx]]

        contexts, chunk_ids = contexts_from_hits(hits, max_chunks=max_ctx)
        allow_list = sorted(self.p0.citation_urls_normalized)

        llm_base = self.defaults.get("llm_base_url")
        llm_base_url = str(llm_base).strip() if llm_base else None

        model_primary = str(self.defaults.get("llm_model", "llama-3.3-70b-versatile"))
        model_fb = str(self.defaults.get("llm_fallback_model") or "").strip()
        models_try = [model_primary]
        if model_fb and model_fb not in models_try:
            models_try.append(model_fb)

        model = model_primary
        route = "extractive"
        answer_text = ""

        evidence_blocks = []
        for h in hits[:max_ctx]:
            meta = (
                f"scheme_id={h.metadata.get('scheme_id')!s} "
                f"source_url={h.metadata.get('canonical_url')!s} "
                f"fetched_at={h.metadata.get('fetched_at_utc')!s}"
            )
            evidence_blocks.append(f"[{meta}]\n{h.text}")

        resolved_sid = sid if sid in self.p0.scheme_id_to_citation else None
        fund_label = fund_label_for_answer(
            query=query,
            scheme_id=resolved_sid,
            schemes=self.p0.schemes,
        )
        nav_fact: NavFact | None = None
        manager_fact: FundManagementFact | None = None
        if nav_focus_only_query(query):
            nav_fact = extract_nav_fact_from_contexts(contexts)
        if fund_manager_focus_query(query):
            manager_fact = extract_fund_managers_from_contexts(contexts)

        def _shape(answer_text: str) -> str:
            return shape_answer_for_query(
                query,
                answer_text,
                nav_fact=nav_fact,
                manager_fact=manager_fact,
                fund_label=fund_label,
            )

        try:
            from dotenv import load_dotenv

            load_dotenv(self.repo_root / ".env", override=True)
        except ImportError:
            pass

        use_groq = groq_api_configured()
        llm_obj: dict[str, Any] | None = None
        groq_model_used: str | None = None
        if use_groq:
            groq_retry_hints: list[str | None] = [
                None,
                "Return exactly one JSON object with keys answer, citation_url, scheme_id. "
                "citation_url must be copied verbatim from the allowlist block (one line). "
                "answer: at most 3 short neutral sentences, facts from EVIDENCE only.",
                "Your response must be valid JSON only (no prose outside the object). "
                "If unsure, pick the allowlist URL closest to the top evidence chunk.",
            ]
            for try_model in models_try:
                _log.info(
                    "phase3_synthesize groq=1 model=%s evidence_blocks=%d",
                    try_model,
                    len(evidence_blocks),
                )
                for hint in groq_retry_hints:
                    llm_obj = try_groq_json_answer(
                        query=query,
                        evidence_blocks=evidence_blocks,
                        allowlist_urls=allow_list,
                        model=try_model,
                        base_url=llm_base_url,
                        extra_user_instructions=hint,
                        nav_fact=nav_fact,
                        manager_fact=manager_fact,
                        fund_label=fund_label,
                    )
                    if isinstance(llm_obj, dict) and str(llm_obj.get("answer") or "").strip():
                        groq_model_used = try_model
                        model = try_model
                        break
                    llm_obj = None
                if llm_obj:
                    break

        else:
            _log.info("phase3_synthesize groq=0 (no GROQ_API_KEY in .env / environment after dotenv)")

        if isinstance(llm_obj, dict) and llm_obj.get("answer"):
            answer_text, citation_url, sid = self._apply_llm_dict(llm_obj, citation_url=citation_url, sid=sid)
            route = "groq" if groq_model_used == models_try[0] else "groq_fallback"

        if not answer_text:
            answer_text = _extractive_from_contexts(query, contexts)
            route = "extractive"

        answer_text = _shape(answer_text)

        ok, reason = grounding_ok(
            answer=answer_text,
            citation_url=citation_url,
            allowlist=self.p0.citation_urls_normalized,
            scheme_id=sid if sid in self.p0.scheme_id_to_citation else None,
            scheme_id_to_citation=self.p0.scheme_id_to_citation,
        )

        if not ok and reason == "forbidden_phrase" and route.startswith("groq"):
            llm_retry = try_groq_json_answer(
                query=query,
                evidence_blocks=evidence_blocks,
                allowlist_urls=allow_list,
                model=model,
                base_url=llm_base_url,
                extra_user_instructions=(
                    "The previous answer violated the facts-only policy (e.g. advisory or promotional wording). "
                    "Rewrite: at most 3 neutral sentences, only facts supported by evidence, "
                    "no 'you should', 'recommend', 'best', or suitability language."
                ),
                nav_fact=nav_fact,
                manager_fact=manager_fact,
                fund_label=fund_label,
            )
            if isinstance(llm_retry, dict) and llm_retry.get("answer"):
                answer_text, citation_url, sid = self._apply_llm_dict(llm_retry, citation_url=citation_url, sid=sid)
                answer_text = _shape(answer_text)
                ok, reason = grounding_ok(
                    answer=answer_text,
                    citation_url=citation_url,
                    allowlist=self.p0.citation_urls_normalized,
                    scheme_id=sid if sid in self.p0.scheme_id_to_citation else None,
                    scheme_id_to_citation=self.p0.scheme_id_to_citation,
                )
                route = "groq_retry"

        if not ok:
            if use_groq and route.startswith("groq") and reason != "forbidden_phrase":
                grounding_hints = (
                    "The previous answer failed automated grounding (citation / allowlist / scheme consistency). "
                    "Return a NEW JSON object. citation_url must be one allowlist string copied exactly. "
                    "answer: at most 3 neutral sentences supported only by EVIDENCE; no invented figures.",
                    "Grounding still failed. Use only facts verbatim or clearly paraphrased from EVIDENCE; "
                    "citation_url must match the scheme's official Groww page from the allowlist.",
                )
                for gi, ghint in enumerate(grounding_hints):
                    llm_fix = try_groq_json_answer(
                        query=query,
                        evidence_blocks=evidence_blocks,
                        allowlist_urls=allow_list,
                        model=model,
                        base_url=llm_base_url,
                        extra_user_instructions=f"{ghint} Failure detail: {reason!s}.",
                        nav_fact=nav_fact,
                        manager_fact=manager_fact,
                        fund_label=fund_label,
                    )
                    if isinstance(llm_fix, dict) and llm_fix.get("answer"):
                        answer_text, citation_url, sid = self._apply_llm_dict(
                            llm_fix, citation_url=citation_url, sid=sid
                        )
                        answer_text = _shape(answer_text)
                        ok, reason = grounding_ok(
                            answer=answer_text,
                            citation_url=citation_url,
                            allowlist=self.p0.citation_urls_normalized,
                            scheme_id=sid if sid in self.p0.scheme_id_to_citation else None,
                            scheme_id_to_citation=self.p0.scheme_id_to_citation,
                        )
                        route = "groq_grounding_retry" if gi == 0 else "groq_grounding_retry2"
                        if ok:
                            break
                if not ok:
                    answer_text = _extractive_from_contexts(query, contexts)
                    answer_text = _shape(answer_text)
                    ok2, _ = grounding_ok(
                        answer=answer_text,
                        citation_url=citation_url,
                        allowlist=self.p0.citation_urls_normalized,
                        scheme_id=sid if sid in self.p0.scheme_id_to_citation else None,
                        scheme_id_to_citation=self.p0.scheme_id_to_citation,
                    )
                    ok = ok2
                    route = "extractive_fallback"

        if not ok:
            return self._refusal("refusal_out_of_corpus")

        if not answer_text.strip():
            return self._refusal("refusal_out_of_corpus")

        return Phase3Response(
            refusal=False,
            answer=answer_text,
            citation_url=citation_url,
            last_updated=footer_date,
            footer_line=footer_line,
            scheme_id=sid if sid else None,
            educational_url=None,
            educational_label=None,
            refusal_template_key=None,
            needs_scheme_clarification=False,
            clarification_message=None,
            generator_route=route,
            evidence=evidence_rows,
            retrieval_scores=scores,
            chunk_ids_used=chunk_ids,
        )
