#!/usr/bin/env python3
from time import time

from .... import LOGGER
from ...ext_utils.bot_utils import clock_fmt, EngineStatus, get_readable_file_size, MirrorStatus, get_readable_time, async_to_sync
from ...ext_utils.fs_utils import get_path_size, get_path_stats


class ZipStatus:
    def __init__(self, name, size, gid, listener):
        self.__name = name
        self.__size = size
        self.__gid = gid
        self.__listener = listener
        self.upload_details = listener.upload_details
        self.__uid = listener.uid
        self.__start_time = time()
        self.message = listener.message
        self.__proc_size = 0
        self.__proc_files = 0

    def gid(self):
        return self.__gid

    def speed_raw(self):
        return self.processed_raw() / (time() - self.__start_time)

    def progress_raw(self):
        try:
            return self.processed_raw() / self.__size * 100
        except:
            return 0

    def progress(self):
        return f'{round(self.progress_raw(), 2)}%'

    def speed(self):
        return f'{get_readable_file_size(self.speed_raw())}/s'

    def name(self):
        return self.__name

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        try:
            seconds = (self.__size - self.processed_raw()) / self.speed_raw()
            return clock_fmt(seconds)
        except:
            return '-'

    def status(self):
        return MirrorStatus.STATUS_ARCHIVING

    def __stats(self):
        if self.__listener.newDir:
            size, files = async_to_sync(get_path_stats, self.__listener.newDir)
            base_files = 0
        else:
            size, files = async_to_sync(get_path_stats, self.__listener.dir)
            base_files = 0
        self.__proc_size = size - (0 if self.__listener.newDir else self.__size)
        self.__proc_files = files - base_files
        return self.__proc_size

    def processed_raw(self):
        return self.__stats()

    def files_count(self):
        return 0, 0

    def processed_bytes(self):
        return get_readable_file_size(self.processed_raw())

    def download(self):
        return self

    async def cancel_download(self):
        LOGGER.info(f'Cancelling Archive: {self.__name}')
        if self.__listener.suproc is not None:
            self.__listener.suproc.kill()
        else:
            self.__listener.suproc = 'cancelled'
        await self.__listener.onUploadError('archiving stopped by user!')


    def eng(self):
        return EngineStatus().STATUS_ZIP
