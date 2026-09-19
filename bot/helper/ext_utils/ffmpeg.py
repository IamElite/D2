from os import path as os_path, replace as os_replace
import json
import logging
from re import sub as re_sub, search as re_search, IGNORECASE as re_IGNORECASE
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


class SafeTagDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"


def extract_media_tags(filename: str, size: str = '') -> dict:
    name, _ = os_path.splitext(filename)
    season_match = re_search(r'\b(?:S|Season)[.\-_\s]*(\d{1,2})\b', name, re_IGNORECASE)
    season = season_match.group(1).zfill(2) if season_match else ''
    episode_match = re_search(r'\b(?:E|EP|Episode)[.\-_\s]*(\d{1,4})\b', name, re_IGNORECASE)
    episode = episode_match.group(1).zfill(2) if episode_match else ''
    quality_match = re_search(r'(480p|720p|1080p|1440p|2160p|4K)', name, re_IGNORECASE)
    quality = quality_match.group(1) if quality_match else ''
    codec_match = re_search(r'(x264|x265|HEVC|AV1|H264|H265|10bit|10Bit|AVC)', name, re_IGNORECASE)
    codec = codec_match.group(1) if codec_match else ''
    audio_match = re_search(r'(Dual[\s\.\-]?Audio|Multi[\s\.\-]?Audio|Hindi|English|Tamil|Telugu|Malayalam|Kannada|Bengali)', name, re_IGNORECASE)
    audio = audio_match.group(1).title().replace('.', ' ') if audio_match else ''
    sub_match = re_search(r'(ESub|HC-ENG|MSub|Multi[\s\-]?Sub|Subbed)', name, re_IGNORECASE)
    sub = sub_match.group(1) if sub_match else ''
    clean_title = re_sub(r'\[.*?\]|\(.*?\)', '', name)
    clean_title = re_sub(r'(\s|-|\.)+', ' ', clean_title).strip()
    noise_pattern = r'(\b(?:S|Season)[.\-_\s]*\d{1,2}\b|\b(?:E|EP|Episode)[.\-_\s]*\d{1,4}\b|480p|720p|1080p|1440p|2160p|4K|x264|x265|HEVC|AV1|H264|H265|10bit|10Bit|AVC|BluRay|WEB-DL|WEBRip|HDRip|HDTV|Dual[\s\.\-]?Audio|Multi[\s\.\-]?Audio|Hindi|English|Tamil|Telugu|Malayalam|Kannada|Bengali|ESub|HC-ENG|MSub|Multi[\s\-]?Sub|Subbed|Audio|Dual)'
    clean_title = re_sub(noise_pattern, '', clean_title, flags=re_IGNORECASE)
    clean_title = re_sub(r'\s+', ' ', clean_title).strip()
    return {
        'title': clean_title or name,
        'movie_name': clean_title or name,
        'moviename': clean_title or name,
        'season': season,
        'episode': episode,
        'quality': quality,
        'codec': codec,
        'audio': audio,
        'sub': sub,
        'size': size or '',
        'language': audio,
    }


def apply_dynamic_tags(val: str, tags: dict) -> str:
    if not val or not isinstance(val, str) or '{' not in val:
        return val
    try:
        res = val.format_map(SafeTagDict(tags))
        if not tags.get('season') and not tags.get('episode'):
            res = res.replace('SE', '').replace('S E', '')
        elif not tags.get('season') and tags.get('episode'):
            res = res.replace('SE', 'E')
        return re_sub(r'\s+', ' ', res).strip()
    except Exception:
        return val


def parse_meta_overlay(metadata: str, basenameX: str = '', tags: dict = None) -> dict:
    overlay = {}
    if metadata and ':' in metadata:
        for pair in metadata.split('|'):
            if ':' in pair:
                k, v = pair.split(':', 1)
                val = v.strip()
                if tags:
                    val = apply_dynamic_tags(val, tags)
                overlay[k.strip().lower()] = val
    elif metadata:
        val = metadata
        if tags:
            val = apply_dynamic_tags(val, tags)
        overlay['title'] = val
    return overlay


async def probe_tag_args(path, overlay=None, md_streams=None):
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
    movie_val = overlay.get('movie name') or overlay.get('moviename') or overlay.get('movie') or overlay.get('title')
    has_explicit_movie = bool(overlay.get('movie name') or overlay.get('moviename') or overlay.get('movie'))
    stream_title_override = overlay.get('title') if has_explicit_movie else None
    stream_meta = {}
    for uk, uv in overlay.items():
        if uk.startswith('__') or not uv:
            continue
        for sname in ('video', 'audio', 'subtitle'):
            if uk.startswith(sname + ' '):
                stream_meta.setdefault(sname, {})[uk[len(sname) + 1:]] = uv
                break
            elif uk == sname:
                stream_meta.setdefault(sname, {})['title'] = uv
                break
    has_user_meta = any(not k.startswith('__') and v for k, v in overlay.items())
    orig_fmt = dict((data.get('format') or {}).get('tags') or {})
    fmt = dict(orig_fmt)
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
    if movie_val:
        fmt['title'] = movie_val
    for uk, uv in overlay.items():
        if uk.startswith('__') or uk in key_map or uk.split(' ', 1)[0] in ('video', 'audio', 'subtitle') or uk in ('movie name', 'moviename', 'movie'):
            continue
        if uv:
            fmt[uk] = uv
    if has_user_meta:
        ukeys = {key_map.get(uk, uk).lower() for uk in overlay if not uk.startswith('__') and overlay.get(uk)}
        if has_explicit_movie:
            ukeys.add('title')
        for k in list(orig_fmt):
            kl = str(k).lower()
            if kl in _TAG_SKIP or kl in ukeys or kl.replace('_', ' ') in ukeys:
                continue
            args.extend(['-metadata', f'{k}='])
            fmt.pop(k, None)
    for k, v in fmt.items():
        if str(k).lower() in _TAG_SKIP or v is None or v == '':
            continue
        args.extend(['-metadata', f'{k}={v}'])
    active_streams = [s.lower() for s in (md_streams or [])]
    vi = ai = si = 0
    for st in data.get('streams') or []:
        tags = dict(st.get('tags') or {})
        ctype = st.get('codec_type')
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
        if purge_streams:
            tags.pop('title', None)
            if custom_st[0] and ctype == 'video':
                tags['title'] = custom_st[0]
            if custom_st[1] and ctype == 'audio':
                tags['title'] = custom_st[1]
        if ctype in active_streams:
            for k, v in fmt.items():
                if str(k).lower() not in _TAG_SKIP and str(k).lower() != 'title' and v:
                    tags[k] = v
            if stream_title_override:
                tags['title'] = stream_title_override
        for stk, stv in stream_meta.get(ctype, {}).items():
            tags[stk] = stv
        if purge_streams and 'title' not in tags:
            args.extend([f'-metadata:s:{pref}:{idx}', 'title='])
        for k, v in tags.items():
            if str(k).lower() in _TAG_SKIP or v is None or v == '':
                continue
            args.extend([f'-metadata:s:{pref}:{idx}', f'{k}={v}'])
    return args


_MUX_PRIORITY = ('mp4', 'matroska', 'webm', 'mov', 'mpegts', 'avi', 'flv', 'asf', 'ogg', 'wav', 'mp3', 'aac', 'flac')
_MP4_FMT_KEYS = {'title', 'artist', 'album', 'composer', 'genre', 'copyright', 'comment',
                 'date', 'description', 'lyrics', 'encoder', 'grouping'}
_MP4_EXTS = ('.mp4', '.m4v', '.mov', '.m4a')

async def media_muxer(path):
    out, _, _ = await cmd_exec(['ffprobe', '-v', 'error', '-show_entries', 'format=format_name',
                                '-of', 'default=nw=1:nk=1', path])
    tokens = {t.strip().lower() for t in (out or '').split(',') if t.strip()}
    for name in _MUX_PRIORITY:
        if name in tokens:
            return name
    return None


async def edit_metadata(listener, base_dir: str, media_file: str, outfile: str, metadata: str = '', stream_titles: str = '', md_streams: list = None):
    file_name = os_path.basename(media_file)
    basename = os_path.splitext(file_name)[0]
    basenameX = re_sub(r'www\S+', '', basename)
    basenameX = re_sub(r'(^\s*-\s*|(\s*-\s*){2,})', '', basenameX)

    size_str = getattr(listener, 'size', '') or ''
    tags = extract_media_tags(file_name, size=size_str)
    overlay = parse_meta_overlay(metadata, basenameX, tags=tags)
    if stream_titles:
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
        mux = await media_muxer(media_file)
        if not mux:
            LOGGER.info(f'Metadata skipped (not media): {media_file}')
            return None
        outfile += '.mkv'
    inplace = os_path.abspath(outfile) == os_path.abspath(media_file)
    if inplace:
        outfile += '.meta' + os_path.splitext(media_file)[1].lower()
    if md_streams is None and listener and hasattr(listener, 'user_dict'):
        md_streams = listener.user_dict.get('md_streams', [])
    tag_args = await probe_tag_args(media_file, overlay, md_streams)
    cmd = [bot_cache['pkgs'][2], '-nostdin', '-threads', '1', '-y', '-hide_banner', '-loglevel', 'error',
           '-i', media_file, '-map', '0', '-c', 'copy']
    if os_path.splitext(outfile)[1].lower() in _MP4_EXTS:
        cmd.extend(['-movflags', 'use_metadata_tags'])
    cmd.extend(tag_args)
    cmd.append(outfile)

    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()

    if code == 0:
        if inplace:
            os_replace(outfile, media_file)
            return media_file
        await clean_target(media_file)
        final_path = os_path.join(base_dir, os_path.basename(outfile))
        if final_path != outfile:
            os_replace(outfile, final_path)
        listener.seed = False
        return final_path
    else:
        if os_path.abspath(outfile) != os_path.abspath(media_file):
            await clean_target(outfile)
        LOGGER.error('%s. Changing metadata failed, Path %s', (await listener.suproc.stderr.read()).decode(errors='ignore'), media_file)
        return None


async def edit_attachment(listener, base_dir: str, media_file: str, outfile: str, attachment: str = ''):
    file_name = os_path.basename(media_file)

    file_ext = os_path.splitext(file_name)[-1].lower()
    attachment_ext = attachment.split(".")[-1].lower()
    if file_ext == '.mkv':
        omg = "cover"
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
    elif file_ext == '.mp4':
        cmd = [
            bot_cache['pkgs'][2], '-hide_banner', '-loglevel', 'error', '-progress', 'pipe:1',
            '-i', media_file,
            '-i', attachment,
            '-map', '0',
            '-map', '1',
            '-c', 'copy',
            '-disposition:v:1', 'attached_pic',
            outfile
        ]
    else:
        return
    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()
    if code == 0:
        await clean_target(media_file)
        listener.seed = False
        await move(outfile, base_dir)
    else:
        await clean_target(outfile)
        LOGGER.error('%s. Changing failed, Path %s', await listener.suproc.stderr.read().decode(), media_file)
