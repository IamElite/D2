from time import time

from .... import LOGGER
from ...ext_utils.bot_utils import (
    clock_fmt, EngineStatus, get_readable_file_size, MirrorStatus, async_to_sync
)
from ...ext_utils.file_count import stage_counts
from ...ext_utils.fs_utils import get_path_stats


class VideoToolsStatus:
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
        elapsed = time() - self.__start_time
        return self.processed_raw() / elapsed if elapsed > 0 else 0

    def progress_raw(self):
        try:
            return self.processed_raw() / self.__size * 100
        except Exception:
            return 0

    def progress(self):
        return f"{round(self.progress_raw(), 2)}%"

    def speed(self):
        return f"{get_readable_file_size(self.speed_raw())}/s"

    def name(self):
        return self.__name

    def size(self):
        return get_readable_file_size(self.__size)

    def eta(self):
        try:
            spd = self.speed_raw()
            if spd > 0:
                seconds = (self.__size - self.processed_raw()) / spd
                return clock_fmt(seconds)
            return "-"
        except Exception:
            return "-"

    def status(self):
        return MirrorStatus.STATUS_VID_TOOLS

    def processed_bytes(self):
        return get_readable_file_size(self.processed_raw())

    def __stats(self):
        if self.__listener.newDir:
            size, files = async_to_sync(get_path_stats, self.__listener.newDir)
            base_files = 0
        else:
            size, files = async_to_sync(get_path_stats, self.__listener.dir)
            base_files = 0
        self.__proc_size = max(0, size - (0 if self.__listener.newDir else self.__size))
        self.__proc_files = files - base_files
        return self.__proc_size

    def processed_raw(self):
        return self.__stats()

    def files_count(self):
        return stage_counts(self.__listener)

    async def cancel_download(self):
        LOGGER.info(f"Cancelling Video Tools: {self.__name}")
        if self.__listener.suproc is not None and not isinstance(self.__listener.suproc, str):
            try:
                self.__listener.suproc.kill()
            except Exception:
                pass
        self.__listener.suproc = "cancelled"
        await self.__listener.onUploadError("Video Tools processing stopped by user!")

    def eng(self):
        return EngineStatus().STATUS_VIDEO_TOOL
