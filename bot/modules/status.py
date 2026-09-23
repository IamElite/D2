#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from psutil import cpu_percent, virtual_memory, disk_usage
from time import time
from asyncio import sleep

from .. import bot_cache, status_reply_dict_lock, download_dict, download_dict_lock, botStartTime, Interval, config_dict, bot, LOGGER
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.message_utils import sendMessage, editMessage, deleteMessage, auto_delete_message, sendStatusMessage, user_info, update_all_messages, delete_all_messages
from ..helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, turn_page, setInterval, new_task, get_bot_stats
from ..helper.themes import BotTheme


@new_task
async def mirror_status(_, message):
    async with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        currentTime = get_readable_time(time() - botStartTime)
        cpu, ram, d_stat = get_bot_stats()
        msg = BotTheme('NO_ACTIVE_DL', cpu=cpu, free=get_readable_file_size(d_stat.free), free_p=round(100 - d_stat.percent, 1),
                       ram=ram, uptime=currentTime)
        reply_message = await sendMessage(message, msg)
        await auto_delete_message(message, reply_message)
    else:
        try:
            await sendStatusMessage(message)
        except Exception as e:
            LOGGER.error("status: %s", e)
            currentTime = get_readable_time(time() - botStartTime)
            cpu, ram, d_stat = get_bot_stats()
            msg = BotTheme('NO_ACTIVE_DL', cpu=cpu, free=get_readable_file_size(d_stat.free), free_p=round(100 - d_stat.percent, 1),
                           ram=ram, uptime=currentTime)
            await sendMessage(message, msg)
            return
        await deleteMessage(message)
        async with status_reply_dict_lock:
            if Interval:
                Interval[0].cancel()
                Interval.clear()
                Interval.append(setInterval(config_dict['STATUS_UPDATE_INTERVAL'], update_all_messages))


@new_task
async def status_pages(_, query):
    user_id = query.from_user.id
    data = query.data.split()
    if "list" in data:
        try:
            from ..helper.ext_utils.bot_utils import MirrorStatus, get_readable_file_size, get_bot_stats
            from ..helper.telegram_helper.button_build import ButtonMaker
            from .. import download_dict as _dd
            from psutil import cpu_percent, disk_usage, virtual_memory
            from time import time as _t2
            from .. import botStartTime
            counts = {"Download": 0, "Upload": 0, "Seed": 0, "Archive": 0, "Extract": 0, "Split": 0, "QueueDl": 0, "QueueUp": 0, "Clone": 0, "CheckUp": 0, "Pause": 0, "SamVideo": 0, "Convert": 0, "FFmpeg": 0}
            dl = 0
            ul = 0
            seed = 0
            for dl_obj in list(_dd.values()):
                try:
                    st = dl_obj.status()
                except:
                    st = ""
                if st == MirrorStatus.STATUS_DOWNLOADING:
                    counts["Download"] += 1
                elif st == MirrorStatus.STATUS_UPLOADING:
                    counts["Upload"] += 1
                elif st == MirrorStatus.STATUS_SEEDING:
                    counts["Seed"] += 1
                elif st == MirrorStatus.STATUS_ARCHIVING:
                    counts["Archive"] += 1
                elif st == MirrorStatus.STATUS_EXTRACTING:
                    counts["Extract"] += 1
                elif st == MirrorStatus.STATUS_SPLITTING:
                    counts["Split"] += 1
                elif st == MirrorStatus.STATUS_QUEUEDL:
                    counts["QueueDl"] += 1
                elif st == MirrorStatus.STATUS_QUEUEUP:
                    counts["QueueUp"] += 1
                elif st == MirrorStatus.STATUS_CLONING:
                    counts["Clone"] += 1
                elif st == MirrorStatus.STATUS_CHECKING:
                    counts["CheckUp"] += 1
                elif st == MirrorStatus.STATUS_PAUSED:
                    counts["Pause"] += 1
                else:
                    counts["Download"] += 1
                try:
                    spd = dl_obj.speed() if hasattr(dl_obj, 'speed') else "0B/s"
                    if st == MirrorStatus.STATUS_SEEDING and hasattr(dl_obj, 'upload_speed'):
                        spd = dl_obj.upload_speed()
                        if "K" in spd:
                            b = float(spd.split("K")[0]) * 1024
                        elif "M" in spd:
                            b = float(spd.split("M")[0]) * 1048576
                        elif "G" in spd:
                            b = float(spd.split("G")[0]) * 1073741824
                        else:
                            b = 0
                        seed += b
                        ul += b
                    else:
                        if "K" in spd:
                            b = float(spd.split("K")[0]) * 1024
                        elif "M" in spd:
                            b = float(spd.split("M")[0]) * 1048576
                        elif "G" in spd:
                            b = float(spd.split("G")[0]) * 1073741824
                        else:
                            b = 0
                        if st == MirrorStatus.STATUS_DOWNLOADING:
                            dl += b
                        elif st == MirrorStatus.STATUS_UPLOADING:
                            ul += b
                        elif st == MirrorStatus.STATUS_SEEDING:
                            seed += b
                except:
                    pass
            cpu, ram, d_st = get_bot_stats()
            from ..helper.ext_utils.bot_utils import get_readable_time
            from time import time as _tt
            up = get_readable_time(int(_tt() - botStartTime))
            overview = f"㊂ Tasks Overview :\n       \n┎ Download: {counts['Download']} | Upload: {counts['Upload']}\n┠ Seed: {counts['Seed']} | Archive: {counts['Archive']}\n┠ Extract: {counts['Extract']} | Split: {counts['Split']}\n┠ QueueDL: {counts['QueueDl']} | QueueUP: {counts['QueueUp']}\n┠ Clone: {counts['Clone']} | CheckUp: {counts['CheckUp']}\n┠ Paused: {counts['Pause']} | SamVideo: {counts['SamVideo']}\n┖ Convert: {counts['Convert']} | FFmpeg: {counts['FFmpeg']}\n  \n┎ Total Tasks: {len(_dd)}\n┠ Total DL Spd: {get_readable_file_size(dl)}/s\n┠ Total UL Spd: {get_readable_file_size(ul)}/s\n┖ Total Seed Spd: {get_readable_file_size(seed)}/s\n  \n❑ Bot Stats\n┠ CPU: {cpu}% | F: {get_readable_file_size(d_st.free)} [{round(100 - d_st.percent, 1)}%]\n┠ RAM: {ram}% | UP: {up}\n┖ DL: {get_readable_file_size(dl)}/s | UL: {get_readable_file_size(ul)}/s"

            btn = ButtonMaker()
            btn.ibutton("← Back", "status back", position="header")
            await editMessage(query.message, overview, btn.build_menu(1))
            await query.answer()
        except Exception as e:
            await query.answer(f"Overview error: {e}", show_alert=True)
        return
    if "ref" in data:
        bot_cache.setdefault('status_refresh', {})
        if user_id in (refresh_status := bot_cache['status_refresh']) and (curr := (time() - refresh_status[user_id])) < 7:
            return await query.answer(f'Already Refreshed! Try after {get_readable_time(7 - curr)}', show_alert=True)
        else:
            refresh_status[user_id] = time()
        await editMessage(query.message, f"{(await user_info(user_id)).mention(style='html')}, <i>Refreshing Status...</i>")
        await sleep(1.5)
        await update_all_messages(True)
    elif "nex" in data or "pre" in data:
        await turn_page(data)
        await update_all_messages(True)
    elif "ps" in data:
        await turn_page(data)
        await update_all_messages(True)
    elif "back" in data:
        await update_all_messages(True)
    elif "close" in data:
        await delete_all_messages()
    await query.answer()


bot.add_handler(MessageHandler(mirror_status, filters=command(
    BotCommands.StatusCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
bot.add_handler(CallbackQueryHandler(status_pages, filters=regex("^status")))
