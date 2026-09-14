from asyncio import create_subprocess_exec, sleep, subprocess
from os import path as ospath
from secrets import token_hex
from sys import executable
from time import time
import shlex

from .... import (
    LOGGER, download_dict, download_dict_lock, non_queued_dl, queue_dict_lock
)
from ...ext_utils.bot_utils import clock_fmt
from ...ext_utils.fs_utils import get_path_stats
from ...ext_utils.task_manager import is_queued, stop_duplicate_check
from ..status_utils.gallery_dl_status import GalleryDLStatus
from ..status_utils.queue_status import QueueStatus
from ...telegram_helper.message_utils import sendMessage, sendStatusMessage


class GalleryDLHelper:
    def __init__(self, listener):
        self.listener = listener
        self.name = ""
        self.size = 0
        self.processed_bytes = 0
        self.files_count = 0
        self.speed = 0
        self.eta = "-"
        self.progress = "0%"
        self._proc = None
        self._is_cancelled = False
        self._start_time = time()
        self._last_downloaded = 0
        self._last_time = time()

    async def add_download(self, link, path, name=None, opt=None):
        self.name = name or self.listener.name or "Gallery"
        msg, button = await stop_duplicate_check(self.name, self.listener)
        if msg:
            await sendMessage(self.listener.message, msg, button)
            return

        gid = token_hex(5)
        added_to_queue, event = await is_queued(self.listener.uid)
        if added_to_queue:
            LOGGER.info(f"Added to Queue/Download: {self.name}")
            async with download_dict_lock:
                download_dict[self.listener.uid] = QueueStatus(
                    self.name, 0, gid, self.listener, "dl"
                )
            await self.listener.onDownloadStart()
            await sendStatusMessage(self.listener.message)
            await event.wait()
            async with download_dict_lock:
                if self.listener.uid not in download_dict:
                    return
            from_queue = True
        else:
            from_queue = False

        async with download_dict_lock:
            download_dict[self.listener.uid] = GalleryDLStatus(self, gid, self.listener)

        async with queue_dict_lock:
            non_queued_dl.add(self.listener.uid)

        if from_queue:
            LOGGER.info(f"Start Queued Download from Gallery-dl: {self.name}")
        else:
            LOGGER.info(f"Download from Gallery-dl: {self.name}")
            await self.listener.onDownloadStart()
            await sendStatusMessage(self.listener.message)

        cmd = [
            executable, "-m", "gallery_dl",
            "--dest", path,
            "--filename", "{filename}.{extension}",
            "--no-part",
        ]
        if opt:
            try:
                cmd.extend(shlex.split(opt))
            except Exception:
                pass
        cmd.append(link)

        try:
            self._proc = await create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            LOGGER.error(f"Failed to start gallery-dl: {e}")
            await self.listener.onDownloadError(str(e))
            return

        while self._proc.returncode is None:
            if self._is_cancelled:
                return
            await sleep(2)
            if self._proc.returncode is not None:
                break
            try:
                size, files = await get_path_stats(path)
                now = time()
                dt = now - self._last_time
                if dt > 0:
                    self.speed = max(0, (size - self._last_downloaded) / dt)
                    self._last_downloaded = size
                    self._last_time = now
                self.processed_bytes = size
                self.size = size
                self.files_count = files
                if files > 0:
                    self.progress = f"{files} files"
            except Exception:
                pass

        _, stderr = await self._proc.communicate()
        if self._is_cancelled:
            return

        final_size, total_files = await get_path_stats(path)
        self.size = final_size
        self.processed_bytes = final_size
        self.files_count = total_files

        if total_files == 0:
            err = stderr.decode().strip() if stderr else "No files downloaded by gallery-dl"
            LOGGER.error(f"gallery-dl failed: {err}")
            await self.listener.onDownloadError(err)
            return

        LOGGER.info(f"Gallery-dl completed: {self.name} ({total_files} files, {final_size} bytes)")
        await self.listener.onDownloadComplete()

    async def cancel_download(self):
        self._is_cancelled = True
        LOGGER.info(f"Cancelling Gallery-dl download: {self.name}")
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
            except Exception:
                pass
        await self.listener.onDownloadError("Download Cancelled by User!")
