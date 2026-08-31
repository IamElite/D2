"""HyperDL: pipelined GetFile. Never pin FileId.dc_id — start on bot DC, FileMigrate follows."""
from asyncio import FIRST_COMPLETED, TimeoutError as AsyncTimeout, create_task, sleep, wait, wait_for
from logging import getLogger
from os import O_RDWR, O_CREAT, close as os_close, makedirs, open as os_open, path as ospath, pwrite

from pyrogram import StopTransmission, raw
from pyrogram.errors import FloodWait, FileMigrate
from pyrogram.file_id import FileId

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
NSLOT = 4
WINDOW = 4


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
        self._dc = None

    async def download_media(self, client, message, path, progress=None, cancelled=None):
        try:
            media = media_of(message)
        except Exception:
            media = getattr(message, getattr(message, "media", None) and message.media.value, None)
        size = getattr(media, "file_size", 0) or 0
        if not media or size < CHUNK * 4:
            return await client.download_media(message=message, file_name=path, progress=progress)
        try:
            n = await wait_for(self._pipeline(client, media, path, size, progress, cancelled), 90)
            if n:
                return n
        except StopTransmission:
            raise
        except AsyncTimeout:
            LOGGER.error("HyperDL pipeline watchdog 90s — fallback download_media")
        except Exception as e:
            LOGGER.error("HyperDL pipeline: %s", e)
        return await client.download_media(message=message, file_name=path, progress=progress)

    async def _getfile(self, sess, loc, off, csz):
        kwargs = dict(location=loc, offset=off, limit=csz)
        try:
            r = await wait_for(
                sess.invoke(raw.functions.upload.GetFile(precise=True, cdn_supported=True, **kwargs)),
                12,
            )
        except TypeError:
            r = await wait_for(sess.invoke(raw.functions.upload.GetFile(**kwargs)), 12)
        except AsyncTimeout:
            raise RuntimeError("GetFile timeout")
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
        if ospath.isdir(path) or path.endswith(("/", "\\")):
            path = ospath.join(path, getattr(media, "file_name", None) or "tg.bin")
        parent = ospath.dirname(path)
        if parent:
            makedirs(parent, exist_ok=True)
        with open(path, "wb") as f:
            f.truncate(size)
        fd = os_open(path, O_RDWR | O_CREAT)

        bot_dc = await client.storage.dc_id()
        # Do not lock FileId.dc_id (often stale vs bot DC). Start on bot DC; Telegram FileMigrate.
        self._dc = bot_dc
        sesses = []
        for slot in range(NSLOT):
            sesses.append(await wait_for(self._pool.get_session(idx, self._dc, is_media=True, slot=slot), 20))
        LOGGER.info(
            "HyperDL start bot_dc=%s file_id_dc=%s using_dc=%s slots=%s size=%s",
            bot_dc, fid.dc_id, self._dc, NSLOT, size,
        )

        done = 0
        cur = 0
        inflight = set()
        first_err = [None]
        got_any = [False]

        async def _one(off):
            slot = (off // CHUNK) % NSLOT
            sess = sesses[slot]
            csz = min(CHUNK, size - off)
            for _ in range(4):
                if cancelled and cancelled():
                    raise StopTransmission
                try:
                    data = await self._getfile(sess, loc, off, csz)
                    if data:
                        got_any[0] = True
                        return off, data
                except FileMigrate as e:
                    new_dc = int(getattr(e, "value", 0) or self._dc)
                    LOGGER.info("HyperDL FileMigrate %s -> %s", self._dc, new_dc)
                    self._dc = new_dc
                    sesses[slot] = await self._pool.get_session(idx, new_dc, is_media=True, slot=slot)
                    sess = sesses[slot]
                    await sleep(0.15)
                except (FloodWait, FloodPremiumWait) as f:
                    await sleep(int(getattr(f, "value", 2)) + 1)
                except Exception as e:
                    first_err[0] = first_err[0] or e
                    await sleep(0.2)
            return off, b""

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
                if cur > CHUNK * WINDOW and not got_any[0]:
                    LOGGER.error("HyperDL no bytes after first window err=%s — fallback", first_err[0])
                    break
                while len(inflight) < WINDOW and cur < size:
                    t = create_task(_one(cur))
                    inflight.add(t)
                    cur += CHUNK
                if not inflight:
                    break
                finished, inflight = await wait(inflight, return_when=FIRST_COMPLETED)
                for t in finished:
                    try:
                        off, data = t.result()
                    except StopTransmission:
                        raise
                    except Exception as e:
                        first_err[0] = first_err[0] or e
                        continue
                    if data:
                        await _write(off, data)
        finally:
            for t in inflight:
                t.cancel()
            os_close(fd)
        if done < size * 0.95:
            LOGGER.error("HyperDL incomplete %s/%s err=%s using_dc=%s — fallback", done, size, first_err[0], self._dc)
            return None
        LOGGER.info("HyperDL done %s bytes dc=%s", done, self._dc)
        return path
