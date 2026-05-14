# Ingestion — `src/ingestion`

Corpus **ingestion** code (fetch, store, normalize) lives here, separate from query-time RAG code (later under e.g. `src/phase3` or a dedicated package).

## Phase 1 layout (`phase1/`)

| Subfolder | Architecture ID | Status |
|-----------|-----------------|--------|
| [`phase1/s1_manifest_binding/`](phase1/s1_manifest_binding/) | **P1-S1** | Implemented |
| [`phase1/s2_http_fetch/`](phase1/s2_http_fetch/) | **P1-S2** | Implemented |
| [`phase1/s3_raw_artifact_store/`](phase1/s3_raw_artifact_store/) | **P1-S3** | Implemented |
| [`phase1/s4_html_normalization/`](phase1/s4_html_normalization/) | **P1-S4** | Implemented |
| [`phase1/s5_js_fallback/`](phase1/s5_js_fallback/) | **P1-S5** | Scaffold |
| [`phase1/s6_runner_handoff/`](phase1/s6_runner_handoff/) | **P1-S6** | Scaffold |

Run **P1-S1** from repo root:

```bash
python scripts/ingestion/phase1/run_s1_manifest_binding.py
```

Run **P1-S2** + **P1-S3** (fetch + store; needs network):

```bash
python scripts/ingestion/phase1/run_s2_s3_fetch_and_store.py
```

Run **P1-S4** (normalize HTML from raw artifacts):

```bash
python scripts/ingestion/phase1/run_s4_normalize.py
```

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §4.1.
