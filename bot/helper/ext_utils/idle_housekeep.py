"""One-shot rest when no bot tasks. Must not poll qBit every 45s (that WAS extra CPU)."""
from logging import getLogger

LOGGER = getLogger(__name__)

_rested = False
_dht_on = False


async def idle_now():
    """Call when last task ends. Safe to call often — runs work once."""
    global _rested
    if _rested:
        return
    from ... import download_dict, download_dict_lock, Interval
    async with download_dict_lock:
        if download_dict:
            return
    _rested = True
    if Interval:
        try:
            Interval[0].cancel()
        except Exception:
            pass
        Interval.clear()
    await _set_dht(False)
    await _purge_engines()
    LOGGER.info("Idle rest: DHT off (once)")


async def start_idle_housekeep():
    from asyncio import sleep
    from ... import download_dict, download_dict_lock

    global _rested
    LOGGER.info("Idle housekeep: check every 3 min only")
    while True:
        try:
            await sleep(180)
            async with download_dict_lock:
                n = len(download_dict)
            if n:
                _rested = False
                continue
            await idle_now()
        except Exception as e:
            LOGGER.error("idle housekeep: %s", e)


async def _set_dht(on: bool):
    global _dht_on
    if on == _dht_on:
        return
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
        LOGGER.warning("aria2 DHT: %s", e)
    try:
        client = await sync_to_async(get_client)
        await sync_to_async(
            client.app_set_preferences,
            {"dht": on, "pex": on, "lsd": False},
        )
        await sync_to_async(client.auth_log_out)
    except Exception as e:
        LOGGER.warning("qBit DHT: %s", e)
    _dht_on = on


async def _purge_engines():
    from ... import get_client, QbTorrents, qb_listener_lock
    from .bot_utils import sync_to_async

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
