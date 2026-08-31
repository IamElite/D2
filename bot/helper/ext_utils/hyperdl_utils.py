"""HyperDL — parallel MTProto GetFile (same client, multiple media sessions).

Telegram GetFile is 1 MiB/request. Sequential download caps ~15–20 MB/s.
N media sessions to the file DC fetch offsets in parallel. Fail → normal
download_media. HELPER_TOKENS not required.
"""
from asyncio import Lock, Queue, QueueEmpty, gather, sleep
from logging import getLogger
from os import makedirs, path as ospath

from pyrogram import raw, StopTransmission
from pyrogram.errors import FloodWait
from pyrogram.file_id import FileId

from ... import bot, user
from ..telegram_helper.tg_transfer import HypertgTransfer, media_of

LOGGER = getLogger(__name__)

CHUNK = 1024 * 1024
WORKERS = 6


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


class HypertgDownload(HypertgTransfer):
    async def download_media(self, client, message, path, progress=None, cancelled=None):
        try:
            media = media_of(message)
        except Exception:
            media = getattr(message, message.media.value) if message.media else None
        size = getattr(media, "file_size", 0) or 0
        if size < 8 * CHUNK or media is None:
            return await client.download_media(
                message=message, file_name=path, progress=progress
            )
        try:
            return await self._parallel(client, media, path, size, progress, cancelled)
        except StopTransmission:
            raise
        except Exception as e:
            LOGGER.warning("HyperDL parallel fail, fallback download_media: %s", e)
            return await client.download_media(
                message=message, file_name=path, progress=progress
            )

    async def _parallel(self, client, media, path, size, progress, cancelled):
        fid = FileId.decode(media.file_id)
        loc = self._location(fid)
        dc_id = fid.dc_id
        idx = self._client_idx(client)
        if idx is None:
            idx = 0
            self.clients[0] = client
        n = min(WORKERS, max(2, size // (16 * CHUNK)))
        parent = ospath.dirname(path)
        if parent:
            makedirs(parent, exist_ok=True)
        with open(path, "wb") as fh:
            fh.truncate(size)

        q = Queue()
        for off in range(0, size, CHUNK):
            q.put_nowait(off)
        done = 0
        dlock = Lock()

        async def worker(slot):
            nonlocal done
            session = await self._pool.get_session(idx, dc_id, is_media=True, slot=slot)
            while True:
                if cancelled and cancelled():
                    raise StopTransmission
                try:
                    off = q.get_nowait()
                except QueueEmpty:
                    return
                limit = min(CHUNK, size - off)
                for attempt in range(4):
                    try:
                        r = await session.invoke(
                            raw.functions.upload.GetFile(
                                location=loc, offset=off, limit=limit
                            )
                        )
                        data = r.bytes
                        break
                    except FloodWait as f:
                        await sleep(int(getattr(f, "value", 3)) + 1)
                    except Exception:
                        if attempt == 3:
                            raise
                        await sleep(1)
                        session = await self._pool.get_session(
                            idx, dc_id, is_media=True, slot=slot
                        )
                else:
                    continue
                def _write():
                    with open(path, "r+b") as f:
                        f.seek(off)
                        f.write(data)
                await sleep(0)
                _write()
                async with dlock:
                    done += len(data)
                    if progress:
                        await progress(done, size)

        LOGGER.info("HyperDL parallel GetFile workers=%s size=%s dc=%s", n, size, dc_id)
        await gather(*[worker(s) for s in range(n)])
        return path
