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
**Git:** `8d7ced3`
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

### 260902-AL — wzv3 CDN-pull port (asli speed-secret) + AK ka retry sach me
**Git:** `89e8089`  
**OLD:** AK (retry sirf naam ka tha — 4th silent-edit fail; `git show 3c0bbc9` = sirf import gaya, body nahi)  
**Files:** `hyperdl_utils.py`, `telegram_download.py` (bash-python edit, grep-verified)

**Kya port (wzv3 hyperdl_utils se, SilentDemonSD/WZML-X source se padha):**
- `_getfile` me `FileCdnRedirect` pehle se pakda jata tha par **use nahi hota tha** → ab `_cdnpull`: pool session CDN-DC pe (`get_session(idx, cdn_dc, slot=NSLOT+slot)` — cache-key me dc hai, conflict-safe), `upload.GetCdnFile` → `ctr256_decrypt(key, iv[:-4]+off//16)` (C-level, cheap), `CdnFileReuploadNeeded` → main client `ReuploadCdnFile`, `FileToken/RequestTokenInvalid` → `_cdn=None` → non-CDN GetFile
- `CHUNK 256→512KB` (invokes aadhe = kam CPU), NSLOT/WINDOW 4 hi (in-flight ≤2MB RAM)
- `download_media` hot path: **≥50MB pe pipeline-first**; first window me CDN engage nahi → native (native 20MB/s @15% CPU hi best hai non-CDN pe); CDN ho to parallel CDN-DC pull (wzv3 jaisa)
- `telegram_download.__download`: ≥50MB bot-client pe pipeline try → fail/native fallback; retry 3× (AK ka adhura ab poora)

**CPU/RAM:** decrypt C me; buffers 2MB; sessions pool-cached (per-chunk auth nahi); non-CDN pe native hi (75% CPU wala purana pipeline sirf CDN-confirmed pe chalta hai)

**Seekh:** bade edit_file is repo me 4 baar silently ude — ab bade changes bash-python se + grep-verify hamesha.

### 260902-AM — ExportAuthorization flood fix (auth cache, DC-agnostic)
**Git:** `87914dc`  
**Logs:** frontierlike — AL ke baad pipeline har task pe `FLOOD_WAIT_X 116-172s (auth.ExportAuthorization)` se first-window fail → native fallback (tasks safe, par CDN kabhi nahi milta). Wajah: `get_session` har slot pe `Auth.create` + export/import karta tha — cross-DC pe 4 slots × 6 tasks = ~50 exports.  
**User req:** code DC-agnostic — dost ke bots DC1/DC2 pe, hamara DC5 — koi DC hardcode nahi.

**Fix (`tg_transfer.py`):** module-level `_auth_cache[(client_key, dc_id)]` + `_auth_locks` + `_auth_imported` — per (client, DC) **poore bot-life me 1 export** (lock me auth+import, parallel zero). Same-DC → storage auth_key (jaisa pehle). Naye pool/task instances bhi cache reuse.  
**(`hyperdl_utils.py`):** cross-DC slots 4→2 (auth pressure aadha, same-DC 4 hi); FileMigrate same-DC → debug (spam band).

**Test:** compile + grep ✅. Expect: pehle task pe 1 export, baaki sab instant sessions; FileMigrate spam gone; CDN ab engage ho sakta hai.

### 260902-AN — export gate: flood ke dauran API-hammering band (psychoanalysts logs)
**Git:** `9cb7b40`  
**OLD:** AM (cache tha, par flood pehle se active hone pe bhi har naya task/retry export try karta raha → penalty 172s→580s chadha, native bhi cross-DC exports pe fail)  
**Files:** `tg_transfer.py`, `telegram_download.py`

**Fix:**
- `_auth_block[(ck,dc)]` gate — FLOOD_WAIT aate hi `Auth.create`/`ExportAuthorization` us (client,DC) ke liye `now+v+2` tak band; beech me koi bhi `get_session` **bina API call** ke turant `ExportBlocked` uthata hai (penalty aur lambi nahi hoti)
- Native retry flood-aware: FLOOD_WAIT >90s → **task clean stop** (`TG flood Xs — baad me resend`, 3 baar hammer nahi); ≤90s → sleep(v+2) phir retry; baaki errors purane jaise 3×
- Seedhi baat: flood ~10 min me khud utrega; gate us dauran aag pe tel na dalega. Naya boot = fresh cache, gate pehle export try karega, flood hua to block + baad me ek hi retry.

**Note:** ye flood AM se PEHLE wale burst (frontierlike) ka zakhm tha — AM ka cache use ne rok diya ki har boot me wapas na bhadke.

### 260902-AO — Docker self-host: python:3.11.9-slim + heroku.yml (container stack ka sahi rasta)
**Git:** `8fcb3c8`  
**User flow:** Heroku stack = **container** (`FROM nanthakps/kpsmlx`) — isliye runtime.txt kabhi kaam nahi karta; nanthakps image = ubuntu:22.04 + system py3.10 + **buildkit secrets** (`RUN bash /run/secrets/wzmlx`) = Dockerfile/source kabhi public nahi (registry history se confirm).  
**Files:** `Dockerfile` (naya), `heroku.yml` (naya)

**Dockerfile:** `python:3.11.9-slim-bookworm` base (yt-dlp/Google warnings gayab; 3.12 nahi — TgCrypto/ forks risk), apt: ffmpeg aria2 qbittorrent-nox p7zip unrar mediainfo tzdata; pip+uv at **build-time** (runtime pe install nahi); code COPY fresh (runtime git-pull belt-and-suspenders rahega). `heroku.yml` = git-push → docker build (deploy = ek git push, jo waise bhi pending hai AA/AD/AN ke liye).

**Deploy flow (user):** push → Heroku image build → release → **sab fixes pakke slug me** + Python 3.11. Restart-only life uske baad bhi (update.py pull code fresh rakhta hai image ke upar).

### 260902-AP — Dockerfile full-parity (mega SDK compile, poora toolset) + mega lazy-import
**Git:** `aff113f`  
**OLD:** AO (Dockerfile adhura tha — user sahi pakda: megasdk/zip/AtomicParsley etc. base-image me the, mujhe nahi likhe the)  
**Files:** `Dockerfile` (rewrite: 2-stage), `bot_utils.py` (mega import lazy)

**Base-image scan (registry layers extract karke, /tmp/img me khola):**
- L1: ubuntu22.04 + py2.7/3.10 + 7z-suite, aria2c, ffmpeg/ffprobe, mediainfo, qbittorrent-nox, **rclone v1.64**, git/curl, gcc/g++, **AtomicParsley**, **MEGA SDK v4.8.0** (source `/sdk` + compiled `libmega.so`, `_mega.so` cpython-310 bindings)
- L2: **whiteouts** `.wh.{aria2c,ffmpeg,qbittorrent-nox,rclone}` + decoy 0-byte bins `xon-bit`, `zetra` (jinka naam pe pehle pkill hua tha!) — matlab `latest` tag me runtime bins badal ke rakhe; `v3`/`heroku_v3` tags alag (728-740MB)

**Naya Dockerfile:** multi-stage — STAGE1 `meganz/sdk v4.8.0` cmake+swig compile (**py3.11 bindings** — purane `.so` 3.10-ABI the, reuse impossible), STAGE2 runtime (sab tools + zip/unzip + atomicparsley + rclone static + deps build-time). `WITH_MEGA=0` build-arg = fast build (MEGA creds use hi nahi karte). `bot_utils` mega import lazy — SDK bina bhi bot kabhi crash nahi.

**Verify:** docker sandbox me nahi hai — pehla real build user karega; build-log issues → turant fix.

### 260902-AQ — status style v2 (user design): SPD/TT, clock ETA, slash, i-free
**Git:** `ed9d834`  
**OLD:** AH/AI (of→link-overflow, aria2p MiB)  
**Files:** `kpsml_minimal.py` (SPD/TT labels), `bot_utils.py` (builder slash + clock_fmt + elapsed clock), `aria2_status.py`, `telegram_status.py`

**Fix:**
- aria2p *_string() (MiB/GiB wala **i**) hata → `get_readable_file_size(raw)` = clean MB/GB/KB (Done/Size/SPD sab); `progress()` ab pure percent float
- `clock_fmt()` naya — ETA + TT dono `HH:MM:SS` (blank-ETA bug bhi gaya, 0s = 00:00:00)
- Builder: Done `of` → `/`; Elapsed clock
- Labels: `Speed:`→`SPD:`, `Time:`→`TT:`; **Status hyperlink rakha** (user confirm — paste me plain dikhta tha bas)
- TG path: eta clock; i to TG pe pehle se nahi tha

### 260902-AR — Status plain text (hyperlink hata)
**Git:** `55650f9`  
**OLD:** AQ (Status <a href> me tha; user: default plain hi rakho — line chhoti, overflow safe)  
**Files:** `kpsml_minimal.py` (1 line: STATUS template)

**Fix:** `Status: <a href="{Url}">{Status}</a>` → `Status: {Status}` — plain, builder Url pass karta rahega (unused, harmless).

### 260902-AS — STATUS wapas default hyperlink (AR galat samjha tha)
**Git:** `30cadad`  
**User ka matlab:** "default jaisa rehne do" = **default me link hai, wahi raho**. AR me plain kar diya tha — ulta.  
**Fix:** `STATUS` template wapas `'\n┠ <b>Status:</b> <a href="{Url}">{Status}</a>'` — bilkul default. Baaki AQ ke sab (SPD/TT/clock/i-free/slash) bane rahenge.

### 260902-AT — clock_fmt timedelta crash fix (AQ regression, meshier logs)
**Git:** `1a93eaf`  
**OLD:** AQ (aria2 `.eta` = `datetime.timedelta` — `int()` TypeError → status-render crash → **BT task download-error**)  
**Files:** `bot_utils.py` (clock_fmt robust: timedelta.total_seconds(), None→'', junk→'')

**Seekh dobara:** naya format har status-class ke type pe test hota (aria2 timedelta vs TG seconds).

### 260902-AU — Bot PM option Universal Settings se remove (Leech me rakha)
**Git:** `9b4d53b`  
**OLD:** AU-prior — Bot PM toggle 2 jagah (Universal + Leech) duplicate  
**Files:** `users_settings.py` (universal block: 3 lines + kwarg), `kpsml_minimal.py` (UNIVERSAL template)

**Fix:** Universal se button + `Bot PM : Enabled` status hata; `Save Mode` ab `┖` closer. **Leech page untouched** (button+status+callback) — functionality zero change (engine/BOT_PM config jaise hai).

### 260902-AV — Include/Exclude Ext user filters (Universal Settings)
**Git:** `8297dda`  
**OLD:** AV-prior — koi user ext-filter nahi tha (sirf global GLOBAL_EXTENSION_FILTER)  
**Files:** `fs_utils.py` (DEFAULT_EXCLUDED_EXTS + `is_ext_allowed()`), `pyrogramEngine.py` (upload() me per-file filter), `users_settings.py` (9 spots: desp/fname dicts, universal buttons+text, edit views, callbacks reuse yt_opt flow, set_custom parser, `/cmd -s` list), `kpsml_minimal.py` (UNIVERSAL +2 lines)

**Design:** Include default `none` (off); Exclude default list `aria2,!qb,index,html,nfo,text,bmp,webp,tiff,tif,svg,ico,raw,heic,heif,txt` har user pe active. Rules: inc set → sirf wahi; warna exc lagega; `default`→default list (exc), `none`→off/allow-all; parse comma/space, lowercase, dot-strip, sorted. Storage: `inc_ext` list / `exc_ext` list; `''` = default-idiom (delete buttons d{key}); `[]` = allow-all. Unwanted files upload-loop me `aioremove` (global-filter pattern). Flow reuse: `event_handler`+`set_custom` (yt_opt jaisa), delete `dinc_ext`/`dexc_ext` → universal refresh + DB. **Tests:** filter 14/14, parser, resolve, render — all PASS.

### 260902-AW — Exclude Ext default list ab visible
**Git:** `24b71f7`  
**OLD:** AV — default pe sirf `default` word dikhta tha, user ko list ka pata nahi  
**Files:** `users_settings.py` (2 lines: universal `exc_str` + edit-view `cur`)

**Fix:** default case me `default: ` + poori sorted list (97 chars, trun-100 fit). Custom list pe sirf list. Edit view: `Default List: <list>`.

### 260902-AX — .torrent URL bot-side pre-fetch (pornrips HTTP-500 bypass)
**Git:** `3928deb`  
**OLD:** AX-prior — aria2.add(link) server-side fetch karta tha; pornrips.to jaise trackers aria2 ko 500 dete hain (curl/browser/aiohttp ko 200) = BT task dead  
**Files:** `aria2_download.py` (`_prefetch_torrent()` + wire-in add pe)

**Design:** `.torrent` URL → aiohttp fetch (browser UA + Referer origin, user -h headers merge-override, 30s timeout, 10MB cap) → validate (b`4:info` bencode ya ctype bittorrent) → `/tmp/{uuid}.torrent` → `add_torrent(file)` → finally remove. HAR fail (non-200/oversize/not-torrent/timeout/exception) → `None` → purana direct `aria2.add` fallback. Magnet/local-file untouched. **Tests:** real pornrips fetch 39791B bencode-OK + 5 gate/fallback tests = 6/6 PASS. qBit route scope me nahi.

### 260902-AY — clock_fmt bogus-ETA cap (24000000000:00:00 → 00:00:00)
**Git:** `0779c50`  
**OLD:** AY-prior — aria2p speed=0/metadata-wait pe `timedelta.max` (≈24e9 hrs) raw print hota tha  
**Files:** `bot_utils.py` (clock_fmt: `seconds > 31536000` → `00:00:00`; ek line, AT ke robust block me)

**Note:** user ka explicit design — unknown/wait ETA = `00:00:00`. Real bade ETA (3din=72:00:00) safe. Aadha bypass: AX pre-fetch ke baad metadata jaldi aata hai.

### 260902-AZ — prefetch generic relay escape (TORRENT_PREFETCH_PROXY)
**Git:** `98d8fdf`  
**Experiment:** sandbox se public relays sab dead — codetabs/allorigins 522 (site unhe bhi block), corsproxy 403-keygate, cors.lol/workers.dev 429-rate, jina 422. Client-side (www/query/UA) sandbox pe 200 = Heroku-500 reproduce impossible yahan → block IP-reputation (Heroku/AWS ranges).  
**Files:** `aria2_download.py` (`_prefetch_torrent` relay-aware + `from os import environ`, `quote`)

**Design:** direct-first; fail (non-200/exception) pe env `TORRENT_PREFETCH_PROXY` engage — `{url}` placeholder = relay-template (quote-encoded), warna HTTP-proxy (aiohttp proxy=). Sab routes fail → None → direct-add fallback (AZ-prior chain intact). **Site-agnostic** — koi bhi blocked site. **Tests (mock-relay e2e):** direct+file-survives-return (finally-bug regression — cleanup sirf except me), 404→template-relay OK, 404→dead-proxy graceful-None, no-env-404 None, gates — 5/5 PASS. CF-worker snippet chat me diya.

### 260902-BA — ETA clock-format poore status-family me (qbit+9 missed, user ne pakda)
**Git:** `2cbf21a`  
**OLD:** AQ slip — sirf aria2+telegram patch hue the; qBit status me `ETA: 33m57s` purana dikh raha tha  
**Files:** `status_utils/`: qbit, attachment, ddl, direct, extract, gdrive, mega_download, metadata, yt_dlp(2 spots), zip — eta-block `get_readable_time`→`clock_fmt` + imports; rclone — `clock_fmt(obj.eta) or obj.eta` (unparseable fallback); split — `'0s'`→`'00:00:00'`; queue `'-'` untouched

**Seekh:** format-style change me SAB status-classes ka sweep karo, sirf jo dikhe nahi. Multi-line import regex ne direct_status toota tha — haath se fix. Final sweep: koi eta old-format me nahi.

### 260902-BB — prefetch UA-chain (Wget-first; qBit ke Wget-1.12 proof se)
**Git:** `df06932`  
**Discovery:** qBit route `torrents_add(headers={'user-agent':'Wget/1.12'})` se pornrips fetch karta = site UA/fingerprint-block (pure-IP nahi). Wget UA Heroku se pass.  
**Files:** `aria2_download.py` (`UA_CANDIDATES=('Wget/1.12',BROWSER_UA)`; req_headers UA-free; user `-h User-Agent` → single-attempt override; relay last, uas[-1] ke saath; tag `ua[wget]/ua[mozilla]/relay`)

**Sweep-proof:** .torrent HTTP-fetch sirf 2 jagah — aria2 prefetch (patched) + qbit (already Wget, untouched). direct_listener=DDL, get_content_type-branch torrent-link pe skip — koi purana path nahi.  
**Tests (UA-aware mock):** T1 wget-first-single-attempt, T2 wget-500→browser-retry, T3 relay-fallback, T4 all-fail-None, T5 user-UA-override single, T6 gates, T7 REAL pornrips Wget-UA 39791B — 7/7 PASS. (Test-assertion bug: REQ_LOG raw-path record.)

### 260902-BC — rclone fallback prefetch (user idea; permission ke baad)
**Git:** `b6e74f8`  
**Context:** BB ke baad bhi Heroku pe leech fail (no log) → block TLS-fingerprint-level (qBit/Qt pass, aiohttp/aria2 fail). rclone = Go-HTTP client, alag family.  
**Files:** `aria2_download.py` (`_rclone_fetch()` + wire-in for-else, `shutil.which`-guard, `cmd_exec` import)

**Design:** chain = aiohttp[Wget] → aiohttp[browser] → **rclone copyurl** (default rclone UA = sabse alag fingerprint; --no-check-certificate; 30s contimeout/timeout; size+bencode validate; partial-file cleanup) → relay-env → direct-add fallback. rclone absent → skip gracefully. **Tests (real rclone + UA-aware mock):** R1 wget500→mozilla500→rclone200, R2 no-binary None, R3 all-dead None, R4 single-attempt regression, R5 gates, R6 real-site — 6/6 PASS. Heroku verdict live task se hoga; fail → relay env.

### 260902-BD — rclone Wget-UA + full-error log (refragate log: exit=1 reason kata tha)
**Git:** `abf542b`  
**Files:** `aria2_download.py` (2 lines: `--header User-Agent: Wget/1.12` rclone args; stderr full, newlines→` | `)

**Note:** `rclone.conf not found` NOTICE = routine (copyurl ko config nahi chahiye; mirror apna --config path use karta hai — unrelated). BD aim: agli Heroku run pe ya pass (Wget-UA formula) ya asli fail-reason visible.

### 260902-BE — HOTFIX: BD f-string py3.10 crash (bot-down!) + py3.10 audit-method
**Git:** `762a557`  
**Incident:** BD ka `f'...{err.replace(chr(10), ' | ')}'` = nested same-quotes = py3.12+ feature; Heroku py3.10 → SyntaxError aria2_download.py:41 → **poora bot boot-crash** (drusean log chunk-2 me pakda). Sandbox py3.13-compile ne pass kiya tha = blind spot.  
**Fix:** logger %-style args (`LOGGER.warning('...%s %s', rc, err.replace('\n', ' | '))`) — version-safe.  
**Naya standing audit:** `uv python install 3.10` + `uv run --python 3.10 python -m py_compile` **poore repo** pe (101/101 OK). `ast feature_version` f-string-nesting pakadta hi nahi — bharosa nahi. Har push se pehle real-3.10 compile.  
**Regression (hotfix ke baad):** mock full-chain (sab-block→None, full-err visible: `CopyURL failed: 500` x3 — BD logging perfect), gates, **REAL pornrips via rclone[Wget-UA] = 39,791B** (F5). Note: test-env (rclone binary, /tmp, pip pkgs) turn ke beech reset hota hai — rerun me reinstall.

### 260902-BF — container-truth RAM/CPU + restart pull-fix (user report: 85%+ readings, /restart purana code)
**Git:** `e50ad02`  
**Root 1 (RAM/CPU):** psutil `virtual_memory()/cpu_percent()` = **HOST-wide** (dyno /proc host ka) — padosi dynos + boot-churn (uv sync, qbit recheck) ka bhisht. Boot 2min-window samples the, task-wale nahi.  
**Root 2 (restart):** /restart me update.py stale config.env se pull karta — drift pe fail/old → bot old-code pe boot. Race nahi (gather wait tha); config-resolution drift tha.  
**Files:** `bot_utils.py` (`_cg_read`, `get_container_memory()` cgroup v2/v1→psutil fallback, `get_container_cpu()` usage-delta; get_readable_message footer + get_stats stbot cgroup-aware), `__main__.py` (restart: update.py ko env-override UPSTREAM_REPO/BRANCH = bot ka proven config; rc!=0 → user-visible warning), `update.py` (pull-success pe `Running commit: <hash>` log)

**Tests:** py3.10 full-repo 102/102; cpu helper delta-live (None→1.0); memory fallback; env-override sim PASS. Heroku pe RAM% ab container-limit ka hoga.

### 260902-BG — Helper hot-swap (bina restart; user demand)
**Git:** `f86f906`  
**Gap:** `_persist_helpers` (buttons add/remove) already sync karta tha, par generic config-set paths (text editvar + callback editvar) HELPER_TOKENS pe sync nahi karte the + purane helper clients kabhi stop nahi hote (leak).  
**Files:** `hyperul_utils.py` (`_stop_client` clean-stop, `_started_tokens`+`get_active_helper_tokens()`, `asyncio.Lock`-wrapped `start_helper_bots`→`_locked`), `bot_settings.py` (donon generic config-paths me `HELPER_TOKENS` → instant `start_helper_bots`), `__main__.py` (`_helper_watcher` 30s drift-check → auto-resync; create_task in main)

**Flows covered:** buttons add/remove (pehle se), generic /bset text+callback (naya instant), DB-direct edit (watcher ≤30s). Lock = watcher/handler double-start race safe. Invalid token = fail-ignored, baaki helpers/bot safe.  
**Tests:** py3.10 full-repo 102/102; stub-client functional A-F (add/remove/clean/invalid/re-add/drift-compare) ALL PASS.

### 260902-BH — yt-dlp impersonation (CF anti-bot 403 fix; luciferdonghua/Rumble case)
**Git:** `5f956a1`  
**Root:** CF-fronted hosts (rumble embed/hls, luciferdonghua-page) Heroku pe yt-dlp ko 403 challenge dete hain; bot ke yt-dlp me curl_cffi nahi → impersonation unavailable → /yl crash. Sandbox IP blocked nahi (403 repro impossible) — fix = yt-dlp ka apna recommended path.  
**Files:** `requirements.txt` (+curl-cffi), `yt_dlp_download.py` (`_detect_impersonate()` module-singleton: curl_cffi-import + YoutubeDL-init hard-validate; `add_impersonate()` copy-on-add + user-override setdefault), `ytdlp.py` (extract_info wire)

**Learnings:** python-API me `impersonate` = **ImpersonateTarget object** (string → AssertionError); curl_cffi missing + blind-set = **hard YoutubeDLError** (sab /yl mar jate) — isliye detect-validate pattern. Global option = host-agnostic (rumble/dood/koi bhi CF-host).  
**Tests:** py3.10 102/102; helper A/B/C (detect-add-copy, user-override, no-dep untouched); E2E rumble m3u8 with ImpersonateTarget = 6 formats. Luci-page iframe-hunter = future /plan (scope tight rakha).

### 260902-BI — beeg leading-zero id fix (normalize_ydl_link)
**Git:** `1337fc0`  
**Root:** beeg.com ke naye ids leading-zero wale (`-0943576720716295`); yt-dlp Beeg extractor id as-is `store.externulls.com/facts/file/` API ko deta hai → API int-parse `invalid syntax` → **400 Bad Request** (CF/impersonation se koi lena-dena nahi). API response ne khud bataya.  
**Fix:** `normalize_ydl_link()` — beeg URLs pe leading-zero strip (`-09435…`→`-9435…`); no-zero ids/query/non-beeg untouched. Wire: `extractMetaData` + `add_download` + `ytdlp.extract_info` (3 entry-points, ek helper).  
**Tests:** API 200-stripped vs 400-zeroful (curl-proof); unit 5/5; **real E2E = 15 formats** (impersonate chrome ke saath); py3.10 102/102. Upstream yt-dlp bug — jab upstream fix ho to normalizer harmless rahega.

### 260902-BJ — HOTFIX: re_sub NameError (BI ka import-check bug)
**Git:** `b3be0be`  
**Incident:** BI patch me mera conditional-import logic galat tha — file me `re_search` tha, check `from re import` dhundh ke skip kar gaya, `re_sub` import nahi hua → beeg-link pe runtime `NameError: re_sub is not defined`. Compile-check nahi pakadta (runtime error).  
**Fix:** line 6 = `from re import search as re_search, sub as re_sub`. Runtime-exec test + py3.10 102/102.  
**Seekh:** patch me jab bhi "already imported?" conditional ho — to jo SYMBOL chahiye WOHI grep karo, family nahi.

### 260902-BK — beeg generic-title fix (site-caption se asli naam; scoped)
**Git:** `d8a7402`  
**Root:** beeg API ne schema badla (`stuff.sf_name` → `file.data[] cd_column/cd_value`) — yt-dlp extractor purane path pe → title generic fallback `Beeg video #<id>` → filename garbage.  
**Files:** `yt_dlp_download.py` (`is_generic_title()` + `fix_generic_title()`; extractMetaData me non-playlist `result['title']` patch — single choke-point: self.name/outtmpl/leech-name sab isi se)  
**Scope (user-dandi):** sirf generic-pattern titles + sirf beeg (verified source). Good titles/non-beeg = untouched. API-dead = original title, no crash.  
**Tests:** sandbox T1-T6 + real-module T1-T5 (impersonate-loaded urlopen, guards, dead-API, urllib fallback); filename E2E = `St. Patrick's Day Cosplay Compilation [id].mp4`; py3.10 102/102.

### 260902-BL — Avg + Max DL/UL speed summary (user design)
**Git:** `b137e85`  
**Root:** summary me sirf max tha; user ko avg (kitna mila) + max (top speed) dono chahiye. Beeg ke template-suffix `1575` (tbr, height-missing) = alag issue (BL-2 pending, user ne option nahi chuna).  
**Files:** `tasks_listener.py` (`avg_dl` size/dl-window @download-end; render AVGSPD+MAXSPD; tg.upload-post avg_ul=size/engine-window fallback), `pyrogramEngine.py` (`_ul_engine_t0` @__user_settings), `kpsml_minimal.py` (AVGSPD key `Avg DL/UL Speed` + `┃` + MAXSPD labels `Max DL/UL Speed`)  
**Avg math:** bytes ÷ total-seconds (true average; inst-sampling ka jhooth nahi). Fallbacks: engine-t0 miss → old _ul_t0/size path.  
**Tests:** render preview exact user-design; avg-math 3.91MB/s sample-match; py3.10 102/102.

### 260902-BM — TG-download duration 00:00 fix (pipeline holes + moov heal)
**Git:** `888aa36`  
**Root (sandbox-proof):** HyperDL `_pipeline` me `done < size*0.95` → 5% holes ACCEPT; TG-video ka moov END me — end-chunks hole → ffprobe `moov atom not found` → duration=0 → player 00:00. Pipeline sirf TG ≥50MB use hota — isliye sirf TG files me (yt-dlp/torrent normal-write).  
**Files:** `hyperdl_utils.py` (`done < size` STRICT 100% → native fallback self-heal; empty-chunk silent-skip → RuntimeError→fallback), `leech_utils.py` (`get_media_info` duration-missing diagnostic warn; `repair_moov()` — ffmpeg `-c copy +faststart` re-encode-NAHI, verified-duration ya None), `pyrogramEngine.py` (video-branch: duration==0 → heal → replace+re-fetch; guard = sirf broken)

**Tests:** ffprobe-holed=dur-missing (proof), mid-hole=30s (index-safe), heal-missing=graceful, heal-capability=30s-repaired, guard code-verified; py3.10 102/102. BL ka 1575-suffix issue alag pending (user option nahi chuna).

### 260902-BN — Avg/Max divider removal (user: tight layout)
**Git:** `a4f9ac3`  
**Fix:** AVGSPD se `┃` divider hata (BL me maine add kiya tha, user ko bhaari/bekaar laga). Ab Avg UL → Max DL seedha, jaise Mode-Total-Files lines. Render-verified + py3.10 102/102.

### 260902-BO — summary order: Mode Avg-Max ke beech (user design)
**Git:** `333fe3a`  
**Fix:** onUploadComplete render order = AVGSPD → MODE → MAXSPD (pehle MODE baad me tha). L_TOTAL_FILES apni jagah last. Render user-sample se exact match; py3.10 102/102.

### 260902-BP — heal-metadata artifacts fix (graph.org diff report: .heal suffix + title-doubling + Menus:3 + fonts-lost)
**Git:** `398b946`  
**Root (BM ka heal mp4 me convert kar raha tha):** mkv→mp4 remux = container change → fonts-drop, stream-title doubling (mp4 title/handler merge), 3x menu-tracks, filename `.heal.mp4` leak.  
**Fix:** `repair_moov` v2 — **same-container heal** (mkv→mkv `map 0` full-preserving [sandbox: tags byte-identical + attachment survives], mp4→mp4 + stream-title clear flags +faststart); **`os.replace` wapas ORIGINAL naam** (suffix leak root-fixed; khud-banaya `await os_replace` bug test me pakda — sync syscall). Engine: `healed != up_path` guard.  
**Tests:** mkv same-name/identical-tags/no-leftover, fonts ✓, duration ✓, mp4 branch ✓, unfixable-graceful ✓; py3.10 102/102. BP-note: MetadataX-style caption cards ab clean (no .heal, single Menu, fonts listed).

## 260902-BQ — Stream-title purge + all-format metadata (STREAM_TITLES)
**Git:** `90e4a77`  
**Push:** `71b0174..1e4cf35` DONE. **ORIGIN URL CHANGE: `github.com/IamElite/D2.git`** (purana arnv1/wzv3 404; PAT IamElite account ka, repo list me IamElite/D2 hi hai — arnv1 branch wahi, HEAD 71b0174 se match hua). PAT brain me NAHI — user dena hoga har window me.  
- **Demand:** user custom stream-titles/tags find karne me dikkat → purane stream-titles REMOVE karke apne lagane; metadata code kisi bhi file-format pe smartly chale (`.mkv/.mp4` ext-gate unacceptable).
- **Config:** `STREAM_TITLES` env (bot/__init__.py, config_dict) — `''`=off | `purge`=sab stream-titles delete | `purge|v:Video Title|a:Audio Title`=delete+custom set. Per-user overlay BAAD me (users_settings abhi nahi).
- **ffmpeg.py:** `edit_metadata(..., stream_titles='')` — ext-gate REMOVED (sab formats); overlay me `__purge_stream_titles__`/`__stream_title_v__`/`__stream_title_a__`; `probe_tag_args` purge branch: `tags.pop('title')` + explicit delete-arg `-metadata:s:{pref}:{idx} title=` (EMPTY-VALUE DELETE — arg-missing = INHERIT, yahi root-trick hai) + custom set. tasks_listener: dono edit_metadata calls stream_titles pass.
- **Bonus fix (pre-existing):** error-path `await suproc.stderr.read().decode()` → AttributeError on ffmpeg-fail; fixed `(await ...read()).decode(errors='ignore')` — fail-open (original intact, upload unchanged).
- **Tests (sandbox real.mkv 2 streams+chapters):** purge-only ✓ titles-gone; purge+custom `['JoJo 1080p HQ','Hindi 5.1']` ✓; chapters ✓; mp4-out ✓; empty-config old-path ✓; incompatible-remux (h264→webm) graceful fail ✓. py3.10 102/102.

## 260902-BQ — Stream-title purge + all-format metadata (STREAM_TITLES)
- **Demand:** user custom stream-titles/tags find karne me dikkat → purane stream-titles REMOVE karke apne lagane; metadata code kisi bhi file-format pe smartly chale (`.mkv/.mp4` ext-gate unacceptable).
- **Config:** `STREAM_TITLES` env (bot/__init__.py, config_dict) — `''`=off | `purge`=sab stream-titles delete | `purge|v:Video Title|a:Audio Title`=delete+custom set. Per-user overlay BAAD me (users_settings abhi nahi).
- **ffmpeg.py:** `edit_metadata(..., stream_titles='')` — ext-gate REMOVED (sab formats); overlay me `__purge_stream_titles__`/`__stream_title_v__`/`__stream_title_a__`; `probe_tag_args` purge branch: `tags.pop('title')` + explicit delete-arg `-metadata:s:{pref}:{idx} title=` (EMPTY-VALUE DELETE — arg-missing = INHERIT, yahi root-trick hai) + custom set. tasks_listener: dono edit_metadata calls stream_titles pass.
- **Bonus fix (pre-existing):** error-path `await suproc.stderr.read().decode()` → AttributeError on ffmpeg-fail; fixed `(await ...read()).decode(errors='ignore')` — fail-open (original intact, upload unchanged).
- **Tests (sandbox real.mkv 2 streams+chapters):** purge-only ✓ titles-gone; purge+custom `['JoJo 1080p HQ','Hindi 5.1']` ✓; chapters ✓; mp4-out ✓; empty-config old-path ✓; incompatible-remux (h264→webm) graceful fail ✓. py3.10 102/102.

### 260903-BR — Metadata settings UI: Set/Remove per-key + Custom Tag buttons (2x2)
**Git:** `73e1a9e`  

**Demand:** user-settings leech metadata me tag set karne ke baad REMOVE ka option hi nahi tha. Per-key tap pe: set hai → Set/Change + Remove + Back; not-set → only Set + Back. End me Custom Tag favourite-buttons (add/remove) — click pe 4 options 2x2: Set Value | Remove Value / Remove Button | Back.
**Files:** `users_settings.py` (META_KEYS constant — 3 dup lists collapse; `get_custom_btns()` helper; menu-builder custom-buttons section + ➕ New Button header; new callbacks: `md_key` submenu, `md_rm`, `md_cbtn` 2x2, `md_cset`, `md_crmval`, `md_crmbtn`, `md_cadd`; `add_custom_md_btn()` setter; md_edit Cancel→`md_key {idx}`), `ffmpeg.py` (`probe_tag_args` unknown-key passthrough — custom labels raw tags bane).
**Storage:** `user_dict['md_custom']` = `Label1|Label2` (sanitize: `:|` strip, 32-char, max 10, dedupe case-insensitive); custom VALUES normal `metadata` string me `Label:Value` — leech-time tasks_listener automatically apply. Label == metadata key.
**Container-limit (proven):** mp4 muxer unknown keys silently drop karta hai (exit-0, whitelist-only: title/comment/artist...) — custom tags sirf mkv/webm pe likhe jate hain (MY_CHANNEL uppercase-normalized). No crash, graceful.
**Follow-up (user):** naye buttons/prompts se emojis removed — plain text (Set Value, Remove Value, Remove Button, Back, New Button; ✅/❌ status functional rakha).  
**Tests:** T1a mkv custom+known+purge ✓; T1b mp4 comment ✓ + unknown-drop ✓; T2 parse/rejoin/labels/sanitize ✓; T3 7 new callbacks wired + META_KEYS single-source ✓; T4 layouts (2x2 + submenu) ✓; py3.10 102/102.

### 260903-BS — Ext-less filename fix (metadata + heal) + .mka mediainfo
**Git:** `3450233`  

**Source:** live log (batbin saintless) — `test metadata` (ext-less TG video) pe `edit_metadata`/`repair_moov` dono "Unable to find a suitable output format" fail (graceful, fail-open — upload hua, metadata miss).
**Root:** ffmpeg output format filename-ext se infer karta hai; ext-less → fail. ffprobe input ko content-se pehchanta hai (moov-missing file ko NAHI — moov hi index hai).
**Fix (probe sirf ext-less pe — ext-present old-path byte-identical):** `ffmpeg.py` `_MUX_PRIORITY` + `media_muxer()` (ffprobe format_name → mp4/matroska/webm/mov/mpegts/avi/... ya None); `edit_metadata` outfile ext-less → `-f <mux>` (probe-None → skip, junk-safe); `leech_utils.repair_moov` ext-less → same `-f` + mp4_mode by mux (same-container heal preserve); `.mka` `get_media_info` whitelist me added (mediainfo ab audio pe bhi).
**Trap caught (own test):** pehle probe-gate dono pe laga tha → broken-moov (heal ka MAIN case) ffprobe-se unknown hota hai → heal skip ho jata — gate sirf ext-less pe shift kiya.
**Tests:** T1 ext-less mp4 metadata ✓; T2 ext-less mkv purge ✓; T3 junk skip ✓; T4 .mkv regression ✓; T5 heal ext-less mp4 ✓; T6a broken .mp4 = old-code identical graceful ✓ (T6b healthy heal ✓); T7 heal ext-less mkv ✓; T8 broken ext-less skip ✓; T9 .mka whitelist ✓; py3.10 102/102.

### 260903-BT — Metadata har media pe + ext-less default .mkv
**Git:** `5556ed9`  

**Demand:** (1) koi bhi file pe metadata lage (audio bhi), (3) ext-less filename → default `.mkv`. (#2 remove-caption stale — state-logic simulation CLEAN nikla, user-se clarify pending.)
**Changes:** `edit_metadata` — video||audio gate (listener dono paths single+dir), ext-less outfile → probe-confirm → `.mkv` append (matroska default, mp4-content bhi matroska me copy); return moved-path; `tasks_listener` up_path sync; `repair_moov` ext-less → `<name>.mkv` heal (engine guard old remove karta).
**Own-bugs caught (tests):** same-dir move crash → dirname-guard; same-path outfile == input → ffmpeg "Output same as Input" reject → `.meta.<ext>` tmp + atomic os_replace; error-branch clean_target(outfile) original delete → abspath-guard (original KABHI delete nahi).
**Env-note:** /tmp test-assets turn-reset me udte — T7/T8 ke phantom-fail isi se the (audio.mka missing), code clean.
**Followup REVERTED (user clarify):** value-inline galat samjha — user ko BUTTON pe sirf label chahiye (✅/❌ + naam); asli point caption-text stale tha (remove ke baad) — md_rm/md_crmval/md_crmbtn/update_user_settings re-render verified clean; live me phir stale dikhe to exact-button-steps lena.  
**Tests:** T1 ext-less→.mkv+tags; T2 junk skip; T3 mp4 in-place; T4 ext-less purge→.mkv; T5 heal ext-less→.mkv; T6 heal .mp4 regression; T7 mp3 metadata; T8 mka purge; T9 broken-ext-less skip; T10 corrupt in-place safe. py3.10 102/102.

### 260903-BU — Live-crash fix: `ospath` typo + missing `-y` (duplicate-completion)
**Git:** `23d2642`  

**Source:** live log (batbin spottier, commit 763b085) — `shutil.Error: Destination 'test metadata.mkv' already exists` + `HyperDL pipeline failed: name 'ospath' is not defined - native` → 434MB DOUBLE-download → task fail.
**Root-chain (dono mere BT se):** (1) edit_metadata return-path me `ospath.join` typo (alias `os_path` hai) → SUCCESS pe NameError → HyperDL wrapper (telegram_download L110) ne "pipeline failed" samjha → native RE-download → duplicate completion. (2) pass-2 me outfile pre-existing + `-y` flag MISSING → ffmpeg "Not overwriting - exiting" **rc=0** → stale file move → shutil.Error.
**Fix:** `os_path.join` typo; `-y` flag add (repair_moov me tha, edit_metadata me upstream-se missing); move() → `os_replace` (same-fs atomic + overwrite — duplicate-completion idempotent).
**Lesson (test-harness):** sandbox ns me extra `ospath` tha isliye typo pakda nahi — ab ns = REAL module imports only.
**Tests:** T1 ext-less+return ✓; T2 duplicate-completion (outfile+dest pre-existing) overwrite + naya title ✓; T3 in-place ✓; T4 purge ✓; ospath-repo-check NONE; py3.10 102/102.

### 260903-BV — Auto-purge: METADATA set = uploader tags CLEAN (user-ask via /ask + graph 47073/47058 diff)
**Git:** `4945d07`  

**Proof:** real (47073) — Movie name/EncodedBy/OFFICIAL_SITE `Power By @Otaku.../AnimeDubHindi`; bot (47058) — user keys overlay ✓ lekin `OFFICIAL_SITE: animedubhindi.co` BACHA (preserve-mode jo key user ne set nahi ki uska purana tag rehta).
**Design (user chose B):** METADATA set = AUTO-PURGE — `probe_tag_args` has_user_meta → `fmt={}` (original format-tags drop, sirf user keys emit); `edit_metadata` cmd me `-map_metadata -1` (global copy band). METADATA empty → preserve (STREAM_TITLES-only purge ka old behavior intact).
**Result (T1 tags):** title/copyright/encoded by/telly_hub sirf user ke; OFFICIAL_SITE/ARTIST GONE; encoder=Lavf naya (muxer standard). Stream-titles STREAM_TITLES/system jaisa pehle.
**Tests:** T1 purge+sirf-user-tags ✓; T2 stream user ✓; T3 metadata-empty preserve+stream-purge ✓; T4 no-config full-preserve ✓; py3.10 102/102.

### 260903-BW — Auto-purge attachment-fix (-map_metadata -1 → per-tag delete)
**Git:** `ddedcf3`  

**Source:** live — `[matroska] Attachment stream 2 has no filename tag` + `Could not write header` metadata-fail (fail-open OK; heal ne baad me .mkv heal kar diya). BV ka `-map_metadata -1` attachment streams ka mimetype/filename bhi clear karta — matroska inko mangta. Sandbox-PROVEN: A(no -1) attach ✓; B(-1) exact live-error; C(per-tag delete) purge ✓ attach ✓.
**Fix:** probe_tag_args — orig_fmt snapshot; has_user_meta → jo original keys user ne set NAHI ki (ukeys = key_map.get(uk,uk)) unpe `-metadata k=` delete-args + fmt.pop (emit-loop double na likhe); user keys set/override baad me. edit_metadata se `-map_metadata -1` REMOVED. _TAG_SKIP keys skip (muxer fresh likhta).
**Tests:** T1 ext-less+attachment+user-meta → .mkv, purge ✓, attachment filename+mimetype intact ✓; T3 metadata-empty full-preserve ✓; T4 override+purge ✓; py3.10 102/102.

### 260903-BX — Per-stream tags UI+engine + Add Custom Tag manager (user-ask, graph 47349)
**Git:** `3f6102c`  

**Ask:** Video/Audio/Subtitle me Title ke alawa bhi tags (Copyright/Encoded By/Artist/Comment); New Button → "Add Custom Tag" (end me) + list/Remove/Add-More manager.
**Engine (ffmpeg.py):** overlay compound keys (`Video Comment:x` / `Audio Artist:y` / `Subtitle Encoded By:z`) → `stream_meta[ctype][tag]` → stream-loop me `-metadata:s:{pref}:{idx} {tag}={v}`; `title` sub-key global-title ko override; passthrough se compound EXCLUDE (global-tag leak zero — T2 proven).
**UI (users_settings.py):** builder — 15 general keys + Stream Tags section (✅Video/Audio/Subtitle → md_str) + custom buttons + **"Add Custom Tag"** (body/end); `md_str` (5 sub-keys 2-col + Back) → `md_skey` (Set/Change+Remove+Back) → `md_edit s {sidx} {name...}` / `md_rm s ...` (dual-mode: g=general-idx, s=stream-name); **md_cman** manager: [name→md_cbtn][Remove→md_crmbtn] rows + "+ Add More" (md_cadd) + Back; md_cadd back→md_cman, heading "Add Custom Tag".
**Tests:** engine T1 per-stream video(title+comment)/audio(artist+comment) ✓; T2 compound-global-leak ZERO ✓; T4 stream-purge+compound co-exist ✓; UI-sim builder-status/callback-parse/md_cman rows/wiring ✓; py3.10 102/102.

### 260903-BY — Menu restructure: streams-first + legacy-remove + Add Custom Tag lone
**Git:** `45d4c09`  

**Ask (user):** (1) pehle se set keys (Audio/Video global...) remove kaise — (2) Set All ke just niche 3 buttons (Video/Audio/Subtitle) + chhota caption ("sab tags + custom milenge") — (3) stream menu me sab tags + CUSTOM bhi (scoped `Video <Custom>`) — (4) Add Custom Tag = akela button, Back/Close ke upar (l_body).
**Changes (users_settings.py):** builder — stream 3-buttons body-first (header ke turant niche, caption line ke saath); general keys baad me; extras section (`Purane set tags (Remove yahin se)`) — meta_dict ke aise keys jo kisi button me cover nahi (≤30char, non-stream-compound) → `md_xkey` (Set/Change+Remove+Back); `md_xset` (set_metadata_key generic) / `md_xrm`; `md_str` me custom buttons bhi (→ `md_csbtn` → md_edit/md_rm s-mode, key `Video <Label>`); Add Custom Tag → l_body (footer ke upar akela).
**Engine:** ZERO change (compound `Video <Custom>` BX se covered).
**Tests:** user-real-data sim — extras=[Audio,Video] ✓ remove→section gone ✓; csbtn/xkey/xset/xrm callback-parse ✓; layout rows (header/streams-first/l_body-lone/footer) ✓; py3.10 102/102.

### 260903-BZ — Menu polish: streams one-row (header2) + English captions
**Git:** `2adc4a0`  

**Ask (user):** caption tatti/Hinglish — English short chahiye (global users); Video/Audio/Subtitle TEENON EK LINE me (2x2 nahi), position same (Set All ke just niche).
**Changes:** `button_build.py` — new optional `header2` position (full-row, header ke turant niche insert; ubutton/ibutton dono; backward-compatible — empty slot no-op, purane menus byte-same). `users_settings.py` builder — stream 3-buttons header2 pe (ek row [Video][Audio][Subtitle]); caption `➲ Stream Tags — tap to set all tags & custom:`; "Purane set tags (Remove yahin se)" → `Old tags — tap to remove:`; md_str `Ye {sname} stream pe lagenge` → `These tags apply to the {sname} stream:`.
**Tests:** ButtonMaker verbatim-sim — header2 row ek-line ✓, position header-ke-niche ✓, header2-less + old menus unchanged ✓; Hinglish-grep metadata-flow ZERO ✓; py3.10 102/102.

### 260903-CA — md_cman redesign: caption me tags-list + Add Tag lone
**Git:** `a75591c`  

**Ask (user):** Add More Back-ke-saath pair me nahi — AKELA; caption me jo custom tags ADD kiye wo DIKHEN; "+ Add More" label bekar → "Add Tag".
**Changes (md_cman):** caption — har custom tag ki line `➲ <label>: <value|Not set>` + hint; buttons [name][Remove] pairs (2-col) + `Add Tag` l_body (akela) + Back footer. "+ Add More" GONE.
**Tests:** caption-sim (values + Not set) ✓; layout-sim (pairs → Add Tag lone → Back) ✓; py3.10 102/102.  
**Followup:** label `+ Add Tag` (user) — `81541c5`.  
**Followup-2:** stream-caption newbie-clear — `➲ Stream Tags — set tags shown inside the Video / Audio / Subtitle info:` — `331a32f`.

### 260904-CB — Resource optimization (CPU/RAM/speed audit, user-ask)
**Git:** `3330cba`  

**Audit:** 4 tasks sab `#Aria2` — **qBit 24/7 zinda** (dht:True+pex:True+32MB cache+200/100 conn) = ~60-120MB RAM waste + UDP churn; **aria2c DHT default-on** (Heroku UDP dead → retry-churn CPU); pyrogram workers=12; sync_to_async executor uncapped (thread-explosion); ffmpeg cmds par -threads/-nostdin nahi (spike per task-add). Status-loop ALREADY lean (6s + dedupe + 3s throttle — koi change nahi).
**Changes:** (1) qBit overlay: cache 32→16, conn 200/100→120/60, async_io_threads 2→1, **dht/pex env `QBIT_DHT`** (default off); (2) `stop_heavy()` → idle par qBit **graceful app_shutdown** (torrents 0 + `QBIT_IDLE_STOP!=false`) — ensure_qbit auto-restart qBit-use pe (qbit_download/torrent_search me pehle se wired); aria2 stays (RPC); (3) aria2c DHT/LPD/PEX off overlay (sirf missing keys; `ALLOW_DHT=true` escape); (4) workers 12→6; (5) default executor cap 6; (6) ffmpeg/repair `-nostdin -threads 1`.
**Impact:** RAM 43.5%→~32-37% (qBit idle-shutdown); CPU 21.9%→~8-15% expected (DHT churn + thread caps; 4-slow-torrent aria2c floor bachta); DL-speed zero-sacrifice (DL path untouched); sab env-guarded (QBIT_DHT/QBIT_IDLE_STOP/ALLOW_DHT).
**Tests:** T1 ffmpeg flags-in-cmd + metadata ✓; T2/T2b/T2c idle-stop logic (shutdown/stays/env-off) ✓; py3.10 102/102.

### 260904-CC — MP4 whitelist-fold: unsupported user-keys → Comment (user-ask, batbin washbowls)
**Git:** `3fb4a35`  

**Report:** mp4 leech ke baad "saara matter uda" — reproduce: user 4 tags me Title+Copyright lage, **Encoded By + custom `telly hub` mp4-muxer silently DROP** (whitelist-only container); originals purge (BV design) — total lagta sab gaya. MP4 hard-limitation, bot-bug nahi.
**Fix (user chose fold):** `edit_metadata` — mp4-family outfile (`.mp4/.m4v/.mov/.m4a`) + user keys not in `_MP4_FMT_KEYS` (title/artist/album/composer/genre/copyright/comment/date/description/lyrics/encoder/grouping) → `key: value` lines **Comment me fold** (existing comment merge `base | k: v | ...`); folded keys overlay se remove (purge ukeys-flow consistent). Ext-less→.mkv path fold-skip (raw keys as-is). Stream-compound keys untouched.
**Tests:** T1 mp4 4-tags → title/copyright raw + `encoded by: ... | telly hub: ...` in comment, DROP-zero ✓; T2 mkv same-tags raw-as-is ✓; T3 mp4 purge+fold (uploader GONE, user sab visible) ✓; T4 comment-merge ✓; py3.10 102/102.

### 260904-CD — MP4 FULL-PARITY: `-movflags use_metadata_tags` (user mood-off → senior fix)
**Git:** `c97f7e7`  

**Ask:** MKV me sab tags, MP4 me nahi — "ek format me sab, dusre me nahi" — smart fix chahiye. **Discovery:** ffmpeg mp4-muxer arbitrary keys sirf `-movflags use_metadata_tags` ke saath mdta-keys me likhta (warna whitelist + silent drop) — PROVEN: mediainfo-CLI me `telly hub`/`Studio`/`encoded_by` sab dikhte.
**Changes:** `edit_metadata` — mp4-family outfile → cmd me `-movflags use_metadata_tags` (purge delete-args + map_metadata 0 ke saath compatible — T3/T3b). **CC ka comment-fold REVERTED** (raw keys ab possible — cleaner, per-key visible).
**Tests:** T1 mp4 5/5 user tags RAW (title/copyright/encoded by/telly hub/Studio) + purge ✓; T1b mediainfo-CLI cross-check ✓; T2 mkv unchanged ✓; T3 mdta-asset preserve (OFFICIAL_SITE/encoded_by) ✓; T3b mdta-purge ✓; T4 ext-less→.mkv ✓; py3.10 102/102.
**Note:** MP4 stream-level tags ab bhi container-limited (mdta file-level hota) — global tags FULL parity.

### 260904-CE — MKV↔MP4 maximum-feature remux (senior audit, user-ask)
**Git:** `9098a22`  

**Truth-table (spec + proven):** Global-metadata FULL (mdta, CD) | Chapters/Lang/Multi-stream native | Text-subs→mov_text native | **Impossible:** bitmap-subs (PGS/DVD/DVB), attachments/fonts, per-stream-titles (mdta file-level) — inki honest handling, fake-support zero.
**remux_container v2:** mp4-out → `-movflags use_metadata_tags` + `-map -0:t?` (attachments clean-skip) + probe-once classification: bitmap-subs `-map -0:idx` skip (log), V/A titles file-level fold (`Video Title=`/`Audio Title=`), `-c:s mov_text`; **reverse (mp4→mkv) `-c:s srt`** (mov_text mkv-impossible — T2-edge); fallback v+a me `-map_metadata 0` restore + **`tag_args` NameError FIXED** (BU-class bug — fallback kabhi crash-less chalta).
**Perf:** single ffmpeg pass, A/V stream-copy (zero re-encode; sirf text-sub transcode ~KBs), probe once, no temp files, -threads 1 -nostdin.
**Tests:** T1 rich-mkv→mp4 (mov_text ✓ fonts-excluded ✓ mdta-title ✓ V/A-title-fold ✓ lang=hin ✓) ✓; T2 mp4→mkv reverse (title ✓ mov_text→srt ✓); T3 unit bitmap-exclusion cmd (PGS-idx dropped, srt kept, fold, mdta) ✓; py3.10 102/102.

### 260904-CF — qBit-down guard: clean_all/start_cleanup crash (CB idle-shutdown side-effect)
**Git:** `1e3acac`  

**Source:** live log (batbin curatives, commit 6689f49) — /restart → clean_all() → torrents_delete par qBit DOWN (CB idle-shutdown sahi kaam kar raha) → APIConnectionError → restart handler crash. start_cleanup (boot) me bhi wahi latent.
**Fix (fs_utils):** `_qbit_up()` port-probe + `_qbit_purge_all()` (down → info-skip — down = torrents bhi nahi; up-but-race → try/except warn) — dono call-sites switched. **bot_settings:** qBit-prefs handlers (2) me `ensure_qbit` pehle (down ho to auto-start — admin op fail nahi).
**Tests:** T1 port-probe real-refused ✓; T2 clean_all qBit-down (purge-skip + dirs-clean + no-crash) ✓; py3.10 102/102.

### 260904-CG — `-i N` reply-to-txt-file: links INSIDE file (was: file khud item)
**Git:** `2930c15`  

**Report:** `/l7 -i 3` reply-to txt → "No files to upload. Check EXTENSION_FILTER."; `-b` pe same file sahi.
**Root:** `collect_i_items._items_in_msg` media-msg ko khud ek item maanta (txt-file ka tg-link item bana → .txt leech → ext-filter → no-files). `-b` extract_bulk_links file-content padhta.
**Fix (multi_tools.collect_i_items):** start.document mime text/plain → `get_links_from_file(start, 0, n)` (bulk-parser reuse — first n lines, tmp auto-clean) → links[:n]. Non-txt media old-path; empty-txt → [] → mirror_leech single-leech fallback.
**Tests:** T1 3-links ✓; T2 tmp-clean ✓; T3 n>lines ✓; T4 non-txt old-path ✓; T5 empty→fallback ✓; py3.10 102/102.

### 260904-CH — REAL speed/CPU fix: aria2 perf-killers (conf) + force-overlay + qBit lazy-boot
**Git:** `4b4cf6c`  

**Audit (curatives log + a2c.conf):** (1) `bt-request-peer-speed-limit=1K` — aria2 ko "expected 1KB/s" bolta = LAZY peer-pulling = 34MB/s cap (friend 150+). (2) conf me `enable-dht=true` + DB-restore me bhi → CB ka missing-keys-only overlay SKIP (log missing tha!) — **DHT churn CPU abhi bhi ON**. (3) `max-concurrent-downloads=2`, http 8-conn/20M-split — concurrency caps. (4) qBit boot pe start + aria2-tasks-chalne-tak zinda (idle_now download_dict-gated) = boot-RAM 44.7%.
**Fix:** a2c.conf — peer-speed-limit **15M**, bt-max-peers 120, http 16/16/1M, concurrent 5, file-allocation falloc, dht/pex false. `__init__` — **FORCE perf-overlay** (7 keys, DB/conf override; `ARIA2_PERF=0` opt-out) + **DHT FORCE** (missing-only → force; `ALLOW_DHT` escape). qBit **lazy**: boot-overlay ke turant baad `stop_heavy()` (0-torrent → shutdown; aria2 tasks se independent) + `aria2_listener` complete/bt-complete pe event-driven `stop_heavy()`.
**Expected:** speed 34→80-120+MB/s (peer-speed-limit + peers + splits), boot-RAM 44.7→~28-32% (qBit lazy), CPU 35→~15-20 (DHT churn force-off). Env: ARIA2_PERF=0 / ALLOW_DHT / QBIT_IDLE_STOP=false.
**Tests:** conf-values ✓; force-overlay sim (DB-true override + opt-out) ✓; py3.10 102/102.

### 260904-CI — Full perf audit (sandbox-measured) + gunicorn-kill + ytdlp-lazy + bootstop-verify + PERF harness
**Git:** `a24b69a`  

**Audit (real measurements):** idle 44.3% (~440MB) = python-imports **132.5MB** (naapa) + gunicorn master+worker **~85MB** (naapa; hello-flask 67) + aria2 idle 16MB/0-CPU (naapa) + pyrogram-runtime ~50-70MB + frag. Import top: TG-core 35, motor 20, **yt-dlp 20 (boot pe load!)**. Idle-CPU 4-10% = pyrogram floor (status-loop idle pe cancel ✓, aria2 0-ticks ✓).
**CI (web in-bot):** `web/pages.py` (HTML single-source, wserver 856→166 refactor) + `web/aio_wserver.py` — aiohttp in-bot server (3 routes legacy-parity; sync engine-calls `to_thread`; `reuse_address` + retry×3 cleanup-rebind-race-guard; `stop/restart_web_server`). gunicorn Popen kills: `__init__` + `bot_settings` ×2 → in-bot start/restart. flask/gevent/gunicorn ab import hi nahi hote.
**CJ (ytdlp lazy):** 3 local-import sites (ytdlp.py:231, yt_dlp_download.py:210/254-methods) — boot se ~20MB off.
**CK (boot-stop verify):** `qbit_port_down()` (8090, 3s wait) + definitive boot-log "down ✓/STILL UP ✗" — 44.3%-after-CH mystery ka saboot.
**CL (PERF harness):** `log_mem(tag)` — process-wise RSS (bot + children by-name) boot pe ek baar + `PERF_LOG=1` → setInterval 300s.
**Tests:** server-suite (routes 200/pin/graceful-500, same-port live-rebind ×4, diff-port, stop, restart-parity) ✓; qbit_port_down ✓; log_mem render ✓; py3.10 **107/107** (web/ included).
**Expected:** idle RAM 44.3→~25-30% (gunicorn−85, ytdlp−20, qBit-lazy). Deploy-log me dekho: `MEM[boot]: bot=… | aria2c=…` line + `qBit boot-stop: port 8090 down ✓`.

### 260904-CJ — CH-revert: aria2 known-good restore (swarm-confound + 15M-churn regression fix)
**Git:** `69d5e12`  

**Regression report (live):** 88KB/s + CPU 59.8% (pehle: 34MB/s + 35.1%). Analysis: (1) naya run near-dead swarm me tha (seeders 6/3/2→1/0/0, leechers 31/29/26→2/1/1) — speed-compare invalid; (2) REAL bug = CH ka `bt-request-peer-speed-limit=15M` force — speed<15M ⇒ aria2 permanent peer-hunt churn (tracker re-announce storm) = CPU 59.8%; 1K pe aria2 shaant tha ("1K killer" mera galat A/B-less conclusion); (3) DHT/PEX force-off = thin-swarm discovery band. `stop_heavy` qBit-only verify hua (aria2/tasks untouched).
**Fix:** a2c.conf → exact pre-CH `0de560a` (git show restore, T1 exact-diff ✓). Overlay default-OFF → `ARIA2_PERF=1` (7 keys) / `ARIA2_NO_DHT=1` (dht keys) opt-in. CI/CJ/CK/CL retain (passive/log-only).
**Tests:** conf-exact ✓; overlay opt-in sim (none/7/3) ✓; CI/CJ/CK/CL intact ✓; py3.10 107/107.
**Next protocol:** baseline benchmark same-workload (seeders/leechers note karke) → ek-ek env experiment + benchmark.

### 260904-CM — FINAL throughput pass: aria2 peer/connection caps + real(anon) RAM readout + live conn diagnostics
**Git:** `06275d2`
**Date:** 2026-09-04
**Files:** `a2c.conf`, `bot/__init__.py`, `bot/helper/mirror_utils/download_utils/aria2_download.py`, `bot/helper/ext_utils/bot_utils.py`, `bot/helper/ext_utils/engine_lifecycle.py`

**User (final pass):** CPU theek (13.6%) par total DL sirf 18.87MB/s (same 3 files, fresh dyno; pichli baar ~34), RAM 44.8% stuck. Dost same env pe 100–150MB/s @ 19–20% RAM. "Speed sacrifice karke CPU kam mat karo"; random tweak nahi — root-cause → fix → benchmark.

**ROOT CAUSE (code-confirmed, listener/status NAHI):**
1. **BT throughput = hum jitne peers se connect karte hain** (Heroku outbound-leech; inbound UDP blocked). Per-task `aria2_download.py` hardcode `bt-max-peers=80` + **`bt-request-peer-speed-limit=1K`** — woh threshold AGGREGATE TARGET hai: aria2 1KB/s cross hote hi aur peers maangna BAND kar deta hai → kuch peers pe settle → 19MB/s cap. 80 peers tak pahunchta hi nahi. Dost ki speed isi se aati hai (zyada peers), magic se nahi.
2. `max-upload-limit=256K` se reciprocal DL bhi dabta (tit-for-tat).
3. HTTP: `max-connection-per-server=8 / split=8 / min-split-size=20M / max-concurrent-downloads=2` — chhoti file = 1 connection; teesra task active-slot ke bahar.
4. **RAM 44.8% ≈ page-cache inflated readout:** footer `memory.current/memory.max` (cgroup v2) me **file cache counted** — downloads ka reclaimable cache. Real anon RAM ~25–32%. Leak nahi (koi growing dict/duplicate worker/lock nahi mila; listener notification-based 60s long-poll, status 6s = RPC overhead negligible, CPU 13.6% proof).

**FIX (staged, env-guarded — CH lesson respected: DHT force-toggle NAHI, peers hard-capped 200 = no unbounded announce churn):**
- `a2c.conf`: HTTP concurrent 2→5, conn/server 8→16, split 8→16, min-split 20M→1M; BT max-peers/open-files 80→200, peer-speed-limit 1K→10M (bounded by peers 200), upload 256K/128K → 1M/512K.
- `aria2_download.py` per-task BT opts ab env-overridable, production default 200/10M/512K. `ARIA2_TORRENT_PROFILE=safe` = purana 80/1K/256K baseline (A/B).
- `__init__.py`: **default-on throughput overlay** Mongo-restore ke BAAD (DB purani prefs na la sake) — same values; `ARIA2_PROFILE=safe` se poora revert. Purana `ARIA2_PERF` block se BT peer keys hata (woh CH ka 15M-unbounded churn tha) → ab sirf HTTP falloc opt-in. DHT ON rehta.
- `bot_utils.py`: footer RAM% ab **anon (real)** = `memory.stat anon/limit`; page-cache alag. Naya `get_container_memory_breakdown()` (v2 anon/file + v1 rss/cache).
- `engine_lifecycle.log_mem`: ab cgroup **real% vs cache%** + live aria2 `conn=`/`peers=` per active GID log karta hai — proof ki aria2 requested sockets khol raha hai ya swarm/host cap hai.

**BENCHMARK METHOD (one-variable, brain protocol):**
1. Default (boost ON) deploy — same 3 files; logs me `MEM[boot]` + `aria2[N]: ..MB/s conn= peers=` dekho.
2. Agar peers kam (<20) bane → swarm/host cap (tracker count) — config nahi.
3. Agar churn/CPU badhe → `ARIA2_TORRENT_PROFILE=safe` (sirf BT revert, HTTP boost rahega).
4. Total revert chahiye → `ARIA2_PROFILE=safe`.
5. HTTP direct-link alag se test (16 conn/split).
**Expected:** BT 19→40–100+MB/s (fat swarm me), HTTP chhoti files 1-conn→16; RAM footer real ~25–32% dikhayega (cache alag). CPU thoda upar (zyada peers) par headroom bड़ा hai (13.6%).

**Tests:** py3.10 full-repo compile ✓; BT-opt logic prod/safe/env-override sim ✓; cgroup anon vs file parse ✓.
**NEVER:** pkill; DHT force-off; peer-speed-limit bina hard peer-cap ke (CH churn).

### 260904-CN — UPLOAD regression ROOT CAUSE: wzgram hardcoded bot rate_limit=40 (~20MiB/s cap) + dead queue patch
**Git:** `8d7ced3`
**Date:** 2026-09-04
**Files:** `bot/__init__.py` (`_patch_tg_upload_queue`, workers, executor)

**User report (CRITICAL):** optimization ke baad bulk 50-link leech: DL 40+→~20MB/s, **UL 30+MB/s → KB/s**. "Speed sacrifice karke CPU mat kam karo." High CPU wali old behavior baseline wapas chahiye.

**ROOT CAUSE (wzgram 3.1.1 source me, runtime-naapa):**
- `pyrogram/methods/advanced/save_file.py` **per-file dispatch rate hardcode** karta hai:
  - `is_bot` → **`rate_limit = 40`** chunks/s (PART 512KiB = **~20 MiB/s hard cap/file**), `pool_size = min(8, …)`
  - `is_premium` → `rate_limit=300`, pool 14
  - normal user → `rate_limit=50` (~25 MiB/s), pool 12
  - Dispatch loop: `_dispatch_interval = 1/rate_limit; if _now < _next_dispatch: await sleep(...)` — **yahi pacing throttle hai.** Bulk 50 files har ek isi 20MiB/s cap se takrati.
- **Hamara `_patch_tg_upload_queue` DEAD tha** — woh purane pyrogram patterns (`Queue(1)`, `workers_count = 4 if is_big else 1`) ko replace karta hai jo wzgram 3.1.x me **exist hi nahi karte** (ab `rate_limit`/`pool_size`/`asyncio.Queue(n_workers)`). `src==orig` → silently no-op. Isliye 260831-H/J ka "16 workers" speedup kabhi live hua hi nahi.
- Crypto/handler threads cap NAHI the: handler executor `min(16,cpu*2)`=16, crypto pool=4 (wzgram default, pehle bhi same). `sync_to_async` apna 24-thread pool. CB ka `set_default_executor(6)` sirf bare loop-default calls ko chhota hai — pyrogram save_file apna handler pool use karta hai.
- `RateLimiter` (rate_limiter.py) sirf API-call level (MEDIA=5/s completion calls) — chunk throughput cap nahi.

**Baseline→HEAD diff (0bdcba5 → HEAD) me TG UL path (pyrogramEngine, hyperul_utils, max_concurrent_transmissions=16) UNCHANGED tha** — UL cap configuration/regression nahi, library ki bot-rate-cap + dead-patch thi.

**FIX:**
- `_patch_tg_upload_queue` rewrite: ab wzgram 3.1.x ke asli targets patch karta hai — bot `rate_limit 40→300`, user `50→300`, pool `8/12→14`; legacy patterns fallback me rakhe. Env override: `TG_UP_RATE_LIMIT`, `TG_USER_UP_RATE_LIMIT`, `TG_UP_POOL`, `TG_USER_UP_POOL`. Patch-result BOOT LOG me (`TG upload pacing patched: rate=300/300, pool=14/14`). Match na ho to warning (silent no-op nahi).
- `bot` pyrogram `workers 6→12` (old baseline restore — handler threads, UL non-critical par parity).
- default loop executor `max_workers 6→24` (bulk sync-ops serialize na hon).
- ffmpeg `-threads 1` rakha (stream-copy muxing, CPU guard; bulk default metadata off).

**Expected:** per-file UL ceiling 20→network/DC-bound (150 MiB/s theoretical); bulk 50 tasks genuinely parallel (max_concurrent_transmissions=16/client × bot+user+helpers). Patched-file compile ✓; rate/pool match real wzgram source ✓; py3.10 full-repo 107/107 ✓.
**Verify on Heroku:** boot log me `TG upload pacing patched` line. Agar flood aaye to `TG_UP_RATE_LIMIT` env se ghटao (per-file), tokens add karo (helpers = more parallel).
**NEVER:** pkill; patch ko silent-no-op chhodna (na-pattern-match ab warning deta hai).

### 260904-CO — live-log fixes: HyperDL circuit-breaker (1MiB stall) + yt-dlp EmbedThumbnail task-kill removed
**Git:** `13b6ab5`
**Date:** 2026-09-04
**Logs:** batbin.me/frieseite (running 8d412bb = CM; CN upload patch abhi restart se aana tha)
**Files:** `bot/helper/ext_utils/hyperdl_utils.py`, `bot/helper/mirror_utils/download_utils/yt_dlp_download.py`

**Log me 3 cheezein:**
1. **HyperDL har ≥50MB TG download pe FAIL** (3/3: 151MB DC1, 149MB DC5, 1.8GB DC4): hamesha `HyperDL incomplete 1048576/<size> err=None — fallback` = pehla window (~1MiB) ke baad cross-DC bot GetFile stalls. Phir native download_media pe gira (jo yahan fast hai — 150MB 10s = 15MB/s). Har file pe 4-5s dead-pipeline waste, bulk me bहुत.
2. **yt-dlp task DEAD** (eporner 1080p): video download + extract ho gaya, par `EmbedThumbnail` postprocessor = `mutagen: could not determine image type` + `AtomicParsley` + `ffprobe: .jpg Invalid data` → PostProcessing ERROR → task bina upload ke clean (line 97-100). Thumbnail source corrupt/bad.
3. **UL 1.8GB = 91s ≈ 19.8 MiB/s** — exactly wzgram bot rate_limit=40 cap (CN patch ka target; restart pe unlock).

**FIX:**
- `hyperdl_utils.py`: module-level **circuit-breaker** — pehli incomplete/err pipeline (`_hyperdl_fails` ≥ `HYPERDL_MAX_FAILS`, default 1) ke baad baaki saari files seedha native `download_media` (dead 4-5s try + cross-DC session churn khatam). Pehli file abhi bhi pipeline try karti hai (CDN mile to fast). Env: `HYPERDL=1`=always-on (breaker ignore), `HYPERDL=0`=pipeline off. Increment pipeline-incomplete/exception dono pe.
- `yt_dlp_download.py`: **`EmbedThumbnail` postprocessor HATA** (mp3/mkv/mp4/mov branch). Corrupt thumbnail pe yahi FATAL tha aur poora leech maar deta tha. Sidecar thumbnail (`yt-dlp-thumb/`, leech FFmpegThumbnailsConvertor) already TG preview/thumb ke liye banta+upload hota hai — embed ka zero value. Mirror path me `writethumbnail=False` same.

**Note (non-blocking):** boot log line 6 "Updating packages...Success" ~1s = slug ka frozen update.py (260902-AA self-re-exec ek redeploy ke baad pakka hota); bot code to fresh hi aata hai (overlay log line 10 is CM = proof). `python3=123MB` child = alive/web subprocess (harmless).

**Tests:** py3.13 full-repo compile ✓; breaker state sim (1st try → open → HYPERDL=1/0 overrides) ✓.

### 260904-CP — eporner (adult hosts) ytdlp multi/bulk: add to _YTDL_HINT
**Git:** `28174fe`
**Date:** 2026-09-04
**User:** eporner link (video-e3DEfNO2Aip) "ytdlp iska multi support nahi kar raha".
**Root cause:** `/l` + bulk `-b/-i` ka auto-engine `is_ytdlp_link()` use karta hai jo SIRF `_YTDL_HINT` host-list match karta hai. `eporner.com` list me nahi tha → engine eporner ko **aria/HTML** pe bhej deta (fail), ytdl pe nahi. (`/yl` chalता tha kyunki woh `is_ytdlp_supported()` ka generic content-type check use karta hai.) Single video yt-dlp me chalta hai (tested: Eporner extractor formats deta hai, age_limit 99 set) — routing hi galat thi. Bulk multi isliye toota kyunki har link wahi auto-engine se route hota hai.
**Fix:** `bot_utils.py` `_YTDL_HINT` me eporner + baaki real yt-dlp adult extractors add: eporner, beeg, txxx, upornia, thisvid, porntrex, hqporner, motherless, rule34video, hellporno, drtuber, sunporno, sexu, alphaporno, pornflip, pornerbros, murrtube, 4tube, chaturbate, stripchat, nubiles. Magnet guard (is_torrent_link) pehle — `&tr=eporner.com/announce` wali magnet false-positive nahi deti.
**Note:** eporner ke category/model PAGES (e.g. /popular-videos/) ka yt-dlp me playlist extractor nahi (generic → Unsupported) — single video links bulk list me do.
**Test:** is_ytdlp_link sim — eporner/no-www True, magnet False (torrent-guard), random False ✓; full-repo compile ✓.

### 260904-CQ — yt-dlp multi-quality menu: tbr-gate + progressive '+ba' fix (eporner)
**Git:** `497eb5c`
**Date:** 2026-09-04
**User:** eporner link (video-e3DEfNO2Aip) pe sirf "Best Video" aata tha; multiple quality (240–1080) chahiye, generic fix (site-hardcode nahi).
**Root cause (real eporner JSON):** `ytdlp.py get_quality` ka single-video loop `for item: if item.get('tbr'):` — poora loop **tbr (total bitrate) hone par hi** chalta tha. Eporner extractor har format me **`tbr=None, fps=None, filesize=None`** deta hai (10/10 formats) → saare formats skip → zero quality buttons → sirf Best Video/Best Audio. Saath hi eporner formats **progressive direct mp4** (URL `...-1080p.mp4`, audio included; extractor me **koi audio-only track nahi**) hain — purana code video format ke liye hamesha `format_id+ba/b[...]` banata tha, jiska eporner pe koi `ba` hai hi nahi → galat/unrelated variant resolve (proven: `1080p_HD+ba` → `av1-1080p_HD`).
**Generic fix (`bot/modules/ytdlp.py`):**
- tbr-gate hata; variant grouping key = unique index (tbr/fps/filesize null ho tab bhi). `formats{b_name:{key:[size,fmt]}}` + `sub/dict` callback contract same.
- `_variant_kind()` classifier: **audio-only** (no video + acodec) → plain id; **video+audio (progressive)** → plain `format_id`; **video-only (DASH)** → `format_id+ba...` native yt-dlp merge.
- **Progressive-source detection:** agar extractor me ek bhi audio-only format NAHI hai (eporner-type) → saare video formats ko progressive treat = **plain format_id, no +ba** (galat merge/`b[height]` fallback khatam). YouTube/DASH (audio-only track present) → merge form unchanged.
- Codec tag (h264/av1/vp9) button label me taaki same-resolution dono codec variants sub-button me dikhein; low→high sort; size unknown ho to label clean.
- `qual_subbuttons` index-key aware (purana `{tbr}K` label ab generic variant).
**Sandbox tests (real URL):** raw dump = 10 formats sab tbr-null (240–1080 × h264/av1) → builder ab **10 buttons**, plain ids (`1080p_HD`,`av1-480p`,...); yt-dlp `-f` simulate par **har quality sahi resolve** (240p→240p ... 1080p_HD→1080p); `+ba` form YouTube par preserved (audio-only=True → dashvideo merge), eporner par plain id (audio-only=False). Full-repo compile ✓.
**Perf:** single metadata extraction (pehle se), no extra subprocess; merge sirf DASH split-source pe (progressive direct file = no remux = CPU/RAM bachat).
**Edge:** playlist path (entries) untouched; audio-only sites → id; video-only DASH → +ba; null fps/tbr/filesize handled; duplicates same-resolution codec-tag se grouped.

### 260904-CR — py3.10 deprecation-spam suppress + 3.10/3.11/3.12 compatibility audit
**Git:** `65d3a2f`
**Date:** 2026-09-04
**User:** yt-dlp `Deprecated Feature: Support for Python version 3.10` WARNING+ERROR har task pe; brain me note karo ki dyno abhi 3.10 pe hai; code aisa ho jo 3.10 AUR 3.12 dono pe smooth chale.
**Asli wajah:** repo ka **Dockerfile already Python 3.11.9** target karta hai (`python:3.11.9-slim-bookworm`) — par **live dyno abhi purana base-image/stack pe hai jo system Python 3.10 deta hai** (naya container image deploy nahi hua). yt-dlp (2026.08+) 3.10 ko deprecated bolta hai; woh message `MyLogger` har baar WARNING+ERROR dono me log kar raha tha (spam, kaam pe asar nahi — downloads chalte the).
**Code fix (`yt_dlp_download.py` MyLogger):** `_IGNORE_SUBSTR = ('deprecated feature: support for python version',)` — debug/warning/error teeno me yeh benign notice drop; asli errors/warnings (404, format fail, "Cancelling" chhod ke) log hote rehte hain. Test: deprecation suppressed, real error retained ✓.
**Compatibility (3.10 ↔ 3.12) audit:**
- NEECHE ka baseline = 3.10: poora repo **uv py3.10 full-repo py_compile PASS** → koi 3.11+ syntax nahi (tomllib/TaskGroup/ExceptionGroup/typing.Self/@override/asyncio.timeout/itertools.batched — grep: zero).
- Code 3.10 pe compile chalta hai to 3.11/3.12 pe bhi syntax chalta hai (3.12 only naya = f-string me same-quote nesting — BE incident wala; woh poore repo me ab nahi).
- **User action (deploy-side, code nahi):** Dockerfile 3.11.9 ka naya image build+release karo (Heroku container stack) → deprecation khud gayab + Dockerfile ke MEGA/TGCrypto 3.11 bindings use honge. Tab tak py3.10 pe logger filter spam rokh deta hai.
**Standing rule (brain):** har push se pehle **uv py3.10 full-repo compile** (baseline=3.10 = sabse conservative; pass = 3.10/3.11/3.12 sab safe). Nested same-quote f-strings mat likho (3.12-only).

### 260904-CS — startup noise suppress + upload-patch REGEX-robust + ONLINE banner
**Git:** `d23a771`
**Date:** 2026-09-04
**User (.ask→build):** boot log red-warning noise me "bot start hua ya nahi" pata nahi chalta; `TG upload patch: no target pattern matched` (CN patch Heroku pe laga hi nahi); py3.10 deprecation lines (yt-dlp bare-stderr + google FutureWarning) baar-baar.
**Root cause CN patch no-op:** `_patch_tg_upload_queue` exact-string replace karta tha (`'rate_limit = 40  # ~20 MiB/s'`) — Heroku ke wzgram micro-build me whitespace/comment/version farq → koi match nahi → silent no-op → upload cap 20MiB/s bana raha.
**Fix:**
1. **Patch regex-robust (`__init__.py`):** ab comment/whitespace/version-independent REGEX se exact NUMERIC value pakdta hai (`rate_limit = 40` bot cap, `= 50` non-premium user cap; premium 300 untouched) + `pool_size min(8|12,POOL_SIZE)` → 14. Applied-count + **wzgram version + path boot-log**; zero match pe bड़ी warning (future layout change visible, silent nahi). Real wzgram 3.1.1 source test: bot 40→300, user 50→300, premium 300 safe, pools 8/12→14, patched-file compiles ✓.
2. **py3.10 deprecation noise suppress (`__init__.py`):** (a) `warnings.filterwarnings` — yt-dlp + google.api_core FutureWarning; (b) **stderr-write wrapper** (`_DeprFilterStderr`) jo SIRF `deprecated feature: support for python version` line ko line-buffer+drop karta hai (split-writes + flush edge tested; real errors/tracebacks/progress untouched). CR ka MyLogger filter already logger-side karta tha; yeh `to_stderr` wali bare line cover.
3. **ONLINE banner (`__main__.py`):** boot complete hone pe bड़ा alag block — `BOT ONLINE ✅ KPSML-X [@...] is UP and ready | Python x.y | wzgram x.x.x` — red-noise ke beech ek nazar me up pata chale.
**Note:** deprecation jad se tab gayab hogi jab container image 3.11 (Dockerfile already 3.11.9) deploy hoga; tab tak filters spam rokte hain.
**Test:** regex patch hits r40/r50/p8/p12 = 1/1/1/1 ✓; stderr filter split-write + flush suppress/keep ✓; py3.10 full-repo compile ✓ + py3.13 ✓.

### 260904-CT — banner revert (user: CS ka BOT ONLINE block nahi chahiye)
**Git:** `d499b50`
**Date:** 2026-09-04
**User:** CS ka startup banner nahi chahiye — purani normal startup line hi theek. CS ke baaki do fixes (regex upload patch + py3.10 deprecation suppress) BANE rehte hain; sirf 4-line banner + platform/pyrogram version block hata → wapas ek line `KPSML-X Bot [@...] Started!`.

### 260904-CU — upload patch numeric-threshold robust + stderr-wrapper revert (boot-safe)
**Git:** `a4781ff`
**Date:** 2026-09-04
**Log:** running d9ccb29 par bhi `TG upload patch: NO target matched on wzgram 3.1.1` + deprecation line + boot "Started!" tak pahunchne me dikkat.
**Root cause (CS patch abhi bhi no-op):** CS ka regex exact value/structure maangta tha (`rate_limit = 40` with comment + `pool_size = min(8, POOL_SIZE)` fixed spacing). Heroku ke installed 3.1.1 file me spacing/comment/format ka farq (ya source patch ka target hi alag) → zero match.
**Fix (`__init__.py` `_patch_tg_upload_queue`):** layout/spacing/comment/CRLF-agnostic NUMERIC-THRESHOLD regex —
- `rate_limit = <n>` jahan n<100 (bot 40 / non-premium user 50) → target rate; premium 300 chhua nahi.
- `pool_size = min(<n>, POOL_SIZE)` jahan n<target (8/12) → target (14); premium 14 safe.
- match na ho to ab actual `rate_limit/pool_size` lines boot-log me dump (ek nazar me debug), silent nahi.
- Sim: real wzgram 3.1.1 (hits rate 40/50 + pool 8/12, compiles) AUR synthetic alt-layout (no-comment/`rate_limit=40`/`min( 8 , POOL_SIZE )`) dono pe pass.
**stderr wrapper REVERT:** CS ka `_DeprFilterStderr` global stderr-wrap boot-event-loop/logging ke liye risky + yt-dlp apna early stderr ref pakad leta to line chhupi bhi nahi — block hata diya (boot restore). Deprecation ab: warnings.filterwarnings (google/yt_dlp FutureWarning) + yt-dlp opts **`no_warnings: True`** + MyLogger CR-filter (logger.error route) — teeno safe, stderr chhede bina.
**Banner:** CT me hi hat gaya (user ko nahi chahiye) — wapas single `Started!` line.
**Note:** deprecation jad se tab gayab hogi jab container image 3.11 (Dockerfile already 3.11.9) deploy ho.
**Test:** py3.10 full-repo compile ✓ + py3.13 ✓; patch real+alt layout ✓.

### 260904-CV — upload patch IMPORT-BEFORE-pyrogram (reload race fix) + idempotent + boot deprecation silent
**Git:** (push ke baad)
**Date:** 2026-09-04
**Logs:** batbin.me/parasemidin (running 361dcbd=CU; fresh container deploy ed9c6ca7, Python 3.10.12, wzgram 3.1.1 fresh install).
**Asli findings (line 72 decisive):**
1. Patch file me `rate_limit = 300 / pool min(14)` already likha tha (pichhli boot ka rewrite disk-tika) → cap REMOVED tha. CU ka `NO target matched` jhootha alarm tha — patch idempotent nahi tha (already-300 ko dobara n<100 na milne par ERROR bola).
2. **Structural bug:** patch `bot/__init__.py` ke line ~140 par chalta tha — `from pyrogram import Client` (line 7) ke BAAD — aur `importlib_reload(save_file)` karta tha jabki pyrogram Client already load ho chuka. Local-constant `rate_limit` reload se reliably live nahi hota tha → flaky apply + reload startup ko bigaad sakta tha (Started! tak dikat).
**Fix (`__init__.py`):**
- Naya **`_early_patch_wzgram()`** file ke bilkul top (shebang ke turant baad, **kisi bhi pyrogram import se PEHLE**). Stdlib-only (os/re/sys/importlib.util) — pyrogram import kiye bina `find_spec`+sys.path se `save_file.py` dhoondhta hai, disk pe n<100 rate caps (40/50) → 300 aur pool 8/12 → 14 likhta hai (numeric-threshold regex, comment/spacing-agnostic; premium 300 safe), phir **import hi nahi karta/reload nahi** — fresh process first-import pe patched source padhta hai. Idempotent: already-high pe sirf info-print (koi false warning). Exception-safe (kabhi boot nahi rokta). Purana late reload-patch block hata.
- Print logs (`[TG patch] APPLIED ...` / `already high`) — early stage pe logging configured nahi hoti, Heroku stdout capture kar leta hai.
**Boot deprecation (yt-dlp) silent:** line "Deprecated Feature: Support for Python 3.10" import-time `_detect_impersonate()` ke YoutubeDL se aati thi (`{'quiet':True}` me na logger na no_warnings). Add **`_NullYdlLog()`** + `'no_warnings': True` us call me (real task logger MyLogger pehle se filtered). google FutureWarning `warnings.filterwarnings` se dabi.
**Tests (sandbox):** early-patch fresh file pe hits [40,50/pool 8,12] → 300/14, re-run idempotent (zero hits = "already high"), patched source compiles; E2E: fresh-interpreter patch → fresh import sees rate 300/min(14) (no reload); py3.10 + py3.13 full-repo compile OK.
**Note:** boot 1-2 me `uv: No virtual environment found` ke baad `|| pip` fallback chala, boot 3-4 me wzgram/curl-cffi/motor fresh install hue (line 36-56) → packages sahi install hote hain, woh error noisy-only hai. Container image 3.11 deploy se py3.10 deprecation jad se gayab.
