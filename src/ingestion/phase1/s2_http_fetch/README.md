# P1-S2 — HTTP fetch layer

**Inputs:** URL string (from crawl plan row).

**Outputs:** `FetchResult` (status, body bytes, `Last-Modified`, `ETag`, `Content-Type`, truncation flag, retry count).

## Behaviour (architecture §4.1 P1-S2)

- **HTTPS only**; after redirects, **final URL host** must be `groww.in` (same pilot rule as P1-S1).
- **Retries** with exponential backoff on `429`, `502`, `503`, `504`, and transient `URLError` / timeouts (configurable `max_retries`).
- **`Retry-After`** header honored when present (capped at 60s).
- **Max body size** (default 10 MiB) to limit memory (edge E1.6).
- **`robots.txt`:** optional `RobotsPolicy` loads `https://groww.in/robots.txt`; if download/parse fails, fetch is still allowed but `robots_note` records the issue—tighten for production if required.

## Code

- [`fetcher.py`](fetcher.py) — `fetch_url()`, `RobotsPolicy`, `FetchResult`, helpers.

## CLI

Used together with P1-S3 via [`run_s2_s3_fetch_and_store.py`](../../../../scripts/ingestion/phase1/run_s2_s3_fetch_and_store.py).
