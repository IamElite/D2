"""Back-compat. Real idle = stop qBit/aria2 (engine_lifecycle)."""
from .engine_lifecycle import idle_now, ensure_aria2, ensure_qbit, stop_heavy


async def _set_dht(on: bool):
    if on:
        ensure_qbit()


async def start_idle_housekeep():
    return
