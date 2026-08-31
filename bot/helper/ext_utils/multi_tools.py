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
