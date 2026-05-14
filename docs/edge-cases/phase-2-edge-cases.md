# Phase 2 — Edge Cases (Chunking, Enrichment, Index Build)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 5).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E2.1 | **Key-value split across chunks** (e.g. label in chunk *n*, value in *n+1*) | Retrieval returns wrong half; wrong or vague answers | Smaller chunks + overlap for dense tables; or table-aware extraction before chunking for critical fields. |
| E2.2 | **Wrong `scheme` metadata** on chunks from a shared help page | Metadata filter routes user to wrong fund | For non-scheme-specific Groww pages, tag `scheme=multi` or `scheme=none` and disable strict scheme filter for those chunks. |
| E2.3 | **Embedding model version** changes mid-project | Old vectors incomparable with new query embeddings | Full re-embed + rebuild index; pin model ID in README and CI. |
| E2.4 | **Language mix** (English + Hinglish labels) | Retrieval mismatch for some users | Document supported query languages; optional query translation policy (Phase 0) if you add it later. |
| E2.5 | **Empty or near-empty chunks** after strip noise | Pollutes index | Drop chunks below token threshold; log counts per URL. |
| E2.6 | **All top-k from one long page** (e.g. generic MF glossary) | Right domain, wrong specificity | MMR / score threshold; boost chunks whose metadata `source_url` matches UI-selected scheme. |
| E2.7 | **Identical text** duplicated across schemes (boilerplate) | Ambiguous attribution | Dedupe at index level **or** attach strongest scheme signal from URL path / DOM section. |
| E2.8 | `fetched_at` missing on legacy chunk | Footer date breaks | Backfill from raw artifact store or use index build time with `date_source=build` flag (document honesty in UI copy if needed). |

**Golden-set risk:** If golden questions fail Phase 2 gate, triage E2.1 vs E2.6 before tuning k or chunk size.
