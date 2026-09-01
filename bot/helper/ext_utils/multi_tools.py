from secrets import token_hex

from ... import CMD_SUFFIX, multi_tags
from ..telegram_helper.message_utils import deleteMessage, sendMessage


def _tg_link(m):
    chat = getattr(m, "chat", None)
    if chat is None or getattr(m, "id", None) is None:
        return None
    un = getattr(chat, "username", None)
    if un:
        return f"https://t.me/{un}/{m.id}"
    cid = str(chat.id)
    if cid.startswith("-100"):
        cid = cid[4:]
    return f"https://t.me/c/{cid}/{m.id}"


def _uid(m):
    fu = getattr(m, "from_user", None)
    if fu is not None:
        return fu.id
    sc = getattr(m, "sender_chat", None)
    return getattr(sc, "id", None) if sc is not None else None


def _is_link_line(line):
    s = line.strip().lower()
    return (
        s.startswith("http://")
        or s.startswith("https://")
        or s.startswith("magnet:")
        or s.startswith("tg://")
        or "t.me/" in s
    )


def _items_in_msg(m):
    if m is None or getattr(m, "empty", False):
        return []
    if getattr(m, "media", None):
        link = _tg_link(m)
        return [link] if link else []
    text = (getattr(m, "text", None) or getattr(m, "caption", None) or "")
    out = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if ln and _is_link_line(ln):
            out.append(ln)
    return out


async def collect_i_items(client, start, cmd, n):
    """Same user only, consecutive msgs, stop on other user/bot. Link+flags or media."""
    if start is None or n <= 0:
        return []
    owner = _uid(start)
    chat = getattr(start, "chat", None)
    if chat is None or owner is None:
        return _items_in_msg(start)[:n]
    items = []
    mid = start.id
    cmd_id = getattr(cmd, "id", None)
    scans = 0
    limit = min(80, max(n * 12, 16))
    while len(items) < n and scans < limit:
        scans += 1
        if cmd_id is not None and mid >= cmd_id:
            break
        try:
            m = await client.get_messages(chat_id=chat.id, message_ids=mid)
        except Exception:
            break
        if m is None or isinstance(m, str) or getattr(m, "empty", False):
            mid += 1
            continue
        fu = getattr(m, "from_user", None)
        if fu is not None and getattr(fu, "is_bot", False):
            break
        if _uid(m) != owner:
            break
        for it in _items_in_msg(m):
            items.append(it)
            if len(items) >= n:
                break
        mid += 1
    return items[:n]

_cmd_by_tag = {}


def ensure_multi_tag(tag, multi):
    if multi <= 1:
        return tag
    if not tag:
        tag = token_hex(3)
        multi_tags.add(tag)
    elif tag not in multi_tags:
        multi_tags.add(tag)
    return tag


def cmd_with_cancel(cmd_text, tag, multi):
    if tag and multi > 1:
        return f"{cmd_text}\n\n➲ cancel /c{CMD_SUFFIX}_{tag}"
    return cmd_text


def multi_still_on(tag):
    return not tag or tag in multi_tags


def drop_multi_tag(tag):
    if tag:
        multi_tags.discard(tag)


def remember_cmd(tag, message):
    if tag and message is not None:
        _cmd_by_tag[tag] = message


async def delete_own(message):
    if message is None:
        return
    try:
        await deleteMessage(message)
    except Exception:
        pass


def next_cmd_text(input_list, bulk, nxt):
    if bulk:
        return f"{input_list[0]} {bulk[0]} -i {nxt}"
    parts = [s.strip() for s in input_list]
    if "-i" in parts:
        i = parts.index("-i")
        if i + 1 < len(parts):
            parts[i + 1] = str(nxt)
        else:
            parts.append(str(nxt))
    else:
        parts.extend(["-i", str(nxt)])
    return " ".join(parts)


async def next_origin(client, message, bulk, has_link):
    """Bulk/list: reply to the user's list. Same-link: this cmd. File-multi: next msg."""
    user_src = getattr(message, "reply_to_message", None)
    if bulk:
        if user_src is not None and getattr(user_src, "id", None):
            return user_src
        return message
    if has_link:
        return message
    reply_id = getattr(message, "reply_to_message_id", None)
    chat = getattr(message, "chat", None)
    if reply_id is None or chat is None:
        return message
    try:
        got = await client.get_messages(chat_id=chat.id, message_ids=reply_id + 1)
    except Exception:
        return message
    if got is None or isinstance(got, str) or getattr(got, "empty", False):
        return message
    if getattr(got, "id", None) is None:
        return message
    return got


async def send_multi_cmd(origin, cmd_text, tag, multi):
    sent = await sendMessage(origin, cmd_with_cancel(cmd_text, tag, multi))
    remember_cmd(tag, sent)
    return sent


async def stop_multi(tag, notice=None):
    """Drop queue, delete last /cmd -i line, one notice only."""
    drop_multi_tag(tag)
    await delete_own(_cmd_by_tag.pop(tag, None))
    if notice is not None:
        await sendMessage(notice, "Multi Task has been cancelled!")
