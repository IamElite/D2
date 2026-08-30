"""WZML-X HypertgUpload (wzv3 hyperul_utils) adapted to this repo.

HyperUL is least-loaded helper/user/bot + send_video/document — not chunk-split.
HELPER_TOKENS extra bots must be admin in LEECH_LOG. Failures never abort boot.
"""
from asyncio import gather, sleep
from logging import getLogger
from os import path as ospath

from pyrogram import Client, StopTransmission, enums
from pyrogram.errors import FloodWait, PhotoInvalidDimensions

try:
    from pyrogram.errors import FloodPremiumWait
except ImportError:
    FloodPremiumWait = FloodWait

from ... import TELEGRAM_API, TELEGRAM_HASH, LOGGER as ROOT, bot, user, config_dict
from ..telegram_helper.tg_transfer import (
    HypertgTransfer,
    helper_bots,
    helper_loads,
    pick_hyper_client,
    release_hyper_client,
    reset_work_loads,
)

LOGGER = getLogger(__name__)


async def start_helper_bots(tokens: str):
    reset_work_loads()
    helper_bots.clear()
    helper_loads.clear()
    if bot:
        helper_bots[0] = bot
        helper_loads[0] = 0
    if not tokens or not str(tokens).strip():
        ROOT.info("HyperUP: no HELPER_TOKENS — main bot (+ user if set) only")
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
            st = h.start()
            if hasattr(st, "__await__"):
                await st
            helper_bots[no] = h
            helper_loads[no] = 0
            uname = getattr(h.me, "username", None) or h.me.first_name
            ROOT.info(f"HyperUP Helper Bot #{no} [@{uname}] ID={h.me.id} Started!")
        except Exception as e:
            ROOT.error(f"HyperUP Helper Bot #{no} failed (ignored): {e}")

    toks = [t for t in str(tokens).split() if t.strip()]
    ROOT.info(f"HyperUP: starting {len(toks)} helper bot(s) from HELPER_TOKENS")
    await gather(*(_one(i, t) for i, t in enumerate(toks, start=1)))
    reset_work_loads()
    if len(helper_bots) > 1:
        names = ", ".join(
            f"#{n} @{getattr(b.me, 'username', None) or getattr(b.me, 'first_name', n)}"
            for n, b in helper_bots.items()
            if n != 0
        )
        ROOT.info(f"HyperUP ready: {len(helper_bots) - 1} extra helper(s) — {names}")
    else:
        ROOT.warning("HyperUP: extra helpers failed — upload uses main bot/user")


def pick_upload_client(prefer_user_for_small=True, file_size=0):
    try:
        if file_size and file_size > 2097152000 and user:
            return user, None
        if len(helper_bots) > 1:
            return pick_hyper_client()
        if prefer_user_for_small and user:
            return user, None
        return bot, 0
    except Exception as e:
        ROOT.error("pick_upload_client fallback bot: %s", e)
        return bot, None


class HypertgUpload(HypertgTransfer):
    def __init__(self, obj):
        super().__init__(obj)
        self._up_file = ""
        self._file_progress = {}

    async def _progress(self, current, total, file_path):
        listener = self._listener
        if listener is not None and getattr(listener, "is_cancelled", False):
            raise StopTransmission()
        if self._obj is not None and getattr(self._obj, "_TgUploader__is_cancelled", False):
            raise StopTransmission()
        self._file_progress[file_path] = current
        total_done = sum(self._file_progress.values())
        if self._obj is not None:
            try:
                last = getattr(self._obj, "_TgUploader__last_uploaded", 0)
                setattr(self._obj, "_TgUploader__processed_bytes",
                        getattr(self._obj, "_TgUploader__processed_bytes", 0) + max(0, current - last))
                setattr(self._obj, "_TgUploader__last_uploaded", current)
            except Exception:
                pass
            if hasattr(self._obj, "_processed_bytes"):
                self._obj._processed_bytes = total_done

    async def _send_with_retry(self, send_func, **kwargs):
        while True:
            try:
                return await send_func(**kwargs)
            except (FloodWait, FloodPremiumWait) as f:
                LOGGER.warning(f"HypertgUL flood {getattr(f, 'value', 5)}s on {self._up_file}")
                await sleep(int(getattr(f, "value", 5)) + 1)

    async def _try_send(self, key, client, kwargs):
        from inspect import signature

        def _filt(fn, kw):
            try:
                params = signature(fn).parameters
                if any(p.kind == p.VAR_KEYWORD for p in params.values()):
                    return kw
                return {k: v for k, v in kw.items() if k in params}
            except Exception:
                return kw

        try:
            if key == "videos":
                return await self._send_with_retry(client.send_video, **_filt(client.send_video, kwargs))
            if key == "audios":
                return await self._send_with_retry(client.send_audio, **_filt(client.send_audio, kwargs))
            if key == "photos":
                return await self._send_with_retry(client.send_photo, **_filt(client.send_photo, kwargs))
            return await self._send_with_retry(client.send_document, **_filt(client.send_document, kwargs))
        except PhotoInvalidDimensions:
            kwargs.pop("thumb", None)
            kwargs.pop("video_cover", None)
            if key == "videos":
                return await self._send_with_retry(client.send_video, **_filt(client.send_video, kwargs))
            if key == "audios":
                return await self._send_with_retry(client.send_audio, **_filt(client.send_audio, kwargs))
            if key == "photos":
                return await self._send_with_retry(client.send_photo, **_filt(client.send_photo, kwargs))
            return await self._send_with_retry(client.send_document, **_filt(client.send_document, kwargs))

    async def _hyper_send(
        self,
        file_path,
        key,
        thumb,
        cap_mono,
        chat_id,
        reply_to_message_id,
        thread_id=None,
        duration=0,
        width=0,
        height=0,
        artist="",
        title="",
        user_only=False,
        reply_markup=None,
        progress=None,
    ):
        if user_only:
            candidates = {k: self.work_loads[k] for k in self.clients if k < 0}
            idx = min(candidates, key=candidates.get) if candidates else self._pick_client()
        else:
            idx = self._pick_client()
        client = self.clients.get(idx) or bot
        self.work_loads[idx] = self.work_loads.get(idx, 0) + 1
        ROOT.info(f"HypertgUL _hyper_send via client idx={idx} key={key} file={self._up_file}")
        try:
            kwargs = {
                "chat_id": chat_id,
                "disable_notification": True,
                "progress": progress or self._progress,
                "progress_args": (file_path,),
            }
            if cap_mono:
                kwargs["caption"] = cap_mono
            if reply_to_message_id:
                kwargs["reply_to_message_id"] = reply_to_message_id
            elif thread_id:
                kwargs["message_thread_id"] = thread_id
            if reply_markup is not None:
                kwargs["reply_markup"] = reply_markup
            if key == "videos":
                if duration:
                    kwargs["duration"] = duration
                if width:
                    kwargs["width"] = width
                if height:
                    kwargs["height"] = height
                if thumb:
                    kwargs["video_cover"] = thumb
                    kwargs["thumb"] = thumb
                kwargs["supports_streaming"] = True
                kwargs["video"] = file_path
            elif key == "audios":
                if duration:
                    kwargs["duration"] = duration
                if artist:
                    kwargs["performer"] = artist
                if title:
                    kwargs["title"] = title
                if thumb:
                    kwargs["thumb"] = thumb
                kwargs["audio"] = file_path
            elif key == "photos":
                kwargs["photo"] = file_path
            else:
                if thumb:
                    kwargs["thumb"] = thumb
                kwargs["document"] = file_path
                kwargs["force_document"] = True
            return await self._try_send(key, client, kwargs)
        finally:
            self.work_loads[idx] = max(0, self.work_loads.get(idx, 1) - 1)

    async def _direct_send(
        self,
        file_path,
        key,
        thumb,
        cap_mono,
        chat_id,
        reply_to_message_id,
        thread_id=None,
        duration=0,
        width=0,
        height=0,
        artist="",
        title="",
        user_session=False,
        reply_markup=None,
        progress=None,
    ):
        client = user if user_session and user else (self.clients.get(0) or bot)
        kwargs = {
            "chat_id": chat_id,
            "disable_notification": True,
            "progress": progress or self._progress,
            "progress_args": (file_path,),
        }
        if cap_mono:
            kwargs["caption"] = cap_mono
        if reply_to_message_id:
            kwargs["reply_to_message_id"] = reply_to_message_id
        elif thread_id:
            kwargs["message_thread_id"] = thread_id
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        if key == "videos":
            if thumb:
                kwargs["thumb"] = thumb
                kwargs["video_cover"] = thumb
            if duration:
                kwargs["duration"] = duration
            if width:
                kwargs["width"] = width
            if height:
                kwargs["height"] = height
            kwargs["supports_streaming"] = True
            kwargs["video"] = file_path
        elif key == "audios":
            if thumb:
                kwargs["thumb"] = thumb
            if duration:
                kwargs["duration"] = duration
            if artist:
                kwargs["performer"] = artist
            if title:
                kwargs["title"] = title
            kwargs["audio"] = file_path
        elif key == "photos":
            kwargs["photo"] = file_path
        else:
            if thumb:
                kwargs["thumb"] = thumb
            kwargs["document"] = file_path
            kwargs["force_document"] = True
        return await self._try_send(key, client, kwargs)

    async def send_media(self, file_path, key, **kwargs):
        """Used by pyrogramEngine: WZML _hyper_send if helpers/user, else _direct_send."""
        self._up_file = ospath.basename(file_path)
        up_size = ospath.getsize(file_path) if ospath.exists(file_path) else 0
        hyper_user_only = False
        user_session = bool(user)
        if up_size > 2097152000 and any(k < 0 for k in self.clients):
            if user:
                use_hyper = False
                user_session = True
            else:
                use_hyper = True
                hyper_user_only = True
                user_session = False
        else:
            use_hyper = bool(self.clients) and up_size > 10 * 1024 * 1024
        if use_hyper:
            return await self._hyper_send(
                file_path, key, user_only=hyper_user_only, **kwargs
            )
        return await self._direct_send(
            file_path, key, user_session=user_session, **kwargs
        )
