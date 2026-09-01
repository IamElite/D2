from secrets import token_hex

from ... import CMD_SUFFIX, multi_tags
from ..telegram_helper.message_utils import deleteMessage, sendMessage

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
