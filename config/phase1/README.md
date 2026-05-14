# Phase 1 — Corpus acquisition & raw artifacts

**Inputs:** `config/phase0/manifest.json` (URLs with `included_in_crawl: true`).

**P1-S1 (implemented):** Build validated crawl plan + deterministic `run_id`:

```bash
python scripts/ingestion/phase1/run_s1_manifest_binding.py
```

Writes `data/phase1/crawl_plans/crawl_plan__<run_id>.json`. Code: `src/ingestion/phase1/s1_manifest_binding/`.

**P1-S2 + P1-S3 (implemented):** Fetch and store raw corpus (see `src/ingestion/phase1/s2_http_fetch/`, `s3_raw_artifact_store/`).

```bash
python scripts/ingestion/phase1/run_s2_s3_fetch_and_store.py
```

Writes `data/phase1/raw/{run_id}/` and `data/phase1/runs/{run_id}/fetch_report.json`.

**P1-S4 (implemented):** Normalize HTML to JSON for Phase 2 (see `src/ingestion/phase1/s4_html_normalization/`).

```bash
python scripts/ingestion/phase1/run_s4_normalize.py
```

Produces `data/phase1/normalized/{run_id}/*.normalized.json` and `normalize_report.json`.

**Components (architecture):** Fetcher, normalizer, raw artifact store, manifest runner.

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §4 and [docs/edge-cases/phase-1-edge-cases.md](../../docs/edge-cases/phase-1-edge-cases.md).
