# cdn — Cloudflare Worker (not Hugging Face, not D2)

Workers **cannot** run Aria2 / DHT / 50GB disk. They only **proxy HTTP**.

| Input | What Worker does |
|---|---|
| `https://…/file.mkv` | Instant `{ dl }` → `/dl/<hash>?src=` streams through CF (Range, no store) |
| `magnet:` or `.torrent` | **501** unless `TORRENT_ORIGIN` = a VPS that does BT |

Paid Worker max in `wrangler.toml`: `cpu_ms = 30000`, smart placement, edge cache on `/dl` (no Range). Still **128MB RAM**, still **no Aria2**. Magnet needs `TORRENT_ORIGIN`.

## Deploy

```bash
cd cdn
npx wrangler login
npx wrangler deploy
```

Secrets:

```bash
npx wrangler secret put CDN_TOKEN
# optional VPS:
npx wrangler secret put TORRENT_ORIGIN
```

## API

```
GET /?url=https://cdn.example/a.mp4
→ { "dl": "https://cdn.<workers.dev>/dl/<hash>?src=https://cdn.example/a.mp4" }

Aria2 /l7 that `dl` URL.
```

Magnet without VPS will not become a file. Use a small VPS + open ports as `TORRENT_ORIGIN`, or Debrid.
