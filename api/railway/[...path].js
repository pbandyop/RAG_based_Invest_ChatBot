/**
 * Proxy Phase 6 API calls to Railway. Set RAILWAY_API_URL in Vercel (HTTPS origin, no trailing slash).
 * @see deploy/HOSTING-RAILWAY-VERCEL.md
 */

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

export default {
  /**
   * @param {Request} request
   */
  async fetch(request) {
    const baseRaw = process.env.RAILWAY_API_URL;
    if (!baseRaw || typeof baseRaw !== "string") {
      return Response.json(
        {
          error:
            "RAILWAY_API_URL is not set. In Vercel → Project → Settings → Environment Variables, add RAILWAY_API_URL with your Railway HTTPS origin (no trailing slash).",
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
      if (HOP_BY_HOP.has(key.toLowerCase())) return;
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
      return Response.json({ error: "Upstream fetch failed", detail: msg }, { status: 502 });
    }

    const outHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (HOP_BY_HOP.has(key.toLowerCase())) return;
      outHeaders.append(key, value);
    });

    return new Response(upstream.body, {
      status: upstream.status,
      headers: outHeaders,
    });
  },
};
