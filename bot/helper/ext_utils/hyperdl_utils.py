"""WZML-X wzv3 HyperDL core: one bot, pipelined GetFile (not helper tokens).

Their 30 MB/s on a single bot is ~32 in-flight GetFile(precise, cdn) + pwrite,
not extra USER_SESSION / HELPER_TOKENS. Sequential download_media ≈ 6–18 MB/s.
"""
from asyncio import FIRST_COMPLETED, CancelledError, create_task, sleep, wait
from logging import getLogger
from os import O_RDWR, O_CREAT, close as os_close, makedirs, open as os_open, path as ospath, pwrite

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
WINDOW = 32


def pick_download_client(session="bot"):
    try:
        if session == "user" and user:
            return user
        return bot
    except Exception as e:
        LOGGER.error("HyperDL pick fallback bot: %s", e)
        return bot


class HypertgDownload(HypertgTransfer):
    def __init__(self, obj):
        super().__init__(obj)
        self._cdn = None
        self._cdn_sess = None

    async def download_media(self, client, message, path, progress=None, cancelled=None):
        try:
            media = media_of(message)
        except Exception:
            media = getattr(message, getattr(message, "media", None) and message.media.value, None)
        size = getattr(media, "file_size", 0) or 0
        if not media or size < CHUNK * 4:
            return await client.download_media(message=message, file_name=path, progress=progress)
        try:
            n = await self._pipeline(client, media, path, size, progress, cancelled)
            if n:
                return n
        except StopTransmission:
            raise
        except Exception as e:
            LOGGER.error("HyperDL pipeline: %s", e)
        return await client.download_media(message=message, file_name=path, progress=progress)

    async def _cdn_session(self, client, dc):
        if self._cdn_sess and getattr(self._cdn_sess, "is_started", None) and self._cdn_sess.is_started.is_set():
            return self._cdn_sess
        tm = await client.storage.test_mode()
        ak = await Auth(client, dc, tm).create()
        try:
            s = Session(client, dc, ak, tm, is_media=True, is_cdn=True)
        except TypeError:
            s = Session(client, dc, ak, tm, is_media=True)
        await s.start()
        self._cdn_sess = s
        return s

    async def _cdnpull(self, client, off, csz):
        if not self._cdn or not ctr256_decrypt:
            return None
        try:
            sess = await self._cdn_session(client, self._cdn["dc"])
            r = await sess.invoke(
                raw.functions.upload.GetCdnFile(
                    file_token=self._cdn["token"], offset=off, limit=csz
                )
            )
            if isinstance(r, raw.types.upload.CdnFile):
                iv = bytearray(self._cdn["iv"][:-4] + (off // 16).to_bytes(4, "big"))
                return ctr256_decrypt(r.bytes, self._cdn["key"], iv)
        except Exception as e:
            LOGGER.warning("HyperDL CDN pull: %s", e)
            self._cdn = None
        return None

    async def _getfile(self, sess, loc, off, csz):
        kwargs = dict(location=loc, offset=off, limit=csz)
        try:
            r = await sess.invoke(raw.functions.upload.GetFile(precise=True, cdn_supported=True, **kwargs))
        except TypeError:
            r = await sess.invoke(raw.functions.upload.GetFile(**kwargs))
        if isinstance(r, raw.types.upload.File):
            return r.bytes
        if isinstance(r, raw.types.upload.FileCdnRedirect):
            self._cdn = {
                "dc": r.dc_id,
                "token": r.file_token,
                "key": r.encryption_key,
                "iv": r.encryption_iv,
            }
            return None
        raise TypeError(type(r))

    async def _pipeline(self, client, media, path, size, progress, cancelled):
        fid = FileId.decode(media.file_id)
        loc = self._location(fid)
        idx = self._client_idx(client)
        if idx is None:
            idx = 0
            self.clients[0] = client
        parent = ospath.dirname(path)
        if parent:
            makedirs(parent, exist_ok=True)
        with open(path, "wb") as f:
            f.truncate(size)
        fd = os_open(path, O_RDWR | O_CREAT)
        sess = await self._pool.get_session(idx, fid.dc_id, is_media=True, slot=0)
        LOGGER.info("HyperDL pipeline window=%s chunk=%sB size=%s dc=%s (bot-only)", WINDOW, CHUNK, size, fid.dc_id)

        done = 0
        cur = 0
        inflight = set()
        offmap = {}

        async def _one(off):
            csz = min(CHUNK, size - off)
            for attempt in range(5):
                if cancelled and cancelled():
                    raise StopTransmission
                try:
                    if self._cdn:
                        data = await self._cdnpull(client, off, csz)
                        if data:
                            return off, data
                    data = await self._getfile(sess, loc, off, csz)
                    if data:
                        return off, data
                    if self._cdn:
                        data = await self._cdnpull(client, off, csz)
                        if data:
                            return off, data
                except FileMigrate as e:
                    dc = getattr(e, "value", fid.dc_id)
                    sess = await self._pool.get_session(idx, dc, is_media=True, slot=0)
                    await sleep(0.2)
                except (FloodWait, FloodPremiumWait) as f:
                    await sleep(int(getattr(f, "value", 2)) + 1)
                except Exception:
                    await sleep(0.3)
            return off, b""

        async def _one_retry(s, off, csz):
            data = await self._getfile(s, loc, off, csz)
            return off, data or b""

        async def _write(off, data):
            nonlocal done
            if not data:
                return
            pwrite(fd, data, off)
            done += len(data)
            if progress:
                await progress(done, size)

        try:
            while cur < size or inflight:
                if cancelled and cancelled():
                    raise StopTransmission
                while len(inflight) < WINDOW and cur < size:
                    t = create_task(_one(cur))
                    offmap[t] = cur
                    inflight.add(t)
                    cur += CHUNK
                if not inflight:
                    break
                finished, inflight = await wait(inflight, return_when=FIRST_COMPLETED)
                for t in finished:
                    offmap.pop(t, None)
                    try:
                        off, data = t.result()
                    except StopTransmission:
                        raise
                    except Exception as e:
                        LOGGER.warning("HyperDL chunk: %s", e)
                        continue
                    if data:
                        await _write(off, data)
        finally:
            for t in inflight:
                t.cancel()
            os_close(fd)
        if done < size * 0.95:
            LOGGER.error("HyperDL incomplete %s/%s — fallback", done, size)
            return None
        return path
