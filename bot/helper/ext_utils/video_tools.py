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

# ponytail: drawtext bina fontfile ke kai ffmpeg build me fail hota hai, mila to jodo
_FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    'C:\\Windows\\Fonts\\arial.ttf',
    'C:\\Windows\\Fonts\\DejaVuSans.ttf',
)

_FONT_FILE = next((f for f in _FONT_CANDIDATES if os_path.isfile(f)), None)


def _drawtext_filter(text, coord, fontsize=24, enable=None):
    esc = (text or '').replace(":", "\\:").replace("'", "\\'")
    filt = f"drawtext=text='{esc}':{coord}:fontsize={fontsize}:fontcolor=white@0.8"
    if _FONT_FILE:
        esc_font = _FONT_FILE.replace(":", "\\:").replace("'", "\\'")
        filt += f":fontfile='{esc_font}'"
    if enable:
        filt += f":enable='{enable}'"
    return filt


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
    # ponytail: har toggle ka status dikhao taaki ON karke bhoola na rahe
    trim_val = f"{st('trim')} ({vt.get('trim_start') or '?'}->{vt.get('trim_end') or 'end'})" if vt.get('trim') else st('trim')
    wm_val = f"{st('watermark')} ({vt.get('watermark_text') or 'notytools'})" if vt.get('watermark') else st('watermark')
    hs_val = f"{st('hardsub')} ({'set' if vt.get('hardsub_file') else 'no file'})" if vt.get('hardsub') else st('hardsub')
    conv_val = f"{st('convert')} (->{vt.get('convert_to') or 'mp4'})" if vt.get('convert') else st('convert')
    ext_val = f"{st('extract')} ({vt.get('extract_what') or 'audio'})" if vt.get('extract') else st('extract')
    si_val = f"{st('subintro')} ({vt.get('subintro_text') or 'not set'})" if vt.get('subintro') else st('subintro')

    text = (
        "MERGE (single-file map)\n"
        f"Vid+Vid » {st('vidvid')} | Vid+Aud » {st('vidaud')} | Vid+Sub » {st('vidsub')}\n\n"
        "STREAM\n"
        f"Extract » {ext_val} | Swap » {st('swap')}\n"
        f"Remove » {st('remove')}\n\n"
        f"ENCODE » {st('encode')}\n"
        f"CONVERT » {conv_val}\n"
        f"WATERMARK » {wm_val} | Intro Sub » {si_val}\n"
        f"Hardsub » {hs_val}\n"
        f"Trim » {trim_val}\n"
        f"FFMPEG CMD » {st('ffmpeg_cmd')} | MegaMeta » {st('megametadata')}\n\n"
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
        ],
        [
            InlineKeyboardButton("TrimSet", callback_data=f"userset {user_id} vt_trim"),
            InlineKeyboardButton("WM Text", callback_data=f"userset {user_id} vt_wmark"),
            InlineKeyboardButton("HardsubFile", callback_data=f"userset {user_id} vt_hardsub"),
        ],
        [
            InlineKeyboardButton("ConvertTo", callback_data=f"userset {user_id} vt_convert"),
            InlineKeyboardButton("ExtractOpt", callback_data=f"userset {user_id} vt_extract"),
            InlineKeyboardButton("SubIntroTxt", callback_data=f"userset {user_id} vt_subintro"),
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
    # ponytail: convert target pehle nikalo taaki inplace naam sahi ext le
    target_ext = os_path.splitext(media_file)[1].lower()
    audio_only_out = False
    if vtools.get('convert'):
        conv = str(vtools.get('convert_to') or 'mp4').strip().lower().lstrip('.')
        if conv not in ('mp4', 'mkv', 'webm', 'mov', 'avi', 'flv', 'm4a', 'mp3', 'aac', 'ogg', 'flac', 'wav'):
            conv = 'mp4'
        target_ext = f'.{conv}'
        audio_only_out = conv in ('m4a', 'mp3', 'aac', 'ogg', 'flac', 'wav')
    inplace = os_path.abspath(outfile) == os_path.abspath(media_file)
    if inplace:
        outfile += '.vt' + target_ext
    elif os_path.splitext(outfile)[1].lower() != target_ext:
        outfile = os_path.splitext(outfile)[0] + target_ext

    # ponytail: extract sidecar (audio/subs) alag pre-pass, fail ho to main pass fir bhi chale
    if vtools.get('extract'):
        what = str(vtools.get('extract_what') or 'audio').strip().lower()
        stem = os_path.splitext(os_path.basename(media_file))[0]
        # ponytail: sidecar output ke folder me taaki upload me saath jaye
        side_dir = os_path.dirname(os_path.abspath(outfile)) or base_dir
        if what.startswith('sub'):
            sidecar = os_path.join(side_dir, f"{stem}_sub.srt")
            ext_cmd = [ffmpeg_bin, '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
                       '-i', media_file, '-map', '0:s:0?', '-c', 'copy', sidecar]
        else:
            sidecar = os_path.join(side_dir, f"{stem}_audio.m4a")
            ext_cmd = [ffmpeg_bin, '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
                       '-i', media_file, '-map', '0:a:0?', '-c', 'copy', sidecar]
        try:
            listener.suproc = await create_subprocess_exec(*ext_cmd, stderr=PIPE)
            if await listener.suproc.wait() != 0:
                err = (await listener.suproc.stderr.read()).decode(errors='ignore')
                LOGGER.error(f"Video Tools extract failed: {err}")
        except Exception as e:
            LOGGER.error(f"Video Tools extract error: {e}")

    cmd = [ffmpeg_bin, '-nostdin', '-threads', '2', '-y', '-hide_banner', '-loglevel', 'error']

    if vtools.get('trim') and (t_start := vtools.get('trim_start')):
        cmd.extend(['-ss', str(t_start)])
        if t_end := vtools.get('trim_end'):
            cmd.extend(['-to', str(t_end)])

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
        filters.append(_drawtext_filter(wm_text, coord))
        need_encode = True

    if vtools.get('subintro') and (intro_text := (vtools.get('subintro_text') or '').strip()):
        try:
            intro_dur = max(1, int(vtools.get('subintro_time') or 5))
        except Exception:
            intro_dur = 5
        filters.append(_drawtext_filter(
            intro_text, "x=(w-tw)/2:y=h-th-80", fontsize=28,
            enable=f"between(t,0,{intro_dur})"))
        need_encode = True

    if vtools.get('hardsub') and (sub_file := vtools.get('hardsub_file')):
        if os_path.exists(sub_file):
            esc_sub = sub_file.replace(":", "\\:").replace("'", "\\'")
            filters.append(f"subtitles='{esc_sub}'")
            need_encode = True
        else:
            LOGGER.error(f"Video Tools hardsub file missing: {sub_file}")

    if vtools.get('encode'):
        need_encode = True

    if filters and not audio_only_out:
        cmd.extend(['-vf', ','.join(filters)])

    if audio_only_out:
        cmd.extend(['-map', '0:a:0?', '-c:a', 'aac' if need_encode else 'copy', '-vn'])
    elif need_encode:
        cmd.extend(['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '26', '-c:a', 'copy'])
    else:
        cmd.extend(['-c', 'copy'])

    # ponytail: map priority remove > swap > vid-preset, ek se zyada ON ho to pehla jeete
    if vtools.get('remove'):
        cmd.extend(['-map', '0', '-map', '-0:s?'])
    elif vtools.get('swap'):
        cmd.extend(['-map', '0:v', '-map', '0:a:1?', '-map', '0:a:0?', '-map', '0:s?'])
    elif vtools.get('vidvid'):
        cmd.extend(['-map', '0:v:0?', '-map', '0:a?', '-map', '0:s?'])
    elif vtools.get('vidaud'):
        cmd.extend(['-map', '0:v:0?', '-map', '0:a:0?'])
    elif vtools.get('vidsub'):
        cmd.extend(['-map', '0:v:0?', '-map', '0:a?', '-map', '0:s:0?'])

    if vtools.get('megametadata'):
        base_title = os_path.splitext(os_path.basename(media_file))[0]
        cmd.extend(['-map_metadata', '-1', '-metadata', f'title={base_title}'])

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
