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
| `PHASE6_CORS_ORIGINS` | Unused (reserved) | CORS is **`Access-Control-Allow-Origin: *`** for this API (no browser credentials). |

**Resources:** Loading `sentence-transformers` + FAISS needs enough RAM; choose a plan / replica size that avoids OOM on first model load.

### Public URL

After deploy, generate a **public domain** for the service (Railway **Settings → Networking → Public Networking**). Note the HTTPS origin, e.g. `https://your-service.up.railway.app` (exact domain depends on your Railway project).

---

## 2. Vercel — static frontend + API

Use the **`frontend/`** folder as the Vercel project root (**Root Directory = `frontend`**). **`npm run build`** copies **`src/phase5/public`** → **`frontend/public/`** and writes **`phase6-api-origin.js`** from **`RAILWAY_API_URL`**.

**Important:** The UI calls **Railway directly** from the browser for `/query`, `/meta/*`, and `/health`. That avoids **504 / timeout** from the Vercel serverless proxy (Hobby tier often caps execution around **10s**, while RAG + LLM can take much longer). The `api/railway/*` handlers remain as a fallback but are not used when `phase6-api-origin.js` contains your Railway origin.

### Vercel environment variable (required)

| Key | Value |
|-----|--------|
| **`RAILWAY_API_URL`** | Railway **HTTPS origin**, e.g. `https://your-service.up.railway.app` — **no trailing slash**. Hostname-only is fine. Must be set for **Production** and **Preview** (or whichever environments you deploy) so **build** can embed it in `public/phase6-api-origin.js`. Runtime-only is not enough—Vercel runs `npm run build` first.

Add it under **Project → Settings → Environment Variables** and trigger a **new deployment** after changes.

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

- **`vercel.json`** — build/install/output **public**; optional rewrites to **`/api/railway/...`** (fallback).
- **`api/railway/…`** — serverless proxy to **`RAILWAY_API_URL`** if you hit same-origin API paths without browser-direct config.
- **`frontend/public/`** is **not** committed (generated on each build, including **`phase6-api-origin.js`**).

When the Railway URL changes, update **`RAILWAY_API_URL`** in Vercel and **redeploy** so the static bundle picks up the new origin.

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
| API via Vercel (browser) | Open site → network tab should show **`/query`** etc. going to **`https://<railway-host>/…`** (cross-origin), not only to `vercel.app`. |
| UI | `https://<vercel-host>/` → should load `index.html` from `src/phase5/public` |

If the UI cannot reach Railway, confirm **`RAILWAY_API_URL`** is present at **build** time on Vercel, redeploy, and check the browser console for CORS errors (Railway logs should show `OPTIONS`/`GET` from your Vercel origin).

### Chat returns 500, 504, or times out

1. **504 on Vercel / “couldn’t complete request”:** Usually means traffic was still going through the **serverless proxy** and hit the platform time limit. **Fix:** redeploy after this repo’s browser-direct change; confirm requests target **Railway** in DevTools → Network. Ensure **`RAILWAY_API_URL`** is set for the environment that runs **`npm run build`**.
2. **Vercel Hobby `maxDuration`:** Still applies only to **`/api/railway/*`** if you use the proxy; it does not limit the browser’s direct `fetch` to Railway.
3. **Railway:** In Railway → **Logs**, look for `query_engine_error`, missing **`GROQ_API_KEY`**, or OOM during embedder load. Fix env vars and redeploy Railway.
4. **Custom domain on Vercel:** No extra Railway env needed for CORS (wildcard). If you lock CORS down later, change `CORSMiddleware` in `src/phase6/app.py`.
5. **Clearer UI errors:** Failed responses should show **FastAPI `detail`** or a short response snippet when possible.
