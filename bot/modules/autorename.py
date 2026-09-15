#!/usr/bin/env python3
import re
import os
from .. import user_data, LOGGER, bot, DATABASE_URL
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from ..helper.telegram_helper.message_utils import sendMessage
from ..helper.ext_utils.bot_utils import update_user_ldata
from ..helper.ext_utils.db_handler import DbManger
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.bot_commands import BotCommands
from html import escape

def trun(text, limit=60):
    text = str(text)
    return text[:limit] + "..." if len(text) > limit else text

VALID_AUTORENAME_TAGS = {'title', 'season', 'episode',
                          'quality', 'codec', 'audio', 'sub', 'size', 'language'}

def validate_autorename_format(format_str):
    used_tags = set(re.findall(r'\{([a-zA-Z_]+)\}', format_str))
    return used_tags - VALID_AUTORENAME_TAGS

def get_autorename(filename, user_id, size="", media_quality="", lang="", subs="", caption="", skip=False):
    user_dict = user_data.get(user_id, {})

    if skip:
        return filename

    if not user_dict.get('autorename', False):
        return filename

    format_str = user_dict.get('autorename_format', '{title} - S{season}E{episode} - {quality} {codec} {audio} {sub}')
    if not format_str:
        format_str = '{title} - S{season}E{episode} - {quality}'

    name, ext = os.path.splitext(filename)

    has_custom_ext = bool(re.search(r'\.[A-Za-z0-9]{2,5}$', format_str.strip()))

    caption_name = os.path.splitext(caption.split('\n')[0])[0] if caption else ""

    season_match = re.search(r'(?:S|Season\s*)(\d{1,2})', name, re.IGNORECASE)
    if not season_match and caption_name:
        season_match = re.search(r'(?:S|Season\s*)(\d{1,2})', caption_name, re.IGNORECASE)
    season = season_match.group(1).zfill(2) if season_match else ""

    episode_match = re.search(r'(?:E|Ep|Episode\s*)(\d{1,3})', name, re.IGNORECASE)
    if not episode_match and caption_name:
        episode_match = re.search(r'(?:E|Ep|Episode\s*)(\d{1,3})', caption_name, re.IGNORECASE)
    episode = episode_match.group(1).zfill(2) if episode_match else ""

    quality_match = re.search(r'(480p|720p|1080p|1440p|2160p|4K)', name, re.IGNORECASE)
    quality = quality_match.group(1) if quality_match else media_quality
    
    codec_match = re.search(r'(x264|x265|HEVC|AV1|H264|H265|10bit|10Bit|AVC)', name, re.IGNORECASE)
    codec = codec_match.group(1) if codec_match else ""
    
    audio_match = re.search(r'(Dual[\s\-]?Audio|Multi[\s\-]?Audio|Hindi|English|Tamil|Telugu|Malayalam|Kannada|Bengali)', name, re.IGNORECASE)
    audio = audio_match.group(1).title() if audio_match else lang
    
    sub_match = re.search(r'(ESub|HC-ENG|MSub|Multi[\s\-]?Sub|Subbed)', name, re.IGNORECASE)
    sub = sub_match.group(1) if sub_match else subs

    clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', name) 
    noise_pattern = r'(S\d{1,2}|E\d{1,3}|Ep\s*\d{1,3}|Episode\s*\d{1,3}|480p|720p|1080p|1440p|2160p|4K|x264|x265|HEVC|AV1|H264|H265|10bit|10Bit|AVC|BluRay|WEB-DL|WEBRip|HDRip|HDTV|Dual[\s\-]?Audio|Multi[\s\-]?Audio|Hindi|English|Tamil|Telugu|Malayalam|Kannada|Bengali|ESub|HC-ENG|MSub|Multi[\s\-]?Sub|Subbed|Audio)'
    clean_title = re.sub(noise_pattern, '', clean_title, flags=re.IGNORECASE)
    clean_title = re.sub(r'(\s|-|\.)+', ' ', clean_title).strip() 

    custom_title = user_dict.get('custom_title', '')
    final_title = custom_title if custom_title else clean_title

    try:
        new_name = format_str.format(
            title=final_title,
            season=season,
            episode=episode,
            quality=quality,
            codec=codec,
            audio=audio,
            sub=sub,
            size=size,
            language=audio
        )
        
        if not season and not episode:
            new_name = new_name.replace('SE', '').replace('S E', '')
        elif not season and episode:
            new_name = new_name.replace('SE', 'E')
        elif season and not episode:
            new_name = re.sub(rf'S{re.escape(season)}E(?!\d)', f'S{season}', new_name)
            
        new_name = re.sub(r'\s+', ' ', new_name)
        new_name = re.sub(r'-\s*-', '-', new_name)
        new_name = re.sub(r'\.\s*\.', '.', new_name)
        new_name = new_name.strip(' -.')
        
        if not new_name:
            new_name = final_title

        final_name = new_name if has_custom_ext else f"{new_name}{ext}"

        LOGGER.info(f"Auto Renamed: {filename} -> {final_name}")
        return final_name
    
    except KeyError as e:
        LOGGER.error(f"Auto Rename KeyError: Missing tag {e} in user format.")
        return filename
    except Exception as e:
        LOGGER.error(f"Auto Rename Error: {e}")
        return filename


async def autorename_cmd(client, message):
    user_id = message.from_user.id

    if len(message.command) > 1:
        new_format = message.text.split(maxsplit=1)[1]
        if invalid_tags := validate_autorename_format(new_format):
            bad = ", ".join(f"{{{t}}}" for t in sorted(invalid_tags))
            await sendMessage(
                message,
                f"<b>⚠️ Invalid Tag(s) In Format:</b> <code>{escape(bad)}</code>\n\n"
                f"<b>Available Tags :</b> <code>{{title}}</code>, <code>{{season}}</code>, <code>{{episode}}</code>, "
                f"<code>{{quality}}</code>, <code>{{codec}}</code>, <code>{{audio}}</code>, <code>{{sub}}</code>, "
                f"<code>{{size}}</code>, <code>{{language}}</code>\n\n"
                f"<i>Format was not saved. Please fix the tag and try again.</i>"
            )
            return
        update_user_ldata(user_id, 'autorename_format', new_format)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
        await sendMessage(message, f"<b>Auto Rename Format Updated To:</b>\n<code>{escape(new_format)}</code>")
        return

    user_dict = user_data.get(user_id, {})
    buttons = ButtonMaker()

    auto_status = 'Enabled' if user_dict.get('autorename', False) else 'Disabled'
    format_str = user_dict.get('autorename_format', 'Not Exists')
    custom_title = user_dict.get('custom_title', 'Not Exists')
    
    text = f"㊂ <b><u>Auto Rename Settings :</u></b>\n\n"
    text += f"➲ <b>Status :</b> <i>{auto_status}</i>\n"
    text += f"➲ <b>Current Format :</b> <code>{escape(trun(format_str, 60))}</code>\n"
    text += f"➲ <b>Custom Title :</b> <code>{escape(trun(custom_title, 60))}</code>\n\n"
    text += f"➲ <b>Available Tags :</b> <code>{{title}}</code>, <code>{{season}}</code>, <code>{{episode}}</code>, <code>{{quality}}</code>, <code>{{codec}}</code>, <code>{{audio}}</code>, <code>{{sub}}</code>, <code>{{size}}</code>, <code>{{language}}</code>\n"
    text += f"➲ <b>Format Example :</b> <code>{{title}} S{{season}}E{{episode}} [{{quality}}] Hindi.mkv</code>\n\n"
    text += f"➲ <b>Description :</b> <i>Set your Custom Format and Title for Auto Renaming files. Custom Title will override {{title}}. Add an extension (.mkv/.mp4) at the end of the format to force it, otherwise the original file's extension is kept. Season/Episode are auto-detected from the filename, and from the file caption if missing in the name. A manual rename command (e.g. \"-n filename.mkv\") always overrides Auto Rename.</i>"

    buttons.ibutton("Disable" if auto_status == 'Enabled' else "Enable", f"userset {user_id} toggle_autorename")
    buttons.ibutton("Set Format", f"userset {user_id} autorename_format edit")
    buttons.ibutton("Set Custom Title", f"userset {user_id} custom_title edit")
    
    if format_str != 'Not Exists':
        buttons.ibutton("↻ Delete Format", f"userset {user_id} dautorename_format")
    if custom_title != 'Not Exists':
        buttons.ibutton("↻ Delete Title", f"userset {user_id} dcustom_title")
    
    buttons.ibutton("Close", f"userset {user_id} close", "footer")
    
    button = buttons.build_menu(2)
    await sendMessage(message, text, button)

bot.add_handler(MessageHandler(autorename_cmd, filters=command(BotCommands.AutoRenameCommand) & CustomFilters.authorized_uset))
