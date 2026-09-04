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
        c.auth_log_out()
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


async def idle_now():
    from ... import download_dict, download_dict_lock, Interval
    async with download_dict_lock:
        if download_dict:
            return
    if Interval:
        try:
            Interval[0].cancel()
        except Exception:
            pass
        Interval.clear()
    stop_heavy()


def qbit_port_down(timeout=3):
    """Boot-stop verify: 8090 down hone ka wait (max timeout s) — True=down."""
    from time import sleep as _sleep
    for _ in range(timeout * 2):
        if not _port_up(8090):
            return True
        _sleep(0.5)
    return not _port_up(8090)


def log_mem(tag='tick'):
    """CL: process-wise RSS breakdown — qBit/gunicorn/aria2 presence ka live saboot."""
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
        LOGGER.info(f"MEM[{tag}]: bot={cur.memory_info().rss >> 20}MB | {kid_s or 'no-children'}")
    except Exception as e:
        LOGGER.error(f"MEM log failed: {e}")


async def log_mem_async(tag='perf'):
    log_mem(tag)
