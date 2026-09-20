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
    Returns dict {custom_emoji_id: fallback_char} unique by ID.
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

    text = f"**[ᴍᴇssᴀɢᴇ ɪᴅ:]({message.link})** `{message.id}`\n"
    text += f"**[ʏᴏᴜʀ ɪᴅ:](tg://user?id={your_id})** `{your_id}`\n"

    if len(message.command) > 1:
        try:
            target = message.text.split(None, 1)[1].strip()
            user_obj = await client.get_users(target)
            text += f"**[ᴜsᴇʀ ɪᴅ:](tg://user?id={user_obj.id})** `{user_obj.id}`\n"
        except Exception:
            return await message.reply_text("ᴛʜɪs ᴜsᴇʀ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ.", quote=True)

    text += (
        f"**[ᴄʜᴀᴛ ɪᴅ:](https://t.me/{chat.username})** `{chat.id}`\n\n"
        if chat.username
        else f"**[ᴄʜᴀᴛ ɪᴅ:]** `{chat.id}`\n\n"
    )

    if reply and not getattr(reply, "empty", True):
        text += f"**[ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:]({reply.link})** `{reply.id}`\n"
        if reply.from_user:
            text += f"**[ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ ɪᴅ:](tg://user?id={reply.from_user.id})** `{reply.from_user.id}`\n\n"

        fwd_chat = getattr(getattr(reply, "forward_origin", None), "chat", None) or getattr(reply, "forward_from_chat", None)
        if fwd_chat:
            text += f"ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴄʜᴀᴛ, **{getattr(fwd_chat, 'title', '')}**, ʜᴀs ᴀɴ ɪᴅ ᴏғ `{fwd_chat.id}`\n\n"

        fwd_user = getattr(getattr(reply, "forward_origin", None), "sender_user", None) or getattr(reply, "forward_from", None)
        if fwd_user:
            text += f"ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴜsᴇʀ, **{getattr(fwd_user, 'first_name', '')}**, ʜᴀs ᴀɴ ɪᴅ ᴏғ `{fwd_user.id}`\n\n"

        if reply.sender_chat:
            text += f"ɪᴅ ᴏғ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴄʜᴀᴛ/ᴄʜᴀɴɴᴇʟ ɪs `{reply.sender_chat.id}`\n\n"

        if getattr(reply, "message_thread_id", None):
            text += f"**ᴛᴏᴘɪᴄ / ᴛʜʀᴇᴀᴅ ɪᴅ:** `{reply.message_thread_id}`\n\n"

        for attr, label in MEDIA_TYPES:
            media = getattr(reply, attr, None)
            if media:
                f_id = getattr(media, 'file_id', None)
                if f_id:
                    text += f"**{label} ғɪʟᴇ ɪᴅ:** `{f_id}`\n"
                    if getattr(media, "file_unique_id", None):
                        text += f"**{label} ᴜɴɪǫᴜᴇ ɪᴅ:** `{media.file_unique_id}`\n\n"
                    break

        if reply.poll:
            text += f"**ᴘᴏʟʟ ɪᴅ:** `{reply.poll.id}`\n\n"
        if reply.contact:
            c_id = reply.contact.user_id or reply.contact.phone_number
            text += f"**ᴄᴏɴᴛᴀᴄᴛ ɪᴅ:** `{c_id}`\n\n"
        if reply.location:
            text += f"**ʟᴏᴄᴀᴛɪᴏɴ:** `{reply.location.latitude}, {reply.location.longitude}`\n\n"
        if reply.dice:
            text += f"**ᴅɪᴄᴇ:** `{reply.dice.emoji} -> {reply.dice.value}`\n\n"

    # --- send existing ID info exactly as before (preserve output & forwarding) ---
    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.DEFAULT,
    )

    # --- Premium/Custom Emoji extraction (new, non-breaking) ---
    # Only if reply exists; uses same reply object so forwarding logic is reused
    try:
        premium = _collect_premium_emojis(reply) if (reply and not getattr(reply, "empty", True)) else {}
        if premium:
            # Build HTML with tg-emoji so actual premium emoji renders (not fallback)
            # Format: "<actual premium emoji> - <code>ID</code>" per requirement, copy-friendly
            lines = []
            for cid, fallback in premium.items():
                # html-escape fallback? It is emoji, safe. If fallback contains <>&, escape minimal
                fb = fallback.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                lines.append(f'<tg-emoji emoji-id="{cid}">{fb}</tg-emoji> - <code>{cid}</code>')
            premium_text = "\n".join(lines)
            # Optional header for clarity, but keeps format as specified
            # Not adding extra markdown to avoid breaking copy-friendly
            await message.reply_text(
                premium_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
    except Exception:
        # Never break main flow
        pass

bot.add_handler(MessageHandler(universal_id, filters=command(BotCommands.IdCommand) & (CustomFilters.authorized | CustomFilters.sudo)))
