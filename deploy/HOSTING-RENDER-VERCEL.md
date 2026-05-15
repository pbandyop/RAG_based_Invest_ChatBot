# Hosting: Render (backend API) + Vercel (static frontend)

Phase 6 is one FastAPI app (`src/phase6`) that can serve both API routes and the Phase 5 UI. For a split deployment, **Render runs the Python API** (and may still expose `/ui` for debugging), while **Vercel serves only** `src/phase5/public`. The browser talks to your Vercel origin; **Vercel rewrites** proxy `/query`, `/meta/*`, and `/health` to Render so `app.js` can keep using same-origin URLs (`apiUrl` uses `window.location.origin`).

## Prerequisites

1. **Phase 2 index bundle** must exist on the Render filesystem at runtime. The repo `.gitignore` excludes `data/phase2/index/**` by default. Choose one:
   - Check in a pilot bundle (or use **Git LFS**) for the path you set in `PHASE6_INDEX_DIR`, **or**
   - Add a **build step** on Render that downloads a tarball/artifact and extracts it under `data/phase2/index/`, **or**
   - Run `python scripts/run_phase2_build_index.py` in `buildCommand` (slow; needs HF model download and RAM).
2. **Secrets:** set `GROQ_API_KEY` on Render if you want Groq-backed answers (see Phase 3). Optional: `HF_TOKEN` for Hugging Face rate limits when the embedding model is first downloaded.
3. **Python 3.11** is recommended (matches CI). The repo includes `runtime.txt` so Render’s native Python runtime selects 3.11.x.

---

## 1. Render — Web service (backend)

In the [Render Dashboard](https://dashboard.render.com): **New +** → **Web Service**, connect this repo.

| Setting | Value |
|--------|--------|
| **Root directory** | *(repo root)* |
| **Runtime** | Python 3 |
| **Build command** | `pip install -r requirements.txt` |
| **Start command** | `PYTHONPATH=src python scripts/run_phase6_server.py` |
| **Health check path** | `/health` |

The start script reads Render’s **`PORT`** and binds **`0.0.0.0`** automatically (override host with optional env **`HOST`**). Locally, omit `PORT` to use `config/phase6/defaults.json` (127.0.0.1:8765).

### Environment variables (Render)

| Key | Required | Example / notes |
|-----|----------|------------------|
| `PYTHONPATH` | Set in start command | `src` (already in start command) |
| `PHASE6_INDEX_DIR` | Yes | `data/phase2/index/<your_run_id>` (repo-relative path on the service) |
| `GROQ_API_KEY` | Recommended | From Groq console |
| `HF_TOKEN` | Optional | Hugging Face token for Hub rate limits |
| `PHASE6_CORS_ORIGINS` | Optional | Comma-separated origins if browsers call the **Render URL** directly (e.g. `https://your-app.vercel.app`). Not required if all browser traffic goes through Vercel rewrites only. |

**Plan / memory:** Loading `sentence-transformers` + FAISS needs enough RAM; the **Free** tier may OOM. Use **Starter** or higher if the process dies during startup.

### Blueprint (`render.yaml`)

The repo root includes **`render.yaml`** for [Render Blueprints](https://docs.render.com/blueprint-spec). Sync the repo in the Render dashboard and apply the Blueprint, or create a **Web Service** manually with the same build/start commands.

When creating manually, set secrets in the dashboard (`sync: false` in YAML → “add environment variable” during setup).

```yaml
# See repository render.yaml for the canonical, maintained version.
services:
  - type: web
    name: nextleap-groww-phase6-api
    runtime: python
    plan: starter # free | starter | standard — avoid free if worker OOMs on embedder load
    region: oregon # choose closest to users
    buildCommand: pip install -r requirements.txt
    startCommand: PYTHONPATH=src python scripts/run_phase6_server.py
    healthCheckPath: /health
    envVars:
      - key: PHASE6_INDEX_DIR
        value: data/phase2/index/groww-hdfc-pilot-v1__422a8bf8c13836c8 # change to your bundle id
      - key: GROQ_API_KEY
        sync: false
      - key: HF_TOKEN
        sync: false
```

After deploy, note the public URL, e.g. `https://nextleap-groww-phase6-api.onrender.com`.

---

## 2. Vercel — static frontend

**Project settings**

| Setting | Value |
|--------|--------|
| **Framework preset** | Other |
| **Root directory** | `.` (repository root) |
| **Build command** | *(leave empty)* or `echo "static"` |
| **Output directory** | `src/phase5/public` |

Add a `vercel.json` at the **repository root** (see below). Replace `https://YOUR-RENDER-SERVICE.onrender.com` with your Render **HTTPS** base URL (no trailing slash).

### `vercel.json` (root of repo)

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "trailingSlash": false,
  "rewrites": [
    {
      "source": "/health",
      "destination": "https://YOUR-RENDER-SERVICE.onrender.com/health"
    },
    {
      "source": "/meta/:path*",
      "destination": "https://YOUR-RENDER-SERVICE.onrender.com/meta/:path*"
    },
    {
      "source": "/query",
      "destination": "https://YOUR-RENDER-SERVICE.onrender.com/query"
    }
  ]
}
```

These rewrites keep the browser on the Vercel origin while proxying API traffic to Render (POST bodies included).

### Deploy

- Connect the repo in Vercel and deploy; open the production URL and exercise chat + scheme list.
- If you change the Render URL, update `vercel.json` and redeploy.

---

## 3. GitHub Actions alignment

The workflow `.github/workflows/corpus_refresh.yml` builds the Phase 2 index in CI and uploads artifacts; it does **not** auto-push to Render/Vercel. Typical pattern: download the latest `phase2-index-*` artifact from a successful run, extract under `data/phase2/index/` in a release branch or feed it into a deploy pipeline.

---

## 4. Quick verification

| Check | URL / action |
|-------|----------------|
| API health (Render) | `GET https://<render-host>/health` |
| API via Vercel proxy | `GET https://<vercel-host>/health` |
| UI | `https://<vercel-host>/` → should load `index.html` from `src/phase5/public` |

If `/health` via Vercel fails, confirm rewrites match your Render URL and that Render is awake (cold start on free tier).
