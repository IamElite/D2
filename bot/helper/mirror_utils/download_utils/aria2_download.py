#!/usr/bin/env python3
from re import search as re_search
from uuid import uuid4
from urllib.parse import parse_qs, urlparse
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, path as aiopath
from aiohttp import ClientSession as aioClientSession, ClientTimeout

from .... import aria2, download_dict_lock, download_dict, LOGGER, config_dict, aria2_options, aria2c_global, non_queued_dl, queue_dict_lock
from ...ext_utils.bot_utils import bt_selection_buttons, sync_to_async
from ..status_utils.aria2_status import Aria2Status
from ...telegram_helper.message_utils import sendStatusMessage, sendMessage
from ...ext_utils.task_manager import is_queued


TORRENT_MAX_SIZE = 10 * 1024 * 1024  # 10MB cap — .torrent files are KB-scale

BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'


async def _prefetch_torrent(link, user_headers=None):
    """HTTP(S) .torrent URL ko bot-side fetch karo — kuch trackers aria2c ke
    server-side fetch ko HTTP 500 dete hain (IP/TLS block). Fetch OK ho to temp
    file path return, warna None (caller direct aria2.add pe fallback karega)."""
    if not isinstance(link, str) or not link.startswith(('http://', 'https://')) or not _bt_link(link):
        return None
    p = urlparse(link)
    req_headers = {
        'User-Agent': BROWSER_UA,
        'Accept': '*/*',
        'Referer': f'{p.scheme}://{p.netloc}/',
    }
    if user_headers:
        if isinstance(user_headers, str):
            user_headers = [user_headers]
        for h in user_headers:
            if isinstance(h, str) and ':' in h:
                k, v = h.split(':', 1)
                req_headers[k.strip()] = v.strip()
    tmp_path = f'/tmp/{uuid4().hex}.torrent'
    try:
        async with aioClientSession(trust_env=True) as session:
            async with session.get(link, headers=req_headers, timeout=ClientTimeout(total=30), verify_ssl=False) as resp:
                if resp.status != 200:
                    LOGGER.warning(f'Torrent pre-fetch: HTTP {resp.status}, fallback to direct add')
                    return None
                ctype = resp.headers.get('Content-Type', '').lower()
                data = await resp.read()
        if not data or len(data) > TORRENT_MAX_SIZE:
            LOGGER.warning('Torrent pre-fetch: empty/oversized response, fallback to direct add')
            return None
        if b'4:info' not in data[:8192] and 'bittorrent' not in ctype:
            LOGGER.warning('Torrent pre-fetch: not a bittorrent payload, fallback to direct add')
            return None
        async with aiopen(tmp_path, 'wb') as f:
            await f.write(data)
        LOGGER.info(f'Torrent pre-fetched via HTTP ({len(data)} bytes): {link[:100]}')
        return tmp_path
    except Exception as e:
        LOGGER.warning(f'Torrent pre-fetch failed ({e}); fallback to direct add')
        try:
            if await aiopath.exists(tmp_path):
                await aioremove(tmp_path)
        except Exception:
            pass
        return None


def _bt_link(link):
    if not isinstance(link, str):
        return False
    if link.startswith("magnet:"):
        return True
    return link.lower().split("?", 1)[0].rstrip("/").endswith(".torrent")


async def add_aria2c_download(link, path, listener, filename, header, ratio, seed_time):
    from ...ext_utils.engine_lifecycle import ensure_aria2
    await sync_to_async(ensure_aria2)
    a2c_opt = {**aria2_options}
    [a2c_opt.pop(k) for k in aria2c_global if k in aria2_options]
    a2c_opt['dir'] = path
    if filename:
        a2c_opt['out'] = filename
    elif 'response-content-disposition=' in link:
        q = parse_qs(urlparse(link).query).get('response-content-disposition', [''])[0]
        if m := re_search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', q):
            a2c_opt['out'] = m.group(1).strip().replace('/', '_')
    if header:
        a2c_opt['header'] = header
    if ratio:
        a2c_opt['seed-ratio'] = ratio
    if seed_time:
        a2c_opt['seed-time'] = seed_time
    if TORRENT_TIMEOUT := config_dict['TORRENT_TIMEOUT']:
        a2c_opt['bt-stop-timeout'] = f'{TORRENT_TIMEOUT}'
    added_to_queue, event = await is_queued(listener.uid)
    if added_to_queue:
        if link.startswith('magnet:'):
            a2c_opt['pause-metadata'] = 'true'
        else:
            a2c_opt['pause'] = 'true'
    if _bt_link(link):
        a2c_opt["follow-torrent"] = "true"
        a2c_opt["bt-max-peers"] = "80"
        a2c_opt["bt-request-peer-speed-limit"] = "1K"
        a2c_opt["max-upload-limit"] = "256K"
        a2c_opt["check-integrity"] = "false"
        a2c_opt["realtime-chunk-checksum"] = "false"
        a2c_opt["bt-hash-check-seed"] = "false"
        a2c_opt["seed-ratio"] = "0.0"
        a2c_opt["seed-time"] = "0"
        a2c_opt["enable-dht"] = "true"
        a2c_opt["enable-peer-exchange"] = "true"
        try:
            await sync_to_async(aria2.set_global_options, {
                "enable-dht": "true",
                "enable-peer-exchange": "true",
                "bt-enable-lpd": "false",
                "disable-ipv6": "false",
            })
        except Exception:
            pass
    try:
        if await aiopath.exists(link):
            got = await sync_to_async(aria2.add_torrent, link, None, a2c_opt)
        else:
            torrent_file = await _prefetch_torrent(link, header)
            if torrent_file:
                try:
                    got = await sync_to_async(aria2.add_torrent, torrent_file, None, a2c_opt)
                finally:
                    await aioremove(torrent_file)
            else:
                got = await sync_to_async(aria2.add, link, a2c_opt)
        download = got[0] if isinstance(got, (list, tuple)) else got
    except Exception as e:
        LOGGER.info(f"Aria2c Download Error: {e}")
        await sendMessage(listener.message, f'{e}')
        return
    if await aiopath.exists(link):
        await aioremove(link)
    if download.error_message:
        error = str(download.error_message).replace('<', ' ').replace('>', ' ')
        LOGGER.info(f"Aria2c Download Error: {error}")
        await sendMessage(listener.message, error)
        return

    gid = download.gid
    name = download.name
    async with download_dict_lock:
        download_dict[listener.uid] = Aria2Status(
            gid, listener, queued=added_to_queue)
    if added_to_queue:
        LOGGER.info(f"Added to Queue/Download: {name}. Gid: {gid}")
        if not listener.select or not download.is_torrent:
            await sendStatusMessage(listener.message)
    else:
        async with queue_dict_lock:
            non_queued_dl.add(listener.uid)
        LOGGER.info(f"Aria2Download started: {name}. Gid: {gid}")
        if _bt_link(link):
            try:
                await sync_to_async(aria2.set_global_options, {
                    "enable-dht": "true",
                    "enable-peer-exchange": "true",
                })
            except Exception:
                pass

    await listener.onDownloadStart()

    if not added_to_queue and (not listener.select or not config_dict['BASE_URL']):
        await sendStatusMessage(listener.message)
    elif listener.select and download.is_torrent and not download.is_metadata:
        if not added_to_queue:
            await sync_to_async(aria2.client.force_pause, gid)
        SBUTTONS = bt_selection_buttons(gid)
        msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
        await sendMessage(listener.message, msg, SBUTTONS)

    if added_to_queue:
        await event.wait()

        async with download_dict_lock:
            if listener.uid not in download_dict:
                return
            download = download_dict[listener.uid]
            download.queued = False
            new_gid = download.gid()

        await sync_to_async(aria2.client.unpause, new_gid)
        LOGGER.info(f'Start Queued Download from Aria2c: {name}. Gid: {gid}')

        async with queue_dict_lock:
            non_queued_dl.add(listener.uid)
