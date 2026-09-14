from ...ext_utils.bot_utils import (
    clock_fmt, EngineStatus, MirrorStatus, get_readable_file_size, get_readable_time
)


class GalleryDLStatus:
    def __init__(self, obj, gid, listener):
        self.__gid = gid
        self.__listener = listener
        self.__obj = obj
        self.upload_details = listener.upload_details
        self.message = listener.message

    def gid(self):
        return self.__gid

    def progress(self):
        return self.__obj.progress

    def speed(self):
        return f"{get_readable_file_size(self.__obj.speed)}/s"

    def name(self):
        return self.__obj.name

    def size(self):
        return get_readable_file_size(self.__obj.size)

    def eta(self):
        return self.__obj.eta

    def status(self):
        return MirrorStatus.STATUS_DOWNLOADING

    def processed_bytes(self):
        return get_readable_file_size(self.__obj.processed_bytes)

    def files_count(self):
        return self.__obj.files_count

    def download(self):
        return self.__obj

    def eng(self):
        return EngineStatus().STATUS_GDL
