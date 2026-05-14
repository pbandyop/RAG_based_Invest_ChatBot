# P1-S4 — HTML normalization

**Inputs:** `data/phase1/raw/{run_id}/fetch_*.meta.json` and paired `fetch_*.body.html` (P1-S3).

**Outputs:** `data/phase1/normalized/{run_id}/fetch_*.normalized.json` plus `normalize_report.json`.

## Behaviour (architecture §4.1 P1-S4)

- Strips **script / style / noscript / template** text from DOM walk; collects visible text + **h1–h6** snippets.
- **`<title>`** via regex (handles minified HTML).
- **Inline JSON:** `application/json`, `application/ld+json`, and `id="__NEXT_DATA__"` script blocks appended to **`supplement_text`** (each block capped) for fund data often embedded in CSR HTML.
- **`combined_text_for_chunking`:** title + headings + plain + supplement (Phase 2 input).
- **`metrics.needs_manual_review`:** heuristic when combined chars **and** words are below thresholds (tunable).
- Copies **`fetched_at_utc`**, **`canonical_url`**, **`scheme_id`**, **`document_type`**, **`truncated`**, **`content_sha256`** from P1-S3 meta.

## Code

- [`normalize.py`](normalize.py) — `normalize_run`, `normalize_from_meta_path`, `write_normalized_document`.

## CLI

[`run_s4_normalize.py`](../../../../scripts/ingestion/phase1/run_s4_normalize.py)
