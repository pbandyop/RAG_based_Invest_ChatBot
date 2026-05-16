/**
 * Proxy Phase 6 API calls to Railway. Set RAILWAY_API_URL in Vercel (HTTPS origin preferred, no trailing slash).
 * Hostname-only values (e.g. `my-app.up.railway.app`) are normalized to `https://…`.
 * @see ../../deploy/HOSTING-RAILWAY-VERCEL.md
 *
 * Vercel may invoke this with a Web `Request`, Node `IncomingMessage`, or other shapes; `headers` is not always a `Headers` instance with `.get()`.
 * We normalize headers to a plain object and never call `.get` on the incoming `headers` object.
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

/**
 * Flatten inbound headers to lowercase keys → single string (join duplicate Node values with ", ").
 * Avoids `headers.get` / `instanceof Headers` pitfalls across Vercel runtimes.
 *
 * @param {Request | import("http").IncomingMessage | { headers?: unknown }} req
 * @returns {Record<string, string>}
 */
function buildHeaderRecord(req) {
  /** @type {Record<string, string>} */
  const o = {};
  const h = req && req.headers;
  if (h == null) return o;

  if (!Array.isArray(h) && typeof h.forEach === "function") {
    try {
      h.forEach((value, key) => {
        const k = String(key).toLowerCase();
        const v = String(value);
        o[k] = o[k] ? `${o[k]}, ${v}` : v;
      });
      return o;
    } catch {
      /* fall through to object copy */
    }
  }

  if (typeof h === "object" && !Array.isArray(h)) {
    for (const key of Object.keys(h)) {
      const v = /** @type {Record<string, string | string[] | undefined>} */ (h)[key];
      if (v === undefined) continue;
      const k = String(key).toLowerCase();
      const s = Array.isArray(v) ? v.map(String).join(", ") : String(v);
      o[k] = o[k] ? `${o[k]}, ${s}` : s;
    }
  }

  return o;
}

/**
 * @param {string} pathAndQuery
 * @param {Record<string, string>} headerRecord
 * @returns {URL}
 */
function incomingUrl(pathAndQuery, headerRecord) {
  const raw = pathAndQuery || "/";
  if (typeof raw === "string" && /^https?:\/\//i.test(raw)) {
    return new URL(raw);
  }
  const host =
    headerRecord["x-forwarded-host"]?.split(",")[0]?.trim() ||
    headerRecord["host"] ||
    "localhost";
  const proto =
    (headerRecord["x-forwarded-proto"] || "https").split(",")[0].trim() || "https";
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

function stripResponseHopByHop(headers) {
  const out = new Headers();
  headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return;
    out.append(key, value);
  });
  return out;
}

/**
 * @param {Request | import("http").IncomingMessage | { headers?: unknown; url?: string; method?: string }} req
 * @returns {Promise<ArrayBuffer | undefined>}
 */
async function readUpstreamRequestBody(req) {
  if (typeof req.arrayBuffer === "function") {
    const buf = await req.arrayBuffer();
    return buf.byteLength > 0 ? buf : undefined;
  }
  const nodeReq = /** @type {import("http").IncomingMessage} */ (req);
  const chunks = [];
  for await (const chunk of nodeReq) {
    chunks.push(chunk);
  }
  const buf = Buffer.concat(chunks);
  if (buf.byteLength === 0) return undefined;
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
}

/**
 * @param {Request | import("http").IncomingMessage | { headers?: unknown; url?: string; method?: string }} request
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

  const headerRecord = buildHeaderRecord(request);
  const pathAndQuery = (request && request.url) || "/";

  let u;
  try {
    u = incomingUrl(pathAndQuery, headerRecord);
  } catch (e) {
    const msg = e && typeof e === "object" && "message" in e ? String(e.message) : String(e);
    console.error("railway-proxy invalid request.url", { raw: pathAndQuery, msg });
    return Response.json({ error: "Invalid request URL", detail: msg }, { status: 500 });
  }

  const downstreamPath = downstreamPathFromRequest(u);
  const target = `${base}${downstreamPath}${upstreamSearch(u.searchParams)}`;

  const headers = new Headers();
  for (const [key, value] of Object.entries(headerRecord)) {
    if (!forwardHeader(key)) continue;
    headers.set(key, value);
  }

  /** @type {ArrayBuffer | undefined} */
  let body;
  const method = String((request && request.method) || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    body = await readUpstreamRequestBody(request);
  }

  let upstream;
  try {
    upstream = await fetch(target, { method, headers, body });
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
