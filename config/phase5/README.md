# Phase 5 — Minimal UI

**Implemented:** Static UI in [`src/phase5/public/`](../../src/phase5/public/) (`index.html`, `styles.css`, `app.js`).

**How to open:** Start the Phase 6 server (`python scripts/run_phase6_server.py` with `PYTHONPATH=src`), then visit **`http://127.0.0.1:8765/ui/`** (root **`/`** redirects to `/ui/`). The page calls **`POST /query`** and **`GET /meta/schemes`**, **`GET /meta/disclaimer`** on the same origin.

**Architecture §8.1:** Welcome copy, three in-scope example buttons, sticky disclaimer (from `config/phase0/refusal_and_education.json` → `ui_disclaimer_snippet`), Q&A panel with answer + Groww citation link + footer, scheme dropdown from `config/phase0/schemes.json`. No login or PII fields.

See [docs/phase-wise-architecture.md](../../docs/phase-wise-architecture.md) §8 and [docs/edge-cases/phase-5-edge-cases.md](../../docs/edge-cases/phase-5-edge-cases.md).
