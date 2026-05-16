/**
 * Proxy Phase 6 API calls to Railway. Set RAILWAY_API_URL in Vercel (HTTPS origin, no trailing slash).
 * @see ../../deploy/HOSTING-RAILWAY-VERCEL.md
 */

/** Serverless wait for Railway (RAG + LLM often > 10s). Hobby plan caps at 10s; Pro can use 60. */
export const maxDuration = 60;

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

  const base = baseRaw.replace(/\/$/, "");
  const u = new URL(request.url);
  const prefix = "/api/railway";
  if (!u.pathname.startsWith(prefix)) {
    return Response.json({ error: "Unexpected proxy path" }, { status: 500 });
  }

  let downstreamPath = u.pathname.slice(prefix.length);
  if (downstreamPath === "") downstreamPath = "/";
  else if (!downstreamPath.startsWith("/")) downstreamPath = `/${downstreamPath}`;

  const target = `${base}${downstreamPath}${u.search}`;

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
