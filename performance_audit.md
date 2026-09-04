# 🔬 D2 Performance Audit — Idle RAM 44.3% Root-Cause + Plan
**Date:** 260904 | **Method:** Sandbox real-measurement (per-component RSS) + static code review
**Baseline from user logs:** Idle (No Active Downloads, UPTIME 13–20s): RAM 44.3% (~440MB/1GB), CPU 4–10%

---

## 1. Component-wise RAM Ledger (measured)

| # | Component | RSS (measured) | Kaise measure kiya |
|---|-----------|----------------|--------------------|
| 1 | Python: sab imports (cumulative) | **132.5 MB** | Sandbox: full requirements install → per-group incremental import profile |
| 2 | Python: own code-tree + pyrogram runtime (2 clients: bot workers=6 + user workers=12, sessions, buffers) | ~50–70 MB (est) | Headless boot nahi ho sakta — import total + client-runtime estimate |
| 3 | gunicorn master + gevent worker (Flask `web.wserver`) | **~67 MB** (hello-app) → **~80–90 MB real** (qbittorrent-api + aria2p + nodes imports) | Sandbox gunicorn run, /proc RSS master+worker |
| 4 | aria2c idle | **16 MB, CPU 0 ticks/15s** | Sandbox: a2c.conf ke saath 15s CPU-tick sample |
| 5 | qbittorrent-nox (agar zinda hai) | ~60–120 MB | CH lazy-stop ke baad ye hona hi nahi chahiye — **deploy-log verify pending** |
| 6 | glibc/heap-frag/page-tables/misc | ~30–60 MB | Remainder |

**Total: ~390–470 MB ≈ 40–47% → user ke 44.3% se match.** Koi mystery nahi bacha — 4 processes + 132MB imports hi 44% hai.

### Import breakdown (top contributors, sandbox-measured)
| Import group | Marginal RSS |
|---|---|
| python baseline | 8.5 MB |
| **wzgram + TgCrypto + uvloop** (TG core — irremovable) | 34.7 MB |
| **motor + pymongo** (DB) | 20.3 MB |
| **yt-dlp** (boot pe hi load ho raha!) | 19.6 MB |
| telegraph+natsort+pytz+pycountry+langcodes | 10.4 MB |
| aria2p + qbittorrent-api | 11.8 MB |
| aiohttp+httpx+requests+cloudscraper+curl_cffi ("http zoo") | 7.6 MB |
| flask | 5.6 MB |
| google-api-client | 3.1 MB |
| bs4+lxml | 3.3 MB |
| psutil+mutagen+pymediainfo+magic+xattr | 3.8 MB |
| feedparser+apscheduler+tenacity+markdown | 1.5 MB |
| gevent+lk21+anytree+dns+crypto | 2.4 MB |
| cinemagoer, Pillow | ~0 MB (lazy internals) |

### CPU findings
- aria2c idle = **0 ticks** (dono confs) → idle CPU aria2 ka nahi.
- Status-interval loop idle pe nahi chalta (`update_all_messages` → `Interval.clear()` jab tasks=0) ✓
- Idle 4–10% = pyrogram receive/dispatch loop + TgCrypto + psutil sampling — mostly floor hai; load-time 35% ka killer CH me already fix (DHT-force + peer-speed-limit) — **deploy verify pending**.
- gunicorn gevent worker idle ~0–1% (lekin 67MB RAM kha raha).

---

## 2. Root-Causes (idle RAM 44%)

1. **Web-UI alag process me** — `gunicorn --worker-class gevent` bot se alag 2 processes (master+worker). Kaam sirf 3 routes: torrent-selector page, files list, priority set. Iske liye **~85MB** permanent. gevent+flask dono deps iske liye tree me.
2. **132MB imports boot pe** — jisme **yt-dlp 19.6MB** (jyotshal /ytdlp command rarely use hota, phir bhi boot pe load), flask (web-process side), http-zoo 7.6MB.
3. **qBit status unverified** — CH ka lazy-boot stop user ke diye logs (13–20s uptime) me reflect nahi dikha (44.7→44.3 sirf -0.4%). Ya to CH deploy nahi hua us run me, ya qBit stop fail/cover nahi. Boot-log line confirm karni hai.

---

## 3. Optimization Plan (prioritized, speed-sacrifice = zero)

### CI [P0] — Web-UI ko bot-process me le aao (aiohttp) — **~85–95MB saving**
- `web/wserver.py` ke 3 routes (`/`, `/app/files/<id>` GET, POST priority) → `aiohttp.web` server **bot process ke andar** (aiohttp already imported = +0MB marginal).
- gunicorn spawn hatana: `bot/__init__.py:825` + `bot_settings.py:358, 951`.
- Deps bye: flask, gunicorn, gevent (tree se optional).
- **Risk:** selector page ka HTML/static port karna; Heroku PORT binding in-bot hoti rahegi (aiohttp TCPSite 0.0.0.0:PORT). Routes same rakhenge.

### CJ [P1] — yt-dlp lazy import — **~20MB saving**
- 2 boot-import sites (`bot/modules/ytdlp.py:7`, `yt_dlp_download.py:5`) → first-`/ytdlp`-use pe load. Module-level lazy proxy.

### CK [P1] — qBit lazy verify — **~60–120MB (already shipped CH me)**
- Boot-log me `qBit boot-stop` / `Idle: qBit stopped` line check. Agar fail → fix; agar CH deploy hi nahi tha → deploy ke baad measure.

### CL [P2] — Benchmark harness (measurable metrics) — **~0 RAM cost, env-gated**
- Boot log: process-wise RSS breakdown line (bot self + children).
- `PERF_LOG=1` → har 5min: bot RSS / CPU-ticks / children RSS+CPU (aria2, qbit) ek line me.
- Per-task speed EMA final report me (already TT/ETA hai) + combined-DL in stats.

### CM [P2] — aria2 RPC polling audit
- aria2_listener metadata-wait loop 0.5s + per-gid `get_download` — batch `tellActive` single-call check; status loop RPC count audit. Idle CPU marginal, load-CPU trim.

### CN [P3] — Leak-sweep (targeted greps, findings-based)
- Interval list, download_dict, rss_dict, telegraph cache, uid caches — growing-structure check. (Abhi koi active leak symptom nahi — UPTIME 47s logs me; long-run verify PERF_LOG se.)

### Phase-2 [P2-arch, user-decision] — TG download 100+MB/s target
- Abhi: bot-single-client stream ~20–25MB/s cap (TG DC-side), instability = DC throttling.
- 100+/task = **multi-session range-split downloader** (user-session + bot-session parallel ranges) = HyperUL-class architecture change + helper-bot question. Speed-critical hai to alag se plan banega.

---

## 4. Expected After (CI+CJ+CK sab live)
| State | Abhi | Expected |
|---|---|---|
| Idle RAM | 44.3% | **~25–30%** (gunicorn−85, ytdlp−20, qBit−lazy) |
| Idle CPU | 4–10% | 4–8% (floor; pyrogram loop) |
| DL speed | CH fix pending verify | peer-speed-limit 15M + splits se 80–120+MB/s (BT) |
| Processes | 4 (bot, gunicorn×2, aria2, qBit-boot) | 2 (bot, aria2) |

## 5. Benchmark Protocol (same-workload before/after)
Idle / 1-task / 2-task / 3-task / large-task — RAM, CPU, speed (user PERF_LOG + /s7 logs). Deploy CI ke baad same 3-torrent workload jo user ne diya tha as reference (34.36MB/s, CPU 35.1%, RAM 44.7%).

---

## 6. Phase-2 Plan — TG Download 100+MB/s (approved: plan banao)

**Problem:** bot-single-client pyrogram stream = ~20-25MB/s DC-cap, unstable (DC throttling + single-session chunk pipeline).

**Design: Multi-Session Range-Split Downloader**
1. N sessions (bot + user + optional helper-bot tokens) ek hi message/media pe parallel chunk-ranges download karte (pyrogram low-level `session.invoke` + `upload.getFile` with offset/limit, DC-2/4 direct socket).
2. Assembler: chunks temp-parts me → sequential concat (zero RAM-buffering, disk-only).
3. Backpressure: per-session 4MB chunks × 2-in-flight; aggregate window = N×8MB.
4. Progress: single EMA speed counter, per-session contributions.
5. Fallback: koi session flood-wait → us range ko dusra session le leta.

**Decision points (user):**
- Helper-bot tokens add karne ka mane ya nahi (2 sessions = ~40-50MB/s realistic; 4 = 80-100+).
- USER_SESSION_STRING pehle se hai ✓ (user + bot = 2 sessions base).
- File-auth: media DC pe sessions ko export-auth-transfer karna hota (pyrogram `export_session_invite`? standard: `client.export_auth` DC transfer — wzgram fork me hooks check karne honge).

**Effort:** ~2-3 sessions ka work (downloader class + assembler + listener integration + tests). Pehle CI/CJ/CK deploy ka result dekho, phir iska `/plan` concrete karenge.
