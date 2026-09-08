#!/usr/bin/env python3
from os import path as ospath
from time import time
from .... import LOGGER
from ...ext_utils.bot_utils import EngineStatus, get_readable_file_size, MirrorStatus, clock_fmt
from ...ext_utils.file_count import stage_counts


class SplitStatus:
    def __init__(self, name, size, gid, listener):
        self.__name = name
        self.__gid = gid
        self.__size = size
        self.__listener = listener
        self.__start_time = time()
        self.upload_details = getattr(listener, 'upload_details', {})
        self.message = listener.message

    def gid(self):
        return self.__gid

    def processed_raw(self):
        base = getattr(self.__listener, 'split_base_bytes', 0)
        current_path = getattr(self.__listener, 'split_current_outpath', None)
        current_size = 0
        if current_path and ospath.exists(current_path):
            try:
                current_size = ospath.getsize(current_path)
            except Exception:
                pass
        total = base + current_size
        return min(total, self.__size) if self.__size else total

    def speed_raw(self):
        elapsed = time() - self.__start_time
        if elapsed <= 0:
            return 0
        return self.processed_raw() / elapsed

    def progress_raw(self):
        if not self.__size:
            return 0.0
        return min(100.0, (self.processed_raw() / self.__size) * 100)

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed(self):
        spd = self.speed_raw()
        return f'{get_readable_file_size(spd)}/s' if spd > 0 else '0B/s'

    def name(self):
        return self.__name

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        spd = self.speed_raw()
        if spd <= 0:
            return '-'
        remaining = self.__size - self.processed_raw()
        if remaining <= 0:
            return '00:00:00'
        return clock_fmt(remaining / spd)

    def status(self):
        return MirrorStatus.STATUS_SPLITTING

    def processed_bytes(self):
        return get_readable_file_size(self.processed_raw())

    def files_count(self):
        return stage_counts(self.__listener)

    def download(self):
        return self

    async def cancel_download(self):
        LOGGER.info(f'Cancelling Split: {self.__name}')
        if self.__listener.suproc is not None:
            self.__listener.suproc.kill()
        else:
            self.__listener.suproc = 'cancelled'
        await self.__listener.onUploadError('splitting stopped by user!')

    def eng(self):
        return EngineStatus().STATUS_SPLIT_MERGE

