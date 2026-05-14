# Phase 1 — Edge Cases (Corpus Acquisition & Raw Artifact Management)

Parent reference: [phase-wise-architecture.md](../phase-wise-architecture.md) (Section 4).

| # | Edge case | Why it matters | Suggested handling |
|---|-----------|----------------|-------------------|
| E1.1 | **HTTP 403 / 429** from Groww | Empty or partial corpus | Backoff + jitter; record failure in manifest runner; do not substitute off-manifest URLs. Respect `robots.txt` and terms of use as applicable. |
| E1.2 | **HTML shell only** (content loaded client-side) | Normalizer sees almost empty text | Detect low text density; flag URL; consider prerender/playwright **only** if allowed—otherwise document as known limitation (see Phase 6 README). |
| E1.3 | **Redirect chain** ends off `groww.in` | Breaks pilot corpus boundary | Fail the row if final URL host ≠ `groww.in` (or not in allowlist). |
| E1.4 | Same URL returns **different bytes** by region or A/B | Reproducibility breaks | Store response headers + normalized URL; version manifest; note “corpus snapshot” in build artifacts. |
| E1.5 | **PDF** linked from a Groww page (if later in manifest) | Parser differs from HTML | Separate pipeline; empty extract triggers human review; keep raw blob for re-parse. |
| E1.6 | Page is **huge** (multi-MB HTML) | Memory/timeouts | Max size cap per URL; truncate with warning in metadata (`truncated=true`). |
| E1.7 | **Duplicate manifest rows** with different `priority` | Non-deterministic “latest” | Deduplicate by canonical URL at load time; merge metadata deterministically (max priority wins or first wins—pick one rule). |
| E1.8 | TLS/cert errors or **DNS flake** | Transient failures | Retry with limit; distinguish `permanent_failure` vs `retry_later` in logs for operators. |
| E1.9 | `fetched_at` clock skew across workers | Wrong “last updated” ordering | Use UTC from a single clock source; NTP on runners. |

**Phase gate interaction:** If ≥90% ingest success is missed, document blockers (E1.1, E1.2) before forcing Phase 2.
