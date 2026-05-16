# Frontend (Vercel)

Deploy this folder from Vercel:

1. **Root Directory** → `frontend` (required).
2. **Environment variable** → `RAILWAY_API_URL` = your Railway `https://…` origin (no trailing slash).

`npm run build` copies `../src/phase5/public` → `public/` so Vercel has a normal static root. The API is proxied via `api/railway/*`.

See `deploy/HOSTING-RAILWAY-VERCEL.md`.
