#!/usr/bin/env python3
"""
Bulk Failed Task Report — DM after bulk completes if user enabled universal setting.

Tracker keyed by multi_tag (bulk) or per-user fallback.
Only sends when user_data[user_id].get('failed_report') is True (default OFF).
DM only via sendCustomMsg, chunks if >4000 chars via BytesIO.
File names use formatted name (autorename/prefix/suffix) when available.
"""

import asyncio
from time import time as _now
from html import escape

from ... import user_data, LOGGER

# global tracker: {tag: {user_id, total, done, failed: [{name, reason}], created, sent}}
_bulk_tracker = {}
_lock = asyncio.Lock()

def _tag_display(tag):
    return tag[:8] if tag and len(tag) > 8 else (tag or "single")

async def register_bulk(user_id: int, tag: str, total: int):
    """Called when bulk/multi is initiated. total = expected tasks in batch."""
    if not tag or total <= 1:
        return
    async with _lock:
        if tag in _bulk_tracker:
            # keep larger total, preserve existing done/failed
            if total > _bulk_tracker[tag]['total']:
                _bulk_tracker[tag]['total'] = total
            _bulk_tracker[tag]['user_id'] = user_id
            LOGGER.info(f"FailedReport: bulk { _tag_display(tag)} updated total={total} for user {user_id} (done={_bulk_tracker[tag]['done']})")
            return
        _bulk_tracker[tag] = {
            'user_id': user_id,
            'total': total,
            'done': 0,
            'failed': [],
            'created': _now(),
            'sent': False,
        }
        LOGGER.info(f"FailedReport: registered bulk {_tag_display(tag)} total={total} user={user_id}")

async def _maybe_send_report(tag: str):
    """Check if done == total and send DM if needed. Called with lock held."""
    data = _bulk_tracker.get(tag)
    if not data or data.get('sent'):
        return
    total = data['total']
    done = data['done']
    if done < total:
        return
    # Bulk completed
    data['sent'] = True
    user_id = data['user_id']
    failed = data['failed']
    # Only send if user enabled and there is at least one failure
    u_dict = user_data.get(user_id, {})
    if not u_dict.get('failed_report'):
        LOGGER.info(f"FailedReport: bulk {_tag_display(tag)} done total={total} failed={len(failed)} but user {user_id} disabled — silent")
        # cleanup after delay
        asyncio.create_task(_cleanup_tag(tag, delay=60))
        return
    if not failed:
        LOGGER.info(f"FailedReport: bulk {_tag_display(tag)} done total={total} no failures — no report")
        asyncio.create_task(_cleanup_tag(tag, delay=60))
        return
    # Build report
    try:
        report = await _build_report_text(user_id, total, failed)
        await _send_dm_report(user_id, report, tag)
    except Exception as e:
        LOGGER.error(f"FailedReport: send bulk {_tag_display(tag)} error: {e}")
    finally:
        asyncio.create_task(_cleanup_tag(tag, delay=120))

async def _cleanup_tag(tag: str, delay: int = 60):
    await asyncio.sleep(delay)
    async with _lock:
        _bulk_tracker.pop(tag, None)
        LOGGER.info(f"FailedReport: cleaned tag {_tag_display(tag)}")

async def _build_report_text(user_id: int, total: int, failed: list):
    success = total - len(failed)
    now_s = _now()
    header = (
        f"<b>⚠️ Failed Tasks Report</b>\n"
        f"┎ <b>Total Tasks:</b> <code>{total}</code>\n"
        f"┠ <b>Success:</b> <code>{success}</code>\n"
        f"┖ <b>Failed:</b> <code>{len(failed)}</code>\n\n"
    )
    body = "<b>Failed Files:</b>\n"
    # each entry: name + reason at end
    for idx, entry in enumerate(failed, start=1):
        name = escape(entry.get('name') or 'Unknown')
        reason = escape(entry.get('reason') or 'Unknown reason')
        # truncate very long name/reason for report readability but keep full in file fallback
        disp_name = name if len(name) < 180 else name[:177] + "..."
        disp_reason = reason if len(reason) < 300 else reason[:297] + "..."
        body += f"\n{idx}. <code>{disp_name}</code>\n   └ <b>Reason:</b> <i>{disp_reason}</i>\n"
    footer = f"\n<i>Report generated for bulk tasks — only visible to you (DM). Setting: Universal → Failed Report = Enabled</i>"
    return header + body + footer

async def _send_dm_report(user_id: int, text: str, tag: str):
    """Send via bot DM, chunk if needed, use BytesIO fallback for huge."""
    from ..telegram_helper.message_utils import sendCustomMsg, sendFile
    from io import BytesIO
    # Telegram limit 4096, we keep 4000
    if len(text.encode()) <= 3800:
        try:
            await sendCustomMsg(user_id, text)
            LOGGER.info(f"FailedReport: DM sent bulk {_tag_display(tag)} to {user_id} ({len(text)} chars)")
            return
        except Exception as e:
            LOGGER.warning(f"FailedReport: DM send failed for {user_id}: {e}")
            return
    # chunk large report into multiple messages (2-3 parts) or file fallback
    # if very large (>8000), use file
    if len(text.encode()) > 8000:
        bio = BytesIO(text.encode())
        bio.name = f"failed_report_{tag[:6]}_{int(_now())}.txt"
        try:
            await sendFile(user_id, bio, caption=f"<b>⚠️ Failed Tasks Report</b> — Bulk {escape(_tag_display(tag))} ({len(_bulk_tracker.get(tag,{}).get('failed',[]))} failed)")
            LOGGER.info(f"FailedReport: file DM sent bulk {_tag_display(tag)} to {user_id}")
            return
        except Exception as e:
            LOGGER.warning(f"FailedReport: file DM failed {e}, fallback to chunked")
    # chunked messages
    parts = []
    current = ""
    header_len = 0
    for line in text.split("\n"):
        if len((current + "\n" + line).encode()) > 3800:
            parts.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        parts.append(current)
    for i, part in enumerate(parts):
        try:
            await sendCustomMsg(user_id, part)
            LOGGER.info(f"FailedReport: chunk {i+1}/{len(parts)} sent to {user_id}")
            if i < len(parts)-1:
                await asyncio.sleep(1.2)
        except Exception as e:
            LOGGER.warning(f"FailedReport: chunk {i+1} failed: {e}")
            break

# Public APIs called from mirror_leech / tasks_listener
async def record_success(user_id: int, tag: str):
    if not tag:
        return
    async with _lock:
        data = _bulk_tracker.get(tag)
        if not data:
            return
        # ensure user_id matches (bulk owner)
        if data['user_id'] != user_id:
            # allow still count but log
            LOGGER.warning(f"FailedReport: success user mismatch tag {_tag_display(tag)} {data['user_id']} vs {user_id}")
        data['done'] += 1
        LOGGER.info(f"FailedReport: success tag {_tag_display(tag)} done={data['done']}/{data['total']}")
        await _maybe_send_report(tag)

async def record_failure(user_id: int, tag: str, filename: str, reason: str):
    if not tag:
        # Single non-bulk task: do not DM (spec is bulk-only). Keep silent to avoid spam in group.
        return
    async with _lock:
        data = _bulk_tracker.get(tag)
        if not data:
            LOGGER.warning(f"FailedReport: missing tag {_tag_display(tag)} for failure {filename[:40]} — dropping (bulk not registered yet)")
            return
        # dedupe same filename? keep all
        # truncate stored values to avoid memory bloat
        safe_name = (filename or 'Unknown')[:500]
        safe_reason = (reason or 'Unknown reason')[:800]
        data['failed'].append({'name': safe_name, 'reason': safe_reason})
        data['done'] += 1
        LOGGER.info(f"FailedReport: failure tag {_tag_display(tag)} done={data['done']}/{data['total']} failed={len(data['failed'])} file={safe_name[:60]}")
        await _maybe_send_report(tag)

# Helper to resolve display name with autorename/prefix/suffix
async def get_display_name(listener, fallback: str = "") -> str:
    """
    Return formatted name (autorename/prefix/suffix) if possible.
    Uses format_filename; if fails, returns fallback or listener attrs.
    """
    try:
        from ..ext_utils.leech_utils import format_filename
        # Prefer newname if set (custom name), else fallback or source_url
        raw = getattr(listener, 'newname', '') or fallback or getattr(listener, 'name', '') or getattr(listener, 'source_url', '') or 'File'
        # If raw is URL, extract last part for readability
        if raw.startswith('http'):
            raw = raw.split('/')[-1].split('?')[0] or raw
            if not raw or len(raw) < 3:
                raw = getattr(listener, 'source_url', '') or 'File'
        # format_filename expects file_ name, not path
        # It will apply autorename/prefix etc based on user_data
        user_id = getattr(listener, 'user_id', 0) or getattr(listener.message.from_user, 'id', 0) if hasattr(listener, 'message') else 0
        is_mirror = not getattr(listener, 'isLeech', False)
        has_custom = bool(getattr(listener, 'newname', ''))
        caption = getattr(listener, 'orig_caption', '')
        formatted, _ = await format_filename(raw, user_id, isMirror=is_mirror, has_custom_name=has_custom, caption=caption)
        return formatted or raw
    except Exception as e:
        LOGGER.warning(f"FailedReport get_display_name fallback: {e}")
        return fallback or getattr(listener, 'newname', '') or getattr(listener, 'name', '') or 'File'
