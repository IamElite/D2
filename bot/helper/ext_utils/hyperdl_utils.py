"""HyperDL — WZML-X parallel TG download is multi-client GetFile.

Here: prefer user session (MTProto) then bot. Full chunk pipeline needs
HELPER_TOKENS like HyperUP; without them we must not crash.
"""
from logging import getLogger

from ... import bot, user

LOGGER = getLogger(__name__)


def pick_download_client(session="bot"):
    try:
        if session == "user" and user:
            return user
        if user:
            return user
        return bot
    except Exception as e:
        LOGGER.error("HyperDL pick fallback bot: %s", e)
        return bot
