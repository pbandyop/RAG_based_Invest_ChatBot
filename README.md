# Mutual Fund FAQ Assistant (Groww HDFC pilot)
Check out the online app at **https://rag-based-invest-chat-bot-ec6i.vercel.app/** (Frontend on Vercel, backend on Railway. Groq `llama-3.3-70b-versatile` is used as a lightweight free model. The application was developed using Cursor.)

> **Vercel 404?** Use the URL above (`-ec6i`). If you deploy from this repo, either set **Root Directory = `frontend`** in Vercel, or leave Root Directory empty — root [`vercel.json`](vercel.json) builds `frontend/public` automatically. Set **`RAILWAY_API_URL`** on Vercel and redeploy.

## Environment variables

Copy [`.env.example`](.env.example) to `.env` in the repo root and set values (`.env` is gitignored). After `pip install -r requirements.txt`, **python-dotenv** loads `.env` for Phase 2 index builds and Phase 3 Groq calls—no need to export keys manually for typical local runs.

## Phase 0

Configuration lives in `config/phase0/`. Validate with:

```bash
python scripts/validate_phase0.py
```

## Phase 1 — P1-S1 (manifest binding)

```bash
python scripts/ingestion/phase1/run_s1_manifest_binding.py
```

Produces a crawl plan under `data/phase1/crawl_plans/`. Ingestion code: `src/ingestion/phase1/`.

## Phase 1 — P1-S2 / P1-S3 (fetch + raw store)

Requires crawl plan from P1-S1. Fetches each URL and writes `data/phase1/raw/{run_id}/` plus `data/phase1/runs/{run_id}/fetch_report.json`.

```bash
python scripts/ingestion/phase1/run_s2_s3_fetch_and_store.py
```

## Phase 1 — P1-S4 (HTML normalization)

After raw artifacts exist, build normalized documents for chunking:

```bash
python scripts/ingestion/phase1/run_s4_normalize.py
```

Writes `data/phase1/normalized/{run_id}/`.

## Phase 1 — P1-S5 (low-yield flags / optional Playwright)

After normalized JSON exists, annotate low-yield pages or optionally augment **allowlisted** scheme URLs with headless-rendered text:

```powershell
$env:PYTHONPATH = "src"
python scripts/ingestion/phase1/run_s5_low_yield.py --run-id <run_id>
# Optional: pip install playwright && playwright install chromium
python scripts/ingestion/phase1/run_s5_low_yield.py --run-id <run_id> --playwright
```

## Phase 1 — P1-S6 (full pipeline + handoff)

Runs **P1-S1 → S2/S3 → S4 → S5** and writes `data/phase1/runs/{run_id}/p1_pipeline_report.json` (Phase 2 CLI hint inside):

```powershell
$env:PYTHONPATH = "src"
python scripts/ingestion/phase1/run_s6_pipeline.py --overwrite
```

## Phase 2 — Chunking & index

After normalized JSON exists:

```bash
pip install -r requirements.txt
python scripts/run_phase2_build_index.py --overwrite
```

Writes `data/phase2/index/{run_id}/` (FAISS + metadata). See `config/phase2/README.md`.

**Scheduled refresh (CI):** `.github/workflows/corpus_refresh.yml` and `docs/phase-wise-architecture.md` §9.5.

Architecture: [docs/phase-wise-architecture.md](docs/phase-wise-architecture.md)

## Phase 3 — RAG query runtime

Requires a Phase 2 index. Answers are **facts-only**, with **one Groww citation** (pilot allowlist) and a **last updated** footer when corpus timestamps exist.

```powershell
pip install -r requirements.txt
$env:PYTHONPATH = "src"
python scripts/run_phase3_query.py --query "What is the expense ratio for HDFC ELSS Tax Saver direct growth?" --scheme-id hdfc_elss_tax_saver_direct_growth
```

- **`--scheme-id`**: strongly recommended; must match `scheme_id` in `config/phase0/schemes.json`.
- **`GROQ_API_KEY`**: optional; when set (in the environment or in a repo-root `.env` file; see [`.env.example`](.env.example)), answers use **Groq** (OpenAI-compatible Chat Completions; see `config/phase3/defaults.json` → `llm_base_url`, `llm_model`). Otherwise an **extractive** fallback composes text from retrieved chunks (no third-party corpus).
- **Architecture §6.1 / §9.1 fields**: JSON output includes `last_updated` (ISO date), `evidence` (chunk id, `source_url`, `fetched_at`, score), and `footer_line`.
- **§6.5 gate (automated)**: `python scripts/run_phase3_golden.py` (uses `config/phase3/golden_phase3.json`).

```powershell
python scripts/run_phase3_golden.py
python scripts/run_phase3_query.py --query "..." --scheme-id hdfc_elss_tax_saver_direct_growth --json
```

Python API: `from phase3 import FaqRagEngine` then `FaqRagEngine(repo_root, index_bundle_dir).answer(...)`.

## Phase 4 — Guardrails & adversarial gate

Pre-retrieval rules live in `src/phase4/query_guard.py` (architecture §7.1). Automated checks for §7.3:

```powershell
$env:PYTHONPATH = "src"
python scripts/run_phase4_adversarial.py
```

Uses `config/phase4/adversarial_prompts.json` (same Phase 2 index as Phase 3).

## Phase 5 — Minimal UI (architecture §8)

Static interface in `src/phase5/public/`. **Run the Phase 6 server** and open **`http://127.0.0.1:8765/ui/`** (same process serves API + static files). See `config/phase5/README.md`.

## Phase 6 — Query API (backend)

HTTP server for architecture **§9.1** (`POST /query`). Requires a Phase 2 index (same as Phase 3). Loads repo-root `.env` when `python-dotenv` is installed.

```powershell
pip install -r requirements.txt
$env:PYTHONPATH = "src"
python scripts/run_phase6_server.py
```

Default bind: `config/phase6/defaults.json` → `127.0.0.1:8765`. **Endpoints:** `GET /health` (index manifest summary), `GET /version`, `POST /query` with JSON body `{"query":"...","scheme_id":null}` — response matches `Phase3Response.to_dict()` (`answer`, `citation_url`, `last_updated`, `refusal`, `evidence`, …).

Optional env: **`PHASE6_INDEX_DIR`** (path to a Phase 2 bundle with `manifest.json`), **`PHASE6_CORS_ORIGINS`** (comma-separated origins if the UI is hosted on another origin). Provider keys stay server-side only (**§9 / E6.4**).

Example (PowerShell):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/query -ContentType "application/json" -Body '{"query":"What is the expense ratio for HDFC ELSS?","scheme_id":"hdfc_elss_tax_saver_direct_growth"}'
```

## Layout

| Path | Description |
|------|-------------|
| `config/phase0/` | Manifest, taxonomy, refusal copy, policies (Phase 0 deliverables) |
| `config/phase1/` … `phase6/` | Per-phase notes and future config |
| `data/phase1/raw/` | Raw corpus artifacts (Phase 1) |
| `data/phase1/normalized/` | Normalized JSON per fetch (P1-S4) |
| `data/phase2/index/` | FAISS bundle per normalized `run_id` (Phase 2) |
| `src/ingestion/` | Phase 1 ingestion (subphases `s1`–`s6`) |
| `src/phase2/` | Phase 2 chunk + embed + FAISS |
| `src/phase3/` | Phase 3 retrieval + grounded generation (`FaqRagEngine`) |
| `src/phase5/` | Phase 5 static UI (`phase5/public/` — served at `/ui/` by Phase 6) |
| `src/phase6/` | Phase 6 FastAPI backend (`phase6/app.py` — `POST /query`, `GET /health`, Phase 5 static mount) |
| `scripts/` | Helpers: `scripts/ingestion/phase1/` (`run_s1`…`run_s6`), `scripts/run_phase2_build_index.py`, `scripts/run_phase3_query.py`, `scripts/run_phase3_golden.py`, `scripts/run_phase6_server.py` |
