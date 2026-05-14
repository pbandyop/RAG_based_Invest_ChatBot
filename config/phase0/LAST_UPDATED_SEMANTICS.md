# Phase 0 — “Last updated” semantics

Locked per [phase-wise-architecture.md](../../docs/phase-wise-architecture.md) (Phase 0, activity: define last-updated semantics).

## User-visible footer

Format:

```text
Last updated from sources: <date>
```

## Rules (pilot)

1. **Primary signal:** Use the **`fetched_at`** timestamp (UTC, ISO 8601 date or datetime) from the **chunk(s)** or **document** used to compose the answer, when available from Phase 1 ingestion metadata.
2. **Aggregation:** If multiple chunks contributed, use the **maximum** `fetched_at` among those chunks (the most recent crawl represented in the evidence).
3. **On-page date:** If the Groww page exposes a reliable document date in extracted metadata (optional future field `source_document_date`), you may prefer it for display **only when** it is parsed with high confidence; otherwise fall back to `fetched_at`.
4. **Honesty:** Never invent a regulatory “effective date” or AMFI circular date. If no timestamp exists, use index build time only if labeled clearly in internal docs (e.g. `date_source=index_build`) — product copy should still avoid implying regulator freshness unless true.

## API field

Recommend exposing `last_updated` as ISO 8601 string aligned with the footer line above.
