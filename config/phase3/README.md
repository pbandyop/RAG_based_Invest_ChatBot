# Phase 3 — Retrieval & grounded generation

**Inputs:** Query + optional `scheme_id`; vector index from Phase 2; `config/phase0/citation_allowlist.json` for allowlist checks.

**Outputs (planned):** Structured answer: `answer`, `citation_url`, `last_updated`, optional `refusal` flag (final wiring with Phase 4).

**Components (architecture):** Retriever, citation selection, **Groq** LLM generator (OpenAI-compatible SDK), grounding checks.

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §6 and [docs/edge-cases/phase-3-edge-cases.md](../../docs/edge-cases/phase-3-edge-cases.md).
