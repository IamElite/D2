# D2 / arnv1 — brain.md

Nayi chat me bolo: **read brain.md**  
Is file se pata chalega: kya galti thi, kya fix hua, **kya plan** tha, kaunsi branch, kaunsa hash.  
Alag `plan.md` **mat** banao — plan + built **yahi**.

**Branch:** `arnv1` only (prod `srmlx` / `main` tab tak nahi jab tak user na kahe)  
**Repo:** https://github.com/IamElite/D2  
**Dyno:** Heroku Standard-2X (~1 GB RAM)

---

## Agent rules (har nayi chat + har push se PEHLE)

1. Kaam shuru: pehle **yeh `brain.md` padho** (FIX LOG + **PLANS**). Do files mat.
2. **Git push se pehle** FIX LOG me naya block:
   - 6-digit ID (`YYMMDD` + serial)
   - git short hash (push ke baad)
   - problem / galti / files / fix
   - purana adhura ho to **OLD: `ID`**
3. User **`/plan`**: PLANS me `P-YYMMDD-A`, **mode: plan**. Dono msgs ka matlab (sirf last line mat).
4. User **`/build`** us plan ka: code, phir usi `P-` ko **mode: built** + git hash. FIX LOG me bhi short ID.
5. User ko push se pehle ID; push ke baad hash.
6. Token / PAT is file me **kabhi mat likho**.
7. **Chat modes (user-defined):**
   - `/ask` ya `.ask` = **sirf baat-cheet** — code/cheez par discussion, sawal-jawab. **Plan nahi banana, brain.md me kuch nahi likhna, code nahi chhedna.**
   - `/plan` ya `.plan` = build/fix se **pehle** PLANS me `P-YYMMDD-X` likho (mode: plan), code nahi.
   - `/build` = code edit/fix/new + FIX LOG block + push.

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


### 260831-V — USet: MEDIA default, Bot PM default on, reset confirm
Leech Type default MEDIA (as_doc False, no AS_DOCUMENT force).
Bot PM default Enabled; button Enabled [✅ Bot PM] / Disabled [ Bot PM ]; user can off (no config force).
Reset: Are you sure... 1 Confirm / 2 No (1 col). Confirm reset+home, No home no reset.


### 260831-W — Leech caption Bot PM (no brackets)
Caption: Enabled - ✅ Bot PM / Disabled Bot PM. Toggle buttons Enable/Disable Bot PM.


### 260831-X — delete Task Started / Leech Started after output
Always delete PM_START, L_LOG_START, LINKS_START after file sent (and on error). Not gated on CLEAN_LOG_MSG.


### 260831-Y — /leech auto engine (WZML-style, cheap)
magnet/.torrent → qBit (later **OLD** by `260901-L`: Aria2 first). yt host → yt-dlp. else aria2.


### 260901-A — bulk/multi cancel tag + self-delete
-b and -i same chain. Cmd + ➲ cancel /c{SUFFIX}_tag. Delay 5s then delete own cmd then next -i. /c7_tag stops remaining queue. First status +2s flood wait. Clone /c7 untouched.

### 260901-B — bulk cancel: 1 notice + delete leftover /l -i cmd
OLD: 260901-A. stop_multi deletes last cmd; run_multi silent if tag gone. No 2nd cancelled msg. Point 2 (-i reply) not touched.

### 260901-C — remember_cmd import in mirror_leech (OLD: 260901-B)
NameError on /l7 -b: import missed remember_cmd. Added.

### 260901-D — -i multi (wzv3 logic, D2 files)
Same URL -i N chains on cmd (no reply_id+1). File-multi: next consecutive msg. Bulk unchanged. next_cmd_text/next_origin. ytdlp/clone no crash if no reply.

### 260901-E — /l -i N on a link LIST = first N lines (like -b with count)
Reply to 8-line list + -i 3 → extract[:3], chain like bulk. Bot cmds reply to USER list not own /l7. Help-spam was first-line-only parse.

### 260901-F — -i N walks following msgs (links+media)
Not one message only. Reply to first, collect N items: lines, videos, docs. Skip bots and the /l7 cmd. -b unchanged.

### 260901-G — stop -i infinite spam (OLD 260901-F)
Spawned /l7 url -i N was re-collecting the list → same 6152 forever, new tags. Collect only if no link, no bulk, not bot. Sleep 7s. Same tag, -i 3→2→1.

### 260901-H — -i chain = bulk chain (one tag, 7s)
Collect only on original /l -i (no link, no bulk). Spawned never re-collects. One /c7_id for remaining; per-file /cancel7_GID stays. Pause 7s.

### 260901-I — -i extract URLs+flags, same-user only
Do not use message-id as task. Text lines only if http/magnet/t.me (keep -n flags). Media = one file. Stop on other user or bot.

### 260901-J — delete last /l -i cmd; trim multi_tools docs
Last -i 1 bot line was kept; now delete_own when multi<=1. next_origin shortened.

### 260901-K — last -b/-i cmd line delete (OLD 260901-J)
Last -i 1 stayed: delete raced. sleep 2 then delete; fallback client.delete_messages.

### 260901-L — torrent Aria2 first, qBit on fail
Auto magnet/.torrent = Aria2 (CPU). Aria add/error/dead → one qBit. No cancel/limit fallback. /qb7 still qBit.

### 260901-M — torrent DHT on; adult /l7 → ytdlp
16KiB/s + 51% CPU: a2c DHT/PEX were off so 1 seeder only. DHT on for BT. NSFW not bot-censor: tubes were Aria HTML; /l7 host hint → ytdlp. Site name if still fail (no URL needed).

### 260901-N — torrent /l7 = qBit again (OLD 260901-L)
Users mostly torrent; Aria 16KiB/s unusable. Auto magnet = qBit. HashingThreads 1, MaxActiveDL 1 so 2X dyno restart kam. HTTP still Aria. /ytdl adult hosts remain.

### 260901-O — /l7 SFW+NSFW same path
No bot NSFW filter. HTML/direct fail → yt-dlp (not Aria HTML). yt-dlp age_limit 99 so age-gated still starts. Magnet still qBit.

### 260901-P — qBit DHT/PEX on during DL (OLD CPU-off)
878KB/s @ 16% CPU, 7 seeders: boot overlay dht/pex False. _set_dht(True) did nothing. Now DHT+PEX on torrent add; idle still off. 200/100 conn.

### 260901-Q — speed from peers not hash CPU
User: speed up, CPU must not climb. hashing_threads 1 (SHA-1). DHT/PEX only while DL (P). Do not raise hash/async.

### 260901-R — /l7 page links start (nsfw.net)
Quality menu blocked /l7 ytdl. /l7 uses best auto. extract fail → aria once, no loop. nsfw.net hint.

### 260901-S — no auto qBit on /l7 (OLD N/L)
/l7 /leech never pick qBit. Magnet/torrent/HTTP = Aria2. qBit only /qb7 /qbleech. Removed aria→qBit failover.

### 260901-T — .torrent URL/file stay Aria2
.html/ytdl path ate .torrent (case/?). Skip that; aria2 BT add. Reply .torrent file same.

### 260901-U — .torrent URL WebPage crash (OLD T)
Reply/preview WebPage treated as TG file → file_unique_id. Skip web_page; use URL → Aria2.

### 260901-V — Aria2 BT opts separate from HTTP
HTTP split/conn unchanged. Torrent/magnet add: follow-torrent true, 100 peers, 1K request-peer, 512K/1M UL for reciprocal DL, no extra hash. Heroku inbound BT port still limited.

### 260901-W — idle CPU: Aria2 DHT off at rest (OLD V)
No-task 45% CPU after BT opts. a2c DHT/PEX default false. Idle stop_heavy also aria2 DHT off. DHT only while torrent add.

### 260901-X — dead torrent stop 90s (CPU)
0 seeders still hunted DHT. bt-stop-timeout 90, peers 40, no 1M UL global. Idle DHT off remains.

### 260901-Y — force Aria2 DHT after torrent add
Used to leech same .torrent; 0 seeders after idle DHT-off. Friend bot still gets peers. DHT/PEX/IPv6 on after add; idle off again.

### 260901-Z — wzv3 addTorrent for .torrent file
WZML aria2_download: local file = addTorrent not addUri. Port via aria2.add_torrent. HTTP/magnet still addUri. Idle DHT/CPU rules kept.

### 260901-AA — Aria2 DHT stay on (friend 15 seeders)
Friend /l2 11MB/s 15S Aria2 1.37, 3h uptime. Ours 0S after restart + idle DHT kill. Keep Aria2 DHT/PEX always; qBit idle DHT still off. Mongo overlay DHT on.

### 260901-AB — do not Dead-torrent at 90s
Same file friend 11MB/s. Ours bt-stop-timeout 90 → Dead torrent 1m39s. Removed default 90; only config TORRENT_TIMEOUT.

### 260902-A — plans live in brain.md (no plan.md)
**Git:** `b90a96e` then this commit  
User: alag plan.md = agent ko 2 file, context waste. Plan + built **isi** file.

---

## PLANS

`P-` IDs. **mode:** `plan` = socha, code nahi. `built` = arnv1 push + hash.  
`/plan` pe naya `P-` yahan. `/build` pe mode badlo. FIX LOG se alag.

### `P-260902-A` — /l7 auto-engine detect (no fail-chain)
**mode:** `plan`  
**Date:** 2026-09-02  

**User (do messages, dono):**  
1) Magnet/ytdlp galat detect. WZML jaisa is_rclone / is_magnet. Magnet params: xt=urn:btih, &tr=, announce, udp tracker. Random torrent site / .torrent → BT, yt-dlp mat. Log: magnet toot ke tracker tukda, HTML→ytdl→aria 20+ baar.  
2) Fail-then-next engine = CPU. Seedha ek check → ek engine. announce → BT. m3u8/.ts → ytdl ek baar. Ek URL = ek add. 20 try nahi.

**Execute:** nahi. Gap = HTML→ytdl loop + magnet split.  
**Build:** bolo `/build` auto-engine. /l7 magnet = Aria2; qBit sirf /qb7.

### `P-260902-B` — is_* helpers: URL-type params (WZML-style)
**mode:** `plan`  
**Date:** 2026-09-02  
**Parent:** `P-260902-A` (dono 50-50 msgs — magnet split + no fail-chain). Yeh uska **kaise**: helpers ke andar params.

**Aaj kya galat:**
- `is_magnet` sirf `MAGNET_REGEX` = `magnet:?xt=urn:(btih|btmh):…` + space. Full magnet (`&tr=` / `announce` / `dn=` / `xl=` / `ws=`) regex pehle `\s*` pe toot → tracker tukda alag “URL” → HTML → ytdl → aria **20×**.
- `_torrent_src` = magnet **ya** path `.torrent`. `announce` / `udp://…/announce` / `&tr=` **nahi**.
- `_YTDL_HINT` host list; **m3u8 / .ts** nahi. `is_url_ytdlp` naam ka fn **nahi**.
- `is_rclone_path` hai; `is_url_rclone` nahi — naam WZML, D2 me `is_rclone_path` rakho.
- HTML `get_content_type` fail → `_ytdl` (fail-chain). Forbidden.

**Build pe kya banana (ab nahi):**

1. **`bot_utils.py` — params *andar* `is_*`** (naya `is_url_ytdlp`; magnet/torrent/rclone stretch):
   - **`is_magnet(url)`** True if any: `magnet:?` + `xt=urn:btih` / `xt=urn:btmh`; 40-hex / 32-base32 hash; `&xt=` / `?xt=`. Poori string **ek** magnet, split mat.
   - **`is_torrent_url(url)`** (naya, `_torrent_src` replace): path `.torrent` (query strip, case); body `announce` / `announce-list`; `&tr=` / `?tr=`; `udp://` ya `http(s)://` **…/announce**; `xs=` / `as=` magnet extras. Random torrent-index HTTP **sirf** agar yeh tokens; warna Aria HTTP.
   - **`is_url_ytdlp(url)`** (naya): known hosts (`_YTDL_HINT` + same); path `.m3u8` / `.m3u` / `.ts` (query strip); `playlist.m3u8`. **BT tokens pehle** — magnet/`&tr=`/`announce` yahan **kabhi nahi**.
   - **`is_rclone_path`**: extra param check `:` remote, `rcl`, `mrcc:` — HTTP/magnet mat khao (`(?!magnet:)` already).

2. **`_auto_engine` first-match (ek URL = ek engine):**
   file_ → tg  
   mega → mega  
   gdrive → gd  
   rclone → rc  
   t.me → tg  
   **`is_magnet` OR `is_torrent_url` → aria BT** (`/l7` qBit nahi; `/qb*` alag)  
   **`is_url_ytdlp` → ytdl once**  
   else → aria HTTP  

3. **Hatao:** HTML/direct fail → `_ytdl`; `_ydl_tried` loop; magnet split. Direct-link generator **sirf** known filehosts, BT/ytdl pe nahi.

4. **Log:** ek line `engine=…` + truncated URL. 20 Task Manager nahi.

**Execute:** nahi.  
**Build:** `/build` auto-engine **ya** `/build P-260902-B`.

### `P-260902-C` — wzv3 asli `is_*` (andar dekha)
**mode:** `plan`  
**Date:** 2026-09-02  
**User:** wzv3 bhitari `is_url_torrent` / params dikhao; git naam galti mat.

**Sach wzv3 `links_utils.py`:** `is_url_torrent` **fn nahi**. Torrent = `is_magnet` + `link.endswith(".torrent")`. Engine cmd se (`is_qbit`), nahi fail-chain.

**wzv3 `is_magnet` (yeh regex port):**
```
^magnet:\?.*xt=urn:(btih|btmh):([a-zA-Z0-9]{32,40}|[a-z2-7]{32}).*
```
Params andar: `magnet:?` + koi chars + `xt=urn:btih|btmh` + hash 32–40 alnum **ya** 32 base32 `a-z2-7` + `.*` (poori line: `&tr=` `dn=` `xl=` `ws=` `announce` toot nahi).

**D2 ab:** `magnet:\?xt=urn:(btih|btmh):[a-zA-Z0-9]*\s*` — `.*` nahi, hash length lock nahi, `&tr=` ke baad split.

**wzv3 `is_rclone_path`:**
```
^(mrcc:)?(?!(magnet:|mtp:|sa:|tp:))(?![- ])[a-zA-Z0-9_\. -]+(?<! ):(?!.*\/\/).*$|^rcl$
```

**wzv3 `is_url`:** rtmp/mms/rtsp/http(s)/ftp optional, host, path, query, hash.

**wzv3 `is_mega_link`:** netloc `mega.nz` / `mega.co.nz` (www strip).

**wzv3 mirror:** HTML/direct **sirf** jab NOT magnet, NOT rclone, NOT gdrive, NOT `.torrent`, NOT mega. Magnet/`&tr=` ytdl nahi. Fail pe ERROR msg, **ytdl retry nahi**. `-yt` flag = ytdl. D2 HTML→ytdl extra (hatao).

**Git naam:** commit = `260902-C plan wzv3 is_magnet` — `brain.md: P-… is_*` type mat.

**Build:** `/build P-260902-C` → D2 `is_magnet` = wzv3 regex; `.torrent` endswith; HTML path skip magnet/torrent; no ytdl fail-chain. `/l7` Aria2; qBit `/qb*`.

### `P-260902-D` — magnet + torrent = **ek** BT pattern
**mode:** `plan`  
**Date:** 2026-09-02  
**User:** magnet aur torrent dono torrent; alag-alag fn/engine mat.

**Ek check `is_torrent(link)`** (naam D2 me `is_magnet` stretch ya ek wrapper — **do engine nahi**):

True agar koi bhi:
- wzv3 magnet regex (`xt=urn:btih|btmh` + hash + `.*` taaki `&tr=` saath)
- path `.torrent` (query strip)
- `announce` / `&tr=` / `?tr=` / `udp://…/announce` **usi string pe** (magnet ke tukde alag URL nahi)

**Phir:** `/l7` → **Aria2 BT ek add**. qBit nahi. ytdl nahi. HTML fail-chain nahi.

**Galat jo agent soch raha tha:** `is_url_torrent` alag + `is_magnet` alag + ytdl alag order = teen raaste. User: **dono torrent, pattern ek.**

**Build:** `/build P-260902-D` (ya auto-engine). Code ab nahi.

### `P-260902-E` — `is_url_*` naam ek pattern, pehle block
**mode:** `plan`  
**Date:** 2026-09-02  
**User:** mix mat (`is_magnet` + `is_url_ytdlp`). URL pe kaam = **`is_url_…`**. Naye URL checks **pehle** (file ke upar / `_auto_engine` se pehle import). Ajib-garib naam nahi.

**Ek family (URL):**
- `is_url` (http/ftp pehle se)
- `is_url_torrent` — magnet **aur** `.torrent` **ek** (P-260902-D); andar wzv3 magnet regex + endswith `.torrent` + `&tr=`/`announce` usi string
- `is_url_ytdlp` — hosts + m3u8/.ts; torrent True ho to yeh False
- `is_url_rclone` — aaj `is_rclone_path` (alias/rename; callers update)
- `is_url_gdrive` / `is_url_mega` / `is_url_telegram` — same prefix (aaj `is_gdrive_link` etc.)

**Nahi:** `is_magnet` alag + `is_torrent_url` alag. Path-only (`is_archive`) `is_` reh sakta — woh URL nahi.

**Order file:** `bot_utils` me `is_url*` cluster **upar** ek jagah, phir baaki. `_auto_engine`: torrent → ytdlp → rclone → … Aria HTTP.

**Build:** `/build P-260902-E`.

### 260902-F — is_url_* + ek torrent + no ytdl fail-chain
**Git:** (local)  
**Date:** 2026-09-02  
**Files:** `bot_utils.py`, `mirror_leech.py`  
wzv3 magnet regex; `is_url_torrent` magnet+.torrent+tr/announce; `is_url_ytdlp`; aliases purane naam. HTML fail → ytdl **hata**. `/l7` Aria2.

**P-260902-A..E mode:** built (isi hash).

### `P-260902-G` — aliases hatao (extra nahi)
**mode:** `plan`  
**Date:** 2026-09-02  
**User:** `is_magnet = is_url_torrent` (aur gdrive/telegram/mega/rclone aliases) **extra** — kyun add?

**Sach:** agent ne purane 50 call sites na todne ke liye alias rakha. User nahi maanga. Mix pattern wapas.

**Build pe:** woh 5 lines **delete**. Har file me `is_magnet` → `is_url_torrent`, `is_gdrive_link` → `is_url_gdrive`, `is_telegram_link` → `is_url_telegram`, `is_mega_link` → `is_url_mega`, `is_rclone_path` → `is_url_rclone`. Sirf `is_url_*`. Alias nahi.

**Execute:** nahi. **`/build P-260902-G`**.

### `P-260902-H` — har call `is_url_*`, shortcut nahi
**mode:** `plan`  
**Date:** 2026-09-02  
**User:** jahan `is_` se call ja raha hai wahan **proper `is_url_`**. Alias/shortcut nahi.

**Build:** `bot_utils` se 5 alias lines hatao. Phir **har py** (mirror_leech, ytdlp, clone, gd_*, tasks_listener, pyrogramEngine, users_settings, category_select, direct_link_generator, …): import + call `is_magnet`→`is_url_torrent`, `is_gdrive_link`→`is_url_gdrive`, `is_telegram_link`→`is_url_telegram`, `is_mega_link`→`is_url_mega`, `is_rclone_path`→`is_url_rclone`. `is_url(` generic HTTP rehta. Non-URL `is_archive` etc. mat chhedo.

**Execute:** nahi. **`/build P-260902-H`**.

### `P-260902-I` — old `is_*_link` naam, naya detect andar; `is_url_*` box hatao
**mode:** `plan`  
**Date:** 2026-09-02  
**User:** `is_url_*` extra. Old best — `link` pehle se tha. Naya regex **unhi** fn me. `is_url_*` cluster **delete**. Magnet: `is_magnet_link` **ya** (better) **`is_torrent_link`** — magnet + .torrent dono.

**Rakho (old naam + naya body):**
- `is_torrent_link` — wzv3 magnet regex + `.torrent` + `&tr=`/`announce` (purana `is_magnet` yahan merge; callers `is_magnet` → yeh)
- `is_gdrive_link` / `is_telegram_link` / `is_mega_link` / `is_rclone_path` — naam same; andar naya check (gdrive usercontent, rclone magnet/mtp skip, mega netloc)
- `is_url` — generic HTTP, pehle se
- ytdl: `is_ytdlp_link` (`*_link` pattern; `is_url_ytdlp` nahi)

**Hatao:** `is_url_torrent`, `is_url_ytdlp`, `is_url_rclone`, `is_url_gdrive`, `is_url_telegram`, `is_url_mega` + 5 aliases.

**Execute:** built `260902-J`.

### 260902-J — old `is_*_link`; `is_url_*` box hata
**Git:** (local)  
**Date:** 2026-09-02  
`is_torrent_link` magnet+.torrent. `is_ytdlp_link`. `is_gdrive_link` etc. naam old. Alias/`is_url_*` delete. Callers `is_magnet` → `is_torrent_link`.

### 260902-K — magnet stitch (log supraseptal)
**Git:** (local)  
Log: tracker tukda `dp.tracker…/announce&tr=` + `HTML/direct fail → yt-dlp` = **dyno purani code** + magnet space/newline split.  
**Fix:** `stitch_torrent_link` poori magnet ek string; `&` ke aas-paas space hata. Reply/cmd pehle line mat kaato.

### 260902-L — Invalid URL = user reply, process band
**Git:** (local)  
User: tracker tukda process mat; `ERROR: Invalid URL` pe **user ko Invalid URL**, ytdl/aria/Task Manager nahi. `is_torrent_link` naam hata → `is_magnet` (magnet + `.torrent` only, announce-only nahi).

### 260902-M — stitch hata; `is_torrent_link` rakha (L ka rename revert)
**Git:** `24ea30a`  
stitch_torrent_link hata; `is_torrent_link` naam wapas (magnet + .torrent; announce-only nahi). brain me L ka "is_magnet rename" ab purana.

### 260902-O — ytdlp wzv3 core port + unknown_video filesize
**Git:** `016fe60` + `a5b18b8`  
yt_dlp_download.py wzv3 core D2 stack pe port; unknown_video filesize fix.

### 260902-P — /yl7 quality menu wapas
**Git:** `48f0a9e`

### 260902-Q — ytdlp quality buttons /l + /yl dono
**Git:** `08c1a27`

---

### P-260902-R — zyl27aug07 logs: R2 direct-file ytdl hang + filename garbage + delete 403 + uv silent fail
**mode:** `built` (260902-U ke saath)  
**Date:** 2026-09-02  
**Logs:** batbin.me/unfallenness (bot zyl27aug07)

**Log me 4 alag problem:**
1. **R2 presigned direct link 2 baar yt-dlp generic pe** (08:44:17 + 08:47:59): `...r2.cloudflarestorage.com/hub/...?X-Amz-Signature=...&response-content-disposition=attachment; filename="Kangaroo.2026...mkv"` → `[generic] Extracting URL` + "Downloading webpage" = 40GB body ko HTML samajh ke scrape → hang/CPU. Attempt B (08:46:22) wahi link Aria2 pe gaya = sahi rasta. `_YTDL_HINT` list me match nahi tha + mirror_leech ka `engine=ytdl`/link log bhi absent → ytdl entry **`/ydl` cmd side** se aayi (auto-engine nahi).
2. **Aria2 filename = query garbage**: `onDownloadStarted: 2e982ff42...?X-Amz-Algorithm=...` — poora query naam ban gaya. Boot WARN `Unknown option: remote-header-name=true` → dyno aria2 ye option nahi jaanta → Content-Disposition header se naam bhi nahi milta.
3. **403 MESSAGE_DELETE_FORBIDDEN** 2 baar (08:46:24 `[ERROR]`, 08:47:16 `ERROR:bot:`): ek delete path guarded par noisy (deleteMessage → LOGGER.error), ek unguarded (root `ERROR:bot:`). Bot ko us chat me delete right nahi — crash nahi, spam hai.
4. **uv update silent fail**: boot-2 `error: No virtual environment found` ke sirf **2ms** baad `Successfully Updated all the Packages !` — pip fallback 2ms me possible nahi → rc jhootha / purana update.py path. Boot-1 uv theek tha (`environment at: /usr`). Saath me unpinned majors ude: motor 3.2.0→3.7.1, pymongo 4.4.1→4.17.0.

**Build pe kya banana (ab nahi):**
1. **`ytdlp.py` direct-file guard**: download se pehle check — URL me `X-Amz-Signature` / `response-content-disposition` / `X-Amz-Expires` presigned pattern (m3u8/.ts chhod ke), ya pehle-bytes GET pe `Content-Disposition: attachment` → ytdl skip, seedha `add_aria2c_download` + log `engine=aria2 (direct-file, ytdl skip)`. Saath me `is_ytdlp_link` hints ko `urlparse(url).netloc+path` pe match karo (full URL pe nahi — query ke `filename="...youtube.com/..."` false-positive se bacho).
2. **Filename fix (`aria2_download.py`)**: `filename` None → URL query parse `response-content-disposition` unquote → `filename="..."` → `out=`. Fallback HEAD content-disposition. Dyno aria2 version se independent — `remote-header-name` pe depend nahi.
3. **a2c.conf**: dyno `aria2c --version` dekh ke `remote-header-name` hata/replace (WARN noise band).
4. **Delete guards**: `deleteMessage` MESSAGE_DELETE_FORBIDDEN pe silent (debug ek line); boot-2 wala unguarded site dhundo (auto_delete_message / delete_links / status cleanup) + wrap. Koi retry-loop nahi.
5. **update.py UPDATE_PKGS**: exact command + real rc + output-tail log; "success" sirf rc==0 pe; uv ek hi path: `--system --python $(command -v python3)`. requirements.txt: `motor<4`, `pymongo<5` pin.
6. Restart 08:46:48 (aria2 start ke 24s baad, koi traceback nahi) — manual restart lagta hai; open question, agle logs me dekhenge.

**Execute:** nahi.  
**Build:** `/build P-260902-R`

### P-260902-S — `yl`/`ydl` URL validation + quoting + consistent unsupported msg
**mode:** `built` (260902-U)  
**Date:** 2026-09-02  
**Parent:** `P-260902-R` (R ke points 1,2,4,5 isi build me saath chalege)  
**User confirm:** 403 delete wala isliye — **bot ke paas us chat me delete power hi nahi**. Fix = silent guard, koi naya message/attempt nahi.

**Verify (code me dekha, sach):**
- `ytdlp.py:248` + `mirror_leech.py:63` dono `text[0].split(' ')` → **URL me space ho (R2 ka `; filename="Kangaroo...mkv"`) to link pehle space pe kat jata hai**. Reply-to se aaye full URL to generic extractor poora kha jata hai = webpage-download hang (log me 2 min+).
- `_ytdl` me `extract_info` se **pehle koi validation nahi**: `.m3u8` ya hint-host nahi bhi, koi bhi URL seedha yt-dlp `age_limit:99` ke saath chala → generic extractor 40GB body scrape.
- Exception pe `yt_cmd` (`/yl7`) → raw yt-dlp error hi user ko jata; `Unsupported URL` ka clean message nahi.
- Auto-engine `engine=ytdl` sirf `_auto_engine` (`/l`) me hai — `yl`/`ydl` cmd us validation se guzarte hi nahi. Inconsistent.

**Build pe kya banana (ab nahi):**
1. **`validate_ytdl_url(link)` shared helper** (bot_utils; async, HEAD/range GET):
   - `is_url` False → Invalid URL
   - `.m3u8/.m3u/.ts` path ya hint-host (netloc+path match) → True
   - `Content-Disposition: attachment` ya file-like content-type (video/audio/octet-stream/zip...) → **False**
   - HTML/unknown → True (yt-dlp try)
2. **`_ytdl` entry pe helper**: False → `sendMessage("yt-dlp not support this URL")` + `__run_multi()` cleanup + `delete_links` + return. **Koi aria fallback nahi** (user ne ytdl manga tha). Exception me `Unsupported URL` error bhi isi clean msg pe map; baaki error raw msg + tag (same abhi jaisa).
3. **Auto `/l` same helper use kare** — `l` aur `yl` dono ka unsupported behavior ek jaisa; direct-file auto pe aria2 (R point 1), `yl` pe msg+stop.
4. **Quoting fix (dono files)**: `split(' ')` → quote-aware tokenizer (`"..."|'...'|\\S+` regex) taaki URL-with-space quotes me ek token rahe; `-n "name with space"` bhi sahi; arg_parser ko items same. `-i` multi/bulk flow na toote.
5. **Delete 403**: `deleteMessage` + unguarded sites me MESSAGE_DELETE_FORBIDDEN → debug-log only, silent. Koi retry.
6. R points saath: aria2 `out=` filename (query content-disposition), a2c `remote-header-name` cleanup, `update.py` real rc + `motor<4`/`pymongo<5` pin.

**Execute:** nahi.  
**Build:** `/build P-260902-S`

### P-260902-T — shipways logs: stitch NameError (LIVE crash) + ffprobe .torrent spam + force_pause errors
**mode:** `built` (260902-U)  
**Date:** 2026-09-02  
**Logs:** batbin.me/shipways (zyl27aug07)  
**Parent:** `P-260902-S` (403/uv/remote-header-name/filename wahin covered)  

**Log me naya (S ke alawa):**
1. **🔴 `NameError: name 'stitch_torrent_link' is not defined`** (13:39:33) — `mirror_leech.py:276` abhi bhi `stitch_torrent_link(raw)` call karta hai, par function `24ea30a` (260902-M "stitch hata") me delete ho gaya. `grep` = sirf call site bachi hai, def kahin nahi. **Trigger:** `/l` reply-to kisi magnet text pe → task turant marta hai, **user ko koi reply nahi** ("Task exception was never retrieved"). Live dyno (08:58 build = HEAD ke paas) me confirm hua. **URGENT — pehla fix build me.**
2. **🟠 ffprobe `.torrent` payload pe** (13:47–13:53, ~20 baar): `Media Info FF: .../LegalPorno...torrent: Invalid data found` + `Media Info Sections` ERROR. User ke BT packs ke andar **payload hi .torrent files** hain; upload engine `pyrogramEngine.py:479` har file pe `get_media_info` (ffprobe) chalata hai. Non-media pe ffprobe = error spam + bekar CPU (60 task/6min bulk chal raha tha).
3. **🟡 `GID#xxx cannot be paused now`** (~15 baar ERROR): `aria2_listener.py` `__onBtDownloadComplete` — `listener.seed` False → `force_pause(gid)`; download already complete/state nikal chuka to aria2p ye error deta hai. Benign race, ERROR-level spam. Same call `aria2_download.py:108`, `torrent_select.py:61`.
4. Purane confirm: 403 delete ×6, uv fake-success + `remote-header-name` WARN (08:58 boot me bhi) — S/R plan me hain.

**Build pe kya banana (ab nahi):**
1. **stitch fix**: line 276 → `reply_text = raw.strip() if is_torrent_link(raw.strip()) else raw.split("\n", 1)[0].strip()` — poori magnet (multi-line) `is_torrent_link` se pakdi jayegi, stitch fn ki zaroorat hi nahi. Import check.
2. **get_media_info guard**: media-extension whitelist (video/audio/image) ke alawa sab pe ffprobe skip — `.torrent`/`.zip`/unknown → `(0,"","",")` bina ffprobe, debug-level ek line. `pyrogramEngine:479` duration call bhi pehle extension check.
3. **force_pause benign**: pause se pehle `download.status` check ya except me `"cannot be paused now"` → `LOGGER.info`; ERROR nahi. Teen call sites.
4. S wale points (validate_ytdl_url, quoting, 403 silent, aria2 out=, remote-header-name, update.py rc, pins) isi build me saath.

**Execute:** nahi.  
**Build:** `/build P-260902-T` (S+T ek build — S ke points + T ke 3 fix)

### 260902-U — S+T build: stitch crash, yl validation, quoting, ffprobe guard, pause spam, out=, 403 silent, pins
**Git:** `1084240`  
**OLD:** P-260902-R/S/T (teeno plans isi build me execute)  
**Files:** `mirror_leech.py`, `ytdlp.py`, `bot_utils.py`, `leech_utils.py`, `aria2_listener.py`, `aria2_download.py`, `message_utils.py`, `a2c.conf`, `update.py`, `requirements.txt`

**Fix (minimal, full-repo context):**
1. **T1 stitch NameError**: `mirror_leech.py:276` — deleted fn ki call hata; magnet multi-line ho to `" ".join(raw.split())` (MAGNET_REGEX phir match), warna first-line logic same. Reply-to magnet ab marta nahi.
2. **S1 `is_ytdlp_supported()`** (bot_utils, ek hi jagah): hints/m3u8 → True; `X-Amz-*`/`response-content-disposition` presigned → False; warna 1-byte ranged GET (10s timeout) — attachment/video/audio ctype → False. Guard `_ytdl` me extract se pehle → `/l`-auto aur `/yl` dono funnel wahi hai = **ek insertion point, extra code zero**. False → `yt-dlp not support this URL` + cleanup + stop (koi aria fallback nahi).
3. **S2 shlex** (dono files): `split(' ')` → `shlex.split` (ValueError pe purana split) — quoted URL/`-n "name with space"` ek token.
4. **T2 ffprobe guard**: `get_media_info` me media-extension check pehle — `.torrent`/unknown pe ffprobe nahi (CPU bachat, spam band).
5. **T3 force_pause**: `cannot be paused now` → info level (benign race), baaki errors error hi.
6. **S4**: aria2 `out=` URL query ke `response-content-disposition` se (regex tested: `Kangaroo...mkv` aya); `remote-header-name=true` a2c.conf se hata (WARN band).
7. **S3 403 silent**: `deleteMessage` + `delete_all_messages` me MESSAGE_DELETE_FORBIDDEN → debug (bot ke paas delete power nahi — user confirmed).
8. **S5**: update.py error me `rc=` (3ms fake-success ka sach samne aayega); pins `motor<4`, `pymongo<5`, `wzgram<4`.

**Note:** dyno boot-2/3 me PURANA update.py chal raha tha (slug old) — fake success uska; HEAD honest hai. **Heroku pe ek rebuild/redeploy chahiye** taaki slug fresh ho.

### P-260902-V — update.py self-refresh: restart = latest code, redeploy khatam
**mode:** `built` (260902-AA)  
**Date:** 2026-09-02  
**User:** update.py aisa bano ki main file badlo → bas RESTART me naya code aa jaye, baar-baar redeploy na karna pade.

**Sach (code padh ke, purani galti correction):**
- update.py har boot: `.git` rm → `git init + add . + commit + fetch + reset --hard origin/arnv1` → **bot code restart pe pehle se fresh aata hai** (log: "Successfully updated with Latest Updates!"). Redeploy bot files ke liye zaroori KABHI nahi tha.
- Meri `260902-U` note "slug old, rebuild chahiye" adhuri thi — 08:58 boot ka purana behaviour isliye: (a) us waqt fixes push hi nahi hue the, (b) **update.py khud slug-frozen** hai (pull se PEHLE chalta hai = chicken-egg). Boot-2/3 ka `No virtual environment found` + fake-success = slug me 260830-O se bhi purana update.py → 260830-O ke baad redeploy hi nahi hua.
- Slug-frozen: `update.py`, `start.sh`, `Procfile` (repo me nahi, Heroku setting). Baaki sab (bot/, a2c.conf, qBit conf) restart pe fresh.

**Build pe kya banana (ab nahi) — Option A, sirf update.py, ~10 lines:**
1. Pull se **pehle** `update.py` ka md5 hash (`_h1`), reset ke **baad** `_h2`. `_h1 != _h2` → `os.execv(sys.executable, [sys.executable, __file__])` with env guard `D2_UPD_REX=1` — naya update.py khud re-run (fresh process, koi double memory nahi).
2. Guard phase-2: `D2_UPD_REX` set ho to pull block **skip** (code fresh hai; 3-5s + CPU bachat) — seedha env → uv pkgs → exit.
3. Loop-safe: guard env + hash-same dono; execv fail to normal continue.
4. `start.sh`/`Procfile` ko mat chhedo (bash mid-read risk; aur wo rarely badalte).

**Limit ( sach):** ye code slugs me aane ke liye **EK aakhri redeploy** lagega (chicken-egg) — uske baad update.py khud b restart pe fresh. Start.sh/Procfile badle to hi kabhi redeploy.

**CPU/RAM:** re-exec sirf tab jab update.py badla ho (rare); phase-2 pull-skip = har normal restart pe extra kaam zero.

**Execute:** nahi.  
**Build:** `/build P-260902-V`

### 260902-X — agent rules: chat modes define (/ask par plan banana galti tha)
**Git:** d19faef  
**Galti:** `/ask` (dead-torrent CPU sawal) me jawab ke saath `P-260902-W` bhi brain.md me likh diya — `/ask` sirf discussion ke liye hai.  
**Fix:** Agent rules me rule 7 — teen modes: `/ask` (sirf baat, kuch nahi likhna), `/plan` (P- plan), `/build` (code). `P-260902-W` user ne B approve kiya tha isliye plan valid — ab aage `/build` ke bina code nahi, aur `/ask` me brain.md me kuch nahi.

### P-260902-Y — GoFile DDL upload KeyError: 'folderId' → clean error chahiye
**mode:** `built` (260902-Z)  
**Date:** 2026-09-02  
**Logs:** batbin.me/bisnaga (14:18 boot = naya code live ✅ — uv clean, DBD nyaa .torrent→Aria2 BT, TG DL fast, m3u8→engine=ytdl sab sahi chala)

**Problem (14:31:06):** WowGirls folder (BT complete, 64s me) → DDL upload GoFile pe → `KeyError: 'folderId'` → "DDL Upload has been Cancelled" + traceback, task error.

**Sach (code se):**
- `gofile.py:upload_folder` → `create_folder(...)` → `__resp_handler(resp.json())` return karta hai; GoFile API error de (token expire/rate-limit/status error) to dict me `folderId` **nahi** hota → line 76 `folder_data["folderId"]` pe KeyError. Asli wajah = **API ne error diya**, KeyError sirf symptom (debug-friendly message zero).
- Loop me bhi wahi pattern: `currFolderId = (await self.create_folder(...))["folderId"]` (line 85).
- `ddlEngine.upload` except me `onUploadError(err)` user ko jata — KeyError aaye to user ko sirf `'folderId'` jaisa bekaar msg milta.

**Build pe kya banana (ab nahi) — ~8 lines gofile.py me:**
1. `upload_folder` ke dono `create_folder` results pe guard: `folderId` nahi mila → `raise Exception(f"Gofile: folder create failed ({status/data})")` — 2 call sites, chhota local helper (DRY, extra code zero).
2. `upload()` file path already `gCode.get("downloadPage")` check karta hai — waise hi folder path ab clean raise dega; ddlEngine ka except user ko **real reason** dikhaega (token/limit), traceback spam bhi kam (KeyError ki jagah readable msg).
3. `__resp_handler` ko haath NAHI (sab endpoints use karte hain — risky, rule 1).

**Observation (no code):** m3u8 do baar process hua 12s gap se (:38 `/yl` route, :50 `/l` route `engine=ytdl`) — user ke do cmds lagte hain, bug nahi. DBD-Raws dead torrent 14:20 se chal raha — guard plan W remove ho chuka, bina guard ke chalega.

**Execute:** nahi.  
**Build:** `/build P-260902-Y`

### 260902-Z — GoFile folder-create guard (KeyError → real reason)
**Git:** `da93ff1`  
**OLD:** `P-260902-Y` (plan)  
**Files:** `bot/helper/mirror_utils/upload_utils/ddlserver/gofile.py` (sirf yehi, +12/−5)

**Galti:** `upload_folder` me `create_folder` ka result bina check `["folderId"]` — GoFile API error (token/limit) pe KeyError, user ko bekaar msg + traceback spam.

**Fix:** chhota `__folder_id()` helper — dict me `folderId` nahi → `Gofile folder create failed: <API ka status/message>`. Dono call sites (root folder + loop subfolder). `__resp_handler` untouched. Compile + 5-case logic test pass.

### 260902-AA — update.py self-refresh (push → restart = naya code, redeploy khatam)
**Git:** `c23acbd`  
**OLD:** `P-260902-V` (plan)  
**Files:** `update.py` (sirf yehi, ~+20)

**Galti:** update.py pull se PEHLE chalta hai = khud kabhi update nahi hota (chicken-egg). 260830-O ke baad redeploy nahi hua to purana update.py hi chalta raha (fake-success wala).

**Fix:**
- Pull se pehle `update.py` ka md5 `_h1`, reset ke baad `_h2` — badla → `D2_UPD_REX=1` env + `execv` se khud re-exec (naya updater fresh process me)
- Re-exec run me pull **skip** (`D2_UPD_REX` guard) — code fresh hai, 3-5s + CPU bachat
- Loop-safe: guard env + hash-same dono; execv fail → normal continue
- `start.sh`/`Procfile` untouched (bash mid-read risk)

**Test:** sim — purana→pull→naya re-exec ("pull skipped, NEW VERSION LIVE") ✅; no-change single run ✅; compile ✅

**⚠️ User note:** is fix ko slug me lane ke liye **EK aakhri redeploy** zaroori (chicken-egg) — uske baad kabhi nahi: bot file badlo → push → restart → fresh. Sirf start.sh/Procfile badle tabhi redeploy.

### 260902-AB — GoFile REAL fix: API ne `folderId` → `id` kiya (+ Z ka adhura def)
**Git:** `553b92e`  
**OLD:** `260902-Z` (adhura — def edit file me pahuncha hi nahi tha, sirf call-sites gaye = NameError risk)  
**Files:** `bot/helper/mirror_utils/upload_utils/ddlserver/gofile.py` (sirf yehi)

**Asli galti (dono):**
1. GoFile API badla — `createFolder` success ab `data.id` deta hai, `data.folderId` purana ([gimpyestrada/gofile docs](https://github.com/gimpyestrada/gofile/blob/main/API%20Documentation.md), yaGatito/gofile-client). API call OK hoti thi, code galat key kheenchta → KeyError. Z sirf error-msg polish tha, upload fix nahi.
2. Z commit me `__folder_id` def missing push ho gaya tha — live pe NameError hota. User ne pakda ("fix nhi kiya").

**Fix:** `__folder_id` def (folderId **ya** id dono accept, error pe API ka status raise) + dono call sites (root:81, loop:92). Baki endpoints/`__resp_handler` untouched (servers + uploadfile + update live-tested = alive).

**Test:** compile + runtime class test — new `id` ✅ old `folderId` ✅ error raise ✅

### P-260902-AC — update.py Mongo db `beast` → `kpsmlx` (upstream escape-hatch sab boots pe chale)
**mode:** `built` (260902-AD)  
**Date:** 2026-09-02  
**Logs:** batbin.me/degumming (dyno-start vs /restart diff)

**Proof (degumming):** dyno start (16:53/16:54) = SLUG ka purana update.py — "Updating packages" line nahi, `No virtual environment found` + 2ms fake-success; /restart (17:09) = disk ka NAYA update.py (pull ke baad) — `uv environment at: /usr` + real installs. Deploy `a681d88f` ne arnv1 latest update.py uthaya hi nahi (Heroku Deploy branch check karna hai — user step, code nahi).

**Root cause (design todat hai):** update.py:62 `db = conn.beast` — par bot (bot/__init__.py:118) aur DbManger (db_handler.py:21) dono **kpsmlx** me likhte hain. Dyno boot pe updater ko Mongo-upstream (UPSTREAM_REPO/BRANCH jo BSet save karta) dikhta hi nahi → pull config env pe depend; /restart me bot-ENV inheritance se chal jata hai.

**User design (preserve):** upstream Mongo me rehta hai (escape hatch — galti se galat repo/branch ho to vars me doosra repo daal ke start + BSet se Mongo fix). Isi design ko sab boots pe sahi karna hai — bypass nahi.

**Build pe kya banana (ab nahi) — 1 line:**
1. `update.py:62` → `db = conn.kpsmlx`. Bas. Collections (`settings.deployConfig`/`settings.config`) same hain, bot+updater ab ek hi db padhenge → dyno start pe bhi Mongo-upstream uthega, escape-hatch har boot pe kaam karega.

**Prereq (user step, code nahi):** Heroku Deploy branch `arnv1` — taaki slug me naya update.py (AA self-re-exec + ye fix) aaye.

**Execute:** nahi.  
**Build:** `/build P-260902-AC`

### 260902-AD — update.py db beast → kpsmlx (Mongo-upstream har boot pe)
**Git:** `eb3a032`  
**OLD:** `P-260902-AC` (plan)  
**Files:** `update.py` (1 line)

**Galti:** updater `beast` db padhta tha, bot/BSet `kpsmlx` me likhte — dyno start pe Mongo-upstream invisible, sirf /restart (bot-ENV) se sahi pull.

**Fix:** `update.py:62` → `db = conn.kpsmlx`. Repo me `beast` ka yehi ek reference tha. Escape-hatch design same: upstream Mongo se, vars = override.

### P-260902-AE — /log Web Paste: dead spacebin → BatBin API
**mode:** `built` (260902-AF)  
**Date:** 2026-09-02  
**Logs:** user ka traceback — `spaceb.in/api/v1/documents` POST → 404 HTML → `.json()` → JSONDecodeError crash, block pe try/except bhi nahi.

**Sach (live-tested):** spacebin naya (Luna/Go) rewrite — purana v1 API gaya (404). BatBin zinda: `POST https://batbin.me/api/v2/paste`, body = plain text, **`Content-Type: text/plain;charset=UTF-8` (charset zaroori, warna 415)** → `{"success":true,"message":"<key>"}` → URL `batbin.me/<key>`. Frontend bundle se decode + 2 live pastes se confirm. paste.gg 503 not_allowed, del.dog down.

**Build:** mirror_leech.py `webpaste` block (sirf yehi 1 jagah repo me):
1. spacebin call → BatBin (utf-8 bytes + charset header + `timeout=15`)
2. `success` true → button `📨 Web Paste (BatBin)` → `batbin.me/<message>`; false/exception → LOGGER.error + user ko chhota fail msg (poora block try/except = crash kabhi nahi)
3. Bonus: `else` branch ka undefined-`err` NameError leftover hata (naya except wale me clean hai)

### 260902-AF — build: webpaste spacebin → BatBin
**Git:** `fca9b85`  
**OLD:** `P-260902-AE` (plan)  
**Files:** `bot/modules/mirror_leech.py` (sirf webpaste block, ~+9/−6)

**Fix:** BatBin v2 paste (utf-8 bytes, charset header, timeout=15); success → `📨 Web Paste (BatBin)` button `batbin.me/<key>`; fail/exception → LOGGER + user ko fail-msg, crash kabhi nahi (pehle JSONDecodeError pe callback crash hota). `err` NameError leftover gaya. Live E2E test: 200 + success + `batbin.me/carniferrin` ✅

### 260902-AG — status Engine label: wzgram → notygram (display only)
**Git:** `2b923e6`  
**Files:** `bot_utils.py` (1 line, `STATUS_TG`)  
User request: library wzgram hi rahegi, sirf status me naam "notygram" dikhana hai. Koi package/func change nahi.

### 260902-AH — status style (user design): task no, mention, Done/Time/UP, 〄 footer
**Git:** `f6dc953`  
**Files:** `kpsml_minimal.py` (7 template lines), `bot_utils.py` (builder: enumerate + USER upar + ID hata)

**User ka naya style (usne khud banaya):**
- `{1}` task number name se pehle (enumerate page-aware: STATUS_START+1; Tno=f'{{{tno}}}' = literal braces)
- User line `┎ <b>User</b>: {mention}` upar (name ke turant baad, bar se pehle) — pyrogram mention link; purana `┠ User: <code>| ID:` hata (ID me mention tha hi ab)
- `Processed` → `Done`, `Elapsed` → `Time`, footer `UPTIME` → `UP`, `⌬` → `〄`
- Bar `[■▧□□...]` + `#Tg` mode pehle se code me the (koi change nahi — rule 1)

**Render test:** output user ke sample se line-by-line match ✅ (bar, Done, Time, UP, 〄, {1}, mention, ┎/┖)

### 260902-AI — bar 12-fixed + User line me ID-mention
**Git:** `3108949`  
**OLD:** `260902-AH` (User mention tha, ID nahi; bar 13-block bug)  
**Files:** `bot_utils.py` (bar fn + USER arg), `kpsml_minimal.py` (USER template)

**Fix:** bar partial-block pe 13 ho jata tha (AH nahi, INITIAL se hi) — ab hamesha 12 (`□' * max(12-len)`, 100% pe 12■). User line = ID hi text + ID mention-link (`tg://user?id={Id}`) — user ko tap karke profile.

### 260902-AJ — Tno template asli fix (AH ki edit fail thi) + 〄 → ❑
**Git:** `482552e`  
**OLD:** `260902-AH` (builder Tno bhejta tha par theme me {Tno} hi nahi tha — format_map silently ignore; pichli Mongo-files theory Tno ke liye galat)  
**Files:** `kpsml_minimal.py` (2 line: STATUS_NAME + FOOTER)

**Fix:** `STATUS_NAME = '{Tno} <b><i>{Name}</i></b>'` → `{1} Name`; FOOTER `〄` → `❑`. User ke BSet-upload ke liye poora updated theme workspace me bana (`kpsml_minimal.py`).

**Seekh:** parallel edit_file ke baad verify (grep) karo — do baar (Z, AH) "success" ke baad bhi change persist nahi hua.

### 260902-AK — bar 1-100% proportional + TG download timeout retry
**Git:** `3c0bbc9`  
**OLD:** `260902-AI` (bar 96 pe full ho jata tha — user: "12 blocks me 1-100% fit"); TG `Request timed out` = ek exception me task dead (14m wala)  
**Files:** `bot_utils.py` (bar fn), `telegram_download.py` (`__download` retry)

**Fix:**
- Bar: `filled = int(p * 0.96)` shades (12×8) — 8.33%/block, 96% pe 11■+▧, 100% pe 12■. Test: 8.33→1■, 50→6■, 96→11■▧, 100→12■ (sab 12 len)
- TG DL: `download_media` 3 attempts (3s gap, pyrogram partial-file resume); cancel/decrypter-user_sess path same behaviour; sirf sach me 3 fail hone pe error
