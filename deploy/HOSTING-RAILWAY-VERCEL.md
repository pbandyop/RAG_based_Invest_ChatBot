# Hosting: Railway (backend API) + Vercel (static frontend)

Phase 6 is one FastAPI app (`src/phase6`) that can serve both API routes and the Phase 5 UI. For a split deployment, **Railway runs the Python API** (you can still open `/ui` on the Railway URL for debugging), while **Vercel deploys the `frontend/` directory**: build copies **`src/phase5/public`** into **`frontend/public/`**, and **rewrites** send `/query`, `/meta/*`, and `/health` to a **serverless proxy** that forwards to **`RAILWAY_API_URL`**, so `app.js` can keep using same-origin URLs (`apiUrl` uses `window.location.origin`).

## Prerequisites

1. **Phase 2 index bundle** must exist on the Railway service filesystem at runtime. This repo **ships a tracked pilot bundle** at `data/phase2/index/groww-hdfc-pilot-v1__422a8bf8c13836c8/` (see `.gitignore` exceptions) so a stock deploy works without extra steps. For other bundles: set **`PHASE6_INDEX_DIR`** to a directory that contains **`manifest.json`**, **or** add a build/deploy step that downloads or builds an index under `data/phase2/index/`, **or** use Git LFS for large bundles.
2. **Secrets:** set `GROQ_API_KEY` on Railway if you want Groq-backed answers (see Phase 3). Optional: `HF_TOKEN` for Hugging Face rate limits when the embedding model is first downloaded.
3. **Python 3.11** is recommended (matches CI). The repo pins it with **`.python-version`** (`3.11`) and **`nixpacks.toml`** (`NIXPACKS_PYTHON_VERSION = "3.11"`). **`railway.toml`** sets **`[build] builder = "NIXPACKS"`** so those Nixpacks settings apply. You can still override the Python version in the Railway dashboard if needed.

### Repo files used by Railway (backend)

| File | Role |
|------|------|
| `railway.toml` | `[build] builder = "NIXPACKS"`; `[deploy]` start command, `/health` health check, restart policy |
| `nixpacks.toml` | `NIXPACKS_PYTHON_VERSION` → **3.11** |
| `.python-version` | **3.11** (builders that read this file) |
| `requirements.txt` | Nixpacks install phase runs `pip install -r requirements.txt` |
| `data/phase2/index/groww-hdfc-pilot-v1__422a8bf8c13836c8/` | Committed FAISS bundle (`manifest.json`, `index.faiss`, …) for deploy |
| `scripts/run_phase6_server.py` | Binds `0.0.0.0:$PORT` when Railway sets `PORT` |

### Repo files used by Vercel (frontend)

Deploy with Vercel **Root Directory = `frontend`** (a normal static site root + serverless `api/`).

| Path | Role |
|------|------|
| `frontend/` | Vercel project root — **`public/`** is produced at build time from **`src/phase5/public`** |
| `frontend/vercel.json` | `buildCommand`, `outputDirectory: public`, rewrites to `/api/railway/...` |
| `frontend/package.json` | `npm run build` → `scripts/sync-public.mjs` |
| `frontend/scripts/sync-public.mjs` | Copies `../src/phase5/public` → `frontend/public/` |
| `frontend/api/railway/[...path].js` | Proxies to **`RAILWAY_API_URL`** (Vercel env) |

---

## 1. Railway — Web service (backend)

1. In [Railway](https://railway.com), create a **New Project** → **Deploy from GitHub repo** (or empty project → **New** → **GitHub Repo**).
2. Select this repository. The build uses **Nixpacks** (`railway.toml`) and installs dependencies from **`requirements.txt`**.
3. **Start command / health check:** defined in **`railway.toml`** under `[deploy]`:
   - `startCommand`: `PYTHONPATH=src python scripts/run_phase6_server.py`
   - `healthcheckPath`: `/health`
   If you disable config-as-code for the service, set the same values under **Settings → Deploy**.

The start script reads **`PORT`** (Railway injects it) and binds **`0.0.0.0`** automatically (override host with optional env **`HOST`**). Locally, omit `PORT` to use `config/phase6/defaults.json` (127.0.0.1:8765).

### Environment variables (Railway)

Add these under the service **Variables** tab:

| Key | Required | Example / notes |
|-----|----------|------------------|
| `PHASE6_INDEX_DIR` | Only if not using default | Omit to auto-pick latest index under `data/phase2/index/` (the committed pilot bundle). Set to override, e.g. `data/phase2/index/<other_run_id>` |
| `GROQ_API_KEY` | Recommended | From Groq console |
| `HF_TOKEN` | Optional | Hugging Face token for Hub rate limits |
| `PHASE6_CORS_ORIGINS` | Optional | Comma-separated origins if browsers call the **Railway URL** directly (e.g. `https://your-app.vercel.app`). Not required if all browser traffic goes through Vercel rewrites only. |

**Resources:** Loading `sentence-transformers` + FAISS needs enough RAM; choose a plan / replica size that avoids OOM on first model load.

### Public URL

After deploy, generate a **public domain** for the service (Railway **Settings → Networking → Public Networking**). Note the HTTPS origin, e.g. `https://your-service.up.railway.app` (exact domain depends on your Railway project).

---

## 2. Vercel — static frontend + API proxy

Use the **`frontend/`** folder as the Vercel project root (**Root Directory = `frontend`**). Sources stay in **`src/phase5/public`**; **`npm run build`** copies them into **`frontend/public/`** (Vercel’s usual static layout). **`vercel.json` cannot substitute environment variables into external rewrite URLs**, so **`RAILWAY_API_URL`** is read by the serverless handler under **`frontend/api/`**.

### Vercel environment variable (required)

| Key | Value |
|-----|--------|
| **`RAILWAY_API_URL`** | Railway **HTTPS origin only**, e.g. `https://your-service.up.railway.app` — **no trailing slash** |

Add it under **Project → Settings → Environment Variables** (Production, and Preview if needed).

### Project settings (dashboard)

| Setting | Value |
|--------|--------|
| **Root Directory** | **`frontend`** (required — this is the “frontend folder” for Vercel) |
| **Framework preset** | Other (or leave auto; `frontend/vercel.json` sets `"framework": null`) |
| **Build Command** | *(from `frontend/vercel.json`)* `npm run build` |
| **Output Directory** | *(from `frontend/vercel.json`)* `public` |
| **Install Command** | `npm install` |

`npm run build` copies **`src/phase5/public`** into **`frontend/public/`** so Vercel sees a standard static root (`public/index.html`, etc.). Source files stay in **`src/phase5/public`** for local Phase 6 (`/ui`).

### What is committed under `frontend/`

- **`vercel.json`** — build/install/output **public**, **rewrites** for `/health`, `/meta/:path*`, `/query` → **`/api/railway/...`**.
- **`api/railway/[...path].js`** — forwards to **`RAILWAY_API_URL`**.
- **`frontend/public/`** is **not** committed (generated in CI/Vercel on each build).

When the Railway URL changes, update **`RAILWAY_API_URL`** in Vercel only.

### Deploy

- Connect the GitHub repo, set **Root Directory** to **`frontend`**, set **`RAILWAY_API_URL`**, deploy, then test the Vercel URL.

---

## 3. GitHub Actions alignment

The workflow `.github/workflows/corpus_refresh.yml` builds the Phase 2 index in CI and uploads artifacts; it does **not** auto-push to Railway/Vercel. Typical pattern: download the latest `phase2-index-*` artifact from a successful run, extract under `data/phase2/index/` before deploy, or run ingestion/index in a Railway build step if you accept the time and cost.

---

## 4. Quick verification

| Check | URL / action |
|-------|----------------|
| API health (Railway) | `GET https://<railway-host>/health` |
| API via Vercel proxy | `GET https://<vercel-host>/health` |
| UI | `https://<vercel-host>/` → should load `index.html` from `src/phase5/public` |

If `/health` via Vercel fails, confirm **`RAILWAY_API_URL`** is set correctly in Vercel and that the Railway service is running.

### Chat returns 500 or times out

1. **Vercel function duration (common on Hobby):** Each `/query` can take **15–60+ seconds** (retrieval + Groq). The **free/hobby** tier often limits serverless execution to **~10s**, so the proxy can fail or return **500** while Railway is still working. **Fix:** upgrade the Vercel project (or plan) so **`maxDuration`** up to **60** applies, or test `/query` against Railway directly (bypass Vercel) to confirm the backend is healthy.
2. **Railway:** In Railway → **Logs**, look for `query_engine_error`, missing **`GROQ_API_KEY`**, or OOM during embedder load. Fix env vars and redeploy Railway.
3. **Clearer UI errors:** After redeploy, failed responses should show **FastAPI `detail`** or a short response snippet when possible.
