from asyncio import Event, Lock, gather, sleep

from pyrogram import raw, utils
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileType, ThumbnailSource
from pyrogram.session import Auth, Session

from ... import LOGGER, bot, user

MB = 1024 * 1024

helper_bots = {}
helper_loads = {}
helper_users = {}
helper_user_loads = {}

_global_work_loads = None

_MEDIA_ATTRS = (
    "audio",
    "document",
    "photo",
    "sticker",
    "animation",
    "video",
    "voice",
    "video_note",
    "new_chat_photo",
    "story",
    "web_page",
)


def media_of(message):
    for attr in _MEDIA_ATTRS:
        if m := getattr(message, attr, None):
            return m
    raise ValueError(
        f"No downloadable media in msg {message.id} (type: {message.media})"
    )


def reset_work_loads():
    global _global_work_loads
    _global_work_loads = None


def get_global_work_loads():
    global _global_work_loads
    if _global_work_loads is None:
        _global_work_loads = dict(helper_loads)
        if 0 not in _global_work_loads and bot:
            _global_work_loads[0] = 0
        if helper_users:
            for no, load in helper_user_loads.items():
                _global_work_loads[-no] = load
        if user:
            _global_work_loads[-(len(helper_users) + 1)] = _global_work_loads.get(
                -(len(helper_users) + 1), 0
            )
    return _global_work_loads


def pick_hyper_client():
    loads = get_global_work_loads()
    if not loads:
        return bot, None
    idx = min(loads, key=loads.get)
    loads[idx] = loads.get(idx, 0) + 1
    if idx == 0:
        return bot, 0
    if idx < 0:
        if idx in helper_users:
            return helper_users[-idx], idx
        return user, idx
    return helper_bots.get(idx, bot), idx


def release_hyper_client(idx):
    if idx is None:
        return
    loads = get_global_work_loads()
    loads[idx] = max(0, loads.get(idx, 1) - 1)


def hyper_ready():
    return bool(helper_bots or user or bot)


class MtprotoPool:
    def __init__(self, clients):
        if isinstance(clients, dict):
            self._client_map = dict(clients)
            self._client_order = list(clients.keys())
        else:
            self._client_map = {i: c for i, c in enumerate(clients)}
            self._client_order = list(self._client_map.keys())
        self._sessions = {}
        self._locks = {}

    def _resolve_key(self, client_key):
        if client_key in self._client_map:
            return client_key
        if isinstance(client_key, int) and self._client_order:
            return self._client_order[client_key % len(self._client_order)]
        raise KeyError(f"Client key {client_key} not found")

    async def _get_auth_key(self, client, dc_id):
        test_mode = await client.storage.test_mode()
        main_dc = await client.storage.dc_id()
        if dc_id == main_dc:
            return await client.storage.auth_key(), False
        ak = await Auth(client, dc_id, test_mode).create()
        return ak, True

    async def get_session(self, client_key, dc_id, is_media=True):
        ck = self._resolve_key(client_key)
        cache_key = (ck, dc_id)
        s = self._sessions.get(cache_key)
        if s and s.is_started.is_set():
            return s
        if cache_key not in self._locks:
            self._locks[cache_key] = Lock()
        async with self._locks[cache_key]:
            s = self._sessions.get(cache_key)
            if s and s.is_started.is_set():
                return s
            if s:
                try:
                    await s.stop()
                except Exception:
                    pass
            client = self._client_map[ck]
            ak, is_cross = await self._get_auth_key(client, dc_id)
            s = Session(
                client, dc_id, ak, await client.storage.test_mode(), is_media=is_media
            )
            await s.start()
            if is_cross:
                for _attempt in range(6):
                    try:
                        e = await client.invoke(
                            raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                        )
                        await s.invoke(
                            raw.functions.auth.ImportAuthorization(
                                id=e.id, bytes=e.bytes
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        await sleep(1)
                else:
                    await s.stop()
                    raise RuntimeError(f"Auth export/import failed for DC {dc_id}")
            self._sessions[cache_key] = s
        return s

    async def drop_session(self, client_key, dc_id):
        ck = self._resolve_key(client_key)
        cache_key = (ck, dc_id)
        s = self._sessions.pop(cache_key, None)
        if s:
            try:
                await s.stop()
            except Exception:
                pass

    async def stop(self):
        for s in self._sessions.values():
            try:
                await s.stop()
            except Exception:
                pass
        self._sessions.clear()


class HypertgTransfer:
    def __init__(self, obj=None):
        self._obj = obj
        self._listener = getattr(obj, "_listener", None) if obj is not None else None
        if self._listener is None and obj is not None:
            self._listener = getattr(obj, "_TgUploader__listener", None)
        self.clients = {}
        if bot:
            self.clients[0] = bot
        for no, c in helper_bots.items():
            self.clients[no] = c
        if helper_users:
            for no, client in helper_users.items():
                self.clients[-no] = client
        if user and all(c is not user for c in self.clients.values()):
            key = -(len(helper_users) + 1)
            self.clients[key] = user
        self.work_loads = get_global_work_loads()
        for k in self.clients:
            self.work_loads.setdefault(k, 0)
        self.client_ids = list(self.clients.keys())
        self.num_clients = len(self.clients)
        self._pool = MtprotoPool(self.clients)
        self._cancel = Event()
        self._tasks = []
        LOGGER.info(
            f"HypertgTransfer init clients={self.num_clients} loads={dict(self.work_loads)}"
        )

    def _pick_client(self):
        if not self.work_loads:
            return 0
        return min(self.work_loads, key=self.work_loads.get)

    def _client_idx(self, client):
        for i, c in self.clients.items():
            if c is client:
                return i
        return None

    async def _get_session(self, idx, dc_id, force=False):
        if force:
            await self._pool.drop_session(idx, dc_id)
        return await self._pool.get_session(idx, dc_id, is_media=True)

    async def _warmup(self, indices, dc_id):
        async def _w(i):
            try:
                await self._pool.get_session(i, dc_id)
            except Exception as e:
                LOGGER.warning(f"HypertgTransfer warmup fail client {i}: {e}")

        await gather(*[_w(i) for i in indices])

    async def _close_all(self):
        await self._pool.stop()

    @staticmethod
    def _location(fid):
        ft = fid.file_type
        if ft == FileType.CHAT_PHOTO:
            if fid.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=fid.chat_id, access_hash=fid.chat_access_hash
                )
            elif fid.chat_access_hash == 0:
                peer = raw.types.InputPeerChat(chat_id=-fid.chat_id)
            else:
                peer = raw.types.InputPeerChannel(
                    channel_id=utils.get_channel_id(fid.chat_id),
                    access_hash=fid.chat_access_hash,
                )
            loc = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=fid.volume_id,
                local_id=fid.local_id,
                big=fid.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG,
            )
            return loc
        if ft == FileType.PHOTO:
            loc = raw.types.InputPhotoFileLocation(
                id=fid.media_id,
                access_hash=fid.access_hash,
                file_reference=fid.file_reference,
                thumb_size=fid.thumbnail_size,
            )
            return loc
        loc = raw.types.InputDocumentFileLocation(
            id=fid.media_id,
            access_hash=fid.access_hash,
            file_reference=fid.file_reference,
            thumb_size=fid.thumbnail_size,
        )
        return loc

    async def cancel(self):
        self._cancel.set()
        for t in self._tasks:
            if not t.done():
                t.cancel()
        if self._tasks:
            await gather(*self._tasks, return_exceptions=True)
        await self._close_all()
