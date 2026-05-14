# Data directories

| Path | Phase | Contents |
|------|-------|----------|
| `data/phase1/crawl_plans/` | 1 (P1-S1) | Deterministic crawl plan JSON (`crawl_plan__<run_id>.json`) |
| `data/phase1/raw/` | 1 (P1-S3) | Raw response bytes + `.meta.json` per URL under `{run_id}/` (gitignored) |
| `data/phase1/runs/{run_id}/` | 1 | `fetch_report.json` (P1-S2/S3), **`p1_pipeline_report.json`** (P1-S6 handoff) |
| `data/phase1/normalized/` | 1 (P1-S4–S5) | `fetch_*.normalized.json` + `normalize_report.json` + optional `s5_report.json` per `run_id` (gitignored) |
| `data/phase2/index/{run_id}/` | 2 | `index.faiss`, `chunk_metadata.json`, `chunks.jsonl`, `manifest.json` (gitignored) |

Large binaries should remain **out of git**; use `.gitignore` patterns once artifacts exist.
