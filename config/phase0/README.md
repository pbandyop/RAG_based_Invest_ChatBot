# Phase 0 — Foundation (implemented artifacts)

This folder implements **Phase 0** from [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md): scope lock, URL manifest, query taxonomy, refusal copy, educational links, “last updated” semantics, content policy, and logging policy.

## Files

| File | Purpose |
|------|---------|
| [manifest.json](manifest.json) | URL manifest: `url`, `document_type`, `scheme_id`, `priority`, `allowed_use`, plus pilot flags `citable`, `included_in_crawl`. |
| [citation_allowlist.json](citation_allowlist.json) | Canonical list of URLs allowed as **`citation_url`** for factual answers (**architecture 1.1**). |
| [schemes.json](schemes.json) | UI / API registry of the five locked schemes (maps `scheme_id` → Groww citation URL). |
| [query_taxonomy.json](query_taxonomy.json) | In-scope vs out-of-scope intents and example queries. |
| [refusal_and_education.json](refusal_and_education.json) | Refusal templates, AMFI/SEBI educational links, UI disclaimer snippet. |
| [LAST_UPDATED_SEMANTICS.md](LAST_UPDATED_SEMANTICS.md) | How to populate the response footer date. |
| [CONTENT_POLICY.md](CONTENT_POLICY.md) | Checklist for stakeholder sign-off (Phase 0 gate). |
| [LOGGING_POLICY.md](LOGGING_POLICY.md) | PII-safe logging rules. |

## Validate

From repo root (Python 3.9+):

```bash
python scripts/validate_phase0.py
```

## Phase gate

Complete sign-off table in [CONTENT_POLICY.md](CONTENT_POLICY.md) before large-scale ingestion (Phase 1).

## Repository layout (all phases)

| Path | Phase |
|------|--------|
| `config/phase0/` | Scope, manifest, taxonomy, policies (this folder) |
| `config/phase1/` … `config/phase6/` | Placeholders + inputs/outputs for upcoming work |
| `data/phase1/raw/` | Raw fetched artifacts (gitignored content) |
| `data/phase2/` | Processed chunks / embeddings (gitignored as needed) |
| `data/phase3/` | Reserved for runtime caches or exports (optional) |
| `src/ingestion/` | Phase 1 ingestion (P1-S1–S6 under `phase1/sN_*`) |
| `src/phase4/` … `src/phase6/` | Reserved for future code modules |
| `docs/` | Architecture, edge cases, problem statement |
