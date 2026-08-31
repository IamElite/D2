#!/usr/bin/env python3
from aiohttp import ClientSession
from re import search as re_search
from shlex import split as ssplit
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, path as aiopath, mkdir
from os import path as ospath, getcwd

from pyrogram.handlers import MessageHandler 
from pyrogram.filters import command

from .. import LOGGER, bot, config_dict
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import editMessage, sendMessage
from ..helper.ext_utils.bot_utils import cmd_exec
from ..helper.ext_utils.telegraph_helper import telegraph


async def gen_mediainfo(message, link=None, media=None, mmsg=None):
    temp_send = await sendMessage(message, '<i>Generating MediaInfo...</i>')
    des_path = None
    try:
        path = "Mediainfo/"
        if not await aiopath.isdir(path):
            await mkdir(path)
        if link:
            filename = re_search(".+/(.+)", link).group(1)
            des_path = ospath.join(path, filename)
            headers = {"user-agent":"Mozilla/5.0 (Linux; Android 12; 2201116PI) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36"}
            head_b, tail_b = 16 * 1024 * 1024, 16 * 1024 * 1024
            async with ClientSession() as session:
                async with session.get(link, headers=headers) as response:
                    clen = int(response.headers.get("Content-Length") or 0)
                    got = 0
                    async with aiopen(des_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                            got += len(chunk)
                            if got >= head_b:
                                break
                if clen > head_b + tail_b:
                    rh = dict(headers)
                    rh["Range"] = f"bytes={clen - tail_b}-{clen - 1}"
                    try:
                        async with session.get(link, headers=rh) as response:
                            if response.status in (200, 206):
                                async with aiopen(des_path, "ab") as f:
                                    async for chunk in response.content.iter_chunked(1024 * 1024):
                                        await f.write(chunk)
                    except Exception:
                        pass
        elif media:
            des_path = ospath.join(path, media.file_name or "media.bin")
            if media.file_size and media.file_size <= 50 * 1024 * 1024:
                await mmsg.download(ospath.join(getcwd(), des_path))
            else:
                chunk_sz, head_n, tail_n = 1024 * 1024, 16, 16
                async with aiopen(des_path, "wb") as f:
                    async for chunk in bot.stream_media(media, limit=head_n):
                        await f.write(chunk)
                fsize = getattr(media, "file_size", 0) or 0
                if fsize > (head_n + tail_n) * chunk_sz:
                    total = max(head_n + tail_n, fsize // chunk_sz)
                    off = max(head_n, total - tail_n)
                    try:
                        async for chunk in bot.stream_media(media, offset=off, limit=tail_n):
                            async with aiopen(des_path, "ab") as f:
                                await f.write(chunk)
                    except Exception:
                        pass
        stdout, _, _ = await cmd_exec(ssplit(f'mediainfo "{des_path}"'))
        tc = f"<h4>📌 {ospath.basename(des_path)}</h4><br><br>"
        if len(stdout) != 0:
            tc += parseinfo(stdout)
    except Exception as e:
        LOGGER.error(e)
        await editMessage(temp_send, f"MediaInfo Stopped due to {str(e)}")
    finally:
        if des_path:
            try:
                await aioremove(des_path)
            except Exception:
                pass
    link_id = (await telegraph.create_page(title='MediaInfo X', content=tc))["path"]
    await temp_send.edit(f"<b>MediaInfo:</b>\n\n➲ <b>Link :</b> https://graph.org/{link_id}", disable_web_page_preview=False)


section_dict = {'General': '🗒', 'Video': '🎞', 'Audio': '🔊', 'Text': '🔠', 'Menu': '🗃'}
def parseinfo(out):
    tc = ''
    trigger = False
    for line in out.split('\n'):
        for section, emoji in section_dict.items():
            if line.startswith(section):
                trigger = True
                if not line.startswith('General'):
                    tc += '</pre><br>'
                tc += f"<h4>{emoji} {line.replace('Text', 'Subtitle')}</h4>"
                break
        if trigger:
            tc += '<br><pre>'
            trigger = False
        else:
            tc += line + '\n'
    tc += '</pre><br>'
    return tc


async def mediainfo(_, message):
    rply = message.reply_to_message
    help_msg = "<b>By replying to media:</b>"
    help_msg += f"\n<code>/{BotCommands.MediaInfoCommand[0]} or /{BotCommands.MediaInfoCommand[1]}" + " {media}" + "</code>"
    help_msg += "\n\n<b>By reply/sending download link:</b>"
    help_msg += f"\n<code>/{BotCommands.MediaInfoCommand[0]} or /{BotCommands.MediaInfoCommand[1]}" + " {link}" + "</code>"
    if len(message.command) > 1 or rply and rply.text:
        link = rply.text if rply else message.command[1]
        return await gen_mediainfo(message, link)
    elif rply:
        if file := next(
            (
                i
                for i in [
                    rply.document,
                    rply.video,
                    rply.audio,
                    rply.voice,
                    rply.animation,
                    rply.video_note,
                ]
                if i is not None
            ),
            None,
        ):
            return await gen_mediainfo(message, None, file, rply)
        else:
            return await sendMessage(message, help_msg)
    else:
        return await sendMessage(message, help_msg)

bot.add_handler(MessageHandler(mediainfo, filters=command(BotCommands.MediaInfoCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
