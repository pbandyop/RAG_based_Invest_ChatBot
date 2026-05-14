# Phase 1 ingestion scripts

| Script | Subphase |
|--------|----------|
| [`run_s1_manifest_binding.py`](run_s1_manifest_binding.py) | **P1-S1** — build crawl plan |
| [`run_s2_s3_fetch_and_store.py`](run_s2_s3_fetch_and_store.py) | **P1-S2** + **P1-S3** — fetch URLs and store raw artifacts |
| [`run_s4_normalize.py`](run_s4_normalize.py) | **P1-S4** — HTML → normalized JSON (`data/phase1/normalized/{run_id}/`) |

## P1-S1

```bash
python scripts/ingestion/phase1/run_s1_manifest_binding.py
```

## P1-S2 + P1-S3

Uses newest `data/phase1/crawl_plans/crawl_plan__*.json` by default (needs network):

```bash
python scripts/ingestion/phase1/run_s2_s3_fetch_and_store.py
```

Options: `--crawl-plan`, `--raw-root`, `--report-dir`, `--timeout`, `--max-bytes`, `--max-retries`, `--skip-robots` (dev only), `--insecure-ssl` (dev only; disables TLS verify if your Python CA store fails).

Exit code **0** if all URLs succeed, **2** if any fetch failure (partial corpus still written under `data/phase1/raw/{run_id}/`).

## P1-S4

Uses latest `data/phase1/raw/*/` by `--run-id` or most recently modified run directory:

```bash
python scripts/ingestion/phase1/run_s4_normalize.py
```

Options: `--run-id`, `--raw-root`, `--out-root`, `--overwrite`, `--review-chars`, `--review-words`.

Exit code **0** unless a row throws unexpectedly (**2** if any `errors` in `normalize_report.json`).
