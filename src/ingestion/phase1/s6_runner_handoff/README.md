# P1-S6 — Runner & Phase 2 handoff

**Inputs:** Phase 0 manifest (via P1-S1) and the existing P1-S2–S5 CLIs.

**Outputs:**

- Runs **P1-S1 → P1-S2/S3 → P1-S4 → P1-S5** (S5 optional with `--skip-s5`).
- Writes `data/phase1/runs/{run_id}/p1_pipeline_report.json` with paths to the crawl plan, fetch report, normalized directory, optional `s5_report.json`, and a suggested **Phase 2** CLI line (`handoff.phase2_index_cli`).

**CLI**

```bash
set PYTHONPATH=src
python scripts/ingestion/phase1/run_s6_pipeline.py
python scripts/ingestion/phase1/run_s6_pipeline.py --overwrite --playwright-s5
python scripts/ingestion/phase1/run_s6_pipeline.py --skip-s1 --crawl-plan data/phase1/crawl_plans/crawl_plan__<run_id>.json
```

Fetch dev-only flags are forwarded when passed to this script: `--skip-robots`, `--insecure-ssl`.

See architecture [docs/phase-wise-architecture.md](../../../docs/phase-wise-architecture.md) §4.1 **P1-S6**.
