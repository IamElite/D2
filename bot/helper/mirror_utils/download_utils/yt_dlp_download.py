#!/usr/bin/env python3
from os import path as ospath, listdir, environ, walk, replace, remove
from base64 import urlsafe_b64decode, b64decode
from secrets import token_hex
from logging import getLogger
from re import search as re_search, sub as re_sub, compile as re_compile, findall as re_findall, finditer as re_finditer, I as re_I
from json import loads as json_loads
from urllib.parse import urlparse, urljoin

from .... import download_dict_lock, download_dict, non_queued_dl, queue_dict_lock, bot_cache
from ...telegram_helper.message_utils import sendStatusMessage
from ..status_utils.yt_dlp_download_status import YtDlpDownloadStatus
from ..status_utils.queue_status import QueueStatus
from ...ext_utils.bot_utils import sync_to_async, async_to_sync, as_bytes, get_readable_file_size, cmd_exec
from ...ext_utils.task_manager import is_queued, stop_duplicate_check, limit_checker

LOGGER = getLogger(__name__)

_FFMPEG_BIN = None


def _ffmpeg_bin():
    global _FFMPEG_BIN
    if _FFMPEG_BIN:
        return _FFMPEG_BIN
    for cand in (f"/bin/{bot_cache['pkgs'][2]}", bot_cache['pkgs'][2], 'ffmpeg'):
        try:
            _, _, code = async_to_sync(cmd_exec, [cand, '-version'])
            if code == 0:
                _FFMPEG_BIN = cand
                return cand
        except Exception:
            continue
    _FFMPEG_BIN = 'ffmpeg'
    return _FFMPEG_BIN


class _NullYdlLog:
    """Silent logger for import-time YoutubeDL (suppresses the py3.10
    deprecation stderr notice before bot logging is wired up)."""
    @staticmethod
    def debug(*a, **k): pass
    @staticmethod
    def warning(*a, **k): pass
    @staticmethod
    def error(*a, **k): pass


def _detect_impersonate():
    """curl_cffi + yt-dlp impersonation available ho tabhi target — warna None.
    Validation wahi jo YoutubeDL init karta hai (missing dep pe hard-error hota hai,
    isliye blind-set kabhi nahi — /yl CF-403 sites ke liye chrome TLS-fingerprint)."""
    try:
        from curl_cffi import __version__ as _ccv  # noqa: F401
        from yt_dlp import YoutubeDL as _YDL
        from yt_dlp.networking.impersonate import ImpersonateTarget
        target = ImpersonateTarget('chrome')
        with _YDL({'quiet': True, 'no_warnings': True, 'impersonate': target,
                   'logger': _NullYdlLog()}):
            return target
    except Exception:
        return None


_IMPERSONATE_TARGET = _detect_impersonate()
_IMPERSONATE_WARNED = False


def normalize_ydl_link(link):
    """Host-quirks jo extractor nahi sambhalte:
    beeg.com — leading-zero video-id par facts-API 400 deta hai (int-parse);
    zero-strip karke URL do to extractor+API dono khush (E2E-verified)."""
    if link and 'beeg.com/' in link:
        link = re_sub(r'(beeg\.com/-?)0+(\d)', r'\1\2', link)
    return link


def is_generic_title(title):
    """yt-dlp ka fallback: 'Beeg video #123' / 'generic video #..' — asli title na mile to yahi banta hai."""
    return not title or bool(re_search(r'^\w+ video #\d+$', str(title)))


def fix_generic_title(link, title, ydl=None):
    """Scoped repair: sirf generic-fallback titles pe, sirf un hosts jinke paas verified
    asli-title source hai (beeg facts-API: file.data[].cd_column=='sf_name').
    Good titles / non-beeg links bilkul untouched — sab kuch force nahi hota."""
    if not link or 'beeg.com/' not in link or not is_generic_title(title):
        return title
    vid = re_search(r'beeg\.com/-?0*(\d+)', link)
    if not vid:
        return title
    try:
        url = f'https://store.externulls.com/facts/file/{vid.group(1)}'
        if ydl is not None:
            resp = ydl.urlopen(url)
            data = json_loads(resp.read().decode('utf-8', 'ignore'))
        else:
            from urllib.request import urlopen as _uo
            data = json_loads(_uo(url, timeout=15).read().decode('utf-8', 'ignore'))
        for col in (data.get('file') or {}).get('data') or []:
            if col.get('cd_column') == 'sf_name' and col.get('cd_value'):
                clean = str(col['cd_value']).strip()
                if clean and not is_generic_title(clean):
                    return clean
    except Exception:
        pass
    return title


def _content_length_size(url, headers=None):
    """HEAD -> Content-Length. Extractors that do not publish filesize (eporner
    returns None for every format) leave self.__size = 0, which silently skips
    both the size-limit and the disk-space checks -> a multi-GB 4K file only
    fails minutes later with 'No space left on device'. One cheap HEAD request
    gives the real size up front."""
    from urllib.request import Request, urlopen
    try:
        req = Request(url, headers={**(headers or {}), 'Range': 'bytes=0-0'})
        with urlopen(req, timeout=10) as r:
            cr = r.headers.get('Content-Range')
            if cr and '/' in cr:
                return int(cr.rsplit('/', 1)[1])
            cl = r.headers.get('Content-Length')
            return int(cl) if cl else 0
    except Exception:
        return 0


def add_impersonate(opts):
    """opts me impersonation add karo (agar available + user ne khud set na kiya ho)."""
    global _IMPERSONATE_WARNED
    if _IMPERSONATE_TARGET is not None and 'impersonate' not in opts:
        opts = dict(opts)
        opts['impersonate'] = _IMPERSONATE_TARGET
    elif _IMPERSONATE_TARGET is None and not _IMPERSONATE_WARNED:
        # Without curl_cffi there are zero impersonate targets, and extractors that
        # set require_impersonation (Dailymotion m3u8, CF-403 sites) then fail with
        # a misleading "targets are available: firefox" error. Say why, once.
        _IMPERSONATE_WARNED = True
        LOGGER.warning('yt-dlp impersonation UNAVAILABLE (curl_cffi missing) — sites '
                       'needing a TLS fingerprint (Dailymotion, CF-403) will fail. '
                       'A restart is not enough: rebuild the image so requirements.txt '
                       'installs curl-cffi.')
    return opts


class MyLogger:
    # yt-dlp logs a benign "Deprecated Feature: Support for Python version 3.10"
    # notice on old stacks; harmless (works on 3.10) and irrelevant on 3.11+. Drop it.
    _IGNORE_SUBSTR = ('deprecated feature: support for python version',)

    @classmethod
    def _ignored(cls, msg):
        low = str(msg).lower()
        return any(s in low for s in cls._IGNORE_SUBSTR)

    def __init__(self, obj):
        self.obj = obj

    def debug(self, msg):
        if self._ignored(msg):
            return
        # Hack to fix changing extension
        if not self.obj.is_playlist:
            if match := re_search(r'.Merger..Merging formats into..(.*?).$', msg) or \
                    re_search(r'.ExtractAudio..Destination..(.*?)$', msg):
                LOGGER.info(msg)
                newname = match.group(1)
                newname = newname.rsplit("/", 1)[-1]
                self.obj.name = newname

    @classmethod
    def warning(cls, msg):
        if cls._ignored(msg):
            return
        LOGGER.warning(msg)

    @classmethod
    def error(cls, msg):
        if cls._ignored(msg):
            return
        if msg != "ERROR: Cancelling...":
            LOGGER.error(msg)


class YoutubeDLHelper:
    def __init__(self, listener):
        self.__last_downloaded = 0
        self.__size = 0
        self.__progress = 0
        self.__downloaded_bytes = 0
        self.__download_speed = 0
        self.__eta = '-'
        self.__listener = listener
        self.__gid = ''
        self.__is_cancelled = False
        self.__downloading = False
        self.__ext = ''
        self.__extracted_info = None
        self.name = ''
        self.is_playlist = False
        self.playlist_count = 0
        self.opts = {'progress_hooks': [self.__onDownloadProgress],
                     'logger': MyLogger(self),
                     'no_warnings': True,   # drop yt-dlp benign notices (py3.10 deprecation etc.); errors still logged
                     'usenetrc': True,
                     'age_limit': 99,
                     'cookiefile': 'cookies.txt',
                     'allow_multiple_video_streams': True,
                     'allow_multiple_audio_streams': True,
                     'noprogress': True,
                     'allow_playlist_files': True,
                     'overwrites': True,
                     'writethumbnail': True,
                     'trim_file_name': 220,
                     # 3 bounded retries: transient network errors still recover,
                     # a dead/permanent URL fails in seconds instead of minutes.
                     'retries': 3,
                     'fragment_retries': 3,
                     'concurrent_fragment_downloads': int(environ.get('YDLP_CONCURRENT_FRAGMENTS', '4') or 4),
                     'socket_timeout': 30,
                     'ffmpeg_location': f"/bin/{bot_cache['pkgs'][2]}",
                     'retry_sleep_functions': {'http': lambda n: min(2 * n, 10),
                                               'fragment': lambda n: min(2 * n, 10),
                                               'file_access': lambda n: 1,
                                               'extractor': lambda n: min(2 * n, 10)}}
        self.opts = add_impersonate(self.opts)
        try:
            _msg = getattr(listener, 'message', None)
            _text = (getattr(_msg, 'text', None) or getattr(_msg, 'caption', None) or '')
        except Exception:
            _text = ''
        if re_search(r'\bdub(?:s|bed)?\b', _text, re_I):
            _ea = dict(self.opts.get('extractor_args') or {})
            _ea['d2embed'] = {'lang': ['dub']}
            self.opts['extractor_args'] = _ea

    @property
    def download_speed(self):
        return self.__download_speed

    @property
    def downloaded_bytes(self):
        return self.__downloaded_bytes

    @property
    def size(self):
        return self.__size

    @property
    def progress(self):
        return self.__progress

    @property
    def eta(self):
        return self.__eta

    def __onDownloadProgress(self, d):
        self.__downloading = True
        if self.__is_cancelled:
            raise ValueError("Cancelling...")
        if d['status'] == "finished":
            if self.is_playlist:
                self.__last_downloaded = 0
        elif d['status'] == "downloading":
            self.__download_speed = d.get('speed') or 0
            if self.is_playlist:
                downloadedBytes = d.get('downloaded_bytes') or 0
                chunk_size = downloadedBytes - self.__last_downloaded
                self.__last_downloaded = downloadedBytes
                self.__downloaded_bytes += chunk_size
            else:
                if d.get('total_bytes'):
                    self.__size = d['total_bytes'] or 0
                elif d.get('total_bytes_estimate'):
                    self.__size = d['total_bytes_estimate'] or 0
                self.__downloaded_bytes = d.get('downloaded_bytes') or 0
                self.__eta = d.get('eta', '-') or '-'
            try:
                self.__progress = (self.__downloaded_bytes / self.__size) * 100
            except ZeroDivisionError:
                pass

    async def __onDownloadStart(self, from_queue=False):
        async with download_dict_lock:
            download_dict[self.__listener.uid] = YtDlpDownloadStatus(
                self, self.__listener, self.__gid)
        if not from_queue:
            await self.__listener.onDownloadStart()
            await sendStatusMessage(self.__listener.message)

    def __onDownloadError(self, error):
        self.__is_cancelled = True
        async_to_sync(self.__listener.onDownloadError, error)

    def extractMetaData(self, link, name):
        link = normalize_ydl_link(link)
        if link.startswith(('rtmp', 'mms', 'rstp', 'rtmps')):
            self.opts['external_downloader'] = 'ffmpeg'
        from yt_dlp import YoutubeDL, DownloadError  # CJ: lazy
        register_embed_resolver()   # universal embed IE — YoutubeDL init se PEHLE
        with YoutubeDL(self.opts) as ydl:
            try:
                result = ydl.extract_info(link, download=False)
                if result is None:
                    raise ValueError('Info result is None')
                self.__extracted_info = result
                if 'entries' not in result:
                    result['title'] = fix_generic_title(link, result.get('title'), ydl)
            except Exception as e:
                return self.__onDownloadError(str(e))
            if self.is_playlist:
                self.playlist_count = result.get('playlist_count', 0)
            if 'entries' in result:
                self.name = name
                for entry in result['entries']:
                    if not entry:
                        continue
                    if entry.get('ext') == 'unknown_video':
                        entry['ext'] = 'mp4'
                    # as_bytes: extractor may give numeric strings -> '+=' would
                    # raise TypeError (int + str) and kill the whole task
                    _fa = as_bytes(entry.get('filesize_approx'))
                    _fs = as_bytes(entry.get('filesize'))
                    if _fa:
                        self.__size += _fa
                    elif _fs:
                        self.__size += _fs
                    if not self.name:
                        outtmpl_ = '%(series,playlist_title,channel)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d.%(ext)s'
                        self.name, ext = ospath.splitext(
                            ydl.prepare_filename(entry, outtmpl=outtmpl_))
                        if not self.__ext:
                            self.__ext = ext
            else:
                if result.get('ext') == 'unknown_video':
                    result['ext'] = 'mp4'
                outtmpl_ = '%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s'
                realName = ydl.prepare_filename(result, outtmpl=outtmpl_)
                ext = ospath.splitext(realName)[-1]
                self.name = f"{name}{ext}" if name else realName
                if not self.__ext:
                    self.__ext = ext
                self.__size = as_bytes(result.get('filesize')) or as_bytes(result.get('filesize_approx')) or 0

    def __download(self, link, path):
        from yt_dlp import YoutubeDL, DownloadError  # CJ: lazy
        # Fail fast instead of filling the disk: yt-dlp only errors with
        # "No space left on device" after it has already pulled data (a 4K file
        # can be several GB while a dyno disk is ~1 GB).
        need = self.__size
        if not need and self.__extracted_info:
            fmts = self.__extracted_info.get('formats') or []
            req = self.opts.get('format') or ''
            f = next((x for x in fmts if x.get('format_id') == req), None)
            if f:
                need = as_bytes(f.get('filesize') or f.get('filesize_approx')) \
                    or _content_length_size(f.get('url'), f.get('http_headers'))
                if need:
                    self.__size = need
        if need:
            try:
                from shutil import disk_usage
                if disk_usage(path).free <= need:
                    raise DownloadError(
                        f'Not enough free disk space for {get_readable_file_size(need)}.')
            except (OSError, ValueError):
                pass
        try:
            register_embed_resolver()   # idempotent — extractMetaData na chala ho to bhi safe
            with YoutubeDL(self.opts) as ydl:
                try:
                    # extractMetaData() already fetched webpage+JSON for this link.
                    # Feeding that info back avoids a second full extraction per
                    # task (2 HTTP requests saved, measured) and guarantees the
                    # download uses the exact format/URL/headers we showed the user.
                    if self.__extracted_info is not None:
                        ydl.process_ie_result(
                            ydl.sanitize_info(self.__extracted_info, False), download=True)
                    else:
                        ydl.download([link])
                except DownloadError as e:
                    if not self.__is_cancelled:
                        self.__onDownloadError(str(e))
                    return
            if self.is_playlist and (not ospath.exists(path) or len(listdir(path)) == 0):
                self.__onDownloadError(
                    "No video available to download from this playlist. Check logs for more details")
                return
            if self.__is_cancelled:
                raise ValueError
            self.__polish_media(path)
            async_to_sync(self.__listener.onDownloadComplete)
        except ValueError:
            self.__onDownloadError("Download Stopped by User!")

    def __meta_args(self, info, fallback):
        pairs = (
            ('title', info.get('title') or fallback),
            ('artist', info.get('artist') or info.get('uploader') or info.get('channel') or ''),
            ('album_artist', info.get('album_artist') or ''),
            ('album', info.get('album') or ''),
            ('genre', info.get('genre') or ''),
            ('date', info.get('upload_date') or ''),
            ('comment', (info.get('description') or '')[:1000]),
        )
        args = []
        for key, val in pairs:
            val = str(val).strip()
            if val:
                args += ['-metadata', f'{key}={val}']
        return args

    def __polish_file(self, fpath):
        ext = ospath.splitext(fpath)[1].lower()
        if ext in ('', '.json', '.description', '.jpg', '.jpeg', '.png', '.webp', '.gif',
                   '.txt', '.srt', '.vtt', '.ass', '.ssa', '.part', '.ytdl', '.nfo'):
            return
        tmp = f'{fpath}.polish{ext}'
        info = {} if self.is_playlist else (self.__extracted_info or {})
        cmd = [_ffmpeg_bin(), '-nostdin', '-threads', '1', '-y', '-hide_banner',
               '-loglevel', 'error', '-i', fpath, '-map', '0', '-c', 'copy', '-map_metadata:g', '-1']
        cmd += self.__meta_args(info, ospath.splitext(ospath.basename(fpath))[0])
        cmd += ['-map_chapters', '-1', '-map', '-0:t']
        if ext in ('.mp4', '.m4v', '.mov'):
            cmd += ['-movflags', '+faststart+use_metadata_tags']
        cmd.append(tmp)
        try:
            _, err, code = async_to_sync(cmd_exec, cmd)
            if code == 0 and ospath.exists(tmp) and ospath.getsize(tmp) > 0:
                replace(tmp, fpath)
                return
            LOGGER.warning(f'Media polish skipped for {ospath.basename(fpath)}: {str(err)[-200:]}')
        except Exception as e:
            LOGGER.warning(f'Media polish failed for {ospath.basename(fpath)}: {e}')
        if ospath.exists(tmp):
            try:
                remove(tmp)
            except Exception:
                pass

    def __polish_media(self, path):
        if not ospath.isdir(path):
            return
        for cur, _, files in walk(path):
            for f in files:
                self.__polish_file(ospath.join(cur, f))

    async def add_download(self, link, path, name, qual, playlist, options):
        link = normalize_ydl_link(link)
        if playlist:
            self.opts['ignoreerrors'] = True
            self.is_playlist = True

        self.__gid = token_hex(5)
        await self.__onDownloadStart()

        self.opts['postprocessors'] = [{'add_chapters': False, 'add_infojson': 'if_exists', 'add_metadata': True, 'key': 'FFmpegMetadata'}]
        self.opts['postprocessor_args'] = {
            'ffmpegmetadata+ffmpeg': ['-threads', '1', '-map_metadata', '0'],
            'thumbnailsconvertor+ffmpeg': ['-threads', '1'],
        }

        if qual.startswith('ba/b-'):
            audio_info = qual.split('-')
            qual = audio_info[0]
            audio_format = audio_info[1]
            rate = audio_info[2]
            self.opts['postprocessors'].append({'key': 'FFmpegExtractAudio', 'preferredcodec': audio_format, 'preferredquality': rate})
            if audio_format == 'vorbis':
                self.__ext = '.ogg'
            elif audio_format == 'alac':
                self.__ext = '.m4a'
            else:
                self.__ext = f'.{audio_format}'

        self.opts['format'] = qual

        if options:
            self.__set_options(options)

        await sync_to_async(self.extractMetaData, link, name)
        if self.__is_cancelled:
            return

        base_name, ext = ospath.splitext(self.name)
        trim_name = self.name if self.is_playlist else base_name
        if len(trim_name.encode()) > 200:
            self.name = self.name[:200] if self.is_playlist else f'{base_name[:200]}{ext}'
            base_name = ospath.splitext(self.name)[0]

        if self.is_playlist:
            self.opts['outtmpl'] = {'default': f"{path}/{self.name}/%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s",
                                    'thumbnail': f"{path}/yt-dlp-thumb/%(title,fulltitle,alt_title)s%(season_number& |)s%(season_number&S|)s%(season_number|)02d%(episode_number&E|)s%(episode_number|)02d%(height& |)s%(height|)s%(height&p|)s%(fps|)s%(fps&fps|)s%(tbr& |)s%(tbr|)d.%(ext)s"}
        elif any(key in options for key in ['writedescription', 'writeinfojson', 'writeannotations', 'writedesktoplink', 'writewebloclink', 'writeurllink', 'writesubtitles', 'writeautomaticsub']):
            self.opts['outtmpl'] = {'default': f"{path}/{base_name}/{self.name}",
                                    'thumbnail': f"{path}/yt-dlp-thumb/{base_name}.%(ext)s"}
        else:
            self.opts['outtmpl'] = {'default': f"{path}/{self.name}",
                                    'thumbnail': f"{path}/yt-dlp-thumb/{base_name}.%(ext)s"}

        if qual.startswith('ba/b'):
            self.name = f'{base_name}{self.__ext}'

        if self.__listener.isLeech:
            self.opts['postprocessors'].append(
                {'format': 'jpg', 'key': 'FFmpegThumbnailsConvertor', 'when': 'before_dl'})
        # 260904-CO: EmbedThumbnail HATA DIYA — yt-dlp ka thumbnail-embed postprocessor
        # corrupt/bad thumbnail pe (e.g. source ne invalid image di) FATAL error deta hai
        # ("Unable to embed... Invalid data found") aur poora task mar jata hai — jabki
        # video download ho chuka hota hai. Sidecar thumbnail (yt-dlp-thumb/, FFmpeg
        # converter upar) TG preview ke liye already banta+upload hota hai, to embed
        # zero-value pure risk tha.
        if not self.__listener.isLeech:
            self.opts['writethumbnail'] = False

        msg, button = await stop_duplicate_check(self.name, self.__listener)
        if msg:
            await self.__listener.onDownloadError(msg, button)
            return
        if limit_exceeded := await limit_checker(self.__size, self.__listener, isYtdlp=True, isPlayList=self.playlist_count):
            await self.__listener.onDownloadError(limit_exceeded)
            return
        added_to_queue, event = await is_queued(self.__listener.uid)
        if added_to_queue:
            LOGGER.info(f"Added to Queue/Download: {self.name}")
            async with download_dict_lock:
                download_dict[self.__listener.uid] = QueueStatus(
                    self.name, self.__size, self.__gid, self.__listener, 'dl')
            await event.wait()
            async with download_dict_lock:
                if self.__listener.uid not in download_dict:
                    return
            LOGGER.info(f'Start Queued Download from YT_DLP: {self.name}')
            await self.__onDownloadStart(True)
        else:
            LOGGER.info(f'Download with YT_DLP: {self.name}')

        async with queue_dict_lock:
            non_queued_dl.add(self.__listener.uid)

        await sync_to_async(self.__download, link, path)

    async def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.name}")
        if not self.__downloading:
            await self.__listener.onDownloadError("Download Cancelled by User!")

    def __set_options(self, options):
        options = options.split('|')
        for opt in options:
            key, value = map(str.strip, opt.split(':', 1))
            if key == 'format' and value.startswith('ba/b-'):
                continue
            if value.startswith('^'):
                if '.' in value or value == '^inf':
                    value = float(value.split('^', 1)[1])
                else:
                    value = int(value.split('^', 1)[1])
            elif value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            elif value.startswith(('{', '[', '(')) and value.endswith(('}', ']', ')')):
                value = eval(value)

            if key == 'postprocessors':
                if isinstance(value, list):
                    self.opts[key].extend(tuple(value))
                elif isinstance(value, dict):
                    self.opts[key].append(value)
            else:
                self.opts[key] = value


# ============================================================================
#  UNIVERSAL EMBED BYPASS - page -> player-iframe -> embed-host backend
# ============================================================================
# Design: koi bhi site jo ek known video-host embed karti hai, wo yahan se
# automatically chal jaati hai - site ka naam kahin hardcode NAHI hota.
# Flow:  page fetch -> saare player <iframe> (absolute https, ads filtered)
#        -> har embed pe backend-dispatch (host/path pattern) -> yt-dlp formats.
# Multi-server (?tape=N jaise tabs) bhi generic hain: jitne player iframes/tabs
# mile, sab try hote hain; jo fail ho us pe warning + aage badho.
#
# Yeh section deliberately EK file me hai (user requirement) aur deliberately
# module-level pe `yt_dlp` import NAHI karta - InfoExtractor class factory ke
# andar banti hai, warna boot pe 1751 extractor modules load ho jaate.
# (measure kiya: `from yt_dlp.aes import ...` module-level = +29.8 MB RSS,
#  69 submodules; `cryptography` ka AESGCM = +0 KB.)
# AES ke liye `cryptography` use hota hai (requirements.txt me already hai) -
# `yt_dlp.aes` nahi, kyunki wo poora yt_dlp kheench leta hai. Tag layout
# identical hai (blob = ciphertext + 16-byte GCM tag) - parity live-test kiya.


# -- S1. embed-host backend registry (naya host = 1 entry, nayi class nahi) ---
# Naya embed host aaye to sirf yahan ek tuple add karo:
#   (host-regex-compiled, path-regex-compiled, resolver-attribute-name)
# Dono me se koi bhi None ho sakta hai (sirf host, ya sirf path se match).
_ST_HOST_RE = re_compile(r'(?:^|\.)(?:streamtape\.\w+|streamta\.pe|tapecontent\.net)$')
_BYSE_PATH_RE = re_compile(r'/[edfv]/[\w-]+/?$')
_STREAM_EMBED_PATH_RE = re_compile(r'/(?:stream|embed)/.+/(?:sub|dub)/?$')
_EPISODE_URL_RE = re_compile(r'(?:-episode-|/episode-|/ep-\d|-ep-\d|[?&]ep=\d)', re_I)
_STREAM_EMBED_URL_RE = re_compile(r'https?://[^\s"\'<>\\()]+/(?:stream|embed)/[^\s"\'<>\\()]+/(?:sub|dub)(?![\w-])')
_WP_SERVER_ITEM_RE = re_compile(
    r'data-type=["\'](sub|dub)["\'][^>]*?data-server-name=["\']([^"\']*)["\'][^>]*?data-hash=["\']([^"\']+)["\']')
_ZP_KEY_RE = re_compile(r'OBF_KEY\s*=\s*[\'"]([^\'"]{4,64})[\'"]')
_ZP_JS_RE = re_compile(r'[\'"]([^\'"]*(?:obfuscate|core)[^\'"]*\.js)[\'"]')
_MP_KEYPAIR_RE = re_compile(r'"([^"]{8,32})",\w+="([^"]{8,32})",\w+=/\\?/segment/')
_ZP_DEFAULT_KEY = 'otaku-embed-v1'
_MP_DEFAULT_KEY = b"i?LMTAx0Q6,:}50U" + b'\x00' * 16
_MP_DEFAULT_IV = b"W0;27ToaUpl_P%'c"
_SP_LANG_CODES = {
    'english': 'en', 'japanese': 'ja', 'spanish': 'es', 'french': 'fr', 'german': 'de',
    'arabic': 'ar', 'portuguese': 'pt', 'russian': 'ru', 'italian': 'it', 'indonesian': 'id',
    'thai': 'th', 'vietnamese': 'vi', 'polish': 'pl', 'malay': 'ms', 'chinese': 'zh',
}

_EMBED_BACKENDS = (
    # StreamTape family: obfuscated `robotlink` assignment in the embed page.
    ('streamtape', _ST_HOST_RE, None, '_st_formats'),
    # Byse family: GET /api/videos/<code> -> `playback` blob -> AES-256-GCM
    # -> HLS master playlist ya progressive MP4.
    ('byse', None, _BYSE_PATH_RE, '_byse_formats'),
    ('streamlang', None, _STREAM_EMBED_PATH_RE, '_sp_formats'),
    # voe.sx: DDoS-Guard JS challenge -> 403 (curl_cffi chrome impersonate bhi
    # fail). Browser-less bypass namumkin, isliye koi backend nahi - embed
    # warning ke saath skip hota hai aur baaki servers chalte rehte hain.
)

# Protocol-relative (`//host/...`) iframes is site-family pe ADS hote hain -
# live verify kiya: `//a.magsrv.com/iframe.php?...`, `//a.letsjerk.tv/api/spots/`.
# Player iframe hamesha ABSOLUTE `https://` hota hai. Isliye sirf absolute src
# lete hain + yeh host-blocklist lagate hain.
_AD_HOST_BLOCKLIST = (
    'magsrv', 'exoclick', 'juicyads', 'popads', 'tsyndicate', 'adsterra',
    'propellerads', 'clickadu', 'hilltopads', 'trafficjunky', 'a-ads',
)

# Jin hosts pe embed-discovery enabled hai. Default = letsjerk family.
# `YTDL_EMBED_HOSTS="site1.com,site2.com"` se bina code change ke add karo -
# nayi site ka embed-host pehle se supported ho to sirf yeh env var kaafi hai.
_EMBED_DISCOVERY_HOSTS = {'letsjerk.tv', 'letsjerk.com'}

# Server-tab query params jo multi-server pages use karte hain (?tape=1 etc).
# Generic rakha hai taaki doosri sites ke ?server=2 / ?srv=3 bhi pakde jaayein.
_SERVER_TAB_RE = re_compile(r'[?&](?:tape|server|srv|s|v|vno|embed|source)\s*=\s*\d+')
_IFRAME_SRC_RE = re_compile(r'<iframe[^>]+?\bsrc=(["\'])(?P<src>https?://[^"\']+)\1')
_HREF_RE = re_compile(r'href=(["\'])([^"\']+)\1')
_JS_STR_RE = re_compile(r"""(['"])((?:\\.|(?!\1).)*)\1""")
_JS_METH_RE = re_compile(r'[\s)]*\.\s*(substring|substr|slice)\s*\(\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?\)')

# StreamTape ka `robotlink` assignment. Split point HAR PAGE-LOAD pe move karta
# hai (live verify kiya - do loads me do alag shapes):
#   '//streamtape.com/get_video?id=m' + ('xcdQMGg...').substring(2).substring(1)
#   '//streamtape.com/'               + ('xcdget_video?id=m...').substring(2).substring(1)
# Isliye fixed prefix/payload regex kabhi reliable nahi - poora expression
# evaluate karna padta hai. Purana `ideoooolink` naam bhi accept karte hain
_ROBOTLINK_RE = re_compile(
    r"(?:norobotlink|robotlink|captchalink|ideoooolink)(?!\w)[\s'\")\]]*\.innerHTML\s*=\s*(?P<expr>[^\n]+)")

_HEIGHT_WHITELIST_RE = re_compile(r'\b(240|360|480|576|720|1080|1440|2160)p\b')


def embed_enabled_hosts():
    """Discovery ke liye enabled hosts (default + env override)."""
    hosts = set(_EMBED_DISCOVERY_HOSTS)
    extra = environ.get('YTDL_EMBED_HOSTS', '').strip()
    if extra:
        hosts |= {h.strip().lower().lstrip('.') for h in extra.split(',') if h.strip()}
    return {h for h in hosts if h}


def is_embed_discovery_url(url):
    """True = yeh URL humare universal embed-resolver ka candidate hai.
    Routing (bot_utils.is_ytdlp_link / is_ytdlp_supported) isko use karta hai."""
    if not url or not isinstance(url, str):
        return False
    try:
        host = (urlparse(url).hostname or '').lower()
    except Exception:
        return False
    if not host:
        return False
    return any(host == d or host.endswith('.' + d) for d in embed_enabled_hosts())


def eval_js_concat(expr):
    """JS ka chhota subset evaluate karo: string literals `+` se jude hue,
    optional chained `.substring/.substr/.slice` calls ke saath.

    `eval()`/`exec()` use NAHI hota - sirf tokenizer. Garbage input pe
    ValueError (verified), isliye koi code-injection nahi.
    """
    parts, i, n = [], 0, len(expr)
    while i < n:
        if expr[i].isspace() or expr[i] in '+();':
            i += 1
            continue
        m = _JS_STR_RE.match(expr, i)
        if not m:
            # Trailing garbage tolerate karo: real pages pe assignment ke baad
            # `;</script>` jaisa HTML usi line pe ho sakta hai. Agar ab tak ek
            # bhi string-literal mil chuka hai to wahin ruk jao. FAIL-CLOSED:
            # kuch mila hi nahi to ValueError (pehle jaisa).
            if parts:
                break
            raise ValueError(f'unexpected token {expr[i]!r} at {i}')
        value, i = m.group(2), m.end()
        while (method := _JS_METH_RE.match(expr, i)):
            fn, start = method.group(1), int(method.group(2))
            end = int(method.group(3)) if method.group(3) is not None else None
            if fn == 'substr':
                value = value[start:] if end is None else value[start:start + end]
            else:
                value = value[start:] if end is None else value[start:end]
            i = method.end()
        parts.append(value)
    return ''.join(parts)


def streamtape_media_url(page_html):
    m = _ROBOTLINK_RE.search(page_html or '')
    if not m:
        raise ValueError('robotlink assignment not found')
    try:
        media = eval_js_concat(m.group('expr').strip().rstrip(';'))
    except ValueError as e:
        raise ValueError(f'could not evaluate robotlink expression: {e}') from e
    if media.startswith('//'):
        media = 'https:' + media
    elif media.startswith('/'):
        media = 'https:/' + media
    media = re_sub(r'/get_v[a-zA-Z]*ideo\?', '/get_video?', media)
    media = re_sub(r'([?&])id[a-zA-Z]*=', r'\1id=', media)
    if not media.startswith('http'):
        raise ValueError('robotlink did not yield a usable url')
    return media


def base64url_decode(value):
    return urlsafe_b64decode(value + '=' * (-len(value) % 4))


def byse_decrypt_playback(playback, warn=None):
    """Byse-family `playback` blob -> sources dict (AES-256-GCM).

    Key schedule (site ke videoPagesBundle se nikala, decryption se prove kiya):
        version n -> base64url(key_parts[n]) + base64url(key_parts[31 - n])  (1-based)
    Do asli parts chhote (22-char) hote hain; 32-char entries decoys hain.
    Index server-supplied `version` se aata hai, isliye version bump pe code
    change ki zaroorat nahi. LIVE VERIFY: version 9 (260905-T) -> version 5
    (aaj) - parts 5 aur 26, dono exactly 22-char. Schedule abhi bhi sahi.
    """
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except Exception as e:
        if warn:
            warn(f'cryptography unavailable ({e.__class__.__name__}) - playback decrypt skip')
        return None
    parts = playback.get('key_parts') or []
    payload, iv = playback.get('payload'), playback.get('iv')
    if not (parts and payload and iv):
        return None
    version = str(playback.get('version') or '')
    chosen = parts
    if version.isdigit():
        n = int(version)
        idx = [i for i in (n, 31 - n) if 1 <= i <= len(parts)]
        if idx:
            chosen = [parts[i - 1] for i in idx]
    try:
        key = b''.join(base64url_decode(p) for p in chosen if p)
        blob = base64url_decode(payload)
        nonce = base64url_decode(iv)
    except Exception as e:
        if warn:
            warn(f'playback base64 decode failed ({e.__class__.__name__})')
        return None
    if len(key) not in (16, 24, 32) or len(blob) <= 16:
        if warn:
            warn(f'unexpected key/blob size ({len(key)}/{len(blob)})')
        return None
    try:
        return json_loads(AESGCM(key).decrypt(nonce, blob, None).decode())
    except Exception as e:
        if warn:
            warn(f'playback decrypt failed ({e.__class__.__name__})')
        return None


def zp_decode_player_config(blob, key=None):
    for k in (key, _ZP_DEFAULT_KEY):
        if not k:
            continue
        kb = k.encode()
        try:
            raw = b64decode(blob + '=' * (-len(blob) % 4))
            out = bytes(b ^ kb[i % len(kb)] for i, b in enumerate(raw))
            return json_loads(out.decode('utf-8'))
        except Exception:
            continue
    return None


def megaplay_decrypt_source(enc, key=None, iv=None):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception:
        return None
    pairs = []
    if key and iv:
        pairs.append((key, iv))
    pairs.append((_MP_DEFAULT_KEY, _MP_DEFAULT_IV))
    data = enc.replace('-', '+').replace('_', '/')
    data += '=' * (-len(data) % 4)
    for k, v in pairs:
        try:
            raw = b64decode(data)
            dec = Cipher(algorithms.AES(k), modes.CBC(v)).decryptor()
            pt = dec.update(raw) + dec.finalize()
            pad = pt[-1]
            if not 1 <= pad <= 16 or pt[-pad:] != bytes((pad,)) * pad:
                continue
            return json_loads(pt[:-pad].decode('utf-8')).get('file')
        except Exception:
            continue
    return None


def sp_lang_from_url(embed_url):
    path = (urlparse(embed_url).path or '').rstrip('/').lower()
    if path.endswith('/dub'):
        return 'dub'
    if path.endswith('/sub'):
        return 'sub'
    return None


# -- S2. InfoExtractor factory (class LAZY banti hai - boot pe yt_dlp load nahi)
_EMBED_IE_CLASS = None


def _make_embed_ie():
    global _EMBED_IE_CLASS
    if _EMBED_IE_CLASS is not None:
        return _EMBED_IE_CLASS
    from yt_dlp.extractor.common import InfoExtractor
    from yt_dlp.utils import ExtractorError, UnsupportedError, int_or_none, traverse_obj, url_or_none

    class D2EmbedIE(InfoExtractor):
        IE_NAME = 'd2embed'
        # Broad rakha hai; asli gating `suitable()` me hoti hai (host allow-list).
        _VALID_URL = r'https?://.+'
        _WORKING = True
        _AGE_LIMIT = 18

        _TITLE_BRAND_RE = re_compile(r'Letsjerk|Free Full Porn HD Videos|HiAnime|Watch Anime Online', re_I)
        _TITLE_SEP_RE = re_compile(r'\s*[-\u2013\u2014]\s*')

        @classmethod
        def suitable(cls, url):
            """Sirf enabled hosts pe match - warna built-in extractors (YouTube,
            Vimeo, pornhub, ...) aur GenericIE apna kaam karte rehte hain."""
            if is_embed_discovery_url(url):
                return super().suitable(url)
            try:
                up = urlparse(url)
            except Exception:
                return False
            path = up.path or ''
            if _STREAM_EMBED_PATH_RE.search(path) or _EPISODE_URL_RE.search(f'{path}?{up.query or ""}'):
                return super().suitable(url)
            return False

        def _real_extract(self, url):
            video_id = re_sub(r'\W+', '_', urlparse(url).path.strip('/'))[:80] or 'video'
            lang_pref = (self._configuration_arg('lang', ['sub'])[0] or 'sub').lower()
            if lang_pref not in ('sub', 'dub'):
                lang_pref = 'sub'
            direct_embed = bool(_STREAM_EMBED_PATH_RE.search(urlparse(url).path or ''))
            webpage = '' if direct_embed else (self._download_webpage(url, video_id, fatal=False) or '')
            title = self._clean_title(
                self._og_search_title(webpage, default=None)
                or self._html_search_regex(r'<title>([^<]+)', webpage, 'title', default=None)
                or '') or video_id
            thumbnail = self._og_search_thumbnail(webpage, default=None)

            pages = {url: webpage} if webpage else {}
            candidates = []
            if direct_embed:
                candidates.append((1, sp_lang_from_url(url), 'embed', url))
            else:
                for server_no, page_url in enumerate(self._server_pages(url, webpage), 1):
                    html = pages.get(page_url)
                    if html is None:
                        html = self._download_webpage(
                            page_url, video_id, note=f'Downloading server {server_no} page', fatal=False)
                        if not html:
                            continue
                        pages[page_url] = html
                    for lang, label, embed_url in self._typed_embeds(page_url, html, video_id):
                        if embed_url not in [c[3] for c in candidates]:
                            candidates.append((server_no, lang, label, embed_url))

            def _rank(c):
                if c[1] == lang_pref:
                    return 0
                if c[1] is None:
                    return 1
                return 2
            candidates.sort(key=_rank)

            formats, seen, duration, subtitles = [], set(), None, {}
            chosen = 'unset'
            for server_no, lang, label, embed_url in candidates:
                if chosen != 'unset' and lang != chosen:
                    continue
                note = f'server {server_no} ({label})'
                try:
                    got, meta = self._resolve_embed(embed_url, video_id, note)
                except ExtractorError as e:
                    self.report_warning(f'{note}: skipped - {e.msg}')
                    continue
                except Exception as e:
                    self.report_warning(f'{note}: skipped - {e.__class__.__name__}: {e}')
                    continue
                chosen = lang
                duration = duration or int_or_none(traverse_obj(meta, 'duration_seconds'))
                thumbnail = thumbnail or url_or_none(traverse_obj(meta, 'poster_url'))
                for sub_lang, sub_list in (traverse_obj(meta, 'subtitles') or {}).items():
                    subtitles.setdefault(sub_lang, []).extend(sub_list)
                for fmt in got:
                    key = (re_sub(r'[?#].*$', '', fmt.get('url') or ''),
                           fmt.get('height'), fmt.get('tbr'))
                    if key in seen:
                        continue
                    seen.add(key)
                    if lang:
                        fmt.setdefault('language', 'en' if lang == 'dub' else 'ja')
                    fmt.setdefault('format_note', f'{note} {lang.upper()}' if lang else note)
                    formats.append(fmt)

            if not formats:
                if not candidates:
                    raise UnsupportedError(url)
                raise ExtractorError('No working streaming server found on this page', expected=True)
            return {
                'id': video_id,
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'age_limit': self._AGE_LIMIT,
                'formats': formats,
                'subtitles': subtitles or None,
            }

        def _clean_title(self, raw):
            """Right-to-left trailing dash-segments hatao jab tak branding mile;
            pehla non-branding segment milte hi ruk jao (title ka hissa safe).

            Purana plugin regex (`\\s+-\\s+.*Letsjerk.*$`) GREEDY tha aur pehle
            ' - ' pe cut kar deta tha -> 'Ava Addams - NEW BG Fucks Her Number 1
            Fan - Free Full Porn HD Videos - Letsjerk.com' se sirf 'Ava Addams'
            bachta tha (har letsjerk file ka naam adhoora tha). Regex se yeh
            theek bhi nahi ho sakta: `[^-]*` dash-cross nahi karta, to match
            galat jagah anchor hota hai (live debug karke dekha, start=10).
            """
            raw = (raw or '').strip()
            if not raw:
                return ''
            raw = re_sub(r'\s*Watch All Episodes.*$', '', raw, flags=re_I).strip()
            parts = self._TITLE_SEP_RE.split(raw)
            while len(parts) > 1 and self._TITLE_BRAND_RE.search(parts[-1]):
                parts.pop()
            parts = [p.strip() for p in parts if p.strip()]
            return ' - '.join(parts) if len(parts) > 1 else (parts[0] if parts else raw)

        def _server_pages(self, url, webpage):
            """Har multi-server tab (?tape=N / ?server=N / ...), page order me,
            current page pehle, koi duplicate nahi. Same-host links only."""
            base_host = (urlparse(url).hostname or '').lower()
            found, pages = [], []
            for href in re_findall(_HREF_RE, webpage):
                link = href[1].replace('&amp;', '&')
                if not _SERVER_TAB_RE.search(link.lower()):
                    continue
                link_host = (urlparse(link).hostname or '').lower()
                if link_host and link_host != base_host \
                        and not link_host.endswith('.' + base_host):
                    continue
                if link not in found:
                    found.append(link)
            base = re_sub(r'[?#].*$', '', url).rstrip('/')
            if not any(re_sub(r'[?#].*$', '', p).rstrip('/') == base for p in found):
                found.insert(0, url)
            for page_url in found:
                if page_url not in pages:
                    pages.append(page_url)
            return pages

        def _player_embeds(self, webpage):
            """Player iframes only - absolute http(s) src + non-ad host."""
            out = []
            for m in _IFRAME_SRC_RE.finditer(webpage or ''):
                src = m.group('src').replace('&amp;', '&')
                host = (urlparse(src).netloc or '').lower()
                if not host or any(x in host for x in _AD_HOST_BLOCKLIST):
                    continue
                if not url_or_none(src):
                    continue
                if src not in out:
                    out.append(src)
            return out

        def _typed_embeds(self, page_url, webpage, video_id):
            out = []

            def add(lang, label, u):
                u = url_or_none((u or '').replace('\\/', '/'))
                if u and u not in [o[2] for o in out]:
                    out.append((lang, label, u))

            text = (webpage or '').replace('\\/', '/')
            rest = re_search(r'"rest_url"\s*:\s*"([^"]+)"', text)
            post = re_search(r'wp-json/wp/v2/posts/(\d+)', text)
            if rest and post:
                api = rest.group(1).rstrip('/') + f'/episode/servers?episodeId={post.group(1)}'
                data = self._download_json(
                    api, video_id, note='Downloading server list', fatal=False,
                    headers={'Referer': page_url, 'X-Requested-With': 'XMLHttpRequest'})
                for m in _WP_SERVER_ITEM_RE.finditer(traverse_obj(data, ('html', {str})) or ''):
                    try:
                        embed = b64decode(m.group(3)).decode('utf-8')
                    except Exception:
                        continue
                    add(m.group(1), m.group(2) or m.group(1).upper(), embed)
            for m in _STREAM_EMBED_URL_RE.finditer(text):
                u = m.group(0)
                add(sp_lang_from_url(u), (urlparse(u).netloc or '').lower(), u)
            for e in self._player_embeds(webpage):
                add(None, (urlparse(e).netloc or '').lower(), e)
            for idx, (lang, label, u) in enumerate(out):
                if lang is None and sp_lang_from_url(u):
                    out[idx] = (sp_lang_from_url(u), label, u)
            return out

        def _zp_key(self, page, origin, video_id):
            js_urls = []
            for m in re_finditer(r'<script[^>]+src="([^"]+)"', page or ''):
                src = m.group(1)
                if any(x in src.lower() for x in ('player', 'obfuscate', 'core')):
                    js_urls.append(urljoin(origin + '/', src))
            for js_url in js_urls[:3]:
                js = self._download_webpage(js_url, video_id, note='Downloading player script', fatal=False) or ''
                m = _ZP_KEY_RE.search(js)
                if m:
                    return m.group(1)
                for sub in _ZP_JS_RE.findall(js)[:3]:
                    sub_url = urljoin(js_url, sub)
                    js2 = self._download_webpage(sub_url, video_id, note='Downloading player module', fatal=False) or ''
                    m2 = _ZP_KEY_RE.search(js2)
                    if m2:
                        return m2.group(1)
            return None

        def _sp_formats(self, embed_url, video_id, note):
            up = urlparse(embed_url)
            origin = f'{up.scheme}://{up.netloc}'
            headers = {'Referer': origin + '/'}
            lang = sp_lang_from_url(embed_url)
            page = (self._download_webpage(embed_url, video_id, note=f'{note}: embed page', fatal=False) or '')
            page = page.replace('\\/', '/')
            blob = re_search(r'window\.__P="([^"]+)"', page)
            if blob:
                cfg = zp_decode_player_config(blob.group(1), self._zp_key(page, origin, video_id))
                src = url_or_none(traverse_obj(cfg, ('src', {str})))
                if not src:
                    raise ExtractorError('unable to decode player config', expected=True)
                subs = {}
                for t in traverse_obj(cfg, ('subtitles', lambda _, v: url_or_none(v.get('src')))) or []:
                    lg = (t.get('lang') or '').strip().lower()
                    lg = _SP_LANG_CODES.get(lg, lg if re_search(r'^[a-z]{2}$', lg) else 'und')
                    subs.setdefault(lg, []).append({'url': t['src'], 'http_headers': dict(headers)})
                fmts = self._extract_m3u8_formats(
                    src, video_id, 'mp4', m3u8_id=f'sp-{lang or "hls"}', headers=headers, note=f'{note}: hls')
                for f in fmts:
                    f.setdefault('http_headers', {}).update(headers)
                return fmts, {'subtitles': subs}
            data_id = re_search(r'data-id=["\'](\d+)', page)
            data_id = data_id.group(1) if data_id else next(
                (p for p in reversed((up.path or '').split('/')) if p.isdigit()), None)
            if not data_id:
                raise ExtractorError('no known player signature on embed page', expected=True)
            data = self._download_json(
                f'{origin}/stream/getSources?id={data_id}', video_id, note=f'{note}: sources', fatal=False,
                headers={'Referer': embed_url, 'X-Requested-With': 'XMLHttpRequest'})
            src = url_or_none(traverse_obj(data, ('sources', 'file'))) \
                or url_or_none(traverse_obj(data, ('sources', 0, 'file')))
            if not src and traverse_obj(data, ('enc', {str})):
                key = iv = None
                js = re_search(r'<script[^>]+src="([^"]*newclient[^"]*)"', page)
                if js:
                    js_text = self._download_webpage(
                        urljoin(origin + '/', js.group(1)), video_id, note=f'{note}: client script', fatal=False) or ''
                    km = _MP_KEYPAIR_RE.search(js_text)
                    if km:
                        key = km.group(1).encode()[:32].ljust(32, b'\x00')
                        iv = km.group(2).encode()[:16].ljust(16, b'\x00')
                src = url_or_none(megaplay_decrypt_source(data['enc'], key, iv))
            if not src:
                raise ExtractorError('source api returned no stream', expected=True)
            subs = {}
            for t in traverse_obj(data, ('tracks', lambda _, v: url_or_none(v.get('file')))) or []:
                if t.get('kind') not in (None, 'captions', 'subtitles'):
                    continue
                lg = (t.get('label') or '').strip().lower()
                lg = _SP_LANG_CODES.get(lg, lg if re_search(r'^[a-z]{2}$', lg) else 'und')
                subs.setdefault(lg, []).append({'url': t['file'], 'http_headers': dict(headers)})
            fmts = self._extract_m3u8_formats(
                src, video_id, 'mp4', m3u8_id=f'sp-{lang or "hls"}', headers=headers, note=f'{note}: hls')
            for f in fmts:
                f.setdefault('http_headers', {}).update(headers)
            return fmts, {'subtitles': subs}

        def _resolve_embed(self, embed_url, video_id, note):
            """Backend dispatch - host/path pattern se, site ke naam se nahi."""
            up = urlparse(embed_url)
            host = (up.netloc or '').lower()
            path = up.path or ''
            for _name, host_re, path_re, resolver in _EMBED_BACKENDS:
                if host_re is not None and not host_re.search(host):
                    continue
                if path_re is not None and not path_re.search(path):
                    continue
                return getattr(self, resolver)(embed_url, video_id, note)
            raise ExtractorError(f'no backend for embed host {host}', expected=True)

        # ---- backends ----
        def _st_formats(self, embed_url, video_id, note):
            page = self._download_webpage(embed_url, video_id, note=f'{note}: embed page')
            try:
                media_url = streamtape_media_url(page)
            except ValueError as e:
                raise ExtractorError(str(e))
            fmt = {
                'url': media_url,
                'format_id': 'streamtape',
                'ext': 'mp4',
                'http_headers': {'Referer': 'https://streamtape.com/'},
            }
            # Ek 2-byte request real filesize + resolution de deti hai (embed page
            # inko expose nahi karta). Failure non-fatal hai.
            try:
                resp = self._request_webpage(
                    media_url, video_id, note=f'{note}: probing',
                    headers={'Range': 'bytes=0-1', 'Referer': 'https://streamtape.com/'})
                total = int_or_none(self._search_regex(
                    r'/(\d+)\s*$', resp.headers.get('Content-Range') or '', None, default=None))
                fmt['filesize'] = total or int_or_none(resp.headers.get('Content-Length'))
                hm = _HEIGHT_WHITELIST_RE.search(urlparse(resp.url).path)
                if hm and (height := int_or_none(hm.group(1))):
                    fmt['height'] = height
                resp.close()
            except Exception as e:
                self.report_warning(f'{note}: probe failed ({e.__class__.__name__})')
            return [fmt], {}

        def _byse_formats(self, embed_url, video_id, note):
            up = urlparse(embed_url)
            code = self._search_regex(r'/([A-Za-z0-9_-]+)/?$', up.path, 'video code')
            origin = f'{up.scheme}://{up.netloc}'
            data = self._download_json(
                f'{origin}/api/videos/{code}', video_id, note=f'{note}: playback api',
                headers={'Referer': embed_url})

            payload = traverse_obj(data, ('playback', {dict}))
            sources = None
            if payload:
                decrypted = byse_decrypt_playback(payload, warn=self.report_warning)
                sources = traverse_obj(decrypted, 'sources') if decrypted else None
            if sources is None:
                sources = traverse_obj(data, 'sources')
            if not sources:
                raise ExtractorError('no sources in playback payload')

            headers = {'Referer': origin}
            formats = []
            for src in sources:
                media_url = url_or_none(traverse_obj(src, 'url'))
                if not media_url:
                    continue
                mime = (traverse_obj(src, 'mime_type') or '').lower()
                height = int_or_none(traverse_obj(src, 'height'))
                tbr = int_or_none(traverse_obj(src, 'bitrate_kbps'))
                filesize = int_or_none(traverse_obj(src, 'size_bytes'))
                if 'mpegurl' in mime or media_url.split('?')[0].endswith(('.m3u8', '.m3u')):
                    # API ka `label`/`height` JHOOT bol sakta hai - live dekha:
                    # API ne 1080p bola, actual playlist se height 720 aayi.
                    # Isliye real height playlist se aati hai, API label se nahi.
                    got = self._extract_m3u8_formats(
                        media_url, video_id, 'mp4', m3u8_id=f'byse-{height or "hls"}',
                        headers=headers, fatal=False, note=f'{note}: hls')
                    for f in got:
                        f.setdefault('filesize', filesize)
                    formats.extend(got)
                else:
                    formats.append({
                        'url': media_url,
                        'format_id': f'byse-{height or "http"}',
                        'ext': 'mp4',
                        'height': height,
                        'tbr': tbr,
                        'filesize': filesize,
                        'http_headers': headers,
                    })
            if not formats:
                raise ExtractorError('playback sources had no usable media')
            return formats, data

    _EMBED_IE_CLASS = D2EmbedIE
    return D2EmbedIE


# -- S3. registration (yt-dlp ke andar, GenericIE se PEHLE) --------------------
_EMBED_REGISTERED = False


def register_embed_resolver():
    """Universal embed IE ko yt-dlp me inject karo. Boot-safe + idempotent.

    Do zaroori baatein - DONO live-test se pakdi gayi, guess se nahi:
      1. Pehle `gen_extractor_classes()` se extractors dict POPULATE karo. Warna
         `extractor/extractors.py` ka `setdefault()` loop humare baad chalega aur
         GenericIE humse PEHLE insert ho jaayega. Order matter karta hai -
         `YoutubeDL.extract_info()` pehla `ie.suitable(url)` match use karta hai.
         (Pehla attempt bina populate kiye = 1751 extractors ud gaye, total 2.)
      2. Dict key = CLASS name (`D2EmbedIE`), kyunki `get_info_extractor()`
         `f'{ie_key}IE'` lookup karta hai. Galat key -> KeyError at extract time.

    Fail hone pe bot NAHI rukega - sirf warning. (brain.md 260902-BE: ek chhoti
    si boot-time galti se poora bot down ho gaya tha, isliye yeh guard zaroori.)
    """
    global _EMBED_REGISTERED
    if _EMBED_REGISTERED:
        return True
    try:
        from yt_dlp.extractor import gen_extractor_classes
        gen_extractor_classes()                       # lazy dict bharo (zaroori)
        from yt_dlp.globals import extractors as _extractors
        cls = _make_embed_ie()
        key = cls.__name__                            # 'D2EmbedIE'
        if key not in _extractors.value:
            generic = _extractors.value.get('GenericIE')
            new = {k: v for k, v in _extractors.value.items() if k != 'GenericIE'}
            new[key] = cls
            if generic is not None:
                new['GenericIE'] = generic            # Generic hamesha LAST (fallback)
            _extractors.value = new
    except Exception as e:
        LOGGER.warning(
            f'embed-resolver register failed ({e.__class__.__name__}: {e}) - '
            f'yt-dlp update ne globals API badla hoga; baaki ytdl kaam karega')
    _EMBED_REGISTERED = True   # retry-spam se bachao (fail ho ya pass)
    return _EMBED_REGISTERED
