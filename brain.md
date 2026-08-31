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

### `260830-K` — WZML HyperUL/HyperDL scan; wzgram; Kurigram 5 MB/s  
**OLD:** `260830-I` Kurigram → UL **5.1 MB/s** (worse than pyrofork 9).

**WZML-X wzv3 (checked):**
- Engine: **`wzgram`** (not kurigram)
- Speed: `hyperul_utils.py` + `hyperdl_utils.py` + `tg_transfer.py` **HypertgTransfer**
- **HyperUP = multi-bot / helper_bots + helper_users** parallel MTProto (`USE_HYPER`, extra tokens). 1 bot = no Hyper.
- Poora WZML Heroku pe **mat** (account ban).

**Fix this repo:** `kurigram` → **`wzgram`**. Queue patch 8→4 (flood). Hyper multi-bot baad me extra `BOT_TOKEN`s chahiye.

---

### `260830-L` — HyperUP/HyperDL files (crash-safe, WZML trimmed)
**Files:** `tg_transfer.py`, `hyperul_utils.py`, `hyperdl_utils.py`; wired in `pyrogramEngine`, `telegram_download`, `__main__`.

WZML `_hyper_send` = **ek helper bot pick** (load balance), chunk-split nahi. Extra `HELPER_TOKENS` (space-separated bot tokens, sab LEECH_LOG/group me admin). Bina tokens: user session → bot, **boot crash nahi**.

---

### `260830-M` — NameError HELPER_TOKENS + helper logs
**Crash:** `config_dict['HELPER_TOKENS']` tha, variable define nahi.
**Fix:** `HELPER_TOKENS = environ.get(...)` pehle. `__main__` me `start_helper_bots` import. Logger: `HyperUP Helper Bot #N [@user] ID=... Started!`

---

### `260830-N` — NameError `r` is not defined (boot crash)
**Galti:** `__init__.py` last line duplicate `r(timezone=...)` (scheduler ka broken leftover).
**Fix:** woh line hata. `pyroutils.MIN_*` try/except (wzgram).

---

### `260830-O` — uv: No virtual environment found
**Galti:** `uv pip install` Heroku pe venv maangta hai; `--system` ignore / fail, boot spam.
**Fix:** `UV_SYSTEM_PYTHON=1` + `--python python3` + pip fallback; fail pe bot **continue**.

---

### `260830-P` — pyrogramEngine rewrite (wzgram)
**User:** 9 MB/s, sochta hai old engine Bot API 20+ nahi de sakta.
**Sach:** Telegram bot MTProto ~8–12 MB/s typical; 20+ **user/helper**. Engine phir bhi 0 se: signature-filter send_*, FloodWait loop, tenacity-restart hata, thumb/caption/remux/log/PM/dump/media-group same.

---

### `260830-Q` — wzgram `start()` coroutine (`bot.loop` AttributeError)
**Galti:** wzgram `Client.start()` await-able; `.start()` se coroutine, `.loop` nahi.
**Fix:** `_start_tg()` sync+async dono. Duplicate tail `__init__` hata.

---

### `260830-R` — WZML HypertgTransfer + HypertgUpload (not shortcut)
**OLD:** `260830-L` stubs. User 17.57 MB/s ek bot; maanta hai shortcut ki wajah 20+ nahi.

**Sach (WZML wzv3 source):** `_hyper_send` = **ek** client `send_video/document` + least-load helpers. Chunk-split upload **nahi**. 17 MB/s ek bot pe already typical ceiling ke paas.

**Fix:** WZML `tg_transfer.py` (MtprotoPool, HypertgTransfer) + `hyperul_utils.HypertgUpload` (`_hyper_send` / `_direct_send` / flood retry). Main bot client `0`. Engine `send_media` isi path se. Extra speed = `HELPER_TOKENS` (LEECH_LOG admin).

---

### `260830-S` — sendMessage chat=None + multi nextmsg str
**Galti:** wzgram `Message.reply` `self.chat.type`; `chat` None. `sendMessage` error pe `str` return; `__run_multi` `nextmsg.id` → `'str' has no attribute id`.
**Fix:** chat None → `bot.send_message`. Multi/bulk: `hasattr(nextmsg,'id')` check.

---

### `260830-T` — `-i` multi WZML-style (OLD: S incomplete)
**Galti:** `__run_multi` abhi bhi `nextmsg.id` bina Message check. `message.reply` wzgram pe `chat.type`. User `/cmd -i 3` 3 videos.
**Fix:** `sendMessage` = `bot.send_message` (no `.reply`). Multi = WZML `isinstance(Message)` + next media `reply_id+1`.

---

### `260830-U` — NameError `Message` in `__run_multi` (OLD: T)
**Galti:** `from pyrogram.types import Message` file me nahi raha; `isinstance(nextmsg, Message)` crash.
**Fix:** `_is_tg_msg()` — `id` hai aur str nahi. Import nahi.

---

### `260831-A` — idle 0-task high CPU/RAM (9h 71% CPU)
**Galti:** qBit/aria2 DHT+PEX 24/7; leftover torrents; status Interval leak; `alive.py` fail pe 2s hammer.
**Fix:** idle housekeep 90s empty → DHT/PEX off, leftover delete, Interval cancel. Torrent start pe DHT on. `alive.py` error sleep 60s. RAM ~40% qBit 384MB limit — expected.

---

### `260831-B` — idle housekeep khud CPU kha raha tha (OLD: A)
**Galti:** har 45s qBit `torrents_info` + DHT toggle + gc. Task ke turant baad 90s wait. TG leech 92% = 1 vCPU decrypt (alag).
**Fix:** purge **ek baar**; loop **3 min**. `clean()` pe turant `idle_now()`. workers **32→8**. Aria2 leftover har cycle mat hatao.

---

### `260831-C` — no task = qBit+aria2 PROCESS band
**User:** background chowkidar ka matlab nahi; task nahi to heavy **stop**.
**Fix:** `engine_lifecycle.py` — idle pe `pkill` qBit/aria2. TG leech unhe start nahi karta. Torrent/aria2 task pe `ensure_*`. Bot+gunicorn rehte (command + Heroku).

---

### `260831-D` — commands dead (OLD: C pkill)
**Galti:** `pkill -f zetra/xon-bit` boot pe — pattern bot ko maara / aria2 listener toot; `/l7` `/s7` silent, `/r7` chala.
**Fix:** **pkill hata**. qBit+aria2 **chalte rehte**. Idle = DHT off API. Aria2 listener boot pe wapas. NEVER section brain me.

---

### `260831-E` — /s crash aria2:6800 (logs batbin)
**Galti:** `download.eng()` → `get_all_versions()` → `aria2.get_version()` jab aria2 pkill se mara. `/s7` exception, koi reply nahi.
**Fix:** versions try/except (`aria`/`qbit` = `off`). `/s` fail pe NO_ACTIVE_DL, silent nahi.

---

### `260831-F` — /mi7 MediaInfo empty vs dost
**Galti:** `stream_media(limit=5)` = ~5MB start. MP4 `moov` file ke **end** pe → sirf General, Video/Audio gayab. Dost ke file pe moov start pe tha.
**Fix:** head 16MB + tail 16MB (HTTP Range / stream offset). Full file ≤50MB download. `/mi7` crash-safe.

### `260831-K` — 18 MB/s = sequential download_media (OLD: J)
**Galti:** HyperDL fallback; GetFile bina `precise`/`cdn`; default **bot** client.
**Fix:** WZML wzv3 GetFile+CDN + 6 slot pipeline 256KiB; pick **user** session.

### `260831-J` — TG 19 MB/s lock (HyperDL stub + UL Queue 4)
**Galti:** hyperdl 22-line stub; engine `send_video` HyperUL skip; `Queue(4)`.
**Fix:** parallel GetFile 6 media sessions; engine `HypertgUpload.send_media`; save_file Queue 16 / workers 16; concurrent TX 16. 30+ DC/user-session pe depend.

### `260831-I` — MP4 `-c copy` stream Title uda deta (terminal test)
**Test:** `ffmpeg -map 0 -c copy` orig.mp4 → Video/Audio **Title gayab**. Comment rehta.
**Fix:** ffprobe tags copy + `-metadata:s:v:N`/`s:a:N` phir user METADATA overlay. `edit_metadata` + remux.

### `260831-H` — G ne har MP4 pe extra ffmpeg copy (speed drop)
**Galti:** `ensure_faststart` 1.6GB dubara likhta — UL 6.5MB/s, 3m→6m. Title inject nahi, sirf copy.
**Fix:** extra rewrite **hata**. Tags sirf jab `/uset` Leech Metadata / `METADATA` set ho — `edit_metadata` ek pass (`ffmpeg.py`).

### `260831-G` — leech file metadata udd (OLD: F galat)
**Galti F:** `/mi7` sample size — user ne **leech ke baad file** ka meta compare kiya.
**Asli:** remux/ffmpeg `-c copy` bina `-map_metadata 0` + MP4 bina `+faststart` (moov end) + video ko **rename .mp4** (bytes nahi). Dost ffmpeg copy + tags + faststart.
**Fix:** remux/edit_metadata map_metadata + faststart; fake rename hata; mp4 ensure_faststart. `/mi7` F **revert**.

## NEVER
- `pkill` qBit/aria2/bot names
- boot pe listener/engine maarna
- 1 CPU fix se command loop todna
- `brain.md` padhe bina process ops

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


---

### `260831-L` — Bot Settings Hyper Tokens UI
**Git:** (push after)
**Date:** 2026-08-31
**OLD:** `260831-K` / `b8f9db2` (32 GetFile; still ramp). Tokens were env-only.

**Galti:** HELPER_TOKENS / USER_SESSION_STRING ke liye BSet menu nahi tha.

**Fix:** `bot_settings.py` → **Hyper Tokens**: helper list (# username id 4–5 mask, add/remove), user session add/replace/remove (full token kabhi nahi). Persist config + DB; helpers `start_helper_bots`. Speed still main-bot 32 GetFile — tokens extra, not the 30 MB/s fix.

**NEVER pkill.**


---

### `260831-M` — USER_SESSION_STRING untouched; Hyper = helpers only
**OLD:** `260831-L` Hyper UI me user session add/remove tha.
**Fix:** Hyper Tokens = **HELPER_TOKENS** only. `USER_SESSION_STRING` Config Variables me same (premium 4GB). Hyper se edit/remove/reset nahi. Reset button hide + resetvar blocked.


---

### `260831-N` — done msg: max DL / UL speed
**OLD:** complete caption Size + Elapsed only.
**Fix:** status loop `upload_details max_dl/max_ul` peak. Done msg: `DL Speed | UL Speed` after Elapsed (peak; avg fallback if no sample).


---

### `260831-O` — done msg DL/UL separate lines
**OLD:** `260831-N` one line `DL | UL`.
**Fix:** `MAXSPD` two lines: DL Speed then UL Speed (user layout).


---

### `260831-P` — HyperDL Is a directory + DL/UL still not live
**Log:** `HyperDL pipeline: [Errno 21] Is a directory: .../185334/` then fallback `download_media` (hence 6→18 ramp). filename empty → path = dir only.
**Fix:** always append file name to path; HyperDL if isdir join file_name. FileMigrate `nonlocal sess`.
**DL/UL lines:** `7fd15ec`/`f85318e` **Heroku pe nahi the** (update 16:03 from remote arnv1 without those commits). This commit includes them + path fix.


---

### `260831-Q` — HyperDL 0B hang
**Log:** pipeline window=32 then status 0B/s 1m+. 32 GetFile **same Session** serialize/deadlock.
**Fix:** 8 media **slots** (8 sessions), WINDOW=8, GetFile wait_for 25s, FileMigrate per-slot. Incomplete → fallback + first err log.


---

### `260831-R` — HyperDL no FileId DC lock
**OLD:** session `fid.dc_id` (DC4) jab bot DC5 → hang 0B. Log `dc=4 (bot-only)`.
**Fix:** start **bot storage DC**; `FileMigrate` pe us DC pe jao. 4 slots, GetFile 12s timeout, first window 0B → fallback `download_media`. Log: `HyperDL start bot_dc= file_id_dc= using_dc=`.


---

### `260831-S` — TG DL wapas download_media (CPU)
**User:** pehle 20+ MB/s @ ~15
### 260831-T — status instant speed, skip HyperDL wrapper
OLD: speed = total/elapsed so 2-3-7-10 ramp; HypertgDownload() still built pool every leech (CPU).
Fix: 0.4s window instant DL/UL speed (max in upload_details). Direct download_media, no HypertgTransfer init.


### 260831-U — smooth 1s EWMA speed not 0.4s spikes
User: 19-7-12-20-40 jump, CPU high, 43.91 done-msg spike.
Fix: DL/UL speed 1s sample + 0.3/0.7 EWMA; max_dl/ul from smoothed not burst.

