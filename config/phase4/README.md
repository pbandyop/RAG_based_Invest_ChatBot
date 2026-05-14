# Phase 4 — Refusal & guardrails

**Inputs:** User query; retrieval scores; `config/phase0/query_taxonomy.json`, `config/phase0/refusal_and_education.json`.

**Outputs:** Pre-retrieval guard outcomes and refusal messages (educational links per **architecture §1.1** — omitted for unsupported factual and PII refusals).

**Code:** [`src/phase4/`](../../src/phase4/) — `evaluate_query_guard` (rule layer before retrieval). Phase 3 imports this via [`src/phase3/query_guard.py`](../../src/phase3/query_guard.py) shim.

**Adversarial gate (§7.3):** [`adversarial_prompts.json`](adversarial_prompts.json) + `python scripts/run_phase4_adversarial.py` (requires Phase 2 index; `PYTHONPATH=src`).

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §7 and [docs/edge-cases/phase-4-edge-cases.md](../../docs/edge-cases/phase-4-edge-cases.md).
