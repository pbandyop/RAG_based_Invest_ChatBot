# Hosting: Railway (backend API) + Vercel (static frontend)

Phase 6 is one FastAPI app (`src/phase6`) that can serve both API routes and the Phase 5 UI. For a split deployment, **Railway runs the Python API** (you can still open `/ui` on the Railway URL for debugging), while **Vercel serves only** `src/phase5/public`. The browser talks to your Vercel origin; **Vercel rewrites** proxy `/query`, `/meta/*`, and `/health` to Railway so `app.js` can keep using same-origin URLs (`apiUrl` uses `window.location.origin`).

## Prerequisites

1. **Phase 2 index bundle** must exist on the Railway service filesystem at runtime. The repo `.gitignore` excludes `data/phase2/index/**` by default. Choose one:
   - Check in a pilot bundle (or use **Git LFS**) for the path you set in `PHASE6_INDEX_DIR`, **or**
   - Add a **build or deploy step** on Railway that downloads a tarball/artifact and extracts it under `data/phase2/index/`, **or**
   - Run `python scripts/run_phase2_build_index.py` in a custom build command (slow; needs HF model download and RAM).
2. **Secrets:** set `GROQ_API_KEY` on Railway if you want Groq-backed answers (see Phase 3). Optional: `HF_TOKEN` for Hugging Face rate limits when the embedding model is first downloaded.
3. **Python 3.11** is recommended (matches CI). The repo pins it with **`.python-version`** (`3.11`) and **`nixpacks.toml`** (`NIXPACKS_PYTHON_VERSION = "3.11"`). **`railway.toml`** sets **`[build] builder = "NIXPACKS"`** so those Nixpacks settings apply. You can still override the Python version in the Railway dashboard if needed.

### Repo files used by Railway (backend)

| File | Role |
|------|------|
| `railway.toml` | `[build] builder = "NIXPACKS"`; `[deploy]` start command, `/health` health check, restart policy |
| `nixpacks.toml` | `NIXPACKS_PYTHON_VERSION` → **3.11** |
| `.python-version` | **3.11** (builders that read this file) |
| `requirements.txt` | Nixpacks install phase runs `pip install -r requirements.txt` |
| `scripts/run_phase6_server.py` | Binds `0.0.0.0:$PORT` when Railway sets `PORT` |

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
| `PHASE6_INDEX_DIR` | Yes | `data/phase2/index/<your_run_id>` (path relative to repo root on the running container) |
| `GROQ_API_KEY` | Recommended | From Groq console |
| `HF_TOKEN` | Optional | Hugging Face token for Hub rate limits |
| `PHASE6_CORS_ORIGINS` | Optional | Comma-separated origins if browsers call the **Railway URL** directly (e.g. `https://your-app.vercel.app`). Not required if all browser traffic goes through Vercel rewrites only. |

**Resources:** Loading `sentence-transformers` + FAISS needs enough RAM; choose a plan / replica size that avoids OOM on first model load.

### Public URL

After deploy, generate a **public domain** for the service (Railway **Settings → Networking → Public Networking**). Note the HTTPS origin, e.g. `https://your-service.up.railway.app` (exact domain depends on your Railway project).

---

## 2. Vercel — static frontend

**Project settings**

| Setting | Value |
|--------|--------|
| **Framework preset** | Other |
| **Root directory** | `.` (repository root) |
| **Build command** | *(leave empty)* or `echo "static"` |
| **Output directory** | `src/phase5/public` |

Add a `vercel.json` at the **repository root** (see below). Replace `https://YOUR-RAILWAY-SERVICE.up.railway.app` with your Railway **HTTPS** base URL (no trailing slash).

### `vercel.json` (root of repo)

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "trailingSlash": false,
  "rewrites": [
    {
      "source": "/health",
      "destination": "https://YOUR-RAILWAY-SERVICE.up.railway.app/health"
    },
    {
      "source": "/meta/:path*",
      "destination": "https://YOUR-RAILWAY-SERVICE.up.railway.app/meta/:path*"
    },
    {
      "source": "/query",
      "destination": "https://YOUR-RAILWAY-SERVICE.up.railway.app/query"
    }
  ]
}
```

These rewrites keep the browser on the Vercel origin while proxying API traffic to Railway (POST bodies included).

### Deploy

- Connect the repo in Vercel and deploy; open the production URL and exercise chat + scheme list.
- If you change the Railway URL, update `vercel.json` and redeploy.

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

If `/health` via Vercel fails, confirm rewrites match your Railway URL and that the Railway service is running.
