from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from asyncio import sleep
from aiofiles.os import path as aiopath

from .. import (
    DOWNLOAD_DIR, bot, categories_dict, config_dict, user_data, LOGGER
)
from ..helper.ext_utils.bot_utils import (
    arg_parser, fetch_user_dumps, fetch_user_tds, is_rclone_path, is_url,
    new_task, sync_to_async
)
from ..helper.ext_utils.bulk_links import extract_bulk_links
from ..helper.ext_utils.multi_tools import (
    collect_i_items, delete_own, drop_multi_tag, ensure_multi_tag, multi_still_on,
    next_cmd_text, next_origin, remember_cmd, send_multi_cmd
)
from ..helper.ext_utils.task_manager import task_utils
from ..helper.listeners.tasks_listener import MirrorLeechListener
from ..helper.mirror_utils.download_utils.gallery_dl_download import GalleryDLHelper
from ..helper.mirror_utils.rclone_utils.list import RcloneList
from ..helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    auto_delete_message, delete_links, deleteMessage, open_category_btns,
    open_dump_btns, sendMessage
)


@new_task
async def _gallery_dl(client, message, isLeech=False, compress=False, sameDir=None, bulk=[], multi_tag=None):
    text = message.text.split('\n')
    input_list = text[0].split(' ')

    arg_base = {
        'link': '',
        '-m': '', '-sd': '', '-samedir': '',
        '-n': '', '-name': '', '|': '',
        '-z': False, '-zip': False,
        '-up': '', '-upload': '',
        '-rcf': '',
        '-id': '',
        '-index': '',
        '-c': '', '-category': '',
        '-ud': '', '-dump': '',
        '-t': '', '-thumb': '',
        '-ss': '0', '-screenshots': '',
        '-opt': '',
        '-i': '0',
        '-b': False, '-bulk': False
    }

    args = arg_parser(input_list[1:], arg_base)
    cmd = input_list[0].split('@')[0]

    link = args['link']
    folder_name = args['-m'] or args['-sd'] or args['-samedir']
    name = args['-n'] or args['-name'] or args['|']
    if args['-z'] or args['-zip'] or 'z' in cmd:
        compress = True
    up = args['-up'] or args['-upload']
    rcf = args['-rcf']
    drive_id = args['-id']
    index_link = args['-index']
    gd_cat = args['-c'] or args['-category']
    user_dump = args['-ud'] or args['-dump']
    thumb = args['-t'] or args['-thumb']
    sshots = int(ss) if (ss := (args['-ss'] or args['-screenshots'])).isdigit() else 0
    opt = args['-opt']
    isBulk = args['-b'] or args['-bulk']
    multi = int(args['-i']) if args['-i'].isdigit() else 0

    if folder_name:
        folder_name = f'/{folder_name}'
        if sameDir is None:
            sameDir = {'total': multi, 'tasks': set(), 'name': folder_name}
        sameDir['tasks'].add(message.id)

    if isBulk:
        try:
            bulk = await extract_bulk_links(message, bulk)
        except Exception:
            await sendMessage(message, 'Failed to extract bulk links!')
            return
        if len(bulk) == 0:
            await sendMessage(message, 'No bulk links found!')
            return
        b_msg = input_list[:1]
        b_msg.append(f'{bulk[0]} -i {len(bulk)}')
        nextmsg = await client.send_message(chat_id=message.chat.id, text=' '.join(b_msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        remember_cmd(multi_tag, nextmsg)
        nextmsg.from_user = message.from_user
        _gallery_dl(client, nextmsg, isLeech, compress, sameDir, bulk, multi_tag)
        return

    if len(bulk) != 0:
        del bulk[0]

    multi_tag = ensure_multi_tag(multi_tag, multi)

    @new_task
    async def __run_multi():
        if multi <= 1:
            drop_multi_tag(multi_tag)
            await sleep(2)
            await delete_own(message)
            return
        await sleep(7)
        if not multi_still_on(multi_tag):
            await delete_own(message)
            return
        nxt = multi - 1
        cmd_txt = next_cmd_text(input_list, bulk, nxt)
        origin = await next_origin(client, message, bulk, bool(link))
        if not multi_still_on(multi_tag):
            await delete_own(message)
            return
        await delete_own(message)
        if not multi_still_on(multi_tag):
            return
        nextmsg = await send_multi_cmd(origin, cmd_txt, multi_tag, nxt)
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        remember_cmd(multi_tag, nextmsg)
        if folder_name:
            sameDir['tasks'].add(nextmsg.id)
        nextmsg.from_user = message.from_user
        if not multi_still_on(multi_tag):
            await delete_own(nextmsg)
            return
        _gallery_dl(client, nextmsg, isLeech, compress, sameDir, bulk, multi_tag)

    if username := message.from_user.username:
        tag = f'@{username}'
    else:
        tag = message.from_user.mention

    if not link and (reply_to := message.reply_to_message) and reply_to.text:
        link = reply_to.text.split('\n', 1)[0].strip()

    if not is_url(link):
        help_msg = (
            f"Hey <b>{tag}</b>,\n\n"
            f"<b>Usage:</b>\n"
            f"<code>/{cmd} &lt;link&gt;</code>\n"
            f"Or reply to any media/album link with <code>/{cmd}</code>\n\n"
            f"<b>Supported Commands:</b>\n"
            f"• <code>/{BotCommands.GdlCommand}</code> : Mirror images/album to Drive or Rclone\n"
            f"• <code>/{BotCommands.GdlLeechCommand}</code> : Leech photos directly to Telegram\n"
            f"• <code>/{BotCommands.GdlZipCommand}</code> : Compress into ZIP & Mirror\n"
            f"• <code>/{BotCommands.GdlZipLeechCommand}</code> : Compress into ZIP & Leech\n\n"
            f"<b>Arguments:</b>\n"
            f"• <code>-n name</code> : Custom name for file/folder\n"
            f"• <code>-z</code> : Zip compress\n"
            f"• <code>-up path</code> : Upload destination (Drive/Rclone/Channel)"
        )
        await sendMessage(message, help_msg)
        await delete_links(message)
        return

    error_msg = []
    task_utilis_msg, error_button = await task_utils(message)
    if task_utilis_msg:
        error_msg.extend(task_utilis_msg)

    if error_msg:
        final_msg = f'Hey, <b>{tag}</b>,\n'
        for __i, __msg in enumerate(error_msg, 1):
            final_msg += f'\n<b>{__i}</b>: {__msg}\n'
        if error_button is not None:
            error_button = error_button.build_menu(2)
        await sendMessage(message, final_msg, error_button)
        await delete_links(message)
        return

    if not isLeech:
        if config_dict['DEFAULT_UPLOAD'] == 'rc' and not up or up == 'rc':
            up = config_dict['RCLONE_PATH']
        elif config_dict['DEFAULT_UPLOAD'] == 'ddl' and not up or up == 'ddl':
            up = 'ddl'
        if not up and config_dict['DEFAULT_UPLOAD'] == 'gd':
            up = 'gd'
            user_tds = await fetch_user_tds(message.from_user.id)
            if not drive_id and gd_cat:
                merged_dict = {**categories_dict, **user_tds}
                for drive_name, drive_dict in merged_dict.items():
                    if drive_name.casefold() == gd_cat.replace('_', ' ').casefold():
                        drive_id, index_link = (drive_dict['drive_id'], drive_dict['index_link'])
                        break
            if not drive_id and len(user_tds) == 1:
                drive_id, index_link = next(iter(user_tds.values())).values()
            elif not drive_id and (len(categories_dict) > 1 and len(user_tds) == 0 or len(categories_dict) >= 1 and len(user_tds) > 1):
                drive_id, index_link, is_cancelled = await open_category_btns(message)
                if is_cancelled:
                    await delete_links(message)
                    return
            if drive_id and not await sync_to_async(GoogleDriveHelper().getFolderData, drive_id):
                return await sendMessage(message, "Google Drive ID validation failed!")
        if up == 'gd' and not config_dict['GDRIVE_ID'] and not drive_id:
            await sendMessage(message, 'GDRIVE_ID not Provided!')
            await delete_links(message)
            return
        elif not up:
            await sendMessage(message, 'No Rclone Destination!')
            await delete_links(message)
            return
        elif up not in ['rcl', 'gd', 'ddl']:
            if up.startswith('mrcc:'):
                config_path = f'wcl/{message.from_user.id}.conf'
            else:
                config_path = 'wcl.conf'
            if not await aiopath.exists(config_path):
                await sendMessage(message, f'Rclone Config: {config_path} not Exists!')
                await delete_links(message)
                return
        if up != 'gd' and up != 'ddl' and not is_rclone_path(up):
            await sendMessage(message, 'Wrong Rclone Upload Destination!')
            await delete_links(message)
            return
    else:
        if user_dump and (user_dump.isdigit() or user_dump.startswith('-')):
            up = int(user_dump)
        elif user_dump and user_dump.startswith('@'):
            up = user_dump
        elif (ldumps := await fetch_user_dumps(message.from_user.id)):
            if user_dump and user_dump.casefold() == "all":
                up = [dump_id for dump_id in ldumps.values()]
            elif user_dump:
                up = next((dump_id for name_, dump_id in ldumps.items() if user_dump.casefold() == name_.casefold()), '')
            if not up and len(ldumps) == 1:
                up = next(iter(ldumps.values()))
            elif not up:
                up, is_cancelled = await open_dump_btns(message)
                if is_cancelled:
                    await delete_links(message)
                    return

    if up == 'rcl' and not isLeech:
        up = await RcloneList(client, message).get_rclone_path('rcu')
        if not is_rclone_path(up):
            await sendMessage(message, up)
            await delete_links(message)
            return

    __run_multi()
    await delete_links(message)

    listener = MirrorLeechListener(
        message, compress, isLeech=isLeech, tag=tag, sameDir=sameDir,
        rcFlags=rcf, upPath=up, drive_id=drive_id, index_link=index_link,
        source_url=link, leech_utils={'screenshots': sshots, 'thumb': thumb}
    )

    path = f'{DOWNLOAD_DIR}{listener.uid}{folder_name}' if folder_name else f'{DOWNLOAD_DIR}{listener.uid}'
    LOGGER.info(f'Downloading with gallery-dl: {link}')
    try:
        helper = GalleryDLHelper(listener)
        await helper.add_download(link, path, name=name, opt=opt)
    except Exception as e:
        LOGGER.error(f'Gallery-dl execution error: {e}')
        await sendMessage(message, f'{tag} <b>Gallery-dl Error:</b>\n<code>{e}</code>')
        await delete_links(message)


async def gdl_mirror(client, message):
    await _gallery_dl(client, message)


async def gdl_leech(client, message):
    await _gallery_dl(client, message, isLeech=True)


async def gdl_zip(client, message):
    await _gallery_dl(client, message, compress=True)


async def gdl_zipleech(client, message):
    await _gallery_dl(client, message, isLeech=True, compress=True)


bot.add_handler(MessageHandler(
    gdl_mirror, filters=command(BotCommands.GdlCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted
))
bot.add_handler(MessageHandler(
    gdl_leech, filters=command(BotCommands.GdlLeechCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted
))
bot.add_handler(MessageHandler(
    gdl_zip, filters=command(BotCommands.GdlZipCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted
))
bot.add_handler(MessageHandler(
    gdl_zipleech, filters=command(BotCommands.GdlZipLeechCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted
))
