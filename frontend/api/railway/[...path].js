/**
 * Proxy Phase 6 API calls to Railway. Set RAILWAY_API_URL in Vercel (HTTPS origin preferred, no trailing slash).
 * Hostname-only values (e.g. `my-app.up.railway.app`) are normalized to `https://…`.
 * @see ../../deploy/HOSTING-RAILWAY-VERCEL.md
 */

/** Serverless wait for Railway (RAG + LLM often > 10s). Hobby plan caps at 10s; Pro can use 60. */
export const maxDuration = 60;

/**
 * @param {string} raw
 * @returns {string}
 */
function normalizeRailwayBase(raw) {
  let s = (raw || "").trim();
  if (!s) return "";
  s = s.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(s)) {
    s = `https://${s}`;
  }
  return s;
}

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "te",
  "trailer",
  "upgrade",
  "host",
  "content-length",
]);

function forwardHeader(name) {
  const k = name.toLowerCase();
  if (HOP_BY_HOP.has(k)) return false;
  if (k === "cookie") return false;
  if (k === "accept-encoding") return false;
  if (k === "origin" || k === "referer") return false;
  if (k.startsWith("sec-fetch-")) return false;
  if (k.startsWith("sec-ch-")) return false;
  if (k.startsWith("x-vercel-")) return false;
  return true;
}

function stripResponseHopByHop(headers) {
  const out = new Headers();
  headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return;
    out.append(key, value);
  });
  return out;
}

/**
 * Vercel often passes `request.url` as a path + query only (no origin). `new URL` needs a base in that case.
 * Catch-all routing may add a `...path` query param; do not forward that to Railway.
 *
 * @param {Request} request
 * @returns {URL}
 */
function incomingUrl(request) {
  const raw = request.url || "/";
  if (typeof raw === "string" && /^https?:\/\//i.test(raw)) {
    return new URL(raw);
  }
  const host =
    request.headers.get("x-forwarded-host")?.split(",")[0]?.trim() ||
    request.headers.get("host") ||
    "localhost";
  const proto =
    (request.headers.get("x-forwarded-proto") || "https").split(",")[0].trim() || "https";
  return new URL(raw, `${proto}://${host}`);
}

/**
 * @param {URLSearchParams} searchParams
 * @returns {string} query string including `?` when non-empty
 */
function upstreamSearch(searchParams) {
  const sp = new URLSearchParams(searchParams);
  sp.delete("...path");
  const q = sp.toString();
  return q ? `?${q}` : "";
}

/**
 * Public routes are rewritten to `/api/railway/...`, but `request.url` may still look like `/query` with only a path.
 *
 * @param {URL} u
 * @returns {string} path on Railway (starts with `/`)
 */
function downstreamPathFromRequest(u) {
  const prefix = "/api/railway";
  const p = u.pathname || "/";
  if (p === prefix || p.startsWith(`${prefix}/`)) {
    const rest = p.slice(prefix.length) || "/";
    return rest.startsWith("/") ? rest : `/${rest}`;
  }
  return p.startsWith("/") ? p : `/${p}`;
}

/**
 * @param {Request} request
 */
export default async function railwayProxy(request) {
  const baseRaw = process.env.RAILWAY_API_URL;
  if (!baseRaw || typeof baseRaw !== "string") {
    return Response.json(
      {
        error:
          "Env RAILWAY_API_URL not set. In Vercel → Settings → Environment Variables, add your Railway HTTPS origin (no trailing slash).",
      },
      { status: 502 },
    );
  }

  const base = normalizeRailwayBase(baseRaw);
  try {
    // Reject junk values early so fetch never uses a malformed URL.
    new URL(base);
  } catch {
    return Response.json(
      {
        error:
          "Invalid RAILWAY_API_URL. Use your Railway origin, e.g. https://your-service.up.railway.app (hostname-only is OK; https is added automatically).",
      },
      { status: 502 },
    );
  }
  let u;
  try {
    u = incomingUrl(request);
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String(e.message) : String(e);
    console.error("railway-proxy invalid request.url", { raw: request.url, msg });
    return Response.json({ error: "Invalid request URL", detail: msg }, { status: 500 });
  }

  const downstreamPath = downstreamPathFromRequest(u);
  const target = `${base}${downstreamPath}${upstreamSearch(u.searchParams)}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!forwardHeader(key)) return;
    headers.set(key, value);
  });

  /** @type {ArrayBuffer | undefined} */
  let body;
  if (request.method !== "GET" && request.method !== "HEAD") {
    const buf = await request.arrayBuffer();
    body = buf.byteLength > 0 ? buf : undefined;
  }

  let upstream;
  try {
    upstream = await fetch(target, { method: request.method, headers, body });
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String(e.message) : String(e);
    console.error("railway-proxy fetch error", { target, msg });
    return Response.json({ error: "Upstream fetch failed", detail: msg }, { status: 502 });
  }

  const buf = await upstream.arrayBuffer();
  if (!upstream.ok) {
    console.error("railway-proxy upstream non-OK", upstream.status, target, "bytes", buf.byteLength);
  }

  const outHeaders = stripResponseHopByHop(upstream.headers);
  return new Response(buf, {
    status: upstream.status,
    headers: outHeaders,
  });
}
