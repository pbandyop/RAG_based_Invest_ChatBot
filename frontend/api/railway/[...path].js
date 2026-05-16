/**
 * Catch-all `/api/railway/*` → Railway (see ../../lib/railway-proxy.mjs).
 * Nested paths like `/api/railway/meta/disclaimer` may not always hit this file on Vercel;
 * dedicated routes under `api/railway/meta/` mirror those URLs.
 */
export { maxDuration, default } from "../../lib/railway-proxy.mjs";
