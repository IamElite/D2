"""HyperUP — WZML-X style helper-bot / user-session upload picker.

Does not replace pyrogramEngine; Engine calls pick_upload_client().
Missing tokens or start errors never abort the bot.
"""
from asyncio import gather
from logging import getLogger

from pyrogram import Client, enums

from ... import bot, user, TELEGRAM_API, TELEGRAM_HASH, LOGGER as ROOT
from ..telegram_helper.tg_transfer import helper_bots, helper_loads, pick_hyper_client, release_hyper_client

LOGGER = getLogger(__name__)


async def start_helper_bots(tokens: str):
    if not tokens or not str(tokens).strip():
        LOGGER.info("HyperUP: no HELPER_TOKENS — using bot/user only")
        return
    async def _one(no, token):
        try:
            h = Client(
                f"hyper-hbot{no}",
                api_id=TELEGRAM_API,
                api_hash=TELEGRAM_HASH,
                bot_token=token.strip(),
                parse_mode=enums.ParseMode.HTML,
                no_updates=True,
                in_memory=True,
                sleep_threshold=60,
            )
            await h.start()
            helper_bots[no] = h
            helper_loads[no] = 0
            uname = getattr(h.me, "username", None) or h.me.first_name
            ROOT.info(f"HyperUP Helper Bot #{no} [@{uname}] ID={h.me.id} Started!")
        except Exception as e:
            ROOT.error(f"HyperUP Helper Bot #{no} failed (ignored): {e}")

    toks = [t for t in str(tokens).split() if t.strip()]
    ROOT.info(f"HyperUP: starting {len(toks)} helper bot(s) from HELPER_TOKENS")
    await gather(*(_one(i, t) for i, t in enumerate(toks, start=1)))
    if helper_bots:
        names = ", ".join(
            f"#{n} @{getattr(b.me, 'username', None) or b.me.first_name}"
            for n, b in helper_bots.items()
        )
        ROOT.info(f"HyperUP ready: {len(helper_bots)} helper(s) — {names}")
    else:
        ROOT.warning("HyperUP: no helper bots running — upload uses main bot/user")


def pick_upload_client(prefer_user_for_small=True, file_size=0):
    """Crash-safe: always returns a live client."""
    try:
        if file_size and file_size > 2097152000 and user:
            return user, None
        if helper_bots:
            return pick_hyper_client()
        if prefer_user_for_small and user:
            return user, None
        return bot, None
    except Exception as e:
        ROOT.error("pick_upload_client fallback bot: %s", e)
        return bot, None
