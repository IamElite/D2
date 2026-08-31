"""Start qBit/aria2 only when a task needs them. Stop both when no tasks.

Telegram leech does not start them. Gunicorn + bot stay (Heroku + commands).
"""
from logging import getLogger
from os import getcwd
from socket import create_connection
from subprocess import run as srun
from time import sleep

LOGGER = getLogger(__name__)

_qbit = False
_aria = False
_aria_listen = False


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


def _hook_aria2_listener():
    global _aria_listen
    if _aria_listen:
        return
    try:
        from ..listeners.aria2_listener import start_aria2_listener
        start_aria2_listener()
        _aria_listen = True
    except Exception as e:
        LOGGER.warning("aria2 listener: %s", e)


def ensure_aria2():
    global _aria
    if _port_up(6800):
        _aria = True
        _hook_aria2_listener()
        return
    aria_bin, _ = _bins()
    LOGGER.info("Starting aria2 for a task")
    srun([aria_bin, "--conf-path=/usr/src/app/a2c.conf"], check=False)
    for _ in range(40):
        if _port_up(6800):
            _aria = True
            _hook_aria2_listener()
            return
        sleep(0.25)
    LOGGER.error("aria2 did not listen on 6800")


def ensure_qbit():
    global _qbit
    if _port_up(8090):
        _qbit = True
        return
    _, qbit_bin = _bins()
    LOGGER.info("Starting qBit for a task")
    srun([qbit_bin, "-d", f"--profile={getcwd()}"], check=False)
    for _ in range(50):
        if _port_up(8090):
            _qbit = True
            return
        sleep(0.25)
    LOGGER.error("qBit did not listen on 8090")


def stop_heavy():
    """Kill aria2 + qBit. Call only when download_dict is empty."""
    global _qbit, _aria
    aria_bin, qbit_bin = _bins()
    for name in (aria_bin, qbit_bin):
        try:
            srun(["pkill", "-9", "-f", name], check=False)
        except Exception:
            pass
    _qbit = False
    _aria = False
    _aria_listen = False
    LOGGER.info("No tasks — aria2 and qBit stopped")


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
