import asyncio
import io
from time import time as _now
from html import escape
from datetime import datetime, timezone
from ... import user_data, LOGGER, config_dict, DATABASE_URL, bot
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.filters import regex
_bulk_tracker = {}
_lock = asyncio.Lock()
def _tag(t):
    return t[:8] if t and len(t) > 8 else (t or "single")
async def register_bulk(uid, tag, total):
    if not tag or total <= 1:
        return
    async with _lock:
        if tag in _bulk_tracker:
            if total > _bulk_tracker[tag]["total"]:
                _bulk_tracker[tag]["total"] = total
            _bulk_tracker[tag]["user_id"] = uid
            return
        _bulk_tracker[tag] = {"user_id": uid, "total": total, "done": 0, "failed": [], "created": _now(), "sent": False}
async def _cleanup(tag, delay=60):
    await asyncio.sleep(delay)
    async with _lock:
        _bulk_tracker.pop(tag, None)
async def _build(uid, total, failed):
    succ = total - len(failed)
    head = f"<b>⚠️ Failed Tasks Report</b>\n┎ <b>Total Tasks:</b> <code>{total}</code>\n┠ <b>Success:</b> <code>{succ}</code>\n┖ <b>Failed:</b> <code>{len(failed)}</code>\n\n<b>Failed Files:</b>\n"
    body = ""
    for i, e in enumerate(failed, 1):
        n = escape(e.get("name") or "Unknown")
        r = escape(e.get("reason") or "Unknown reason")
        dn = n if len(n) < 180 else n[:177] + "..."
        dr = r if len(r) < 300 else r[:297] + "..."
        body += f"\n{i}. <code>{dn}</code>\n   └ <b>Reason:</b> <i>{dr}</i>\n"
    foot = "\n<i>Report generated for bulk tasks — only visible to you (DM). Setting: Universal → Failed Report = Enabled</i>"
    return head + body + foot
async def _send(uid, text, tag):
    from ..telegram_helper.message_utils import sendCustomMsg, sendFile
    from io import BytesIO
    if len(text.encode()) <= 3800:
        try:
            await sendCustomMsg(uid, text)
            return
        except Exception:
            return
    if len(text.encode()) > 8000:
        bio = BytesIO(text.encode())
        bio.name = f"failed_report_{tag[:6]}_{int(_now())}.txt"
        try:
            await sendFile(uid, bio, caption=f"<b>⚠️ Failed Tasks Report</b> — Bulk {escape(_tag(tag))} ({len(_bulk_tracker.get(tag, {}).get('failed', []))} failed)")
            return
        except Exception:
            pass
    parts = []
    cur = ""
    for line in text.split("\n"):
        if len((cur + "\n" + line).encode()) > 3800:
            parts.append(cur)
            cur = line
        else:
            cur = cur + "\n" + line if cur else line
    if cur:
        parts.append(cur)
    for i, p in enumerate(parts):
        try:
            await sendCustomMsg(uid, p)
            if i < len(parts) - 1:
                await asyncio.sleep(1.2)
        except Exception:
            break
async def _send_retask_txt(tag, failed):
    try:
        from ..telegram_helper.button_build import ButtonMaker
        cancel_id = tag
        links = []
        for e in failed:
            link = e.get("link") or e.get("name") or ""
            if link:
                links.append(link.strip())
        if not links:
            return
        content = "\n".join(links)
        file = io.BytesIO(content.encode())
        file.seek(0)
        file.name = f"Failed_{cancel_id}.txt"
        log_id = config_dict.get('MIRROR_LOG_ID') or config_dict.get('LINKS_LOG_ID')
        if not log_id:
            return
        btn = ButtonMaker()
        btn.ibutton("🔄 Retask Failed", f"retask_{cancel_id}")
        sent = await bot.send_document(chat_id=log_id, document=file, file_name=file.name, caption=f"<b>Failed Links</b> — <code>{len(links)}</code> links", reply_markup=btn.build_menu(1))
        if not sent:
            return
        if DATABASE_URL:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                conn = AsyncIOMotorClient(DATABASE_URL)
                db = conn.kpsmlx
                await db.retask.create_index("createdAt", expireAfterSeconds=86400)
                await db.retask.update_one({"_id": cancel_id}, {"$set": {"chat_id": log_id, "message_id": sent.id, "cancel_id": cancel_id, "createdAt": datetime.now(timezone.utc)}}, upsert=True)
                try:
                    conn.close()
                except Exception:
                    pass
            except Exception:
                pass
    except Exception as e:
        LOGGER.error(f"retask txt failed {e}")
async def _maybe(tag):
    d = _bulk_tracker.get(tag)
    if not d or d.get("sent"):
        return
    if d["done"] < d["total"]:
        return
    d["sent"] = True
    uid = d["user_id"]
    failed = d["failed"]
    total = d["total"]
    if not user_data.get(uid, {}).get("failed_report", True):
        asyncio.create_task(_cleanup(tag, 60))
        return
    if not failed:
        asyncio.create_task(_cleanup(tag, 60))
        return
    try:
        txt = await _build(uid, total, failed)
        await _send(uid, txt, tag)
        await _send_retask_txt(tag, failed)
    except Exception:
        pass
    finally:
        asyncio.create_task(_cleanup(tag, 120))
async def record_success(uid, tag):
    if not tag:
        return
    async with _lock:
        d = _bulk_tracker.get(tag)
        if not d:
            return
        d["done"] += 1
        await _maybe(tag)
async def record_failure(uid, tag, name, reason, link=None):
    if not tag:
        return
    async with _lock:
        d = _bulk_tracker.get(tag)
        if not d:
            return
        l = (link or name or "Unknown")
        d["failed"].append({"name": (name or "Unknown")[:500], "reason": (reason or "Unknown reason")[:800], "link": l[:2000]})
        d["done"] += 1
        await _maybe(tag)
async def get_display_name(listener, fallback=""):
    try:
        from ..ext_utils.leech_utils import format_filename
        raw = getattr(listener, "newname", "") or fallback or getattr(listener, "name", "") or getattr(listener, "source_url", "") or "File"
        if raw.startswith("http"):
            raw = raw.split("/")[-1].split("?")[0] or raw
            if not raw or len(raw) < 3:
                raw = getattr(listener, "source_url", "") or "File"
        uid2 = getattr(listener, "user_id", 0) or getattr(listener.message.from_user, "id", 0) if hasattr(listener, "message") else 0
        is_mirror = not getattr(listener, "isLeech", False)
        has_custom = bool(getattr(listener, "newname", ""))
        cap = getattr(listener, "orig_caption", "")
        fmt, _ = await format_filename(raw, uid2, isMirror=is_mirror, has_custom_name=has_custom, caption=cap)
        return fmt or raw
    except Exception:
        return fallback or getattr(listener, "newname", "") or getattr(listener, "name", "") or "File"
async def handle_retask_callback(client, query):
    try:
        data = query.data or ""
        if not data.startswith("retask_"):
            return
        cancel_id = data.replace("retask_", "", 1)
        if not DATABASE_URL:
            await query.answer("DB not configured", show_alert=True)
            return
        from motor.motor_asyncio import AsyncIOMotorClient
        conn = AsyncIOMotorClient(DATABASE_URL)
        db = conn.kpsmlx
        doc = await db.retask.find_one({"_id": cancel_id})
        if not doc:
            await query.answer("Expired or not found", show_alert=True)
            try:
                conn.close()
            except Exception:
                pass
            return
        chat_id = doc.get("chat_id")
        message_id = doc.get("message_id")
        try:
            msg = await bot.get_messages(chat_id, message_id)
            if not msg or not msg.document:
                await query.answer("File not found", show_alert=True)
                return
            bio = await bot.download_media(msg, in_memory=True)
            if isinstance(bio, (bytes, bytearray)):
                bio = io.BytesIO(bio)
            if bio is None:
                await query.answer("Download failed", show_alert=True)
                return
            bio.seek(0)
            content = bio.read().decode(errors="ignore")
            lines = [l.strip() for l in content.splitlines() if l.strip() and "http" in l.strip()]
            if not lines:
                await query.answer("No links found", show_alert=True)
                return
            await query.answer(f"Retasking {len(lines)} links...", show_alert=False)
            try:
                from ..ext_utils.bot_utils import is_url, is_mega_link, is_gdrive_link, is_telegram_link
                from ... import DOWNLOAD_DIR
                from ..telegram_helper.message_utils import sendMessage
                from pyrogram.enums import ChatType
                import shlex
                for line in lines:
                    try:
                        txt = line.strip()
                        if not txt:
                            continue
                        fake_text = f"/mirror {txt}"
                        class FChat:
                            def __init__(self, cid, ctype):
                                self.id = cid
                                self.type = ctype
                        class FUser:
                            def __init__(self, u):
                                self.id = u.id
                                self.username = getattr(u, "username", None)
                                self.first_name = getattr(u, "first_name", "User")
                                self.is_bot = False
                                self.mention = getattr(u, "mention", f"user{self.id}")
                        fchat = FChat(query.from_user.id, ChatType.PRIVATE)
                        try:
                            fchat.type = query.message.chat.type
                            fchat.id = query.from_user.id
                        except Exception:
                            pass
                        fuser = FUser(query.from_user)
                        class FMsg:
                            pass
                        fmsg = FMsg()
                        fmsg.id = query.message.id + 1
                        fmsg.chat = fchat
                        fmsg.from_user = fuser
                        fmsg.text = fake_text
                        fmsg.caption = None
                        fmsg.reply_to_message = None
                        fmsg.link = f"https://t.me/c/{str(chat_id).replace('-100','')}/{message_id}"
                        fmsg.sender_chat = None
                        fmsg.date = datetime.now(timezone.utc)
                        from ...modules.mirror_leech import _mirror_leech
                        _mirror_leech(client, fmsg)
                        await asyncio.sleep(1)
                    except Exception:
                        continue
            except Exception as e:
                LOGGER.error(f"retask requeue failed {e}")
            try:
                await bot.delete_messages(chat_id, message_id)
            except Exception:
                pass
            await db.retask.delete_one({"_id": cancel_id})
            try:
                conn.close()
            except Exception:
                pass
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception as e:
            await query.answer(f"Error {e}", show_alert=True)
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        try:
            await query.answer(f"Error {e}", show_alert=True)
        except Exception:
            pass
try:
    bot.add_handler(CallbackQueryHandler(handle_retask_callback, filters=regex(r"^retask_")))
except Exception:
    pass
