# P1-S3 — Raw artifact store

**Inputs:** `FetchResult` + crawl plan row + `run_id` + ordinal.

**Outputs:** Under `data/phase1/raw/{run_id}/`:

- `fetch_{NNNNN}_{slug}.body.{html|json|txt|bin}` — raw response bytes on HTTP success with body.
- `fetch_{NNNNN}_{slug}.meta.json` — sidecar metadata (`content_sha256`, headers, scheme_id, errors, `truncated`, etc.).

Never overwrites an existing `fetch_*` prefix in the same run directory (raises `StoreError`).

## Code

- [`store.py`](store.py) — `store_fetch_result()`, `fetch_result_to_jsonable()`.

## CLI

[`run_s2_s3_fetch_and_store.py`](../../../../scripts/ingestion/phase1/run_s2_s3_fetch_and_store.py) writes artifacts and `data/phase1/runs/{run_id}/fetch_report.json`.
