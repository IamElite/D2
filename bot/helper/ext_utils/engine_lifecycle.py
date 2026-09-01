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
        from ... import get_client
        c = get_client()
        c.app_set_preferences({"dht": False, "pex": False, "lsd": False})
        c.auth_log_out()
        LOGGER.info("Idle: DHT/PEX off (processes still running)")
    except Exception as e:
        LOGGER.warning("Idle DHT off skipped: %s", e)


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
