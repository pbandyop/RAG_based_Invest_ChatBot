# Source layout (by phase)

Implementation will land here as phases progress. Configuration lives under `config/phaseN/`.

| Directory | Intended use |
|-----------|----------------|
| `src/ingestion/` | **Phase 1** corpus ingestion (`phase1/s1_…`–`s6_…`; see `src/ingestion/README.md`) |
| `src/phase2/` | Chunking and index build jobs |
| `src/phase3/` | **Phase 3** RAG runtime (guard → retrieve → synthesize → grounding) |
| `src/phase4/` | **Phase 4** — query guard / refusal policy before retrieval ([`phase4/query_guard.py`](phase4/query_guard.py)) |
| `src/phase5/` | **Phase 5** — static UI ([`phase5/public/`](phase5/public/)); served from Phase 6 at `/ui/` |
| `src/phase6/` | **Phase 6** — FastAPI `POST /query` server ([`phase6/app.py`](phase6/app.py)), `GET /health` |

Phase 0 is **config-only** under `config/phase0/`.
