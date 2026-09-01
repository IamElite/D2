const HASH_LEN = 16;

function sha16(s) {
  const data = new TextEncoder().encode(s);
  return crypto.subtle.digest("SHA-256", data).then((buf) => {
    const h = [...new Uint8Array(buf)]
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    return h.slice(0, HASH_LEN);
  });
}

function isMagnet(u) {
  return u.startsWith("magnet:");
}

function isHttp(u) {
  return u.startsWith("http://") || u.startsWith("https://");
}

function isTorrentHttp(u) {
  try {
    const p = new URL(u);
    return p.pathname.toLowerCase().endsWith(".torrent");
  } catch {
    return false;
  }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "cache-control": "no-store",
    },
  });
}

function auth(req, env) {
  const t = env.CDN_TOKEN;
  if (!t) return true;
  const u = new URL(req.url);
  const got =
    req.headers.get("x-cdn-token") || u.searchParams.get("token") || "";
  return got === t;
}

async function proxyHttp(src, req, ctx) {
  const cache = caches.default;
  const range = req.headers.get("range");
  if (!range && req.method === "GET") {
    const hit = await cache.match(req);
    if (hit) return hit;
  }

  const headers = new Headers();
  if (range) headers.set("Range", range);
  headers.set(
    "User-Agent",
    req.headers.get("user-agent") ||
      "Mozilla/5.0 (compatible; cdn-worker/1.0)"
  );
  const accept = req.headers.get("accept");
  if (accept) headers.set("Accept", accept);

  const up = await fetch(src, {
    method: "GET",
    headers,
    redirect: "follow",
    cf: {
      cacheEverything: !range,
      cacheTtl: range ? 0 : 86400,
      polish: "off",
      minify: { javascript: false, css: false, html: false },
    },
  });

  const out = new Headers();
  const pass = [
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
    "content-disposition",
  ];
  for (const k of pass) {
    const v = up.headers.get(k);
    if (v) out.set(k, v);
  }
  if (!out.has("accept-ranges")) out.set("Accept-Ranges", "bytes");
  out.set("access-control-allow-origin", "*");
  out.set("cache-control", range ? "private, no-store" : "public, max-age=86400");

  const res = new Response(up.body, { status: up.status, headers: out });
  if (!range && req.method === "GET" && up.ok && ctx) {
    ctx.waitUntil(cache.put(req, res.clone()));
  }
  return res;
}

async function torrentViaOrigin(env, src) {
  const origin = (env.TORRENT_ORIGIN || "").replace(/\/$/, "");
  if (!origin) {
    return json(
      {
        ok: false,
        error:
          "magnet/.torrent cannot run inside a Worker isolate. Set TORRENT_ORIGIN (VPS) or use a direct http file URL.",
      },
      501
    );
  }
  const q = new URL(origin + "/");
  q.searchParams.set("url", src);
  const hdrs = {};
  if (env.CDN_TOKEN) hdrs["x-hug-token"] = env.CDN_TOKEN;
  const r = await fetch(q.toString(), {
    headers: hdrs,
    cf: { cacheTtl: 0 },
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) return json({ ok: false, upstream: body }, r.status);
  const dl = body.dl || (body.hash ? `${origin}/dl/${body.hash}` : null);
  return json({ ok: true, hash: body.hash, dl, status: body.status });
}

export default {
  async fetch(req, env, ctx) {
    if (req.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, HEAD, OPTIONS",
          "access-control-allow-headers": "x-cdn-token, range",
          "access-control-max-age": "86400",
        },
      });
    }
    if (!auth(req, env)) return json({ ok: false, error: "unauthorized" }, 401);

    const u = new URL(req.url);
    const parts = u.pathname.split("/").filter(Boolean);

    if (parts[0] === "dl" && parts[1]) {
      const src = u.searchParams.get("src");
      if (!src || !isHttp(src) || isTorrentHttp(src)) {
        return json(
          { ok: false, error: "dl needs ?src=https://direct-file" },
          400
        );
      }
      return proxyHttp(src, req, ctx);
    }

    if (u.pathname === "/" || u.pathname === "") {
      const src = (u.searchParams.get("url") || "").trim();
      if (!src) {
        return json({
          ok: true,
          use: "/?url=https://direct.file",
          limits: "cpu_ms=30000 smart-placement edge-cache",
        });
      }
      if (isMagnet(src) || isTorrentHttp(src)) {
        return torrentViaOrigin(env, src);
      }
      if (!isHttp(src)) return json({ ok: false, error: "bad url" }, 400);
      const hid = await sha16(src);
      const dl = new URL(`/dl/${hid}`, u.origin);
      dl.searchParams.set("src", src);
      return json({ ok: true, hash: hid, dl: dl.toString(), status: "ready" });
    }

    return json({ ok: false }, 404);
  },
};
