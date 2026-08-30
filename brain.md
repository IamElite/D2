# D2 / arnv1 — brain.md

Nayi chat me bolo: **read brain.md**  
Is file se pata chalega: kya galti thi, kya fix hua, kaunsi branch, kaunsa hash.

**Branch:** `arnv1` only (prod `srmlx` / `main` tab tak nahi jab tak user na kahe)  
**Repo:** https://github.com/IamElite/D2  
**Dyno:** Heroku Standard-2X (~1 GB RAM)

---

## Agent rules (har nayi chat + har push se PEHLE)

1. Kaam shuru: pehle **yeh `brain.md` padho**.
2. **Git push se pehle** is file me naya block add karo:
   - 6-digit ID (`YYMMDD` + serial, ya `A` + 5 digits)
   - git short hash (jab push ke baad pata chale, update)
   - problem / galti
   - files
   - kya fix
   - agar purana fix galat/adhura tha to **OLD: `ID`** mention + naya kya kiya
3. User ko push se pehle ID + kya fix batao; push ke baad git hash likh do.
4. Token / PAT is file me **kabhi mat likho**. Chat wala token leaked maano → user revoke kare.

---

## Goal (user)

- Same repo dost 2X pe 5+ task ~30% CPU; hamare idle/kam task pe 70–80% CPU.
- Download slow tha isliye connections badha diye; ab **max throughput** chahiye lekin **RAM use karke**, CPU idle pe waste nahi.
- File-by-file GitHub edit mushkil → `arnv1` pe agent push.

---

## ROOT CAUSE (galti kahan thi)

Idle/high CPU **speed se nahi**, in cheezon se:

| Galti | Effect |
|---|---|
| Pyrogram `workers=1000` | 1000 threads, idle pe bhi CPU |
| `max_concurrent_transmissions=1000` | extra TG sockets |
| Boot pe Linux Mint ISO torrent dummy init | 13s download+hash har restart |
| 4× **all** tracker lists | hazaaron announce, DHT CPU |
| Gunicorn gevent unlimited | extra workers |
| qBit HTTP pool 500 + `pool_block=True` | blocked threads |
| Status interval **2s** | Telegram edit spam |
| Aria2 `split=12` / 12 conn + `falloc` | 2X pe CPU, Mbps nahi |
| qBit listener **har 3s reannounce** | RPC + CPU (baad me pakda) |
| Mongo `settings.aria2c` / `qbittorrent` | deploy config overwrite ho sakti hai |

Dost ka 30% = kam hashing / slow DL ho sakta hai, magic config nahi.

---

## FIX LOG

### `260830-A` — first Heroku 2X profile  
**Git:** `f33b586` (local) → rebase ke baad remote **`cee293`** (`cee2930`)  
**Date:** 2026-08-30  
**Files:** `a2c.conf`, `qBittorrent/config/qBittorrent.conf`, `bot/__init__.py`

**Galti:** idle 70–80% CPU; speed ke liye sockets badhana.

**Fix:**
- Pyrogram workers **1000 → 32**, TG concurrent **1000 → 16**
- Dummy Mint torrent init **band** (sirf `get_global_options`)
- Trackers: all-lists → **best** lists only
- Gunicorn: **1 worker**, gevent, 100 connections, timeout 120
- qBit API pool **500 → 32**, `pool_block=False`, retries 3
- Status default **2s → 6s**
- Aria2: `disk-cache=128M`, mmap, `file-allocation=none`, split/conn **8**, concurrent DL **3**, LPD off, seed 0
- qBit: RAM cache, hashing 1 thread, connections 80, active DL 3, LSD off, seed ratio 0

**Heroku:** deploy **branch `arnv1`**. Mongo purani aria2/qbit prefs ho to reset.

---

### `260830-B` — qBit live 85% CPU (2 torrents)  
**Git:** same push me merge → **`cee293`**  
**OLD:** `260830-A` (qBit DiskIO simple + listener 3s reannounce)  
**Date:** 2026-08-30  
**Files:** `qBittorrent/config/qBittorrent.conf`, `bot/helper/listeners/qbit_listener.py`

**User status (sample):**
- Ep ~7.7 MB/s qBit — OK  
- **102 GB** pack ~2.1 MB/s, 4 seeders — 2X pe saath mat chalao  
- CPU **85.8%**, RAM **52%**, uptime 2m27s, total DL ~9.8 MB/s  

**Samajh:** 85% **hashing (SHA-1)** hai, idle-bug nahi. RAM 52% desired. BT hashing band nahi hoti.

**Purane `260830-A` me kami:** listener `torrents_info` 2 baar + **har 3s reannounce** metaDL/stalled pe.

**Naya fix:**
- Listener: info **ek baar**, reannounce **60s**
- qBit: mmap `DiskIOType=4`, cache **192**, `CoalesceReadWrite`, connection speed 15

**Advice user ko:** 102 GB select (`/btsel`) se chhota karo; 2 bade pack parallel mat. Idle (0 task) 25–35% se upar = Mongo overwrite.

---

### `260830-C` — `arnv1` remote + brain  
**Git:** push `arnv1` `52af96b` ke upar rebase, result **`cee2930`**  
**Date:** 2026-08-30  

Remote pe pehle se `arnv1` tha (`f49c6b8` qBit, `52af96b` a2c). Conflict qBit conf me → **mmap/192 wala (`260830-B`) rakha**.

**Token:** user PAT chat me diya — **revoke** (leaked). Is file me token nahi.

---

### `260830-D` — yeh brain.md (pehle local)  
**Git:** pehle untracked; **`260830-E` se `arnv1` pe push**  
**Date:** 2026-08-30  
**Files:** `brain.md` (naya)

Nayi chat / push se pehle yeh log. Har future commit se pehle yahan 6-digit ID + fix.

---

### `260830-E` — brain.md git pe (local delete se bachao)  
**Git:** `94e15e` (`94e15eb`)  
**Date:** 2026-08-30  
**Files:** `brain.md`

**Galti / risk:** sirf sandbox local tha; local wipe = history gayi.  
**Fix:** `arnv1` pe commit+push taaki GitHub source of truth.  
**OLD:** `260830-D` local-only.

---

## Deploy checklist

1. Heroku app **branch = `arnv1`** (abhi `srmlx` mat)
2. Restart dyno
3. `DATABASE_URL` ho to bot/DB se purani **aria2c / qbittorrent** options clear
4. Config var `STATUS_UPDATE_INTERVAL=2` ho to hatao ya `6`
5. Idle CPU dekho; phir 1 chhota leech

## Expected

| State | CPU | RAM |
|---|---|---|
| Idle 0 tasks | ~15–35% | ~20–40% |
| qBit ~10 MB/s | 70–90% (hash) | ~40–70% |
| Idle phir 70%+ | config/DB overwrite ya 1000 workers wapas | |

## Do / Don't

- **Do:** RAM cache, kam sockets, 1–3 active torrents on 2X  
- **Don't:** workers 1000, split 16+, 100GB + dusra task, all-tracker dump  
- **Don't:** `srmlx` pe force push without user  

---

## Next (pending)

- [x] `brain.md` ko `arnv1` pe push (`260830-E`)
- [x] After F: ~26MB/s @ 42% CPU / 51% RAM (Jaadugar). SG-1 1.3MB/s = 2 seeders.
- [ ] Heroku config: `UPSTREAM_BRANCH=arnv1`
- [ ] 102GB packs `/btsel` or queue — 2X pe saath mat

---

### `260830-G` — max useful speed, ultra-low waste CPU/RAM  
**Git:** (push ke baad)  
**OLD:** `260830-F` (5 active, 64MiB cache, 200 conn — extra sockets, dead 102GB pipe share)

**User:** 26MB/s @ 42% CPU but “speed kam, CPU/RAM zyada”; Heroku “2 Gbps”.

**Sach:** 26 MB/s ≈ 210 Mbps. 2X pe BT SHA-1 ke saath 2 Gbps (250 MB/s) **nahi** milta. 102GB @ 1.3 MB/s **2 seeders**, config nahi. Doosra torrent fast wale ka pipe khaata hai.

**Fix (efficiency, not fake 2Gbps):**
- qBit **max 2 active DL**, slow (<100 KiB/s, 120s) queue
- cache **32MiB**, conn **120/60**
- aria2 concurrent **2**, mmap off, cache 32M

**Expect:** 1 strong swarm ~20–40 MB/s, CPU ~30–50%, RAM ~35–50%. 5 dead torrents = slow + CPU.

---

### `260830-H` — leech upload 9.5 MB/s → user-session + pipeline  
**Git:** (push ke baad)  
**OLD:** har <2GB file **bot client** (`__switching_client`); pyrogram `Queue(1)` ek chunk.

**User:** DL 84 MB/s, UL **9.57 MB/s** PyroMulti; dost **20+** bina Premium. Kurigram / WZML-X wzv3 soch.

**Mat karo:** poora WZML-X Heroku pe — user kehte hain **Heroku account uda deta hai**. Kurigram drop-in nahi (pyrofork 2.2.11 API); rewrite + risk, speed ka source library name nahi.

**Asli bottleneck:** `<2GB` hamesha **Bot API**. User session MTProto DC se 15–25 MB/s common.

**Fix:**
- `user` session ho to **saari <2GB leech user client** se
- `sleep_threshold=60`, concurrent TX 8
- `save_file` `Queue(1)` → `Queue(8)` pipeline

**Zaroor:** Heroku `USER_SESSION_STRING` (user us chat/LEECH_LOG me ho). Premium sirf **>2GB** ke liye.

---

### `260830-I` — Kurigram try (user still 9 MB/s)  
**Git:** (push ke baad)  
**OLD:** `260830-H` pyrofork 2.2.11 + user client; UL still ~9 MB/s.

**User:** labs 20+; Kurigram ek baar try.

**Fix:** `requirements` **pyrofork → kurigram** (import `pyrogram` same). Queue+**8 workers** patch. Status engine **Kurigram**. Bot fallback pe log warning.

**Heroku:** `USER_SESSION_STRING` + logs me `by User Client`. Agar `by Bot Client` → session fail, 9 MB/s guaranteed.  
**Do not** full WZML-X on Heroku.

---

### `260830-J` — requirements.txt extension
**Git:** (push ke baad)
**OLD:** file name `requirements` (no .txt). `update.py` / Heroku `requirements.txt` dhundte hain → kurigram install skip.
**Fix:** `git mv requirements requirements.txt`.


---

### `260830-F` — dost 29MB/s @ 27% CPU vs hum 20MB/s @ 95%  
**Git:** `1a65b9` (`1a65b9d`)  
**Date:** 2026-08-30  
**OLD:** `260830-A` + `260830-B` (mmap DiskIOType=4, HashingThreads=1, conn cap, aur **srmlx reset**)

**Galti (scan):**
1. `start.sh` → `update.py` **har boot** `git reset --hard origin/srmlx` — `arnv1` fixes live pe apply hi nahi ho rahe the (Mongo/env default `srmlx`).
2. `DiskIOType=4` mmap extra CPU, speed nahi.
3. `HashingThreadsCount=1` SHA-1 ek core pe 100% + DL wait = slow + 95% CPU.
4. `THREADPOOL max_workers=1000` (bot_utils) — same class ki galti jo pyrogram 1000 thi.
5. Mongo `qbit_options` boot pe conf overwrite.

**Fix:**
- Default `UPSTREAM_BRANCH=arnv1` (`update.py` + `__init__.py`)
- qBit DiskIO **0 (default)**, hashing **2**, connections **200/80** (speed dost jaisa)
- Runtime `app_set_preferences` Mongo ke **baad** overlay
- THREADPOOL **24**
- mmap / CoalesceReadWrite hata

**Heroku pe zaroor:** config var `UPSTREAM_BRANCH=arnv1` (Mongo me purana `srmlx` ho to overwrite). Restart.

**Note:** Dost ke 27% pe 29MB/s = zyada vCPU ya alag host ho sakta hai (F: 175GB vs 253GB). Phir bhi srmlx-wipe + mmap + 1 hash thread hamare 95% explain karta hai.
