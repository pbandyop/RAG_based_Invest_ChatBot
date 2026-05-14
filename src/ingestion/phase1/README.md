# Phase 1 — corpus ingestion (subphases)

Each **sN_*** folder maps to **P1-SN** in [docs/phase-wise-architecture.md](../../../docs/phase-wise-architecture.md) §4.1.

| Directory | Subphase |
|-----------|----------|
| `s1_manifest_binding/` | P1-S1 — manifest → crawl plan |
| `s2_http_fetch/` | P1-S2 — HTTP GET, retries, headers |
| `s3_raw_artifact_store/` | P1-S3 — immutable raw blobs |
| `s4_html_normalization/` | P1-S4 — HTML → text + metadata |
| `s5_js_fallback/` | P1-S5 — optional headless / low-content flags |
| `s6_runner_handoff/` | P1-S6 — orchestration + Phase 2 bundles |

CLI entrypoints live under `scripts/ingestion/phase1/`:

| Script | Subphase |
|--------|----------|
| `run_s1_manifest_binding.py` | P1-S1 |
| `run_s2_s3_fetch_and_store.py` | P1-S2 / P1-S3 |
| `run_s4_normalize.py` | P1-S4 |
| `run_s5_low_yield.py` | P1-S5 |
| `run_s6_pipeline.py` | P1-S6 |
