import html as _html
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from pyrogram.enums import ParseMode

from .. import bot
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters

MEDIA_TYPES = (
    ('document', 'ᴅᴏᴄᴜᴍᴇɴᴛ'),
    ('photo', 'ᴘʜᴏᴛᴏ'),
    ('video', 'ᴠɪᴅᴇᴏ'),
    ('animation', 'ɢɪғ'),
    ('sticker', 'sᴛɪᴄᴋᴇʀ'),
    ('audio', 'ᴀᴜᴅɪᴏ'),
    ('voice', 'ᴠᴏɪᴄᴇ'),
    ('video_note', 'ᴠɪᴅᴇᴏ ɴᴏᴛᴇ'),
)

# ── Premium/Custom Emoji helpers (existing logic preserved, only extension) ──
def _get_fallback(text, offset, length):
    """Extract UTF-16 slice for custom emoji placeholder. Fallback to 😀."""
    try:
        raw = str(text) if text is not None else ""
        if not raw:
            return "😀"
        b = raw.encode('utf-16-le')
        # offset/length are in UTF-16 code units
        start = int(offset) * 2
        end = start + int(length) * 2
        if start < 0 or end > len(b) or start >= end:
            return "😀"
        fb = b[start:end].decode('utf-16-le')
        if fb and fb.strip():
            return fb
    except Exception:
        pass
    return "😀"

def _collect_premium_emojis(reply):
    """
    Scan reply message for Premium/Custom Emojis.
    Returns dict {custom_emoji_id: fallback_char} unique by ID, order = detection order.
    Covers:
    - text + entities
    - caption + caption_entities
    - inline/reply buttons icon_custom_emoji_id
    """
    out = {}
    if not reply or getattr(reply, "empty", True):
        return out

    # --- 1) text / caption entities ---
    def process(text, entities):
        if not text or not entities:
            return
        for ent in entities:
            try:
                # robust type check across pyrogram/wzgram versions
                is_custom = False
                try:
                    from pyrogram.enums import MessageEntityType
                    is_custom = ent.type == MessageEntityType.CUSTOM_EMOJI
                except Exception:
                    # fallback string compare
                    tname = getattr(getattr(ent, "type", None), "name", str(getattr(ent, "type", "")))
                    is_custom = str(tname).upper() == "CUSTOM_EMOJI"
                if not is_custom:
                    continue
                cid = getattr(ent, "custom_emoji_id", None)
                if not cid:
                    continue
                cid = str(cid)
                if cid in out:
                    continue
                fb = _get_fallback(text, getattr(ent, "offset", 0), getattr(ent, "length", 2))
                out[cid] = fb
            except Exception:
                continue

    try:
        process(getattr(reply, "text", None), getattr(reply, "entities", None))
        process(getattr(reply, "caption", None), getattr(reply, "caption_entities", None))
    except Exception:
        pass

    # --- 2) buttons (inline + reply) ---
    try:
        markup = getattr(reply, "reply_markup", None)
        if markup:
            kb = None
            if hasattr(markup, "inline_keyboard") and getattr(markup, "inline_keyboard"):
                kb = markup.inline_keyboard
            elif hasattr(markup, "keyboard") and getattr(markup, "keyboard"):
                kb = markup.keyboard
            if kb:
                for row in kb:
                    for btn in row or []:
                        try:
                            cid = getattr(btn, "icon_custom_emoji_id", None)
                            if cid and str(cid) not in out:
                                out[str(cid)] = "😀"
                        except Exception:
                            continue
    except Exception:
        pass

    return out

async def universal_id(client, message):
    chat = message.chat
    your_id = message.from_user.id if message.from_user else chat.id
    reply = message.reply_to_message

    # Build main ID text as HTML (so we can send single message with tg-emoji)
    # HTML keeps same visual: <b> for bold, <code> for code, <a> for links
    text = f'<b><a href="{message.link}">ᴍᴇssᴀɢᴇ ɪᴅ:</a></b> <code>{message.id}</code>\n'
    text += f'<b><a href="tg://user?id={your_id}">ʏᴏᴜʀ ɪᴅ:</a></b> <code>{your_id}</code>\n'

    if len(message.command) > 1:
        try:
            target = message.text.split(None, 1)[1].strip()
            user_obj = await client.get_users(target)
            text += f'<b><a href="tg://user?id={user_obj.id}">ᴜsᴇʀ ɪᴅ:</a></b> <code>{user_obj.id}</code>\n'
        except Exception:
            return await message.reply_text("ᴛʜɪs ᴜsᴇʀ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ.", quote=True)

    if chat.username:
        text += f'<b><a href="https://t.me/{chat.username}">ᴄʜᴀᴛ ɪᴅ:</a></b> <code>{chat.id}</code>\n\n'
    else:
        text += f'<b>ᴄʜᴀᴛ ɪᴅ:</b> <code>{chat.id}</code>\n\n'

    if reply and not getattr(reply, "empty", True):
        text += f'<b><a href="{reply.link}">ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:</a></b> <code>{reply.id}</code>\n'
        if reply.from_user:
            text += f'<b><a href="tg://user?id={reply.from_user.id}">ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ ɪᴅ:</a></b> <code>{reply.from_user.id}</code>\n\n'

        fwd_chat = getattr(getattr(reply, "forward_origin", None), "chat", None) or getattr(reply, "forward_from_chat", None)
        if fwd_chat:
            title = _html.escape(getattr(fwd_chat, 'title', '') or '')
            text += f'ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴄʜᴀᴛ, <b>{title}</b>, ʜᴀs ᴀɴ ɪᴅ ᴏғ <code>{fwd_chat.id}</code>\n\n'

        fwd_user = getattr(getattr(reply, "forward_origin", None), "sender_user", None) or getattr(reply, "forward_from", None)
        if fwd_user:
            fname = _html.escape(getattr(fwd_user, 'first_name', '') or '')
            text += f'ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴜsᴇʀ, <b>{fname}</b>, ʜᴀs ᴀɴ ɪᴅ ᴏғ <code>{fwd_user.id}</code>\n\n'

        if reply.sender_chat:
            text += f'ɪᴅ ᴏғ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴄʜᴀᴛ/ᴄʜᴀɴɴᴇʟ ɪs <code>{reply.sender_chat.id}</code>\n\n'

        if getattr(reply, "message_thread_id", None):
            text += f'<b>ᴛᴏᴘɪᴄ / ᴛʜʀᴇᴀᴅ ɪᴅ:</b> <code>{reply.message_thread_id}</code>\n\n'

        for attr, label in MEDIA_TYPES:
            media = getattr(reply, attr, None)
            if media:
                f_id = getattr(media, 'file_id', None)
                if f_id:
                    text += f'<b>{label} ғɪʟᴇ ɪᴅ:</b> <code>{f_id}</code>\n'
                    if getattr(media, "file_unique_id", None):
                        text += f'<b>{label} ᴜɴɪǫᴜᴇ ɪᴅ:</b> <code>{media.file_unique_id}</code>\n\n'
                    break

        if reply.poll:
            text += f'<b>ᴘᴏʟʟ ɪᴅ:</b> <code>{reply.poll.id}</code>\n\n'
        if reply.contact:
            c_id = reply.contact.user_id or reply.contact.phone_number
            text += f'<b>ᴄᴏɴᴛᴀᴄᴛ ɪᴅ:</b> <code>{c_id}</code>\n\n'
        if reply.location:
            text += f'<b>ʟᴏᴄᴀᴛɪᴏɴ:</b> <code>{reply.location.latitude}, {reply.location.longitude}</code>\n\n'
        if reply.dice:
            dice_e = _html.escape(getattr(reply.dice, 'emoji', '') or '')
            text += f'<b>ᴅɪᴄᴇ:</b> <code>{dice_e} -&gt; {reply.dice.value}</code>\n\n'

    # --- Premium/Custom Emoji: append numbered list to SAME message with actual CUSTOM_EMOJI entity (WZGram <emoji id="">) ---
    try:
        premium = _collect_premium_emojis(reply) if (reply and not getattr(reply, "empty", True)) else {}
        if premium:
            # Ensure separator: existing text already ends with \n\n if reply block, else \n\n
            if not text.endswith("\n"):
                text += "\n"
            if not text.endswith("\n\n"):
                text += "\n"
            text += "<b>Premium Emojis:</b>\n"
            for idx, (cid, fallback) in enumerate(premium.items(), start=1):
                fb_raw = fallback.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                # WZGram existing syntax: <emoji id="...">fallback</emoji> => renders actual Premium emoji (id mandatory)
                text += f'{idx}. <emoji id="{cid}">{fb_raw}</emoji> - <code>{cid}</code>\n'
    except Exception:
        pass

    # Single output message (existing + premium appended)
    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
    )

bot.add_handler(MessageHandler(universal_id, filters=command(BotCommands.IdCommand) & (CustomFilters.authorized | CustomFilters.sudo)))
