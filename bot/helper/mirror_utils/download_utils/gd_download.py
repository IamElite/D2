from secrets import token_hex

from .... import download_dict, download_dict_lock, LOGGER, non_queued_dl, queue_dict_lock
from ..upload_utils.gdriveTools import GoogleDriveHelper
from ..status_utils.gdrive_status import GdriveStatus
from ..status_utils.queue_status import QueueStatus
from ...telegram_helper.message_utils import sendMessage, sendStatusMessage
from ...ext_utils.bot_utils import sync_to_async
from ...ext_utils.task_manager import is_queued, limit_checker, stop_duplicate_check


async def add_gd_download(link, path, listener, newname, org_link):
    try:
        drive = GoogleDriveHelper()
        name, mime_type, size, _, _ = await sync_to_async(drive.count, link)
    except Exception as e:
        LOGGER.error(f"GDrive Download Init Error: {e}")
        await sendMessage(listener.message, f"{e}")
        return
    if mime_type is None:
        await sendMessage(listener.message, f"{name}")
        return

    name = newname or name
    gid = token_hex(5)
    msg, button = await stop_duplicate_check(name, listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        return
    if limit_exceeded := await limit_checker(size, listener, isDriveLink=True):
        await sendMessage(listener.message, limit_exceeded)
        return
    added_to_queue, event = await is_queued(listener.uid)
    if added_to_queue:
        LOGGER.info(f"Added to Queue/Download: {name}")
        async with download_dict_lock:
            download_dict[listener.uid] = QueueStatus(
                name, size, gid, listener, 'dl')
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
        await event.wait()
        async with download_dict_lock:
            if listener.uid not in download_dict:
                return
        from_queue = True
    else:
        from_queue = False

    try:
        drive = GoogleDriveHelper(name, path, listener)
    except Exception as e:
        LOGGER.error(f"GDrive Helper Init Error: {e}")
        await sendMessage(listener.message, f"<b>Google Drive Error:</b> <i>{e}</i>")
        return
    async with download_dict_lock:
        download_dict[listener.uid] = GdriveStatus(
            drive, size, listener.message, gid, 'dl', listener.upload_details)

    async with queue_dict_lock:
        non_queued_dl.add(listener.uid)

    if from_queue:
        LOGGER.info(f'Start Queued Download from GDrive: {name}')
    else:
        LOGGER.info(f"Download from GDrive: {name}")
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)

    await sync_to_async(drive.download, link)
