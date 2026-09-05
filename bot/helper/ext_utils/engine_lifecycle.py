"""qBit/aria2 stay running (needed for listeners + commands).

NEVER pkill -f those binaries: the pattern can hit the bot. Idle = DHT off via API only.
"""
from logging import getLogger
from os import getcwd
from socket import create_connection
from subprocess import run as srun
from time import sleep

LOGGER = getLogger(__name__)


def _port_up(port):
    try:
        s = create_connection(("127.0.0.1", int(port)), timeout=0.4)
        s.close()
        return True
    except Exception:
        return False


def _bins():
    from ... import bot_cache
    pkgs = bot_cache.get("pkgs") or ["aria2c", "qbittorrent-nox"]
    return pkgs[0], pkgs[1]


def ensure_aria2():
    if _port_up(6800):
        return
    aria_bin, _ = _bins()
    LOGGER.info("Starting aria2 (was down)")
    srun([aria_bin, "--conf-path=/usr/src/app/a2c.conf"], check=False)
    for _ in range(40):
        if _port_up(6800):
            return
        sleep(0.25)
    LOGGER.error("aria2 did not listen on 6800")


def ensure_qbit():
    if _port_up(8090):
        return
    _, qbit_bin = _bins()
    LOGGER.info("Starting qBit (was down)")
    srun([qbit_bin, "-d", f"--profile={getcwd()}"], check=False)
    for _ in range(50):
        if _port_up(8090):
            return
        sleep(0.25)
    LOGGER.error("qBit did not listen on 8090")


def stop_heavy():
    if not _port_up(8090):
        return
    try:
        from ... import get_client, environ
        c = get_client()
        c.app_set_preferences({"dht": False, "pex": False, "lsd": False})
        if environ.get('QBIT_IDLE_STOP', '').lower() in ('0', 'false', 'no'):
            LOGGER.info("Idle: DHT/PEX off (processes still running)")
            return
        torrents = c.torrents_info()
        if torrents:
            LOGGER.info("Idle: qBit torrents active — process stays")
            return
        try:
            c.app_shutdown()
            LOGGER.info("Idle: qBit stopped (RAM freed) — auto-restarts on next qBit task")
        except Exception:
            LOGGER.info("Idle: DHT/PEX off (shutdown not available)")
    except Exception as e:
        LOGGER.warning("Idle stop skipped: %s", e)


async def idle_stop_if_free():
    """Idle-stop the heavy engines without touching the event loop.

    stop_heavy() does several blocking qBittorrent HTTP calls, so it must never
    run on the loop. It is also pointless while other tasks are still running,
    which is what made bulk mode freeze: every completion paid for it.
    """
    from ... import download_dict
    from .bot_utils import sync_to_async
    if len(download_dict) > 1:
        return
    await sync_to_async(stop_heavy)


async def idle_now():
    from ... import download_dict, download_dict_lock, Interval
    from .bot_utils import sync_to_async
    async with download_dict_lock:
        if download_dict:
            return
    if Interval:
        try:
            Interval[0].cancel()
        except Exception:
            pass
        Interval.clear()
    await sync_to_async(stop_heavy)


def qbit_port_down(timeout=3):
    """Boot-stop verify: 8090 down hone ka wait (max timeout s) — True=down."""
    from time import sleep as _sleep
    for _ in range(timeout * 2):
        if not _port_up(8090):
            return True
        _sleep(0.5)
    return not _port_up(8090)


def log_mem(tag='tick'):
    """CL/CK: process RSS + anon(real) vs page-cache cgroup RAM + live aria2
    connection/peer counts (proof of whether aria2 actually opens the requested
    sockets — if config says 16/200 but actives are 1-2, the swarm/host is the cap)."""
    try:
        from psutil import Process
        cur = Process()
        kids = {}
        for c in cur.children(recursive=True):
            try:
                kids[c.name()] = kids.get(c.name(), 0) + c.memory_info().rss
            except Exception:
                pass
        kid_s = ' '.join(f'{k}={v >> 20}MB' for k, v in sorted(kids.items()))
        # cgroup real-vs-cache RAM
        cg = ''
        try:
            from .bot_utils import get_container_memory, get_container_memory_breakdown
            cm = get_container_memory()
            anon, fc = get_container_memory_breakdown()
            if cm:
                tot = cm[1] >> 20
                anon_p = round(anon / cm[1] * 100, 1) if anon else 0.0
                cache_p = round((fc or 0) / cm[1] * 100, 1)
                cg = f" | cgroup: real={anon_p}% cache={cache_p}% (limit {tot}MB)"
        except Exception:
            pass
        # live aria2 actives: connections + peers per GID
        a2 = ''
        try:
            from ... import aria2
            acts = aria2.get_downloads()
            live = [(d) for d in acts if d.status == 'active' and d.total_length]
            parts = []
            for d in live[:6]:
                spd = (d.download_speed or 0) >> 20
                parts.append(f"{spd}MB/s conn={d.connections} peers={d.num_seeders}")
            if parts:
                a2 = f" | aria2[{len(live)}]: " + " ; ".join(parts)
        except Exception:
            pass
        LOGGER.info(f"MEM[{tag}]: bot={cur.memory_info().rss >> 20}MB | {kid_s or 'no-children'}{cg}{a2}")
    except Exception as e:
        LOGGER.error(f"MEM log failed: {e}")


async def log_mem_async(tag='perf'):
    log_mem(tag)
