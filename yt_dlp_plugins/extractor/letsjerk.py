"""letsjerk.tv — multi-server page extractor and its embed backends.

Backend flow (all of it verified against the live site):

    page  (the site renders exactly ONE player per ?tape=N tab)
      -> player <iframe>            one streaming host per server tab
      -> per-host resolver
           StreamTape : obfuscated `robotlink` assignment in the embed page
           Byse family: GET /api/videos/<code> -> `playback` blob,
                        AES-256-GCM, key = key_parts[version] +
                        key_parts[31 - version] (1-based, base64url).
                        The two real parts are the short ones; the 32-char
                        entries are decoys. Index schedule comes from the
                        server-supplied `version`, so a version bump does
                        not need a code change.
      -> real media (progressive MP4 / HLS master playlist)
      -> yt-dlp formats, one per server, deduplicated

Nothing is pinned to a single page: the ?tape=N tabs, the absolute-https
player iframe, and the two backend families are what the whole site uses.
"""

import base64
import json
import re
from urllib.parse import urlparse

from yt_dlp.aes import aes_gcm_decrypt_and_verify_bytes
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, int_or_none, str_or_none, traverse_obj, url_or_none


def base64url_decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


_JS_STRING_RE = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""")
_JS_METHOD_RE = re.compile(r'[\s)]*\.\s*(substring|substr|slice)\s*\(\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?\)')


def eval_js_concat(expr):
    """Evaluate the small JS subset StreamTape's `robotlink` assignment uses:
    string literals joined with `+`, optionally followed by chained
    .substring/.substr/.slice calls. The split point between the literal parts
    moves between page loads, so the whole expression has to be evaluated
    rather than matched against a fixed shape. No eval()."""
    parts, i, n = [], 0, len(expr)
    while i < n:
        if expr[i].isspace() or expr[i] in '+();':
            i += 1
            continue
        m = _JS_STRING_RE.match(expr, i)
        if not m:
            raise ValueError(f'unexpected token {expr[i]!r} at {i}')
        value, i = m.group(2), m.end()
        while method := _JS_METHOD_RE.match(expr, i):
            fn, start = method.group(1), int(method.group(2))
            end = int(method.group(3)) if method.group(3) is not None else None
            if fn == 'substr':
                value = value[start:] if end is None else value[start:start + end]
            else:
                value = value[start:] if end is None else value[start:end]
            i = method.end()
        parts.append(value)
    return ''.join(parts)


class LetsJerkIE(InfoExtractor):
    IE_NAME = 'letsjerk'
    _VALID_URL = r'https?://(?:www\.)?letsjerk\.tv/(?P<id>[^/?#]+)'
    _WORKING = True
    _AGE_LIMIT = 18

    _TAPE_PARAM = 'tape'
    _TITLE_SUFFIX_RE = re.compile(r'\s+-\s+.*Letsjerk.*$', re.I)
    _IFRAME_RE = re.compile(r'<iframe[^>]+?\bsrc=(["\'])(?P<src>https?://[^"\']+)\1', re.I)

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        og_title = self._og_search_title(webpage, default=None) or ''
        title = self._TITLE_SUFFIX_RE.sub('', og_title).strip() or self._html_search_regex(
            r'<title>([^<]+)', webpage, 'title', default=None) or video_id
        thumbnail = self._og_search_thumbnail(webpage, default=None)

        pages = {url: webpage}
        formats, seen, duration = [], set(), None

        for server_no, page_url in enumerate(self._server_pages(url, webpage), 1):
            html = pages.get(page_url)
            if html is None:
                html = self._download_webpage(
                    page_url, video_id, note=f'Downloading server {server_no} page', fatal=False)
                if not html:
                    continue
                pages[page_url] = html

            for embed_url in self._player_embeds(html):
                host = urlparse(embed_url).netloc.lower()
                note = f'server {server_no} ({host})'
                try:
                    got, meta = self._resolve_embed(embed_url, video_id, note)
                except ExtractorError as e:
                    self.report_warning(f'{note}: skipped — {e.msg}')
                    continue
                except Exception as e:
                    self.report_warning(f'{note}: skipped — {e.__class__.__name__}: {e}')
                    continue
                duration = duration or int_or_none(traverse_obj(meta, 'duration_seconds'))
                thumbnail = thumbnail or url_or_none(traverse_obj(meta, 'poster_url'))
                for fmt in got:
                    key = (re.sub(r'[?#].*$', '', fmt.get('url') or ''), fmt.get('height'), fmt.get('tbr'))
                    if key in seen:
                        continue
                    seen.add(key)
                    fmt.setdefault('format_note', note)
                    formats.append(fmt)

        if not formats:
            raise ExtractorError('No working streaming server found on this page', expected=True)

        return {
            'id': video_id,
            'title': title,
            'thumbnail': thumbnail,
            'duration': duration,
            'age_limit': self._AGE_LIMIT,
            'formats': formats,
        }

    def _server_pages(self, url, webpage):
        """Every ?tape=N tab, in page order, current page first, no duplicates."""
        found, pages = [], []
        for href in re.findall(r'href=(["\'])([^"\']+)\1', webpage):
            link = href[1].replace('&amp;', '&')
            if f'{self._TAPE_PARAM}=' not in link or 'letsjerk.' not in link.lower():
                continue
            if link not in found:
                found.append(link)
        base = re.sub(r'[?#].*$', '', url).rstrip('/')
        if not any(re.sub(r'[?#].*$', '', p).rstrip('/') == base for p in found):
            found.insert(0, url)
        for page_url in found:
            if page_url not in pages:
                pages.append(page_url)
        return pages

    def _player_embeds(self, webpage):
        """Player iframes only. Ad iframes on this site are protocol-relative
        (`//a.magsrv.com/...`, `//a.letsjerk.tv/api/spots/...`) so requiring an
        absolute http(s) src plus a non-letsjerk host excludes them."""
        out = []
        for m in self._IFRAME_RE.finditer(webpage):
            src = m.group('src').replace('&amp;', '&')
            host = urlparse(src).netloc.lower()
            if not host or 'letsjerk.' in host or 'magsrv' in host:
                continue
            if not url_or_none(src):
                continue
            if src not in out:
                out.append(src)
        return out

    def _resolve_embed(self, embed_url, video_id, note):
        host = urlparse(embed_url).netloc.lower()
        if 'streamtape' in host or 'streamta.pe' in host:
            return self._streamtape_formats(embed_url, video_id, note), {}
        if re.search(r'/[edfv]/[\w-]+/?$', urlparse(embed_url).path):
            return self._byse_formats(embed_url, video_id, note)
        raise ExtractorError(f'unsupported embed host {host}', expected=True)

    # ---------------------------------------------------------------- backends

    def _streamtape_formats(self, embed_url, video_id, note):
        page = self._download_webpage(embed_url, video_id, note=f'{note}: embed page')
        m = re.search(r"robotlink['\"]?\)?\.innerHTML\s*=\s*(?P<expr>[^\n]+)", page)
        if not m:
            raise ExtractorError('robotlink assignment not found')
        try:
            media_url = eval_js_concat(m.group('expr').strip().rstrip(';'))
        except ValueError as e:
            raise ExtractorError(f'could not evaluate robotlink expression: {e}')
        if media_url.startswith('//'):
            media_url = 'https:' + media_url
        if not url_or_none(media_url):
            raise ExtractorError('robotlink did not yield a usable url')

        fmt = {
            'url': media_url,
            'format_id': 'streamtape',
            'ext': 'mp4',
            'http_headers': {'Referer': 'https://streamtape.com/'},
        }
        # One 2-byte request buys the real filesize and the resolution, which the
        # embed page does not expose. Failure is non-fatal.
        try:
            resp = self._request_webpage(
                media_url, video_id, note=f'{note}: probing',
                headers={'Range': 'bytes=0-1', 'Referer': 'https://streamtape.com/'})
            total = int_or_none(self._search_regex(
                r'/(\d+)\s*$', resp.headers.get('Content-Range') or '', None, default=None))
            fmt['filesize'] = total or int_or_none(resp.headers.get('Content-Length'))
            if height := int_or_none(self._search_regex(
                    r'\b(240|360|480|576|720|1080|1440|2160)p\b',
                    urlparse(resp.url).path, None, default=None)):
                fmt['height'] = height
            resp.close()
        except Exception as e:
            self.report_warning(f'{note}: probe failed ({e.__class__.__name__})')
        return [fmt]

    def _byse_formats(self, embed_url, video_id, note):
        code = self._search_regex(r'/([A-Za-z0-9_-]+)/?$', urlparse(embed_url).path, 'video code')
        origin = f'{urlparse(embed_url).scheme}://{urlparse(embed_url).netloc}'
        data = self._download_json(
            f'{origin}/api/videos/{code}', video_id, note=f'{note}: playback api',
            headers={'Referer': embed_url})

        payload = traverse_obj(data, ('playback', {dict}))
        sources = None
        if payload:
            decrypted = self._byse_decrypt(payload, note)
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

    def _byse_decrypt(self, playback, note):
        """Rebuild the key exactly as the site's videoPagesBundle does:
        version n -> key_parts[n] + key_parts[31 - n] (1-based)."""
        parts = traverse_obj(playback, ('key_parts', lambda _, v: isinstance(v, str) and v))
        payload = traverse_obj(playback, ('payload', {str}))
        iv = traverse_obj(playback, ('iv', {str}))
        if not (parts and payload and iv):
            return None

        version = str_or_none(playback.get('version')) or ''
        chosen = parts
        if version.isdigit():
            n = int(version)
            idx = [i for i in (n, 31 - n) if 1 <= i <= len(parts)]
            if idx:
                chosen = [parts[i - 1] for i in idx]

        key = b''.join(base64url_decode(p) for p in chosen)
        blob = base64url_decode(payload)
        if len(blob) <= 16 or len(key) not in (16, 24, 32):
            self.report_warning(f'{note}: unexpected key/blob size ({len(key)}/{len(blob)})')
            return None
        try:
            return json.loads(aes_gcm_decrypt_and_verify_bytes(
                blob[:-16], key, blob[-16:], base64url_decode(iv)).decode())
        except Exception as e:
            self.report_warning(f'{note}: playback decrypt failed ({e.__class__.__name__})')
            return None
