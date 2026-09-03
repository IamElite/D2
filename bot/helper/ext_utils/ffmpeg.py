from os import path as os_path, replace as os_replace
import json
import logging
from re import sub as re_sub
from aioshutil import move
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from ... import LOGGER, bot_cache
from .fs_utils import clean_target
from .bot_utils import cmd_exec

LOGGER = logging.getLogger(__name__)

_TAG_SKIP = {
    'major_brand', 'minor_version', 'compatible_brands', 'encoder',
    'handler_name', 'vendor_id', 'writing_library', 'encoding_settings',
}


def parse_meta_overlay(metadata: str, basenameX: str = '') -> dict:
    overlay = {}
    if metadata and ':' in metadata:
        for pair in metadata.split('|'):
            if ':' in pair:
                k, v = pair.split(':', 1)
                overlay[k.strip().lower()] = v.strip()
    elif metadata:
        overlay['title'] = metadata
    return overlay


async def probe_tag_args(path, overlay=None):
    """Keep original tags then overlay user keys.

    ffmpeg -c copy on MP4 drops stream Title unless -metadata:s:v:N is set.
    """
    overlay = overlay or {}
    out, _, _ = await cmd_exec([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', path,
    ])
    try:
        data = json.loads(out or '{}')
    except Exception:
        data = {}
    args = []
    purge_streams = bool(overlay.get('__purge_stream_titles__'))
    custom_st = (overlay.get('__stream_title_v__'), overlay.get('__stream_title_a__'))
    fmt = dict((data.get('format') or {}).get('tags') or {})
    key_map = {
        'title': 'title', 'author': 'author', 'artist': 'artist',
        'comment': 'comment', 'copyright': 'copyright', 'publisher': 'publisher',
        'studio': 'studio', 'encoded by': 'encoded_by',
        'custom tag': 'custom_tag', 'dubbed by': 'dubbed_by', 'channel': 'channel',
        'website': 'website', 'source': 'source', 'official site': 'official_site',
    }
    for uk, fk in key_map.items():
        if overlay.get(uk):
            fmt[fk] = overlay[uk]
    # unknown/custom keys pass-through raw (custom-tag buttons) — _TAG_SKIP emit-loop me filter hota
    for uk, uv in overlay.items():
        if uk.startswith('__') or uk in key_map:
            continue
        if uv:
            fmt[uk] = uv
    for k, v in fmt.items():
        if str(k).lower() in _TAG_SKIP or v is None or v == '':
            continue
        args.extend(['-metadata', f'{k}={v}'])
    vi = ai = si = 0
    for st in data.get('streams') or []:
        tags = dict(st.get('tags') or {})
        ctype = st.get('codec_type')
        extra = overlay.get(ctype) or overlay.get('title')
        if purge_streams:
            # purane stream-titles purge (customize-title demand) — naya chahiye to neeche set hota
            tags.pop('title', None)
            if custom_st[0] and ctype == 'video':
                tags['title'] = custom_st[0]
            if custom_st[1] and ctype == 'audio':
                tags['title'] = custom_st[1]
        elif extra:
            tags['title'] = extra
        if ctype == 'video':
            pref, idx = 'v', vi
            vi += 1
        elif ctype == 'audio':
            pref, idx = 'a', ai
            ai += 1
        elif ctype == 'subtitle':
            pref, idx = 's', si
            si += 1
        else:
            continue
        if purge_streams and 'title' not in tags:
            # explicit delete zaroori — arg-missing = purana title INHERIT ho jata
            args.extend([f'-metadata:s:{pref}:{idx}', 'title='])
        for k, v in tags.items():
            if str(k).lower() in _TAG_SKIP or v is None or v == '':
                continue
            args.extend([f'-metadata:s:{pref}:{idx}', f'{k}={v}'])
    return args


_MUX_PRIORITY = ('mp4', 'matroska', 'webm', 'mov', 'mpegts', 'avi', 'flv', 'asf', 'ogg', 'wav', 'mp3', 'aac', 'flac')

async def media_muxer(path):
    """Probe-based container detect — ext-less files ke liye. Non-media → None."""
    out, _, _ = await cmd_exec(['ffprobe', '-v', 'error', '-show_entries', 'format=format_name',
                                '-of', 'default=nw=1:nk=1', path])
    tokens = {t.strip().lower() for t in (out or '').split(',') if t.strip()}
    for name in _MUX_PRIORITY:
        if name in tokens:
            return name
    return None


async def edit_metadata(listener, base_dir: str, media_file: str, outfile: str, metadata: str = '', stream_titles: str = ''):
    file_name = os_path.basename(media_file)
    basename = os_path.splitext(file_name)[0]
    basenameX = re_sub(r'www\S+', '', basename)
    basenameX = re_sub(r'(^\s*-\s*|(\s*-\s*){2,})', '', basenameX)

    overlay = parse_meta_overlay(metadata, basenameX)
    # koi bhi media-format pe smart apply (mp4/mkv/webm/avi/mov/ts...) — ext-gate hata (user demand)
    if stream_titles:
        # format: 'purge' ya 'purge|v:Custom Video|a:Custom Audio'  (kisi bhi format pe)
        overlay['__purge_stream_titles__'] = True
        for part in stream_titles.split('|')[1:]:
            if ':' in part:
                k, v = part.split(':', 1)
                k = k.strip().lower()
                if k in ('v', 'video'):
                    overlay['__stream_title_v__'] = v.strip()
                elif k in ('a', 'audio'):
                    overlay['__stream_title_a__'] = v.strip()
    if not os_path.splitext(outfile)[1]:
        # ext-less file — probe-se media confirm, phir default .mkv (user-spec)
        mux = await media_muxer(media_file)
        if not mux:
            LOGGER.info(f'Metadata skipped (not media): {media_file}')
            return None
        outfile += '.mkv'
    inplace = os_path.abspath(outfile) == os_path.abspath(media_file)
    if inplace:
        # same-file pe ffmpeg reject karta — original-ext tmp me likh ke atomic swap
        outfile += '.meta' + os_path.splitext(media_file)[1].lower()
    tag_args = await probe_tag_args(media_file, overlay)
    cmd = [bot_cache['pkgs'][2], '-y', '-hide_banner', '-loglevel', 'error',
           '-i', media_file, '-map', '0', '-c', 'copy']
    cmd.extend(tag_args)
    cmd.append(outfile)

    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()

    if code == 0:
        if inplace:
            os_replace(outfile, media_file)  # atomic in-place (sync syscall)
            return media_file
        await clean_target(media_file)
        final_path = os_path.join(base_dir, os_path.basename(outfile))
        if final_path != outfile:
            # newDir<->base_dir same-fs: os_replace atomic + overwrite (duplicate-completion safe)
            os_replace(outfile, final_path)
        listener.seed = False
        return final_path
    else:
        if os_path.abspath(outfile) != os_path.abspath(media_file):
            await clean_target(outfile)  # guard: original kabhi delete nahi
        LOGGER.error('%s. Changing metadata failed, Path %s', (await listener.suproc.stderr.read()).decode(errors='ignore'), media_file)
        return None


async def edit_attachment(listener, base_dir: str, media_file: str, outfile: str, attachment: str = ''):
    file_name = os_path.basename(media_file)

    file_ext = os_path.splitext(file_name)[-1].lower()
    if file_ext != '.mkv':
        return

    omg = "photo"
    attachment_ext = attachment.split(".")[-1].lower()
    mime_type = "application/octet-stream"
    if attachment_ext in ["jpg", "jpeg"]:
        mime_type = "image/jpeg"
    elif attachment_ext == "png":
        mime_type = "image/png"

    cmd = [
        bot_cache['pkgs'][2], '-hide_banner', '-loglevel', 'error', '-progress', 'pipe:1',
        '-i', media_file,
        '-attach', attachment,
        '-metadata:s:t', f'mimetype={mime_type}',
        '-metadata:s:t', f'filename={omg}.{attachment_ext}',
        '-disposition:t', 'default',
        '-c', 'copy',
        '-map', '0',
        '-map', '0:t?',
        outfile
    ]
    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()
    if code == 0:
        await clean_target(media_file)
        listener.seed = False
        await move(outfile, base_dir)
    else:
        await clean_target(outfile)
        LOGGER.error('%s. Changing failed, Path %s', await listener.suproc.stderr.read().decode(), media_file)
