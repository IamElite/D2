"""When download_dict is empty, stop DHT/PEX leftover torrents and status Interval.

Idle 9h @ 70% CPU is qBit/aria2 DHT + leftover torrents + leaked status loop,
not Python hashing.
"""
from asyncio import sleep
from gc import collect
from logging import getLogger

LOGGER = getLogger(__name__)

_idle_cycles = 0
_dht_on = True


async def start_idle_housekeep():
    from ... import download_dict, download_dict_lock, Interval
    from ..telegram_helper.message_utils import delete_all_messages

    global _idle_cycles, _dht_on
    LOGGER.info("Idle housekeep started (45s)")
    while True:
        try:
            await sleep(45)
            async with download_dict_lock:
                n = len(download_dict)
            if n:
                _idle_cycles = 0
                if not _dht_on:
                    await _set_dht(True)
                continue
            _idle_cycles += 1
            if _idle_cycles < 2:
                continue
            if Interval:
                try:
                    Interval[0].cancel()
                except Exception:
                    pass
                Interval.clear()
            try:
                await delete_all_messages()
            except Exception:
                pass
            await _purge_engines()
            if _dht_on:
                await _set_dht(False)
            collect()
            if _idle_cycles in (2, 80):
                LOGGER.info("Idle housekeep: no tasks — DHT off, leftovers purged")
        except Exception as e:
            LOGGER.error("idle housekeep: %s", e)


async def _set_dht(on: bool):
    global _dht_on
    from ... import aria2, get_client
    from .bot_utils import sync_to_async

    try:
        await sync_to_async(
            aria2.set_global_options,
            {
                "enable-dht": "true" if on else "false",
                "enable-peer-exchange": "true" if on else "false",
            },
        )
    except Exception as e:
        LOGGER.warning("aria2 DHT toggle: %s", e)
    try:
        client = await sync_to_async(get_client)
        await sync_to_async(
            client.app_set_preferences,
            {
                "dht": on,
                "pex": on,
                "lsd": False,
                "max_connec": 120 if on else 20,
                "max_connec_per_torrent": 60 if on else 10,
            },
        )
        await sync_to_async(client.auth_log_out)
    except Exception as e:
        LOGGER.warning("qBit DHT toggle: %s", e)
    _dht_on = on


async def _purge_engines():
    from ... import aria2, get_client, QbTorrents, qb_listener_lock
    from .bot_utils import sync_to_async

    try:
        downs = await sync_to_async(aria2.get_downloads)
        for d in downs or []:
            try:
                await sync_to_async(aria2.remove, [d], force=True, files=True, clean=True)
            except Exception:
                pass
    except Exception:
        pass
    try:
        client = await sync_to_async(get_client)
        tors = await sync_to_async(client.torrents_info)
        if tors:
            hashes = [t.hash for t in tors]
            await sync_to_async(client.torrents_delete, torrent_hashes=hashes, delete_files=True)
            LOGGER.info("Idle: removed %s leftover qBit torrent(s)", len(hashes))
        await sync_to_async(client.auth_log_out)
    except Exception as e:
        LOGGER.warning("idle qBit purge: %s", e)
    async with qb_listener_lock:
        QbTorrents.clear()
