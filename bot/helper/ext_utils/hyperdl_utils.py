"""WZML-style HypertgDL: GetFile precise+CDN + pipelined offsets.

Port of SilentDemonSD/WZML-X wzv3 hyperdl_utils (trimmed: no mem_guard).
Single client still uses N media-session slots so one bot can exceed ~18 MB/s.
"""
from asyncio import (
    FIRST_COMPLETED,
    CancelledError,
    Lock,
    create_task,
    gather,
    sleep,
    wait,
)
from logging import getLogger
from os import O_CREAT, O_RDWR, close as osclose, open as osopen, pwrite, path as ospath

from pyrogram import StopTransmission, raw
from pyrogram.errors import FloodWait, FileMigrate
from pyrogram.file_id import FileId
from pyrogram.session import Auth, Session

try:
    from pyrogram.crypto.aes import ctr256_decrypt
except Exception:
    ctr256_decrypt = None
try:
    from pyrogram.errors import FloodPremiumWait
except ImportError:
    FloodPremiumWait = FloodWait

from ... import bot, user
from ..telegram_helper.tg_transfer import HypertgTransfer, media_of

LOGGER = getLogger(__name__)

KB = 1024
CHUNK = 256 * KB
PIPE = 16
SLOTS = 6


def pick_download_client(session="bot"):
    try:
        if session in ("user", "auto") and user:
            return user
        if user:
            return user
        return bot
    except Exception as e:
        LOGGER.error("HyperDL pick fallback bot: %s", e)
        return bot


class HypertgDownload(HypertgTransfer):
    def __init__(self, obj):
        super().__init__(obj)
        self._cdn_info = {}
        self._cdn_sessions = {}

    async def download_media(self, client, message, path, progress=None, cancelled=None):
        try:
            media = media_of(message)
        except Exception:
            media = getattr(message, message.media.value) if getattr(message, "media", None) else None
        size = getattr(media, "file_size", 0) or 0
        if size < 4 * CHUNK or media is None:
            return await client.download_media(message=message, file_name=path, progress=progress)
        try:
            return await self._run(client, media, path, size, progress, cancelled)
        except StopTransmission:
            raise
        except Exception as e:
            LOGGER.warning("HyperDL fail, fallback download_media: %s", e)
            return await client.download_media(message=message, file_name=path, progress=progress)

    async def _get_cdn_session(self, idx, cdn_dc, client):
        key = (idx, cdn_dc)
        s = self._cdn_sessions.get(key)
        if s and getattr(s, "is_started", None) and s.is_started.is_set():
            return s
        tm = await client.storage.test_mode()
        ak = await Auth(client, cdn_dc, tm).create()
        s = Session(client, cdn_dc, ak, tm, is_media=True)
        try:
            s = Session(client, cdn_dc, ak, tm, is_media=True, is_cdn=True)
        except TypeError:
            pass
        await s.start()
        self._cdn_sessions[key] = s
        return s

    async def _cdnpull(self, idx, client, cdn, off, csz):
        if not ctr256_decrypt:
            return None
        sess = await self._get_cdn_session(idx, cdn["cdn_dc"], client)
        try:
            r = await sess.invoke(
                raw.functions.upload.GetCdnFile(
                    file_token=cdn["file_token"], offset=off, limit=csz
                )
            )
        except Exception as e:
            LOGGER.warning("HyperDL CDN: %s", e)
            return None
        if isinstance(r, raw.types.upload.CdnFile):
            iv = bytearray(cdn["iv"][:-4] + (off // 16).to_bytes(4, "big"))
            return ctr256_decrypt(r.bytes, cdn["key"], iv)
        return None

    async def _getfile(self, sess, client, loc, off, csz):
        r = await sess.invoke(
            raw.functions.upload.GetFile(
                precise=True,
                cdn_supported=True,
                location=loc,
                offset=off,
                limit=csz,
            )
        )
        if isinstance(r, raw.types.upload.File):
            return r.bytes, None
        if isinstance(r, raw.types.upload.FileCdnRedirect):
            return None, {
                "cdn_dc": r.dc_id,
                "file_token": r.file_token,
                "key": r.encryption_key,
                "iv": r.encryption_iv,
            }
        raise ValueError(type(r))

    async def _run(self, client, media, path, size, progress, cancelled):
        fid = FileId.decode(media.file_id)
        loc = self._location(fid)
        dc_id = fid.dc_id
        idx = self._client_idx(client)
        if idx is None:
            idx = 0
            self.clients[0] = client
        from os import makedirs
        parent = ospath.dirname(path)
        if parent:
            makedirs(parent, exist_ok=True)
        with open(path, "wb") as f:
            f.truncate(size)
        fd = osopen(path, O_RDWR)
        done = 0
        dlock = Lock()
        LOGGER.info(
            "HyperDL wzgram GetFile+CDN slots=%s chunk=%s size=%s dc=%s",
            SLOTS, CHUNK, size, dc_id,
        )

        async def slot_worker(slot):
            nonlocal done, loc
            sess = await self._pool.get_session(idx, dc_id, is_media=True, slot=slot)
            off = slot * CHUNK
            while off < size:
                if cancelled and cancelled():
                    raise StopTransmission
                csz = min(CHUNK, size - off)
                data = None
                for attempt in range(4):
                    try:
                        cdn = self._cdn_info.get(idx)
                        if cdn:
                            data = await self._cdnpull(idx, client, cdn, off, csz)
                            if data is not None:
                                break
                            self._cdn_info.pop(idx, None)
                        chunk, extra = await self._getfile(sess, client, loc, off, csz)
                        if extra:
                            self._cdn_info[idx] = extra
                            data = await self._cdnpull(idx, client, extra, off, csz)
                            if data is None:
                                await sleep(0.2)
                                continue
                            break
                        data = chunk
                        break
                    except FileMigrate as e:
                        dc = getattr(e, "value", dc_id)
                        sess = await self._pool.get_session(idx, dc, is_media=True, slot=slot)
                    except (FloodWait, FloodPremiumWait) as f:
                        await sleep(int(getattr(f, "value", 3)) + 1)
                    except Exception:
                        if attempt == 3:
                            raise
                        await sleep(0.5)
                if not data:
                    off += SLOTS * CHUNK
                    continue
                await sleep(0)
                pwrite(fd, data, off)
                async with dlock:
                    done += len(data)
                    if progress:
                        await progress(done, size)
                off += SLOTS * CHUNK

        try:
            await gather(*[slot_worker(s) for s in range(SLOTS)])
        finally:
            osclose(fd)
        return path
