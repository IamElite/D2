import base64
import binascii
import html
import json
import os
import re
import urllib.parse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, traverse_obj, url_or_none


def _domain_keywords():
    words = ['hianime', 'otakuthemes', 'zokoanime', 'megaplay', 'megacloud', 'aniwatch', 'anikoto', 'zoro']
    for part in re.split(r'[|,\s]+', os.environ.get('HIANIME_DOMAINS', '')):
        part = re.sub(r'[^A-Za-z0-9.-]', '', part).strip('.')
        if part and part not in words:
            words.append(part)
    return '|'.join(re.escape(w) for w in words)


class HianimeIE(InfoExtractor):
    IE_NAME = 'hianime'
    _VALID_URL = (
        rf'https?://[^/?#]*(?:{_domain_keywords()})[^/?#]*/[^?#]+'
        r'|https?://[^/?#]+/stream/[^?#]+/(?:sub|dub)/?'
    )
    _XOR_KEY = b'otaku-embed-v1'
    _AES_KEY = b'i?LMTAx0Q6,:}50U' + b'\x00' * 16
    _AES_IV = b"W0;27ToaUpl_P%'c"
    _SERVER_RE = re.compile(
        r'data-type="(?P<type>sub|dub)"[^>]*?data-server-name="(?P<name>[^"]*)"[^>]*?data-hash="(?P<hash>[^"]+)"')
    _EMBED_RE = re.compile(r'https?://[^\s"\'<>\\]+/stream/[^\s"\'<>\\]+/(?:sub|dub)(?![\w-])')
    _LANG_CODES = {
        'english': 'en', 'japanese': 'ja', 'spanish': 'es', 'french': 'fr', 'german': 'de',
        'arabic': 'ar', 'portuguese': 'pt', 'russian': 'ru', 'italian': 'it', 'indonesian': 'id',
        'thai': 'th', 'vietnamese': 'vi', 'polish': 'pl', 'malay': 'ms', 'chinese': 'zh',
    }

    def _lang_from_label(self, label):
        label = (label or '').strip().lower()
        if re.fullmatch(r'[a-z]{2}(?:-[a-z0-9]+)?', label):
            return label
        return self._LANG_CODES.get(label, 'und')

    def _xor_decode(self, blob):
        try:
            raw = base64.b64decode(blob)
        except binascii.Error:
            raise ExtractorError('Malformed embed payload', expected=True)
        out = bytes(b ^ self._XOR_KEY[i % len(self._XOR_KEY)] for i, b in enumerate(raw))
        try:
            return json.loads(out.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            raise ExtractorError('Unable to decode embed payload', expected=True)

    def _aes_decrypt(self, token, key, iv):
        data = token.replace('-', '+').replace('_', '/')
        data += '=' * (-len(data) % 4)
        raw = base64.b64decode(data)
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        pt = dec.update(raw) + dec.finalize()
        pad = pt[-1]
        if not 1 <= pad <= 16 or pt[-pad:] != bytes((pad,)) * pad:
            raise ExtractorError('Stream decryption failed')
        return pt[:-pad].decode('utf-8')

    def _megaplay_source(self, enc, embed_page, embed_origin, video_id):
        try:
            return json.loads(self._aes_decrypt(enc, self._AES_KEY, self._AES_IV)).get('file')
        except (ExtractorError, ValueError, binascii.Error, UnicodeDecodeError):
            pass
        js_url = self._search_regex(
            r'<script[^>]+src="([^"]*newclient[^"]*)"', embed_page, 'client script', default=None)
        if js_url:
            js_url = js_url if js_url.startswith('http') else urllib.parse.urljoin(embed_origin + '/', js_url)
            js = self._download_webpage(js_url, video_id, 'Downloading client script', impersonate=True, fatal=False) or ''
            m = re.search(r'"([^"]{8,32})",\w+="([^"]{8,32})",\w+=/\\?/segment/', js)
            if m:
                key = m.group(1).encode()[:32].ljust(32, b'\x00')
                iv = m.group(2).encode()[:16].ljust(16, b'\x00')
                try:
                    return json.loads(self._aes_decrypt(enc, key, iv)).get('file')
                except (ExtractorError, ValueError, binascii.Error, UnicodeDecodeError):
                    pass
        return None

    def _resolve_embed(self, embed_url, referer, video_id):
        parsed = urllib.parse.urlparse(embed_url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        page = self._download_webpage(
            embed_url, video_id, 'Downloading embed page',
            headers={'Referer': referer}, impersonate=True, fatal=False) or ''
        page = page.replace('\\/', '/')
        blob = re.search(r'window\.__P="([^"]+)"', page)
        if blob:
            cfg = self._xor_decode(blob.group(1))
            src = url_or_none(cfg.get('src'))
            if not src:
                return None
            subs = {}
            for track in cfg.get('subtitles') or []:
                turl = url_or_none(track.get('src'))
                if not turl:
                    continue
                lang = track.get('lang') or self._lang_from_label(track.get('label'))
                subs.setdefault(lang, []).append({'url': turl, 'http_headers': {'Referer': origin + '/'}})
            return {'url': src, 'referer': origin + '/', 'subtitles': subs}
        data_id = self._search_regex(r'data-id=["\'](\d+)', page, 'source id', default=None)
        if not data_id:
            data_id = next((p for p in reversed(parsed.path.split('/')) if p.isdigit()), None)
        if not data_id:
            return None
        data = self._download_json(
            f'{origin}/stream/getSources?id={data_id}', video_id, 'Downloading source info',
            headers={'Referer': embed_url, 'X-Requested-With': 'XMLHttpRequest'}, impersonate=True, fatal=False)
        if not isinstance(data, dict):
            return None
        src = url_or_none(traverse_obj(data, ('sources', 'file')))
        if not src:
            src = url_or_none(traverse_obj(data, ('sources', 0, 'file')))
        if not src and data.get('enc'):
            src = url_or_none(self._megaplay_source(data['enc'], page, origin, video_id))
        if not src:
            return None
        subs = {}
        for track in data.get('tracks') or []:
            turl = url_or_none(track.get('file'))
            if not turl or track.get('kind') not in (None, 'captions', 'subtitles'):
                continue
            subs.setdefault(self._lang_from_label(track.get('label')), []).append(
                {'url': turl, 'http_headers': {'Referer': origin + '/'}})
        return {'url': src, 'referer': origin + '/', 'subtitles': subs}

    def _real_extract(self, url):
        url = url.replace('\\/', '/')
        parsed = urllib.parse.urlparse(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        video_id = re.sub(r'[^A-Za-z0-9._-]+', '_', parsed.path.strip('/')).strip('_')[:100] or parsed.netloc
        lang_pref = (self._configuration_arg('lang', ['sub'])[0] or 'sub').lower()
        if lang_pref not in ('sub', 'dub'):
            lang_pref = 'sub'

        direct = re.search(r'/stream/.+/(sub|dub)/?$', parsed.path)
        if direct:
            candidates = [(direct.group(1), 'embed', url)]
            title = video_id
            page_referer = origin + '/'
        else:
            page_referer = url
            webpage = self._download_webpage(url, video_id, headers={'Referer': origin + '/'}, impersonate=True)
            webpage = webpage.replace('\\/', '/')
            title = (self._og_search_title(webpage, default=None)
                     or self._html_search_regex(r'<title>([^<]+)</title>', webpage, 'title', default=None)
                     or video_id)
            title = html.unescape(title)
            title = re.sub(r'\s*Watch All Episodes.*$', '', title, flags=re.I)
            title = re.split(r'\s+[–|]\s+|\s+-\s+', title)[0].strip() or video_id
            candidates = []
            rest_url = self._search_regex(r'"rest_url"\s*:\s*"([^"]+)"', webpage, 'rest url', default=None)
            episode_id = self._search_regex(r'wp-json/wp/v2/posts/(\d+)', webpage, 'episode id', default=None)
            if rest_url and episode_id:
                data = self._download_json(
                    rest_url.rstrip('/') + f'/episode/servers?episodeId={episode_id}', video_id,
                    'Downloading server list', fatal=False, impersonate=True,
                    headers={'Referer': url, 'X-Requested-With': 'XMLHttpRequest'})
                for m in self._SERVER_RE.finditer(traverse_obj(data, ('html', {str})) or ''):
                    try:
                        embed = base64.b64decode(m.group('hash')).decode('utf-8')
                    except (binascii.Error, UnicodeDecodeError):
                        continue
                    embed = url_or_none(embed)
                    if embed:
                        candidates.append((m.group('type'), m.group('name') or m.group('type').upper(), embed))
            if not candidates:
                seen = set()
                for m in self._EMBED_RE.finditer(webpage):
                    embed = url_or_none(m.group(0))
                    if not embed or embed in seen:
                        continue
                    seen.add(embed)
                    candidates.append((embed.rsplit('/', 1)[-1].lower(), urllib.parse.urlparse(embed).netloc, embed))
        if not candidates:
            raise ExtractorError('No stream servers found on page', expected=True)

        ordered = [c for c in candidates if c[0] == lang_pref] + [c for c in candidates if c[0] != lang_pref]
        failures = []
        for lang, server, embed in ordered:
            try:
                resolved = self._resolve_embed(embed, page_referer, video_id)
            except ExtractorError as e:
                failures.append(f'{server}: {e.msg}')
                continue
            if not resolved:
                failures.append(f'{server}: no source')
                continue
            headers = {'Referer': resolved['referer']}
            m3u8_doc = self._download_webpage(
                resolved['url'], video_id, 'Downloading m3u8 information',
                headers=headers, impersonate=True, fatal=False)
            if not m3u8_doc or '#EXTM3U' not in m3u8_doc:
                failures.append(f'{server}: stream rejected')
                continue
            formats, m3u8_subs = self._parse_m3u8_formats_and_subtitles(
                m3u8_doc, resolved['url'], 'mp4', m3u8_id='hls', headers=headers)
            if not formats:
                failures.append(f'{server}: stream rejected')
                continue
            for fmt in formats:
                fmt.setdefault('language', 'en' if lang == 'dub' else 'ja')
                fmt['format_note'] = f'{"DUB" if lang == "dub" else "SUB"} {server}'.strip()
                fmt['impersonate'] = True
                fmt.setdefault('http_headers', {}).update(headers)
            subs = resolved['subtitles']
            for slang, sentries in (m3u8_subs or {}).items():
                subs.setdefault(slang, []).extend(sentries)
            return {
                'id': video_id,
                'title': title,
                'formats': formats,
                'subtitles': subs or None,
                'is_live': False,
            }
        raise ExtractorError('All stream servers failed: ' + '; '.join(failures[:4]))
