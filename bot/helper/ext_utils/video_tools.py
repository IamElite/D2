from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
import json
import logging
from os import path as os_path, replace as os_replace
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from re import sub as re_sub
import shlex

from ... import bot_cache, LOGGER
from .bot_utils import cmd_exec
from .fs_utils import clean_target

LOGGER = logging.getLogger(__name__)


def is_vtool_active(vtools):
    if not vtools or not isinstance(vtools, dict):
        return False
    active_keys = (
        'vidvid', 'vidaud', 'vidsub', 'swap', 'extract', 'remove',
        'encode', 'convert', 'watermark', 'subintro', 'hardsub',
        'trim', 'ffmpeg_cmd', 'megametadata'
    )
    return any(bool(vtools.get(k)) for k in active_keys)


def get_vtools_text(user_dict):
    vt = user_dict.get('vtools', {})

    def st(k):
        return "Enabled" if vt.get(k) else "Disabled"

    custom_name = vt.get('rename') or "Not Set"
    keep_source = st('keepsource')

    text = (
        "STREAM\n"
        f"Extract » {st('extract')} | Swap » {st('swap')}\n"
        f"Remove » {st('remove')}\n\n"
        f"ENCODE » {st('encode')}\n"
        f"CONVERT » {st('convert')}\n"
        f"WATERMARK » {st('watermark')} | Intro Sub » {st('subintro')}\n"
        f"Trim » {st('trim')}\n\n"
        f"Custom Filename » {custom_name}\n"
        f"Keep Source » {keep_source}"
    )
    return text


def build_vtools_keyboard(user_id, user_dict, is_task=False):
    vt = user_dict.get('vtools', {})

    def tick(k):
        return "✓ " if vt.get(k) else ""

    rows = [
        [
            InlineKeyboardButton("FFMPEG CMD", callback_data=f"userset {user_id} vt_ffmpeg"),
            InlineKeyboardButton("MegaMetaData", callback_data=f"userset {user_id} vt_megameta"),
        ],
        [
            InlineKeyboardButton(f"{tick('vidvid')}Vid+Vid", callback_data=f"userset {user_id} vt_tog_vidvid"),
            InlineKeyboardButton(f"{tick('vidaud')}Vid+Aud", callback_data=f"userset {user_id} vt_tog_vidaud"),
            InlineKeyboardButton(f"{tick('vidsub')}Vid+Sub", callback_data=f"userset {user_id} vt_tog_vidsub"),
        ],
        [
            InlineKeyboardButton(f"{tick('swap')}StreamSwap", callback_data=f"userset {user_id} vt_tog_swap"),
            InlineKeyboardButton(f"{tick('extract')}Extract", callback_data=f"userset {user_id} vt_tog_extract"),
            InlineKeyboardButton(f"{tick('remove')}Remove", callback_data=f"userset {user_id} vt_tog_remove"),
        ],
        [
            InlineKeyboardButton(f"{tick('encode')}Encode", callback_data=f"userset {user_id} vt_tog_encode"),
            InlineKeyboardButton(f"{tick('convert')}Convert", callback_data=f"userset {user_id} vt_tog_convert"),
            InlineKeyboardButton(f"{tick('watermark')}Watermark", callback_data=f"userset {user_id} vt_tog_watermark"),
        ],
        [
            InlineKeyboardButton(f"{tick('subintro')}Sub Intro", callback_data=f"userset {user_id} vt_tog_subintro"),
            InlineKeyboardButton(f"{tick('hardsub')}Hardsub", callback_data=f"userset {user_id} vt_tog_hardsub"),
        ],
        [
            InlineKeyboardButton(f"{tick('trim')}Trim", callback_data=f"userset {user_id} vt_tog_trim"),
        ],
        [
            InlineKeyboardButton(f"{tick('keepsource')}Keep Source", callback_data=f"userset {user_id} vt_tog_keepsource"),
        ],
        [
            InlineKeyboardButton("Rename", callback_data=f"userset {user_id} vt_rename"),
        ]
    ]
    if is_task:
        rows.append([
            InlineKeyboardButton("Done", callback_data=f"userset {user_id} vt_done"),
            InlineKeyboardButton("Cancel", callback_data=f"userset {user_id} vt_cancel"),
        ])
    else:
        rows.append([
            InlineKeyboardButton("Back", callback_data=f"userset {user_id} back"),
            InlineKeyboardButton("Close", callback_data=f"userset {user_id} close"),
        ])
    return InlineKeyboardMarkup(rows)


async def execute_video_tools(listener, base_dir, media_file, outfile, vtools):
    if not vtools or not isinstance(vtools, dict):
        return media_file

    ffmpeg_bin = bot_cache.get('pkgs', ['ffmpeg', 'ffprobe', 'ffmpeg'])[2]
    inplace = os_path.abspath(outfile) == os_path.abspath(media_file)
    if inplace:
        outfile += '.vt' + os_path.splitext(media_file)[1].lower()

    cmd = [ffmpeg_bin, '-nostdin', '-threads', '2', '-y', '-hide_banner', '-loglevel', 'error']

    if vtools.get('trim') and (t_start := vtools.get('trim_start')):
        cmd.extend(['-ss', t_start])
        if t_end := vtools.get('trim_end'):
            cmd.extend(['-to', t_end])

    cmd.extend(['-i', media_file])

    filters = []
    need_encode = False

    if vtools.get('watermark'):
        wm_text = vtools.get('watermark_text') or "notytools"
        pos = vtools.get('watermark_pos') or "bottom_right"
        if pos == "top_left":
            coord = "x=20:y=20"
        elif pos == "top_right":
            coord = "x=w-tw-20:y=20"
        elif pos == "bottom_left":
            coord = "x=20:y=h-th-20"
        elif pos == "center":
            coord = "x=(w-tw)/2:y=(h-th)/2"
        else:
            coord = "x=w-tw-20:y=h-th-20"
        escaped_wm = wm_text.replace(":", "\\:").replace("'", "\\'")
        filters.append(f"drawtext=text='{escaped_wm}':{coord}:fontsize=24:fontcolor=white@0.8")
        need_encode = True

    if vtools.get('hardsub') and (sub_file := vtools.get('hardsub_file')):
        if os_path.exists(sub_file):
            esc_sub = sub_file.replace(":", "\\:").replace("'", "\\'")
            filters.append(f"subtitles='{esc_sub}'")
            need_encode = True

    if vtools.get('encode'):
        need_encode = True

    if filters:
        cmd.extend(['-vf', ','.join(filters)])

    if need_encode:
        cmd.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-c:a', 'copy'])
    else:
        cmd.extend(['-c', 'copy'])

    if vtools.get('remove'):
        cmd.extend(['-map', '0', '-map', '-0:s?'])
    elif vtools.get('swap'):
        cmd.extend(['-map', '0:v', '-map', '0:a:1?', '-map', '0:a:0?', '-map', '0:s?'])

    if vtools.get('ffmpeg_cmd') and (custom_args := vtools.get('ffmpeg_cmd').strip()):
        try:
            cmd.extend(shlex.split(custom_args))
        except Exception:
            pass

    cmd.append(outfile)

    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()

    if code == 0:
        if vtools.get('keepsource'):
            final_path = outfile
        elif inplace:
            os_replace(outfile, media_file)
            final_path = media_file
        else:
            await clean_target(media_file)
            final_name = os_path.basename(outfile)
            if vtools.get('rename'):
                final_name = vtools['rename']
                if not os_path.splitext(final_name)[1]:
                    final_name += os_path.splitext(outfile)[1]
            dest = os_path.join(base_dir, final_name)
            os_replace(outfile, dest)
            final_path = dest
        listener.seed = False
        return final_path
    else:
        if os_path.abspath(outfile) != os_path.abspath(media_file):
            await clean_target(outfile)
        err = (await listener.suproc.stderr.read()).decode(errors='ignore')
        LOGGER.error(f"Video Tools failed: {err}")
        return media_file


task_events = {}


async def show_vtools_task_menu(client, message):
    from asyncio import Event, wait_for
    from ... import user_data
    from ..telegram_helper.message_utils import sendMessage, deleteMessage

    user_id = message.from_user.id
    user_dict = user_data.get(user_id, {})
    event = Event()
    task_events[user_id] = {
        'event': event,
        'proceed': False,
        'vtools': dict(user_dict.get('vtools', {}))
    }

    text = get_vtools_text(user_dict) + "\n\n<i>Configure Video Tools and click Done:</i>"
    kb = build_vtools_keyboard(user_id, user_dict, is_task=True)
    msg = await sendMessage(message, text, kb)
    try:
        await wait_for(event.wait(), timeout=120)
    except Exception:
        pass
    finally:
        await deleteMessage(msg)

    data = task_events.pop(user_id, None)
    if data and data.get('proceed'):
        return True, data.get('vtools')
    return False, None
