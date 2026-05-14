# Phase 6 — Integration & Query API

**Implemented:** FastAPI backend in [`src/phase6/app.py`](../../src/phase6/app.py).

| Item | Description |
|------|-------------|
| **Run** | `PYTHONPATH=src` then `python scripts/run_phase6_server.py` |
| **Config** | [`defaults.json`](defaults.json) — `host`, `port`, `cors_origins`, rate limit |
| **`POST /query`** | Body: `{"query": "<string>", "scheme_id": "<optional pilot id>"}`. JSON response = `Phase3Response.to_dict()` (architecture §9.1 + §6.1 fields). |
| **`GET /health`** | `status`, `index` block from Phase 2 `manifest.json` (built_at, chunk_count, fingerprint) for deploy/version checks (E6.2). |
| **`GET /version`** | Static API pilot label. |
| **`GET /meta/schemes`** | `config/phase0/schemes.json` for the Phase 5 scheme dropdown. |
| **`GET /meta/disclaimer`** | `ui_disclaimer_snippet` from `refusal_and_education.json`. |
| **Phase 5 UI** | Static assets at **`/ui/`** (`src/phase5/public/`); **`GET /`** redirects to `/ui/`. |
| **Observability** | §9.2: logs query **length** and short **scrubbed prefix** only — not full user text; logs refusal/clarify, `scheme_id`, latency, top retrieval scores. |
| **Rate limit** | Per-IP sliding window (`max_queries_per_ip_per_minute`); **429** when exceeded (E6.7 baseline). |
| **Env overrides** | `PHASE6_INDEX_DIR`, `PHASE6_CORS_ORIGINS` (comma-separated); see [`.env.example`](../../.env.example). |

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §9 and [docs/edge-cases/phase-6-edge-cases.md](../../docs/edge-cases/phase-6-edge-cases.md).
