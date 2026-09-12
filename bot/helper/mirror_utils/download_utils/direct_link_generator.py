#!/usr/bin/env python3
import re
from threading import Thread
from base64 import b64decode
from json import loads
from os import path
from uuid import uuid4
from hashlib import sha256
from time import sleep, time
from re import findall, match, search, sub

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from lxml.etree import HTML
from requests import Session, session as req_session, post
from urllib.parse import parse_qs, quote, unquote, urlparse, urljoin
from cloudscraper import create_scraper
from lk21 import Bypass
from http.cookiejar import MozillaCookieJar

from .... import LOGGER, config_dict
from ...ext_utils.bot_utils import get_readable_time, is_share_link, is_index_link, is_torrent_link
from ...ext_utils.exceptions import DirectDownloadLinkException
from ...ext_utils.help_messages import PASSWORD_ERROR_MESSAGE

_caches = {}
user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

fmed_list = ['fembed.net', 'fembed.com', 'femax20.com', 'fcdn.stream', 'feurl.com', 'layarkacaxxi.icu',
             'naniplay.nanime.in', 'naniplay.nanime.biz', 'naniplay.com', 'mm9842.com']

anonfilesBaseSites = ['anonfiles.com', 'hotfile.io', 'bayfiles.com', 'megaupload.nz', 'letsupload.cc',
                      'filechan.org', 'myfile.is', 'vshare.is', 'rapidshare.nu', 'lolabits.se',
                      'openload.cc', 'share-online.is', 'upvid.cc']

debrid_sites = ['1fichier.com', '2shared.com', '4shared.com', 'alfafile.net', 'anzfile.net', 'backin.net',
                'bayfiles.com', 'bdupload.in', 'brupload.net', 'btafile.com', 'catshare.net', 'clicknupload.me',
                'clipwatching.com', 'cosmobox.org', 'dailymotion.com', 'dailyuploads.net', 'daofile.com',
                'datafilehost.com', 'ddownload.com', 'depositfiles.com', 'dl.free.fr', 'douploads.net',
                'drop.download', 'earn4files.com', 'easybytez.com', 'ex-load.com', 'extmatrix.com',
                'down.fast-down.com', 'fastclick.to', 'faststore.org', 'file.al', 'file4safe.com', 'fboom.me',
                'filefactory.com', 'filefox.cc', 'filenext.com', 'filer.net', 'filerio.in', 'filesabc.com', 'filespace.com',
                'file-up.org', 'fileupload.pw', 'filezip.cc', 'fireget.com', 'flashbit.cc', 'flashx.tv', 'florenfile.com',
                'fshare.vn', 'gigapeta.com', 'goloady.com', 'docs.google.com', 'gounlimited.to', 'heroupload.com',
                'hexupload.net', 'hitfile.net', 'hotlink.cc', 'hulkshare.com', 'icerbox.com', 'inclouddrive.com',
                'isra.cloud', 'katfile.com', 'keep2share.cc', 'letsupload.cc', 'load.to', 'down.mdiaload.com', 'mediafire.com',
                'mega.co.nz', 'mixdrop.co', 'mixloads.com', 'mp4upload.com', 'nelion.me', 'ninjastream.to', 'nitroflare.com',
                'nowvideo.club', 'oboom.com', 'prefiles.com', 'sky.fm', 'rapidgator.net', 'rapidrar.com', 'rapidu.net',
                'rarefile.net', 'real-debrid.com', 'redbunker.net', 'redtube.com', 'rockfile.eu', 'rutube.ru', 'scribd.com',
                'sendit.cloud', 'sendspace.com', 'simfileshare.net', 'solidfiles.com', 'soundcloud.com', 'speed-down.org',
                'streamon.to', 'streamtape.com', 'takefile.link', 'tezfiles.com', 'thevideo.me', 'turbobit.net', 'tusfiles.com',
                'ubiqfile.com', 'uloz.to', 'unibytes.com', 'uploadbox.io', 'uploadboy.com', 'uploadc.com', 'uploaded.net',
                'uploadev.org', 'uploadgig.com', 'uploadrar.com', 'uppit.com', 'upstore.net', 'upstream.to', 'uptobox.com',
                'userscloud.com', 'usersdrive.com', 'vidcloud.ru', 'videobin.co', 'vidlox.tv', 'vidoza.net', 'vimeo.com',
                'vivo.sx', 'vk.com', 'voe.sx', 'wdupload.com', 'wipfiles.net', 'world-files.com', 'worldbytez.com', 'wupfile.com',
                'wushare.com', 'xubster.com', 'youporn.com', 'youtube.com']

debrid_link_sites = ["1dl.net", "1fichier.com", "alterupload.com", "cjoint.net", "desfichiers.com", "dfichiers.com", "megadl.org", 
                "megadl.fr", "mesfichiers.fr", "mesfichiers.org", "piecejointe.net", "pjointe.com", "tenvoi.com", "dl4free.com", 
                "apkadmin.com", "bayfiles.com", "clicknupload.link", "clicknupload.org", "clicknupload.co", "clicknupload.cc", 
                "clicknupload.link", "clicknupload.download", "clicknupload.club", "clickndownload.org", "ddl.to", "ddownload.com", 
                "depositfiles.com", "dfile.eu", "dropapk.to", "drop.download", "dropbox.com", "easybytez.com", "easybytez.eu", 
                "easybytez.me", "elitefile.net", "elfile.net", "wdupload.com", "emload.com", "fastfile.cc", "fembed.com", 
                "feurl.com", "anime789.com", "24hd.club", "vcdn.io", "sharinglink.club", "votrefiles.club", "there.to", "femoload.xyz", 
                "dailyplanet.pw", "jplayer.net", "xstreamcdn.com", "gcloud.live", "vcdnplay.com", "vidohd.com", "vidsource.me", 
                "votrefile.xyz", "zidiplay.com", "fcdn.stream", "femax20.com", "sexhd.co", "mediashore.org", "viplayer.cc", "dutrag.com", 
                "mrdhan.com", "embedsito.com", "diasfem.com", "superplayxyz.club", "albavido.xyz", "ncdnstm.com", "fembed-hd.com", 
                "moviemaniac.org", "suzihaza.com", "fembed9hd.com", "vanfem.com", "fikper.com", "file.al", "fileaxa.com", "filecat.net", 
                "filedot.xyz", "filedot.to", "filefactory.com", "filenext.com", "filer.net", "filerice.com", "filesfly.cc", "filespace.com", 
                "filestore.me", "flashbit.cc", "dl.free.fr", "transfert.free.fr", "free.fr", "gigapeta.com", "gofile.io", "highload.to", 
                "hitfile.net", "hitf.cc", "hulkshare.com", "icerbox.com", "isra.cloud", "goloady.com", "jumploads.com", "katfile.com", 
                "k2s.cc", "keep2share.com", "keep2share.cc", "kshared.com", "load.to", "mediafile.cc", "mediafire.com", "mega.nz", 
                "mega.co.nz", "mexa.sh", "mexashare.com", "mx-sh.net", "mixdrop.co", "mixdrop.to", "mixdrop.club", "mixdrop.sx", 
                "modsbase.com", "nelion.me", "nitroflare.com", "nitro.download", "e.pcloud.link", "pixeldrain.com", "prefiles.com", "rg.to", 
                "rapidgator.net", "rapidgator.asia", "scribd.com", "sendspace.com", "sharemods.com", "soundcloud.com", "noregx.debrid.link", 
                "streamlare.com", "slmaxed.com", "sltube.org", "slwatch.co", "streamtape.com", "subyshare.com", "supervideo.tv", "terabox.com", 
                "tezfiles.com", "turbobit.net", "turbobit.cc", "turbobit.pw", "turbobit.online", "turbobit.ru", "turbobit.live", "turbo.to", 
                "turb.to", "turb.cc", "turbabit.com", "trubobit.com", "turb.pw", "turboblt.co", "turboget.net", "ubiqfile.com", "ulozto.net", 
                "uloz.to", "zachowajto.pl", "ulozto.cz", "ulozto.sk", "upload-4ever.com", "up-4ever.com", "up-4ever.net", "uptobox.com", 
                "uptostream.com", "uptobox.fr", "uptostream.fr", "uptobox.eu", "uptostream.eu", "uptobox.link", "uptostream.link", "upvid.pro", 
                "upvid.live", "upvid.host", "upvid.co", "upvid.biz", "upvid.cloud", "opvid.org", "opvid.online", "uqload.com", "uqload.co", 
                "uqload.io", "userload.co", "usersdrive.com", "vidoza.net", "voe.sx", "voe-unblock.com", "voeunblock1.com", "voeunblock2.com", 
                "voeunblock3.com", "voeunbl0ck.com", "voeunblck.com", "voeunblk.com", "voe-un-block.com", "voeun-block.net", 
                "reputationsheriffkennethsand.com", "449unceremoniousnasoseptal.com", "world-files.com", "worldbytez.com", "salefiles.com", 
                "wupfile.com", "youdbox.com", "yodbox.com", "youtube.com", "youtu.be", "4tube.com", "academicearth.org", "acast.com", 
                "add-anime.net", "air.mozilla.org", "allocine.fr", "alphaporno.com", "anysex.com", "aparat.com", "www.arte.tv", "video.arte.tv", 
                "sites.arte.tv", "creative.arte.tv", "info.arte.tv", "future.arte.tv", "ddc.arte.tv", "concert.arte.tv", "cinema.arte.tv", 
                "audi-mediacenter.com", "audioboom.com", "audiomack.com", "beeg.com", "camdemy.com", "chilloutzone.net", "clubic.com", "clyp.it", 
                "daclips.in", "dailymail.co.uk", "www.dailymail.co.uk", "dailymotion.com", "touch.dailymotion.com", "democracynow.org", 
                "discovery.com", "investigationdiscovery.com", "discoverylife.com", "animalplanet.com", "ahctv.com", "destinationamerica.com", 
                "sciencechannel.com", "tlc.com", "velocity.com", "dotsub.com", "ebaumsworld.com", "eitb.tv", "ellentv.com", "ellentube.com", 
                "flipagram.com", "footyroom.com", "formula1.com", "video.foxnews.com", "video.foxbusiness.com", "video.insider.foxnews.com", 
                "franceculture.fr", "gameinformer.com", "gamersyde.com", "gorillavid.in", "hbo.com", "hellporno.com", "hentai.animestigma.com", 
                "hornbunny.com", "imdb.com", "instagram.com", "itar-tass.com", "tass.ru", "jamendo.com", "jove.com", "keek.com", "k.to", 
                "keezmovies.com", "khanacademy.org", "kickstarter.com", "krasview.ru", "la7.it", "lci.fr", "play.lcp.fr", "libsyn.com", 
                "html5-player.libsyn.com", "liveleak.com", "livestream.com", "new.livestream.com", "m6.fr", "www.m6.fr", "metacritic.com", 
                "mgoon.com", "m.mgoon.com", "mixcloud.com", "mojvideo.com", "movieclips.com", "movpod.in", "musicplayon.com", "myspass.de", 
                "myvidster.com", "odatv.com", "onionstudios.com", "ora.tv", "unsafespeech.com", "play.fm", "plays.tv", "playvid.com", 
                "pornhd.com", "pornhub.com", "www.pornhub.com", "pyvideo.org", "redtube.com", "embed.redtube.com", "www.redtube.com", 
                "reverbnation.com", "revision3.com", "animalist.com", "seeker.com", "rts.ch", "rtve.es", "videos.sapo.pt", "videos.sapo.cv", 
                "videos.sapo.ao", "videos.sapo.mz", "videos.sapo.tl", "sbs.com.au", "www.sbs.com.au", "screencast.com", "skysports.com", 
                "slutload.com", "soundgasm.net", "store.steampowered.com", "steampowered.com", "steamcommunity.com", "stream.cz", "streamable.com", 
                "streamcloud.eu", "sunporno.com", "teachertube.com", "teamcoco.com", "ted.com", "tfo.org", "thescene.com", "thesixtyone.com", 
                "tnaflix.com", "trutv.com", "tu.tv", "turbo.fr", "tweakers.net", "ustream.tv", "vbox7.com", "veehd.com", "veoh.com", "vid.me", 
                "videodetective.com", "vimeo.com", "vimeopro.com", "player.vimeo.com", "player.vimeopro.com", "wat.tv", "wimp.com", "xtube.com", 
                "yahoo.com", "screen.yahoo.com", "news.yahoo.com", "sports.yahoo.com", "video.yahoo.com", "youporn.com"]


GDFLIX_HOST = re.compile(r'(?:^|\.)(?:gdflix|gdlink)\.[a-z]{2,}$')
BUZZHEAVIER_HOST = re.compile(r'(?:^|\.)(?:buzzheavier|bzzhr|fuckingfast)\.[a-z]{2,}$')
STREAMTAPE_HOST = re.compile(r'(?:^|\.)(?:streamtape|streamta|tpead|tapead|strcloud|strtape|scloud)\.[a-z]{2,}$')
MULTICLOUD_HOST = re.compile(r'(?:^|\.)multicloudlinks\.[a-z]{2,}$')
HUBCLOUD_HOST = re.compile(r'(?:^|\.)(?:hubcloud|drivehub|hubdrive|hubcdn|vcloud)\.[a-z]{2,}$')
DOTFLIX_HOST = re.compile(r'(?:^|\.)(?:dotflix|dtflix)\.[a-z]{2,}$')
FASTDL_HOST = re.compile(r'(?:^|\.)(?:fastdl)\.[a-z]{2,}$')
NEXDRIVE_HOST = re.compile(r'(?:^|\.)(?:nexdrive)\.[a-z]{2,}$')

SUPPORTED_HOST_REGEXES = (
    GDFLIX_HOST, BUZZHEAVIER_HOST, STREAMTAPE_HOST, MULTICLOUD_HOST,
    HUBCLOUD_HOST, DOTFLIX_HOST, FASTDL_HOST, NEXDRIVE_HOST
)

KNOWN_DIRECT_DOMAINS = (
    'mediafire.com', 'pixeldrain.com', 'gofile.io', 'krakenfiles.com',
    '1fichier.com', 'racaty', 'solidfiles.com', 'akmfiles', 'linkbox',
    'easyupload.io', 'streamvid.net', 'filelions', 'dood', 'terabox',
    'fembed', 'sbembed', 'antfiles.com', 'upload.ee', 'shrdsk',
    'letsupload.io', 'wetransfer.com', 'we.tl'
)

def _is_supported_domain(domain):
    if not domain:
        return False
    d = domain.lower()
    return any(p.search(d) for p in SUPPORTED_HOST_REGEXES) or any(x in d for x in KNOWN_DIRECT_DOMAINS)

def direct_link_generator(link, _depth=0):
    auth = None
    if isinstance(link, tuple):
        link, auth = link
    if is_torrent_link(link):
        return real_debrid(link, True)

    domain = urlparse(link).hostname
    if not domain:
        raise DirectDownloadLinkException("ERROR: Invalid URL")
    if 'youtube.com' in domain or 'youtu.be' in domain:
        raise DirectDownloadLinkException("ERROR: Use ytdl cmds for Youtube links")
    elif config_dict['DEBRID_LINK_API'] and any(x in domain for x in debrid_link_sites):
        return debrid_link(link)
    elif config_dict['REAL_DEBRID_API'] and any(x in domain for x in debrid_sites):
        return real_debrid(link)
    elif any(x in domain for x in ['filelions.com', 'filelions.live', 'filelions.to', 'filelions.online']):
        return filelions(link)
    elif 'mediafire.com' in domain:
        return mediafire(link)
    elif 'osdn.net' in domain:
        return osdn(link)
    elif 'github.com' in domain:
        return github(link)
    elif 'sourceforge.net' in domain:
        return sourceforge(link)
    elif GDFLIX_HOST.search(domain or ''):
        return gdflix(link)
    elif 'hxfile.co' in domain:
        return hxfile(link)
    elif '1drv.ms' in domain:
        return onedrive(link)
    elif 'pixeldrain.com' in domain:
        return pixeldrain(link)
    elif 'antfiles.com' in domain:
        return antfiles(link)
    elif 'racaty' in domain:
        return racaty(link)
    elif '1fichier.com' in domain:
        return fichier(link)
    elif 'solidfiles.com' in domain:
        return solidfiles(link)
    elif 'krakenfiles.com' in domain:
        return krakenfiles(link)
    elif 'upload.ee' in domain:
        return uploadee(link)
    elif 'akmfiles' in domain:
        return akmfiles(link)
    elif 'linkbox' in domain:
        return linkbox(link)
    elif 'shrdsk' in domain:
        return shrdsk(link)
    elif 'letsupload.io' in domain:
        return letsupload(link)
    elif 'gofile.io' in domain:
        return gofile(link, auth)
    elif 'easyupload.io' in domain:
        return easyupload(link)
    elif 'streamvid.net' in domain:
        return streamvid(link)
    elif any(x in domain for x in ['dood.watch', 'doodstream.com', 'dood.to', 'dood.so', 'dood.cx', 'dood.la', 'dood.ws', 'dood.sh', 'doodstream.co', 'dood.pm', 'dood.wf', 'dood.re', 'dood.video', 'dooood.com', 'dood.yt', 'doods.yt', 'dood.stream', 'doods.pro']):
        return doods(link)
    elif STREAMTAPE_HOST.search(domain or ''):
        return streamtape(link)
    elif MULTICLOUD_HOST.search(domain or ''):
        return multicloud(link)
    elif HUBCLOUD_HOST.search(domain or ''):
        return hubcloud(link)
    elif DOTFLIX_HOST.search(domain or ''):
        return dotflix(link)
    elif BUZZHEAVIER_HOST.search(domain or ''):
        return buzzheavier(link)
    elif FASTDL_HOST.search(domain or ''):
        return fastdl(link)
    elif NEXDRIVE_HOST.search(domain or ''):
        return nexdrive(link)
    elif '10drives.com' in domain:
        raise DirectDownloadLinkException('ERROR: 10drives is protected by Cloudflare Turnstile captcha and cannot be bypassed server-side')
    elif any(x in domain for x in ['wetransfer.com', 'we.tl']):
        return wetransfer(link)
    elif any(x in domain for x in anonfilesBaseSites):
        raise DirectDownloadLinkException('ERROR: R.I.P Anon Sites!')
    elif any(x in domain for x in ['terabox.com', 'nephobox.com', '4funbox.com', 'mirrobox.com', 'momerybox.com', 'teraboxapp.com', '1024tera.com']):
        return terabox(link)
    elif any(x in domain for x in fmed_list):
        return fembed(link)
    elif any(x in domain for x in ['sbembed.com', 'watchsb.com', 'streamsb.net', 'sbplay.org']):
        return sbembed(link)
    elif is_index_link(link) and link.endswith('/'):
        return gd_index(link, auth)
    elif is_share_link(link):
        if 'gdtot' in domain:
            return gdtot(link)
        elif 'filepress' in domain:
            return filepress(link)
        elif 'www.jiodrive' in domain:
            return jiodrive(link)
        else:
            return sharer_scraper(link)
    elif 'zippyshare.com' in domain:
        raise DirectDownloadLinkException('ERROR: R.I.P Zippyshare')
    elif _depth < 3:
        resolved = _resolve_wrapper_or_embed(link, _depth)
        if resolved:
            return resolved
        raise DirectDownloadLinkException(f'No Direct link function found for {link}')
    else:
        raise DirectDownloadLinkException(f'No Direct link function found for {link}')


def _resolve_wrapper_or_embed(link, _depth=0):
    headers = {
        'User-Agent': user_agent,
        'Referer': f"{urlparse(link).scheme}://{urlparse(link).netloc}/",
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    }
    origin_domain = (urlparse(link).hostname or '').lower()
    resp = None
    try:
        from curl_cffi.requests import Session as CurlSession
        with CurlSession(impersonate='chrome120') as cs:
            resp = cs.get(link, headers=headers, allow_redirects=True, timeout=15)
    except Exception:
        try:
            with create_scraper() as ss:
                resp = ss.get(link, headers=headers, allow_redirects=True, timeout=15)
        except Exception:
            try:
                with Session() as rs:
                    resp = rs.get(link, headers=headers, allow_redirects=True, timeout=15)
            except Exception:
                return None
    if not resp:
        return None
    final_url = getattr(resp, 'url', None) or ''
    final_domain = (urlparse(final_url).hostname or '').lower()
    if final_url and final_url != link and final_domain != origin_domain:
        content_type = (resp.headers.get('content-type') or '').lower()
        content_disp = (resp.headers.get('content-disposition') or '').lower()
        if any(x in content_type for x in ['video/', 'audio/', 'octet-stream', 'matroska', 'zip', 'rar']) or 'attachment' in content_disp:
            return final_url
        if _is_supported_domain(final_domain):
            try:
                return direct_link_generator(final_url, _depth=_depth + 1)
            except Exception:
                pass
    if hasattr(resp, 'history') and resp.history:
        for h in reversed(resp.history):
            h_url = getattr(h, 'url', None) or ''
            h_domain = (urlparse(h_url).hostname or '').lower()
            if h_url and h_url != link and h_domain != origin_domain and _is_supported_domain(h_domain):
                try:
                    return direct_link_generator(h_url, _depth=_depth + 1)
                except Exception:
                    pass
    text = getattr(resp, 'text', '') or ''
    if text:
        meta_match = search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\'\s>]+)', text, re.IGNORECASE)
        if meta_match:
            target = meta_match.group(1).strip()
            if not target.startswith('http'):
                target = urljoin(final_url or link, target)
            target_domain = (urlparse(target).hostname or '').lower()
            if target != link and target_domain != origin_domain and _is_supported_domain(target_domain):
                try:
                    return direct_link_generator(target, _depth=_depth + 1)
                except Exception:
                    pass
        js_match = search(r'(?:window\.)?location(?:\.href|\.replace)?\s*=\s*["\'](https?://[^"\']+)["\']', text, re.IGNORECASE)
        if js_match:
            target = js_match.group(1).strip()
            target_domain = (urlparse(target).hostname or '').lower()
            if target != link and target_domain != origin_domain and _is_supported_domain(target_domain):
                try:
                    return direct_link_generator(target, _depth=_depth + 1)
                except Exception:
                    pass
        found_urls = findall(r'https?://[^\s"\'<>{}|\\^`]+', text)
        seen = set()
        for cand in found_urls:
            cand = cand.rstrip('.,;)]\'"')
            if not cand or cand in seen:
                continue
            seen.add(cand)
            cand_domain = (urlparse(cand).hostname or '').lower()
            if not cand_domain or cand_domain == origin_domain:
                continue
            if _is_supported_domain(cand_domain):
                try:
                    return direct_link_generator(cand, _depth=_depth + 1)
                except Exception:
                    continue
    return None


def real_debrid(url: str, tor=False):
    """ Real-Debrid Link Extractor (VPN Maybe Needed)
    Based on Real-Debrid v1 API (Heroku/VPS) [Without VPN]"""
    def __unrestrict(url, tor=False):
        cget = create_scraper().request
        resp = cget('POST', f"https://api.real-debrid.com/rest/1.0/unrestrict/link?auth_token={config_dict['REAL_DEBRID_API']}", data={'link': url})
        if resp.status_code == 200:
            if tor:
                _res = resp.json()
                return (_res['filename'], _res['download'])
            else:
                return resp.json()['download']
        else:
            raise DirectDownloadLinkException(f"ERROR: {resp.json()['error']}")

    def __addMagnet(magnet):
        cget = create_scraper().request
        hash_ = search(r'(?<=xt=urn:btih:)[a-zA-Z0-9]+', magnet).group(0)
        resp = cget('GET', f"https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/{hash_}?auth_token={config_dict['REAL_DEBRID_API']}")
        if resp.status_code != 200 or len(resp.json()[hash_.lower()]['rd']) == 0:
            return magnet
        resp = cget('POST', f"https://api.real-debrid.com/rest/1.0/torrents/addMagnet?auth_token={config_dict['REAL_DEBRID_API']}", data={'magnet': magnet})
        if resp.status_code == 201:
            _id = resp.json()['id']
        else:
            raise DirectDownloadLinkException(f"ERROR: {resp.json()['error']}")
        if _id:
            _file = cget('POST', f"https://api.real-debrid.com/rest/1.0/torrents/selectFiles/{_id}?auth_token={config_dict['REAL_DEBRID_API']}", data={'files': 'all'})
            if _file.status_code != 204:
                raise DirectDownloadLinkException(f"ERROR: {resp.json()['error']}")

        contents = {'links': []}
        while len(contents['links']) == 0:
            _res = cget('GET', f"https://api.real-debrid.com/rest/1.0/torrents/info/{_id}?auth_token={config_dict['REAL_DEBRID_API']}")
            if _res.status_code == 200:
                contents = _res.json()
            else:
                raise DirectDownloadLinkException(f"ERROR: {_res.json()['error']}")
            sleep(0.5)

        details = {'contents': [], 'title': contents['original_filename'], 'total_size': contents['bytes']}

        for file_info, link in zip(contents['files'], contents['links']):
            link_info = __unrestrict(link, tor=True)
            item = {
                "path": path.join(details['title'], path.dirname(file_info['path']).lstrip("/")), 
                "filename": unquote(link_info[0]),
                "url": link_info[1],
            }
            details['contents'].append(item)
        return details
    try:
        if tor:
            details = __addMagnet(url)
        else:
            return __unrestrict(url)
    except Exception as e:
        raise DirectDownloadLinkException(e)
    if isinstance(details, dict) and len(details['contents']) == 1:
        return details['contents'][0]['url']
    return details
    
    
def debrid_link(url):
    cget = create_scraper().request
    resp = cget('POST', f"https://debrid-link.com/api/v2/downloader/add?access_token={config_dict['DEBRID_LINK_API']}", data={'url': url}).json()
    if resp['success'] != True:
        raise DirectDownloadLinkException(f"ERROR: {resp['error']} & ERROR ID: {resp['error_id']}")
    if isinstance(resp['value'], dict):
        return resp['value']['downloadUrl']
    elif isinstance(resp['value'], list):
        details = {'contents': [], 'title': unquote(url.rstrip('/').split('/')[-1]), 'total_size': 0}
        for dl in resp['value']:
            if dl.get('expired', False):
                continue
            item = {
                "path": path.join(details['title']),
                "filename": dl['name'],
                "url": dl['downloadUrl']
            }
            if 'size' in dl:
                details['total_size'] += dl['size']
            details['contents'].append(item)
        return details


def get_captcha_token(session, params):
    recaptcha_api = 'https://www.google.com/recaptcha/api2'
    res = session.get(f'{recaptcha_api}/anchor', params=params)
    anchor_html = HTML(res.text)
    if not (anchor_token:= anchor_html.xpath('//input[@id="recaptcha-token"]/@value')):
        return
    params['c'] = anchor_token[0]
    params['reason'] = 'q'
    res = session.post(f'{recaptcha_api}/reload', params=params)
    if token := findall(r'"rresp","(.*?)"', res.text):
        return token[0]


def mediafire(url, session=None):
    if '/folder/' in url:
        return mediafireFolder(url)
    if final_link := findall(r'https?:\/\/download\d+\.mediafire\.com\/\S+\/\S+\/\S+', url):
        return final_link[0]
    if session is None:
        session = Session()
        parsed_url = urlparse(url)
        url = f'{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}'
    try:
        html = HTML(session.get(url).text)
    except Exception as e:
        session.close()
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
    if error:= html.xpath('//p[@class="notranslate"]/text()'):
        session.close()
        raise DirectDownloadLinkException(f"ERROR: {error[0]}")
    if not (final_link := html.xpath("//a[@id='downloadButton']/@href")):
        session.close()
        raise DirectDownloadLinkException("ERROR: No links found in this page Try Again")
    if final_link[0].startswith('//'):
        return mediafire(f'https://{final_link[0][2:]}', session)
    session.close()
    return final_link[0]


def osdn(url):
    with create_scraper() as session:
        try:
            html = HTML(session.get(url).text)
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
        if not (direct_link:= html.xapth('//a[@class="mirror_link"]/@href')):
            raise DirectDownloadLinkException("ERROR: Direct link not found")
        return f'https://osdn.net{direct_link[0]}'


def github(url):
    try:
        findall(r'\bhttps?://.*github\.com.*releases\S+', url)[0]
    except IndexError as e:
        raise DirectDownloadLinkException("No GitHub Releases links found") from e
    with create_scraper() as session:
        _res = session.get(url, stream=True, allow_redirects=False)
        if 'location' in _res.headers:
            return _res.headers["location"]
        raise DirectDownloadLinkException("ERROR: Can't extract the link")


def hxfile(url):
    try:
        return Bypass().bypass_filesIm(url)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e


def letsupload(url):
    with create_scraper() as session:
        try:
            res = session.post(url)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if direct_link := findall(r"(https?://letsupload\.io\/.+?)\'", res.text):
            return direct_link[0]
        else:
            raise DirectDownloadLinkException('ERROR: Direct Link not found')

def anonfilesBased(url):
    with create_scraper() as session:
        try:
            html = HTML(session.get(url).text)
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
        if sa := html.xpath('//*[@id="download-url"]/@href'):
            return sa[0]
        raise DirectDownloadLinkException("ERROR: File not found!")

def fembed(link):
    try:
        dl_url = Bypass().bypass_fembed(link)
        count = len(dl_url)
        lst_link = [dl_url[i] for i in dl_url]
        return lst_link[count-1]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e


def sbembed(link):
    """ Sbembed direct link generator
    Based on https://github.com/zevtyardt/lk21
    """
    try:
        dl_url = Bypass().bypass_sbembed(link)
        count = len(dl_url)
        lst_link = [dl_url[i] for i in dl_url]
        return lst_link[count-1]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e


def onedrive(link):
    with create_scraper() as session:
        try:
            link = session.get(link).url
            parsed_link = urlparse(link)
            link_data = parse_qs(parsed_link.query)
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
        if not link_data:
            raise DirectDownloadLinkException("ERROR: Unable to find link_data")
        folder_id = link_data.get('resid')
        if not folder_id:
            raise DirectDownloadLinkException('ERROR: folder id not found')
        folder_id = folder_id[0]
        authkey = link_data.get('authkey')
        if not authkey:
            raise DirectDownloadLinkException('ERROR: authkey not found')
        authkey = authkey[0]
        boundary = uuid4()
        headers = {'content-type': f'multipart/form-data;boundary={boundary}'}
        data = f'--{boundary}\r\nContent-Disposition: form-data;name=data\r\nPrefer: Migration=EnableRedirect;FailOnMigratedFiles\r\nX-HTTP-Method-Override: GET\r\nContent-Type: application/json\r\n\r\n--{boundary}--'
        try:
            resp = session.get( f'https://api.onedrive.com/v1.0/drives/{folder_id.split("!", 1)[0]}/items/{folder_id}?$select=id,@content.downloadUrl&ump=1&authKey={authkey}', headers=headers, data=data).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if "@content.downloadUrl" not in resp:
        raise DirectDownloadLinkException('ERROR: Direct link not found')
    return resp['@content.downloadUrl']


def pixeldrain(url):
    url = url.strip("/ ")
    file_id = url.split("/")[-1]
    if url.split("/")[-2] == "l":
        info_link = f"https://pixeldrain.com/api/list/{file_id}"
        dl_link = f"https://pixeldrain.com/api/list/{file_id}/zip?download"
    else:
        info_link = f"https://pixeldrain.com/api/file/{file_id}/info"
        dl_link = f"https://pixeldrain.com/api/file/{file_id}?download"
    with create_scraper() as session:
        try:
            resp = session.get(info_link).json()
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
    if resp["success"]:
        return dl_link
    else:
        raise DirectDownloadLinkException(
            f"ERROR: Cant't download due {resp['message']}.")


def antfiles(url):
    try:
        return Bypass().bypass_antfiles(url)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e


_STREAMTAPE_ROBOTLINK_RE = re.compile(
    r"(?:norobotlink|robotlink|captchalink|ideoooolink)(?!\w)[\s'\")\]]*\.innerHTML\s*=\s*(?P<expr>[^\n]+)")
_STREAMTAPE_JS_STR_RE = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""")
_STREAMTAPE_JS_METH_RE = re.compile(r'[\s)]*\.\s*(substring|substr|slice)\s*\(\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?\)')


def _streamtape_eval_js(expr):
    parts, i, n = [], 0, len(expr)
    while i < n:
        if expr[i].isspace() or expr[i] in '+();':
            i += 1
            continue
        m = _STREAMTAPE_JS_STR_RE.match(expr, i)
        if not m:
            if parts:
                break
            raise ValueError(f'unexpected token {expr[i]!r} at {i}')
        value, i = m.group(2), m.end()
        while (method := _STREAMTAPE_JS_METH_RE.match(expr, i)):
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
    m = _STREAMTAPE_ROBOTLINK_RE.search(page_html or '')
    if not m:
        raise ValueError('robotlink assignment not found')
    media = _streamtape_eval_js(m.group('expr').strip().rstrip(';'))
    if media.startswith('//'):
        media = 'https:' + media
    elif media.startswith('/'):
        media = 'https:/' + media
    media = sub(r'/get_v[a-zA-Z]*ideo\?', '/get_video?', media)
    media = sub(r'([?&])id[a-zA-Z]*=', r'\1id=', media)
    if not media.startswith('http'):
        raise ValueError('robotlink did not yield a usable url')
    return media


def streamtape(url):
    parsed = urlparse(url)
    try:
        with Session() as session:
            session.headers.update({'user-agent': user_agent})
            page = session.get(url, timeout=30).text
    except Exception:
        try:
            from curl_cffi.requests import Session as CurlSession
            with CurlSession(impersonate='chrome') as session:
                page = session.get(url, timeout=30).text
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
    try:
        durl = streamtape_media_url(page)
        return (durl, f'Referer: {parsed.scheme}://{parsed.hostname}/')
    except ValueError as e:
        raise DirectDownloadLinkException(f"ERROR: {e}") from e
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e


def multicloud(url):
    try:
        from curl_cffi.requests import Session as CurlSession
    except ImportError as e:
        raise DirectDownloadLinkException('ERROR: curl-cffi missing') from e
    with CurlSession(impersonate='chrome') as session:
        try:
            res = session.get(url, timeout=30)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if res.status_code == 403:
            raise DirectDownloadLinkException('ERROR: MultiCloud Cloudflare challenge')
        html = HTML(res.text)
        gdflix_links = html.xpath("//a[contains(@href, 'gdflix')]/@href")
        if gdflix_links:
            return gdflix(gdflix_links[0])
        fp_links = html.xpath("//a[contains(@href, 'filebee') or contains(@href, 'filepress')]/@href")
        if fp_links:
            return filepress(fp_links[0])
        dl_links = html.xpath("//a[contains(@href, 'multidownload') or contains(@href, '/dl/')]/@href")
        if dl_links:
            return dl_links[0]
        all_links = html.xpath("//a[contains(@class, 'btn')]/@href")
        for l in all_links:
            if l.startswith('http') and not any(k in l for k in ['login', 'signup', 'telegram', 'whatsapp', 'facebook', 'twitter']):
                return l
    raise DirectDownloadLinkException('ERROR: MultiCloud mirrors not found')


def hubdrive_ajax(session, url):
    parsed = urlparse(url)
    file_id = parsed.path.rstrip('/').rsplit('/', 1)[-1]
    if not file_id:
        return None
    origin = f'{parsed.scheme}://{parsed.hostname}'
    try:
        res = session.post(
            f'{origin}/ajax.php?ajax=direct-download',
            data={'id': file_id},
            headers={'Referer': url, 'X-Requested-With': 'XMLHttpRequest'},
            timeout=25,
        )
        payload = res.json()
    except Exception:
        return None
    if str(payload.get('code', '')) != '200':
        return None
    data = payload.get('data') or {}
    gd = data.get('gd')
    if isinstance(gd, str) and gd.startswith('http'):
        try:
            head = session.head(gd, timeout=15)
            if head.status_code != 200:
                return None
        except Exception:
            pass
        return gd
    return None


def hubcloud_bypass_page(session, bypass_url, page_url):
    attempt = 0
    while attempt < 2:
        attempt += 1
        try:
            text = session.get(bypass_url, headers={'Referer': page_url}, timeout=25).text
        except Exception:
            return None
        html = HTML(text)
        size = html.xpath("//i[@id='size']/text()")
        expired = bool(size) and 'NAN' in (size[0] or '').upper()
        fsl = html.xpath("//a[@id='fsl']/@href")
        if fsl and not expired:
            link = fsl[0].strip().replace('&amp;', '&')
            link_host = urlparse(link).hostname or ''
            if link.startswith('http') and not HUBCLOUD_HOST.search(link_host) and 'gamerxyt' not in link_host:
                return link
        if expired:
            try:
                fresh = session.get(page_url, timeout=25).text
            except Exception:
                return None
            m = search(r'https?://gamerxyt\.com/hubcloud\.php\?[^"\'\s<>]+', fresh)
            if not m:
                return None
            new_url = m.group(0).replace('&amp;', '&')
            if new_url == bypass_url:
                return None
            bypass_url = new_url
            continue
        pxl = html.xpath("//a[@id='pxl-1']/@href") or findall(
            r'var\s+pxl\s*=\s*["\'](https?://pixeldrain\.[a-z]+/u/[A-Za-z0-9]+)["\']', text)
        if pxl:
            m = search(r'(https?://pixeldrain\.[a-z]+)/u/([A-Za-z0-9]+)', pxl[0].strip().replace('&amp;', '&'))
            if m:
                return f'{m.group(1)}/api/file/{m.group(2)}?download'
        return None
    return None


def hubcloud(url, _depth=0):
    try:
        from curl_cffi.requests import Session as CurlSession
    except ImportError as e:
        raise DirectDownloadLinkException('ERROR: curl-cffi missing') from e
    parsed = urlparse(url)
    with CurlSession(impersonate='chrome') as session:
        direct = hubdrive_ajax(session, url)
        if direct:
            return direct
        try:
            res = session.get(url, timeout=25)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if res.status_code == 403:
            raise DirectDownloadLinkException('ERROR: Cloudflare challenge / access blocked')
        text = res.text
        if 'cf-turnstile' in text or 'captcha-wall' in text:
            raise DirectDownloadLinkException('ERROR: Cloudflare Turnstile captcha active on page')
        bypass_m = search(r'https?://gamerxyt\.com/hubcloud\.php\?[^"\'\s<>]+', text)
        if bypass_m:
            link = hubcloud_bypass_page(session, bypass_m.group(0).replace('&amp;', '&'), url)
            if link:
                return link
        atob_double = search(r'atob\(atob\(["\']([A-Za-z0-9+/=]+)["\']\)\)', text)
        atob_single = search(r'atob\(["\']([A-Za-z0-9+/=]+)["\']\)', text)
        token_url = None
        if atob_double:
            try:
                token_url = b64decode(b64decode(atob_double.group(1)).decode()).decode()
            except Exception:
                pass
        elif atob_single:
            try:
                token_url = b64decode(atob_single.group(1)).decode()
            except Exception:
                pass
        if token_url and token_url.startswith('http'):
            try:
                r2 = session.get(token_url, headers={'Referer': url, 'User-Agent': user_agent}, timeout=25)
                if r2.status_code == 200:
                    html2 = HTML(r2.text)
                    cands = html2.xpath("//a[contains(@href, 'r2.dev') or contains(@href, 'pixeldrain') or contains(@href, 'workers.dev') or contains(@href, 'download') or contains(@href, 'fsl')]/@href")
                    for c in cands:
                        if c.startswith('http'):
                            if any(x in c for x in ['r2.dev', 'googleusercontent.com', 'workers.dev']):
                                return c
                    for c in cands:
                        if c.startswith('http'):
                            if 'pixeldrain' in c:
                                try:
                                    return pixeldrain(c)
                                except Exception:
                                    return c
                            return c
                    pxl_m = search(r'var\s+pxl\s*=\s*["\'](https?://[^"\']+)["\']', r2.text)
                    if pxl_m:
                        c = pxl_m.group(1)
                        if 'pixeldrain' in c:
                            try:
                                return pixeldrain(c)
                            except Exception:
                                return c
                        return c
            except Exception:
                pass
        html = HTML(text)
        instant = html.xpath("//a[contains(@href, 'instant') or contains(@href, 'download')]/@href")
        for l in instant:
            if l.startswith('http'):
                return l
        if _depth < 2:
            mirrors = html.xpath("//a[contains(@href, '/drive/')]/@href")
            for m in mirrors:
                target = urljoin(url, m)
                target_host = urlparse(target).hostname or ''
                if target_host != (parsed.hostname or '') and HUBCLOUD_HOST.search(target_host):
                    try:
                        return hubcloud(target, _depth + 1)
                    except DirectDownloadLinkException:
                        continue
        if 'Please Try Login Method' in text:
            raise DirectDownloadLinkException('ERROR: User login required to generate direct link')
    try:
        with req_session() as s:
            resp = s.get(f'http://hubcloud.cfd/bypass?url={url}', timeout=10).json()
            if resp.get('links'):
                links = sorted(resp['links'], key=lambda x: x.get('priority', 0), reverse=True)
                return links[0]['url']
    except Exception:
        pass
    raise DirectDownloadLinkException('ERROR: No usable download link found')


def dotflix(url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    m = search(r'/share/([A-Za-z0-9]+)', parsed.path)
    if not m:
        raise DirectDownloadLinkException('ERROR: Invalid DOTFLIX share link')
    code = m.group(1)
    hosts = [f'https://{host}']
    if host != 'dotflix.store':
        hosts.append('https://dotflix.store')
    last_error = None
    with Session() as session:
        session.headers.update({'User-Agent': user_agent, 'Referer': url})
        for base in hosts:
            try:
                data = session.post(f'{base}/api/extract-download',
                                    json={'sharingCode': code}, timeout=20).json()
                if data.get('success') and data.get('downloadUrl'):
                    return data['downloadUrl']
                last_error = last_error or data.get('error') or data.get('message')
            except Exception:
                pass
            try:
                data = session.post(f'{base}/api/generate-quick-download',
                                    json={'sharingCode': code}, timeout=20).json()
                if data.get('success') and data.get('workerUrl'):
                    return data['workerUrl']
                last_error = last_error or data.get('error')
            except Exception:
                pass
        try:
            data = session.get(f'https://{host}/api/secure-cloudflare-url/{code}', timeout=20).json()
            if data.get('success') and (data.get('data') or {}).get('cloudflare_url'):
                return data['data']['cloudflare_url']
        except Exception:
            pass
        try:
            page = session.get(url, timeout=20).text
            direct = search(r'https?://[^"\'\s<>]*googleusercontent\.com/[^"\'\s<>]+', page)
            if direct:
                return direct.group(0).replace('&amp;', '&')
            worker = search(r'https?://[a-z0-9.-]+\.workers\.dev/[^"\'\s<>]+', page)
            if worker:
                return worker.group(0).replace('&amp;', '&')
        except Exception:
            pass
    raise DirectDownloadLinkException(f'ERROR: DOTFLIX: {last_error or "Direct link not found (share may be expired)"}')


def buzzheavier(url):
    try:
        from curl_cffi.requests import Session as CurlSession
    except ImportError as e:
        raise DirectDownloadLinkException('ERROR: curl-cffi missing') from e
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split('/') if p and p not in ('f', 'download')]
    if not parts:
        raise DirectDownloadLinkException('ERROR: Invalid Buzzheavier link')
    file_id = parts[-1]
    page_url = f'https://{parsed.netloc}/{file_id}'
    with CurlSession(impersonate='chrome') as session:
        try:
            res = session.get(page_url, timeout=30)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if res.status_code in (404, 410):
            raise DirectDownloadLinkException('ERROR: Buzzheavier file not found or removed')
        m = search(r'hx-get="([^"]+/download[^"]*)"', res.text)
        dl_url = urljoin(page_url, m.group(1).replace('&amp;', '&')) if m else f'{page_url}/download'
        link = ''
        try:
            r = session.get(dl_url, timeout=30, allow_redirects=False,
                            headers={'HX-Request': 'true', 'HX-Current-URL': page_url,
                                     'Referer': page_url, 'Accept': '*/*'})
            link = (r.headers.get('hx-redirect') or '').strip()
        except Exception:
            pass
        if link.startswith('/'):
            link = f'https://{parsed.netloc}{link}'
    if not link.startswith('http') or link.rstrip('/') == page_url.rstrip('/'):
        raise DirectDownloadLinkException('ERROR: Buzzheavier direct link not generated (protected or expired)')
    return link


def racaty(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            json_data = {
                'op': 'download2',
                'id': url.split('/')[-1]
            }
            html = HTML(session.post(url, data=json_data).text)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if (direct_link := html.xpath("//a[@id='uniqueExpirylink']/@href")):
        return direct_link[0]
    else:
        raise DirectDownloadLinkException('ERROR: Direct link not found')


def fichier(link):
    regex = r"^([http:\/\/|https:\/\/]+)?.*1fichier\.com\/\?.+"
    gan = match(regex, link)
    if not gan:
        raise DirectDownloadLinkException(
            "ERROR: The link you entered is wrong!")
    if "::" in link:
        pswd = link.split("::")[-1]
        url = link.split("::")[-2]
    else:
        pswd = None
        url = link
    cget = create_scraper().request
    try:
        if pswd is None:
            req = cget('post', url)
        else:
            pw = {"pass": pswd}
            req = cget('post', url, data=pw)
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
    if req.status_code == 404:
        raise DirectDownloadLinkException("ERROR: File not found/The link you entered is wrong!")
    html = HTML(req.text)
    if dl_url:= html.xpath('//a[@class="ok btn-general btn-orange"]/@href'):
        return dl_url[0]
    if not (ct_warn := html.xpath('//div[@class="ct_warn"]')):
        raise DirectDownloadLinkException("ERROR: Error trying to generate Direct Link from 1fichier!")
    if len(ct_warn) == 3:
        str_2 = ct_warn[-1].text
        if "you must wait" in str_2.lower():
            if numbers := [int(word) for word in str_2.split() if word.isdigit()]:
                raise DirectDownloadLinkException(f"ERROR: 1fichier is on a limit. Please wait {numbers[0]} minute.")
            else:
                raise DirectDownloadLinkException("ERROR: 1fichier is on a limit. Please wait a few minutes/hour.")
        elif "protect access" in str_2.lower():
            raise DirectDownloadLinkException(f"ERROR:\n{PASSWORD_ERROR_MESSAGE.format(link)}")
        else:
            raise DirectDownloadLinkException("ERROR: Failed to generate Direct Link from 1fichier!")
    elif len(ct_warn) == 4:
        str_1 = ct_warn[-2].text
        str_3 = ct_warn[-1].text
        if "you must wait" in str_1.lower():
            if numbers := [int(word) for word in str_1.split() if word.isdigit()]:
                raise DirectDownloadLinkException(f"ERROR: 1fichier is on a limit. Please wait {numbers[0]} minute.")
            else:
                raise DirectDownloadLinkException("ERROR: 1fichier is on a limit. Please wait a few minutes/hour.")
        elif "bad password" in str_3.lower():
            raise DirectDownloadLinkException("ERROR: The password you entered is wrong!")
    raise DirectDownloadLinkException("ERROR: Error trying to generate Direct Link from 1fichier!")


def solidfiles(url):
    with create_scraper() as session:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1985.125 Safari/537.36'
            }
            pageSource = session.get(url, headers=headers).text
            mainOptions = str(
                search(r'viewerOptions\'\,\ (.*?)\)\;', pageSource).group(1))
            return loads(mainOptions)["downloadUrl"]
        except Exception as e:
            raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e


def krakenfiles(url):
    with Session() as session:
        try:
            _res = session.get(url)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        html = HTML(_res.text)
        if post_url:= html.xpath('//form[@id="dl-form"]/@action'):
            post_url = f'https:{post_url[0]}'
        else:
            raise DirectDownloadLinkException('ERROR: Unable to find post link.')
        if token:= html.xpath('//input[@id="dl-token"]/@value'):
            data = {'token': token[0]}
        else:
            raise DirectDownloadLinkException('ERROR: Unable to find token for post.')
        try:
            _json = session.post(post_url, data=data).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__} While send post request') from e
    if _json['status'] != 'ok':
        raise DirectDownloadLinkException("ERROR: Unable to find download after post request")
    return _json['url']



def uploadee(url):
    with create_scraper() as session:
        try:
            html = HTML(session.get(url).text)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if link := html.xpath("//a[@id='d_l']/@href"):
        return link[0]
    else:
        raise DirectDownloadLinkException("ERROR: Direct Link not found")

def terabox(url):
    if not path.isfile('terabox.txt'):
        raise DirectDownloadLinkException("ERROR: terabox.txt not found")
    try:
        jar = MozillaCookieJar('terabox.txt')
        jar.load()
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}") from e
    cookies = {}
    for cookie in jar:
        cookies[cookie.name] = cookie.value
    details = {'contents':[], 'title': '', 'total_size': 0}
    details["header"] = ' '.join(f'{key}: {value}' for key, value in cookies.items())

    def __fetch_links(session, dir_='', folderPath=''):
        params = {
            'app_id': '250528',
            'jsToken': jsToken,
            'shorturl': shortUrl
            }
        if dir_:
            params['dir'] = dir_
        else:
            params['root'] = '1'
        try:
            _json = session.get("https://www.1024tera.com/share/list", params=params, cookies=cookies).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
        if _json['errno'] not in [0, '0']:
            if 'errmsg' in _json:
                raise DirectDownloadLinkException(f"ERROR: {_json['errmsg']}")
            else:
                raise DirectDownloadLinkException('ERROR: Something went wrong!')

        if "list" not in _json:
            return
        contents = _json["list"]
        for content in contents:
            if content['isdir'] in ['1', 1]:
                if not folderPath:
                    if not details['title']:
                        details['title'] = content['server_filename']
                        newFolderPath = path.join(details['title'])
                    else:
                        newFolderPath = path.join(details['title'], content['server_filename'])
                else:
                    newFolderPath = path.join(folderPath, content['server_filename'])
                __fetch_links(session, content['path'], newFolderPath)
            else:
                if not folderPath:
                    if not details['title']:
                        details['title'] = content['server_filename']
                    folderPath = details['title']
                item = {
                    'url': content['dlink'],
                    'filename': content['server_filename'],
                    'path' : path.join(folderPath),
                }
                if 'size' in content:
                    size = content["size"]
                    if isinstance(size, str) and size.isdigit():
                        size = float(size)
                    details['total_size'] += size
                details['contents'].append(item)

    with Session() as session:
        try:
            _res = session.get(url, cookies=cookies)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
        if jsToken := findall(r'window\.jsToken.*%22(.*)%22', _res.text):
            jsToken = jsToken[0]
        else:
            raise DirectDownloadLinkException('ERROR: jsToken not found!.')
        shortUrl = parse_qs(urlparse(_res.url).query).get('surl')
        if not shortUrl:
            raise DirectDownloadLinkException("ERROR: Could not find surl")
        try:
            __fetch_links(session)
        except Exception as e:
            raise DirectDownloadLinkException(e)
    if len(details['contents']) == 1:
        return details['contents'][0]['url']
    return details



_GOFILE_SALT_FALLBACK = '12af056dacea0b'
_GOFILE_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36')


def _gofile_salt(session):
    """The signing secret is baked into /js/wt.obf.js and rotated server-side
    (retired secrets get the caller's IP banned), so it is read at request time
    instead of hardcoded. The fallback only covers an unfetchable bundle."""
    try:
        js = session.get('https://gofile.io/js/wt.obf.js', timeout=15).text
        js = sub(r'\\x([0-9a-f]{2})', lambda m: chr(int(m.group(1), 16)), js)
        if salt := search(r"'([0-9a-f]{14})'", js[js.index('generateWT'):]):
            return salt.group(1)
    except Exception:
        pass
    return _GOFILE_SALT_FALLBACK


def gofile(url, auth=None):
    """GoFile direct link — free/guest access, no premium needed.

    Flow: POST /accounts mints a guest token, then
    GET /contents/<code>?cache=true is signed with
      X-Website-Token = sha256(userAgent :: en-US :: token :: slot :: salt)
    where slot = int(time()) // 14400 (a 4-hour bucket — missing it is what
    makes the API answer error-notPremium) and salt comes from wt.obf.js.
    The download url needs the account cookie, so a header travels with it.
    Verified live: 795 MB mkv, HTTP 200, md5 matched the API's.
    """
    try:
        if '::' in url:
            password = sha256(url.split('::')[-1].encode('utf-8')).hexdigest()
            url = url.split('::')[-2]
        else:
            password = ''
        content_id = url.rstrip('/').split('/')[-1]
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e

    details = {'contents': [], 'title': '', 'total_size': 0}

    def __add_item(node, folderPath):
        item = {'path': path.join(folderPath) if folderPath else folderPath,
                'filename': node['name'], 'url': node['link']}
        if (size := node.get('size')) is not None:
            details['total_size'] += float(size) if isinstance(size, str) and size.isdigit() else size
        details['contents'].append(item)
        return folderPath

    def __fetch(session, token, salt, _id, folderPath=''):
        slot = int(time()) // 14400
        headers = {
            'User-Agent': _GOFILE_UA, 'Accept': '*/*',
            'Authorization': f'Bearer {token}',
            'X-Website-Token': sha256(f'{_GOFILE_UA}::en-US::{token}::{slot}::{salt}'.encode()).hexdigest(),
            'X-BL': 'en-US',
        }
        api = f'https://api.gofile.io/contents/{_id}?cache=true'
        if password:
            api += f'&password={password}'
        try:
            res = session.get(api, headers=headers, timeout=30).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        status = res.get('status')
        if status == 'error-passwordRequired':
            raise DirectDownloadLinkException(f'ERROR:\n{PASSWORD_ERROR_MESSAGE.format(url)}')
        if status == 'error-passwordWrong':
            raise DirectDownloadLinkException('ERROR: This password is wrong!')
        if status == 'error-notFound':
            raise DirectDownloadLinkException("ERROR: File not found on gofile's server")
        if status == 'error-notPublic':
            raise DirectDownloadLinkException('ERROR: This folder is not public')
        if status != 'ok':
            raise DirectDownloadLinkException(f'ERROR: Gofile said {status}')

        data = res['data']
        if not details['title']:
            details['title'] = data['name'] if data.get('type') == 'folder' else _id
        if 'children' not in data:
            __add_item(data, folderPath)
            return
        for child in data['children'].values():
            if child.get('type') == 'folder':
                if not child.get('public'):
                    continue
                base = folderPath or details['title']
                __fetch(session, token, salt, child['id'], path.join(base, child['name']))
            else:
                __add_item(child, folderPath)

    with Session() as session:
        try:
            acc = session.post('https://api.gofile.io/accounts',
                               headers={'User-Agent': _GOFILE_UA}, timeout=20).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if acc.get('status') != 'ok':
            raise DirectDownloadLinkException(f"ERROR: Gofile could not mint a token ({acc.get('status')})")
        token = acc['data']['token']
        # The download url is bound to this account, so the cookie must travel with it.
        details['header'] = f'Cookie: accountToken={token}'
        try:
            __fetch(session, token, _gofile_salt(session), content_id)
        except DirectDownloadLinkException:
            raise
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e

    if not details['contents']:
        raise DirectDownloadLinkException('ERROR: No downloadable file found in this gofile folder')
    if len(details['contents']) == 1:
        return details['contents'][0]['url'], details['header']
    return details


def fastdl(url):
    headers = {'User-Agent': user_agent}
    with Session() as session:
        try:
            res = session.get(url, headers=headers, timeout=20)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if res.status_code != 200:
            raise DirectDownloadLinkException(f'ERROR: FastDL returned HTTP {res.status_code}')
        m = re.search(r'var\s+reurl\s*=\s*["\']([^"\']+)["\']', res.text)
        if not m:
            m = re.search(r'href=["\']([^"\']*dl\.php\?link=[^"\']+)["\']', res.text)
        if not m:
            raise DirectDownloadLinkException('ERROR: FastDL direct link not found in page')
        target = m.group(1)
        if 'link=' in target:
            target = target.split('link=', 1)[1]
        if not target.startswith('http'):
            raise DirectDownloadLinkException('ERROR: FastDL returned invalid target URL')
        return target


def nexdrive(url):
    headers = {'User-Agent': user_agent}
    with Session() as session:
        try:
            res = session.get(url, headers=headers, timeout=20)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if res.status_code != 200:
            raise DirectDownloadLinkException(f'ERROR: Nexdrive returned HTTP {res.status_code}')
        html_text = res.text
        fastdl_match = re.search(r'href=["\'](https?://[^"\']*fastdl\.[^"\']+)["\']', html_text, re.I)
        filepress_match = re.search(r'href=["\'](https?://[^"\']*(?:filepress|filebee)\.[^"\']+)["\']', html_text, re.I)
        hubcloud_match = re.search(r'href=["\'](https?://[^"\']*(?:hubcloud|hubdrive|drivehub|vcloud)\.[^"\']+)["\']', html_text, re.I)
        last_error = None
        if fastdl_match:
            try:
                return fastdl(fastdl_match.group(1))
            except Exception as e:
                last_error = e
        if hubcloud_match:
            try:
                link = hubcloud(hubcloud_match.group(1))
                if link:
                    return link
            except Exception as e:
                last_error = e
        if filepress_match:
            try:
                return filepress(filepress_match.group(1))
            except Exception as e:
                last_error = e
        all_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html_text)
        for cand in all_links:
            cand_domain = urlparse(cand).hostname or ''
            if cand_domain and cand_domain not in url and not any(x in cand_domain for x in ['wordpress.org', 'w.org', 'google.com', 'telegram.me', 't.me', 'bit.ly']):
                try:
                    return direct_link_generator(cand)
                except Exception as e:
                    last_error = e
                    continue
        if last_error:
            raise DirectDownloadLinkException(f'ERROR: Nexdrive ({last_error})')
        raise DirectDownloadLinkException('ERROR: Could not resolve any download server from Nexdrive page')


def sourceforge(url):
    """SourceForge direct link. Chrome impersonation is load-bearing here: with
    cloudscraper the page comes back without the meta-refresh (verified live)."""
    try:
        from curl_cffi.requests import Session as CurlSession
    except ImportError as e:
        raise DirectDownloadLinkException(
            'ERROR: curl-cffi missing — rebuild the image so requirements.txt installs it') from e
    if not url.rstrip('/').endswith('/download'):
        url = f"{url.rstrip('/')}/download"
    with CurlSession(impersonate='chrome') as session:
        res = session.get(url, headers={'Referer': url.rsplit('/', 2)[0] + '/'})
        meta = [x for x in HTML(res.text).xpath('//meta[@http-equiv]/@content')
                if 'url=http' in x]
        if not meta:
            raise DirectDownloadLinkException('ERROR: File Not Found')
        res = session.get(meta[0].split('url=', 1)[1],
                          headers={'Referer': url}, allow_redirects=False)
    if not (durl := res.headers.get('location', '')):
        raise DirectDownloadLinkException('ERROR: File Not Found')
    return durl


def gdflix(url):
    """GDFlix direct link. Cloudflare serves a challenge to anything but a real
    browser fingerprint, so curl-cffi impersonation is load-bearing here
    (cloudscraper gets HTTP 403). Verified live: 96 MB mkv, HTTP 200."""
    if '/pack/' in url:
        raise DirectDownloadLinkException(
            'ERROR: GDFlix pack (multi-file) links are not supported yet — send a /file/ link.')
    try:
        from curl_cffi.requests import Session as CurlSession
    except ImportError as e:
        raise DirectDownloadLinkException(
            'ERROR: curl-cffi missing — rebuild the image so requirements.txt installs it') from e
    with CurlSession(impersonate='chrome') as session:
        res = session.get(url, timeout=30)
        if res.status_code == 403:
            raise DirectDownloadLinkException(
                'ERROR: GDFlix Cloudflare challenge — link may be dead or the domain rotated.')
        instant = HTML(res.text).xpath("//a[contains(@href, 'instant')]/@href")
        if not instant:
            raise DirectDownloadLinkException('ERROR: GDFlix instant download link not found')
        res = session.get(instant[0], allow_redirects=False, timeout=30)
        loc = (res.headers.get('location') or '').strip()
    if not loc:
        raise DirectDownloadLinkException('ERROR: GDFlix file not found or expired')
    durl = parse_qs(urlparse(loc).query).get('url', [loc])[0]
    if not durl.startswith('http'):
        raise DirectDownloadLinkException('ERROR: GDFlix returned an unusable link')
    return durl


def gd_index(url, auth):
    if not auth:
        auth = ("admin", "admin")
    try:
        _title = url.rstrip('/').split("/")[-1]
    except Exception as e:
        raise DirectDownloadLinkException(f"ERROR: {e.__class__.__name__}")

    details = {'contents': [], 'title': unquote(_title), 'total_size': 0}

    def __fetch_links(url, folderPath, username, password):
        with create_scraper() as session:
            payload = {
                "id": "",
                "type": "folder",
                "username": username,
                "password": password,
                "page_token": "",
                "page_index": 0
            }
            try:
                data = (session.post(url, json=payload)).json()
            except:
                raise DirectDownloadLinkException("Use Latest Bhadoo Index Link")
        
        if "data" in data:
            for file_info in data["data"]["files"]:
                if file_info.get("mimeType", "") == "application/vnd.google-apps.folder":
                    if not folderPath: 
                         newFolderPath = path.join(details['title'], file_info["name"]) 
                    else: 
                         newFolderPath = path.join(folderPath, file_info["name"])
                    __fetch_links(f"{url}{file_info['name']}/", newFolderPath, username, password)
                else:
                    if not folderPath:
                        folderPath = details['title']
                    item = { 
                         "path": path.join(folderPath),
                         "filename": unquote(file_info["name"]),
                         "url": urljoin(url, file_info.get("link", "") or ""), 
                     } 
                    if 'size' in file_info:
                         details['total_size'] += int(file_info["size"])
                    details['contents'].append(item)

    try:
        __fetch_links(url, "", auth[0], auth[1])
    except Exception as e:
        raise DirectDownloadLinkException(e)
    if len(details['contents']) == 1:
        return details['contents'][0]['url']
    return details


def filepress(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            raw = urlparse(url)
            json_data = {
                'id': raw.path.split('/')[-1],
                'method': 'publicDownlaod',
            }
            api = f'{raw.scheme}://{raw.hostname}/api/file/downlaod/'
            res = session.post(api, headers={'Referer': f'{raw.scheme}://{raw.hostname}'}, json=json_data).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if 'data' not in res:
        raise DirectDownloadLinkException(f'ERROR: {res["statusText"]}')
    return f'https://drive.google.com/uc?id={res["data"]}&export=download'

def jiodrive(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            cookies = {
                    'access_token': config_dict['JIODRIVE_TOKEN']
            }

            data = {
                'id': url.split("/")[-1]
            }

            resp = session.post('https://www.jiodrive.xyz/ajax.php?ajax=download', cookies=cookies, data=data).json()

        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if resp['code'] != '200':
            raise DirectDownloadLinkException("ERROR: The user's Drive storage quota has been exceeded.")
        return resp['file']
        
def gdtot(url):
    cget = create_scraper().request
    try:
        res = cget('GET', f'https://gdtot.pro/file/{url.split("/")[-1]}')
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    token_url = HTML(res.text).xpath("//a[contains(@class,'inline-flex items-center justify-center')]/@href")
    if not token_url:
        try:
            url = cget('GET', url).url
            p_url = urlparse(url)
            res = cget("POST", f"{p_url.scheme}://{p_url.hostname}/ddl", data={'dl': str(url.split('/')[-1])})
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        if (drive_link := findall(r"myDl\('(.*?)'\)", res.text)) and "drive.google.com" in drive_link[0]:
            return drive_link[0]
        elif config_dict['GDTOT_CRYPT']:
            cget('GET', url, cookies={'crypt': config_dict['GDTOT_CRYPT']})
            p_url = urlparse(url)
            js_script = cget('POST', f"{p_url.scheme}://{p_url.hostname}/dld", data={'dwnld': url.split('/')[-1]})
            g_id = findall('gd=(.*?)&', js_script.text)
            try:
                decoded_id = b64decode(str(g_id[0])).decode('utf-8')
            except:
                raise DirectDownloadLinkException("ERROR: Try in your browser, mostly file not found or user limit exceeded!")
            return f'https://drive.google.com/open?id={decoded_id}'
        else:
            raise DirectDownloadLinkException('ERROR: Drive Link not found, Try in your broswer! GDTOT_CRYPT not Provided, it increases efficiency!')
    token_url = token_url[0]
    try:
        token_page = cget('GET', token_url)
    except Exception as e:
        raise DirectDownloadLinkException(
            f'ERROR: {e.__class__.__name__} with {token_url}'
        ) from e
    path = findall('\("(.*?)"\)', token_page.text)
    if not path:
        raise DirectDownloadLinkException('ERROR: Cannot bypass this')
    path = path[0]
    raw = urlparse(token_url)
    final_url = f'{raw.scheme}://{raw.hostname}{path}'
    return sharer_scraper(final_url)


def sharer_scraper(url):
    cget = create_scraper().request
    try:
        url = cget('GET', url).url
        raw = urlparse(url)
        header = {"useragent": "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.10 (KHTML, like Gecko) Chrome/7.0.548.0 Safari/534.10"}
        res = cget('GET', url, headers=header)
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    key = findall('"key",\s+"(.*?)"', res.text)
    if not key:
        raise DirectDownloadLinkException("ERROR: Key not found!")
    key = key[0]
    if not HTML(res.text).xpath("//button[@id='drc']"):
        raise DirectDownloadLinkException("ERROR: This link don't have direct download button")
    boundary = uuid4()
    headers = {
        'Content-Type': f'multipart/form-data; boundary=----WebKitFormBoundary{boundary}',
        'x-token': raw.hostname,
        'useragent': 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.10 (KHTML, like Gecko) Chrome/7.0.548.0 Safari/534.10'
    }

    data = f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="action"\r\n\r\ndirect\r\n' \
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="key"\r\n\r\n{key}\r\n' \
        f'------WebKitFormBoundary{boundary}\r\nContent-Disposition: form-data; name="action_token"\r\n\r\n\r\n' \
        f'------WebKitFormBoundary{boundary}--\r\n'
    try:
        res = cget("POST", url, cookies=res.cookies,
                   headers=headers, data=data).json()
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
    if "url" not in res:
        raise DirectDownloadLinkException('ERROR: Drive Link not found, Try in your broswer')
    if "drive.google.com" in res["url"]:
        return res["url"]
    try:
        res = cget('GET', res["url"])
    except Exception as e:
        raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if (drive_link := HTML(res.text).xpath("//a[contains(@class,'btn')]/@href")) and "drive.google.com" in drive_link[0]:
        return drive_link[0]
    else:
        raise DirectDownloadLinkException('ERROR: Drive Link not found, Try in your broswer')



def wetransfer(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            splited_url = url.split('/')
            json_data = {
                'security_hash': splited_url[-1],
                'intent': 'entire_transfer'
            }
            res = session.post(f'https://wetransfer.com/api/v4/transfers/{splited_url[-2]}/download', json=json_data).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if "direct_link" in res:
        return res["direct_link"]
    elif "message" in res:
        raise DirectDownloadLinkException(f"ERROR: {res['message']}")
    elif "error" in res:
        raise DirectDownloadLinkException(f"ERROR: {res['error']}")
    else:
        raise DirectDownloadLinkException("ERROR: cannot find direct link")


def akmfiles(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            json_data = {
                'op': 'download2',
                'id': url.split('/')[-1]
            }
            res = session.post('POST', url, data=json_data)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if (direct_link := HTML(res.text).xpath("//a[contains(@class,'btn btn-dow')]/@href")):
        return direct_link[0]
    else:
        raise DirectDownloadLinkException('ERROR: Direct link not found')

def shrdsk(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            res = session.get(f'https://us-central1-affiliate2apk.cloudfunctions.net/get_data?shortid={url.split("/")[-1]}')
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if res.status_code != 200:
        raise DirectDownloadLinkException(f'ERROR: Status Code {res.status_code}')
    res = res.json()
    if ("type" in res and res["type"].lower() == "upload" and "video_url" in res):
        return res["video_url"]
    raise DirectDownloadLinkException("ERROR: cannot find direct link")


def linkbox(url):
    with create_scraper() as session:
        try:
            url = session.get(url).url
            res = session.get(f'https://www.linkbox.to/api/file/detail?itemId={url.split("/")[-1]}').json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if 'data' not in res:
        raise DirectDownloadLinkException('ERROR: Data not found!!')
    data = res['data']
    if not data:
        raise DirectDownloadLinkException('ERROR: Data is None!!')
    if 'itemInfo' not in data:
        raise DirectDownloadLinkException('ERROR: itemInfo not found!!')
    itemInfo = data['itemInfo']
    if 'url' not in itemInfo:
        raise DirectDownloadLinkException('ERROR: url not found in itemInfo!!')
    if "name" not in itemInfo:
        raise DirectDownloadLinkException('ERROR: Name not found in itemInfo!!')
    name = quote(itemInfo["name"])
    raw = itemInfo['url'].split("/", 3)[-1]
    return f'https://wdl.nuplink.net/{raw}&filename={name}'


def route_intercept(route, request):
    if request.resource_type == 'script':
        route.abort()
    else:
        route.continue_()


def mediafireFolder(url):
    try:
        raw = url.split('/', 4)[-1]
        folderkey = raw.split('/', 1)[0]
        folderkey = folderkey.split(',')
    except:
        raise DirectDownloadLinkException('ERROR: Could not parse ')
    if len(folderkey) == 1:
        folderkey = folderkey[0]
    details = {'contents': [], 'title': '', 'total_size': 0, 'header': ''}

    session = req_session()
    adapter = HTTPAdapter(max_retries=Retry(
        total=10, read=10, connect=10, backoff_factor=0.3))
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session = create_scraper(
        browser={"browser": "firefox", "platform": "windows", "mobile": False},
        delay=10,
        sess=session,
    )
    folder_infos = []

    def __get_info(folderkey):
        try:
            if isinstance(folderkey, list):
                folderkey = ','.join(folderkey)
            _json = session.post('https://www.mediafire.com/api/1.5/folder/get_info.php', data={
                'recursive': 'yes',
                'folder_key': folderkey,
                'response_format': 'json'
            }).json()
        except Exception as e:
            raise DirectDownloadLinkException(
                f"ERROR: {e.__class__.__name__} While getting info")
        _res = _json['response']
        if 'folder_infos' in _res:
            folder_infos.extend(_res['folder_infos'])
        elif 'folder_info' in _res:
            folder_infos.append(_res['folder_info'])
        elif 'message' in _res:
            raise DirectDownloadLinkException(f"ERROR: {_res['message']}")
        else:
            raise DirectDownloadLinkException("ERROR: something went wrong!")

    try:
        __get_info(folderkey)
    except Exception as e:
        raise DirectDownloadLinkException(e)
    details['title'] = folder_infos[0]["name"]

    def __scraper(url):
        try:
            html = HTML(session.get(url).text)
        except Exception:
            return
        if final_link := html.xpath("//a[@id='downloadButton']/@href"):
            return final_link[0]

    def __get_content(folderKey, folderPath='', content_type='folders'):
        try:
            params = {
                'content_type': content_type,
                'folder_key': folderKey,
                'response_format': 'json',
            }
            _json = session.get(
                'https://www.mediafire.com/api/1.5/folder/get_content.php', params=params).json()
        except Exception as e:
            raise DirectDownloadLinkException(
                f"ERROR: {e.__class__.__name__} While getting content")
        _res = _json['response']
        if 'message' in _res:
            raise DirectDownloadLinkException(f"ERROR: {_res['message']}")
        _folder_content = _res['folder_content']
        if content_type == 'folders':
            folders = _folder_content['folders']
            for folder in folders:
                if folderPath:
                    newFolderPath = path.join(folderPath, folder["name"])
                else:
                    newFolderPath = path.join(folder["name"])
                __get_content(folder['folderkey'], newFolderPath)
            __get_content(folderKey, folderPath, 'files')
        else:
            files = _folder_content['files']
            for file in files:
                item = {}
                if not (_url := __scraper(file['links']['normal_download'])):
                    continue
                item['filename'] = file["filename"]
                if not folderPath:
                    folderPath = details['title']
                item['path'] = path.join(folderPath)
                item['url'] = _url
                if 'size' in file:
                    size = file["size"]
                    if isinstance(size, str) and size.isdigit():
                        size = float(size)
                    details['total_size'] += size
                details['contents'].append(item)

    try:
        for folder in folder_infos:
            __get_content(folder['folderkey'], folder['name'])
    except Exception as e:
        raise DirectDownloadLinkException(e)
    finally:
        session.close()
    if len(details['contents']) == 1:
        return (details['contents'][0]['url'], details['header'])
    return details


def doods(url):
    if "/e/" in url:
        url = url.replace("/e/", "/d/")
    parsed_url = urlparse(url)
    with create_scraper() as session:
        try:
            html = HTML(session.get(url).text)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__} While fetching token link') from e
        if not (link := html.xpath("//div[@class='download-content']//a/@href")):
            raise DirectDownloadLinkException('ERROR: Token Link not found or maybe not allow to download! open in browser.')
        link = f'{parsed_url.scheme}://{parsed_url.hostname}{link[0]}'
        sleep(2)
        try:
            _res = session.get(link)
        except Exception as e:
            raise DirectDownloadLinkException(
                f'ERROR: {e.__class__.__name__} While fetching download link') from e
    if not (link := search(r"window\.open\('(\S+)'", _res.text)):
        raise DirectDownloadLinkException("ERROR: Download link not found try again")
    return (link.group(1), f'Referer: {parsed_url.scheme}://{parsed_url.hostname}/')

def easyupload(url):
    if "::" in url:
        _password = url.split("::")[-1]
        url = url.split("::")[-2]
    else:
        _password = ''
    file_id = url.split("/")[-1]
    with create_scraper() as session:
        try:
            _res = session.get(url)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
        first_page_html = HTML(_res.text)
        if first_page_html.xpath("//h6[contains(text(),'Password Protected')]") and not _password:
            raise DirectDownloadLinkException(f"ERROR:\n{PASSWORD_ERROR_MESSAGE.format(url)}")
        if not (match := search(r'https://eu(?:[1-9][0-9]?|100)\.easyupload\.io/action\.php', _res.text)):
            raise DirectDownloadLinkException("ERROR: Failed to get server for EasyUpload Link")
        action_url = match.group()
        session.headers.update({'referer': 'https://easyupload.io/'})
        recaptcha_params = {
            'k': '6LfWajMdAAAAAGLXz_nxz2tHnuqa-abQqC97DIZ3',
            'ar': '1',
            'co': 'aHR0cHM6Ly9lYXN5dXBsb2FkLmlvOjQ0Mw..',
            'hl': 'en',
            'v': '0hCdE87LyjzAkFO5Ff-v7Hj1',
            'size': 'invisible',
            'cb': 'c3o1vbaxbmwe'
        }
        if not (captcha_token :=get_captcha_token(session, recaptcha_params)):
            raise DirectDownloadLinkException('ERROR: Captcha token not found')
        try:
            data = {'type': 'download-token',
                    'url': file_id,
                    'value': _password,
                    'captchatoken': captcha_token,
                    'method': 'regular'}
            json_resp = session.post(url=action_url, data=data).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if 'download_link' in json_resp:
        return json_resp['download_link']
    elif 'data' in json_resp:
        raise DirectDownloadLinkException(
            f"ERROR: Failed to generate direct link due to {json_resp['data']}")
    raise DirectDownloadLinkException(
        "ERROR: Failed to generate direct link from EasyUpload.")



def filelions(url):
    if not config_dict['FILELION_API']:
        raise DirectDownloadLinkException('ERROR: FILELION_API is not provided get it from https://filelions.com/?op=my_account')
    file_code = url.split('/')[-1]
    quality = ''
    if bool(file_code.endswith(('_o', '_h', '_n', '_l'))):
        spited_file_code = file_code.rsplit('_', 1)
        quality = spited_file_code[1]
        file_code = spited_file_code[0]
    parsed_url = urlparse(url)
    url = f'{parsed_url.scheme}://{parsed_url.hostname}/{file_code}'
    with Session() as session:
        try:
            _res = session.get('https://api.filelions.com/api/file/direct_link', params={'key': config_dict['FILELION_API'], 'file_code': file_code, 'hls': '1'}).json()
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}') from e
    if _res['status'] != 200:
        raise DirectDownloadLinkException(f"ERROR: {_res['msg']}")
    result = _res['result']
    if not result['versions']:
        raise DirectDownloadLinkException("ERROR: No versions available")
    error = '\nProvide a quality to download the video\nAvailable Quality:'
    for version in result['versions']:
        if quality == version['name']:
            return version['url']
        elif version['name'] == 'l':
            error += f"\nLow"
        elif version['name'] == 'n':
            error += f"\nNormal"
        elif version['name'] == 'o':
            error += f"\nOriginal"
        elif version['name'] == "h":
            error += f"\nHD"
        error +=f" <code>{url}_{version['name']}</code>"
    raise DirectDownloadLinkException(f'ERROR: {error}')



def streamvid(url: str):
    file_code = url.split('/')[-1]
    parsed_url = urlparse(url)
    url = f'{parsed_url.scheme}://{parsed_url.hostname}/d/{file_code}'
    quality_defined = bool(url.endswith(('_o', '_h', '_n', '_l')))
    with create_scraper() as session:
        try:
            html = HTML(session.get(url).text)
        except Exception as e:
            raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
        if quality_defined:
            data = {}
            if not (inputs := html.xpath('//form[@id="F1"]//input')):
                raise DirectDownloadLinkException('ERROR: No inputs found')
            for i in inputs:
                if key := i.get('name'):
                    data[key] = i.get('value')
            try:
                html = HTML(session.post(url, data=data).text)
            except Exception as e:
                raise DirectDownloadLinkException(f'ERROR: {e.__class__.__name__}')
            if not (script := html.xpath('//script[contains(text(),"document.location.href")]/text()')):
                if error := html.xpath('//div[@class="alert alert-danger"][1]/text()[2]'):
                    raise DirectDownloadLinkException(f'ERROR: {error[0]}')
                raise DirectDownloadLinkException("ERROR: direct link script not found!")
            if directLink:=findall(r'document\.location\.href="(.*)"', script[0]):
                return directLink[0]
            raise DirectDownloadLinkException("ERROR: direct link not found! in the script")
        elif (qualities_urls := html.xpath('//div[@id="dl_versions"]/a/@href')) and (qualities := html.xpath('//div[@id="dl_versions"]/a/text()[2]')):
            error = '\nProvide a quality to download the video\nAvailable Quality:'
            for quality_url, quality in zip(qualities_urls, qualities):
                error += f"\n{quality.strip()} <code>{quality_url}</code>"
            raise DirectDownloadLinkException(f'ERROR: {error}')
        elif error:= html.xpath('//div[@class="not-found-text"]/text()'):
            raise DirectDownloadLinkException(f'ERROR: {error[0]}')
        raise DirectDownloadLinkException('ERROR: Something went wrong')
