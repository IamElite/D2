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

    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.DEFAULT,
    )

bot.add_handler(MessageHandler(universal_id, filters=command(BotCommands.IdCommand) & (CustomFilters.authorized | CustomFilters.sudo)))
