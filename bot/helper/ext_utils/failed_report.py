import asyncio
from time import time as _now
from html import escape
from ... import user_data, LOGGER
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
async def record_failure(uid, tag, name, reason):
    if not tag:
        return
    async with _lock:
        d = _bulk_tracker.get(tag)
        if not d:
            return
        d["failed"].append({"name": (name or "Unknown")[:500], "reason": (reason or "Unknown reason")[:800]})
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
