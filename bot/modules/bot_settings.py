#!/usr/bin/env python3
from random import choice
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex, create
from pyrogram.enums import ChatType
from functools import partial
from collections import OrderedDict
from asyncio import create_subprocess_exec, create_subprocess_shell, sleep, gather
from aiofiles.os import remove, rename, path as aiopath
from aiofiles import open as aiopen
from os import environ, getcwd
from dotenv import load_dotenv
from time import time
from io import BytesIO
from html import escape
from aioshutil import rmtree as aiormtree

from .. import config_dict, user_data, HELPER_TOKENS, DATABASE_URL, _parse_port, MAX_SPLIT_SIZE, list_drives_dict, categories_dict, aria2, GLOBAL_EXTENSION_FILTER, status_reply_dict_lock, Interval, aria2_options, aria2c_global, IS_PREMIUM_USER, download_dict, qbit_options, get_client, LOGGER, bot, extra_buttons, shorteners_list
from ..helper.ext_utils.engine_lifecycle import ensure_qbit
from ..helper.telegram_helper.message_utils import sendMessage, sendFile, editMessage, deleteMessage, update_all_messages
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.ext_utils.bot_utils import setInterval, sync_to_async, new_thread
from ..helper.ext_utils.db_handler import DbManger
from ..helper.ext_utils.task_manager import start_from_queued
from ..helper.ext_utils.help_messages import default_desp
from ..helper.mirror_utils.rclone_utils.serve import rclone_serve_booter
from .torrent_search import initiate_search_tools
from .rss import addJob
from ..helper.themes import AVL_THEMES

START = 0
STATE = 'view'
WALL_MODE = 'normal'
WALL_IDX = 0
WALL_START = 0
handler_dict = {}
default_values = {'AUTO_DELETE_MESSAGE_DURATION': 30,
                  'DEFAULT_UPLOAD': 'gd',
                  'DOWNLOAD_DIR': '/usr/src/app/downloads/',
                  'LEECH_SPLIT_SIZE': MAX_SPLIT_SIZE,
                  'RSS_DELAY': 600,
                  'STATUS_UPDATE_INTERVAL': 5,
                  'WALLPAPER_URL': ['https://api.aniwallpaper.workers.dev/random?type=girls','https://api.icatw.site/api/v1/images/random.jpg?category=anime&orientation=landscape','https://api.waifu.im/images?IncludedTags=waifu&Orientation=LANDSCAPE','https://picsum.photos/1920/1080'],
                  'WALLPAPER_MODE': [],
                  'WALLPAPER_MULTIPLIER': 2,
                  'SEARCH_LIMIT': 0,
                  'UPSTREAM_BRANCH': 'srmlx',
                  'BOT_THEME': 'minimal',
                  'BOT_LANG': 'en',
                  'IMG_PAGE': 1,
                  'AUTHOR_NAME': 'sʏɴᴛᴀx ʀᴇᴀʟᴍ',
                  'AUTHOR_URL': 'https://t.me/SyntaxRealm',
                  'TITLE_NAME': 'sʏɴᴛᴀx ʀᴇᴀʟᴍ',
                  'GD_INFO': 'Syntax Realm Leech Bot',
                  }
bool_vars = ['AS_DOCUMENT', 'BOT_PM', 'STOP_DUPLICATE', 'SET_COMMANDS', 'SAVE_MSG', 'SHOW_MEDIAINFO', 'SOURCE_LINK', 'SAFE_MODE', 'SHOW_EXTRA_CMDS',
             'IS_TEAM_DRIVE', 'USE_SERVICE_ACCOUNTS', 'WEB_PINCODE', 'EQUAL_SPLITS', 'DISABLE_DRIVE_LINK', 'DELETE_LINKS', 'CLEAN_LOG_MSG', 'USER_TD_MODE', 
             'INCOMPLETE_TASK_NOTIFIER', 'UPGRADE_PACKAGES', 'SCREENSHOTS_MODE']


async def load_config():

    BOT_TOKEN = environ.get('BOT_TOKEN', '')
    if len(BOT_TOKEN) == 0:
        BOT_TOKEN = config_dict['BOT_TOKEN']

    TELEGRAM_API = environ.get('TELEGRAM_API', '')
    if len(TELEGRAM_API) == 0:
        TELEGRAM_API = config_dict['TELEGRAM_API']
    else:
        TELEGRAM_API = int(TELEGRAM_API)

    TELEGRAM_HASH = environ.get('TELEGRAM_HASH', '')
    if len(TELEGRAM_HASH) == 0:
        TELEGRAM_HASH = config_dict['TELEGRAM_HASH']

    BOT_MAX_TASKS = environ.get('BOT_MAX_TASKS', '')
    BOT_MAX_TASKS = int(BOT_MAX_TASKS) if BOT_MAX_TASKS.isdigit() else ''
    
    OWNER_ID = environ.get('OWNER_ID', '')
    OWNER_ID = config_dict['OWNER_ID'] if len(OWNER_ID) == 0 else int(OWNER_ID)

    DATABASE_URL = environ.get('DATABASE_URL', '')
    if len(DATABASE_URL) == 0:
        DATABASE_URL = ''

    DOWNLOAD_DIR = environ.get('DOWNLOAD_DIR', '')
    if len(DOWNLOAD_DIR) == 0:
        DOWNLOAD_DIR = '/usr/src/app/downloads/'
    elif not DOWNLOAD_DIR.endswith("/"):
        DOWNLOAD_DIR = f'{DOWNLOAD_DIR}/'

    GDRIVE_ID = environ.get('GDRIVE_ID', '')
    if len(GDRIVE_ID) == 0:
        GDRIVE_ID = ''

    RCLONE_PATH = environ.get('RCLONE_PATH', '')
    if len(RCLONE_PATH) == 0:
        RCLONE_PATH = ''

    DEFAULT_UPLOAD = environ.get('DEFAULT_UPLOAD', '')
    if DEFAULT_UPLOAD != 'rc' and DEFAULT_UPLOAD != 'ddl':
        DEFAULT_UPLOAD = 'gd'

    RCLONE_FLAGS = environ.get('RCLONE_FLAGS', '')
    if len(RCLONE_FLAGS) == 0:
        RCLONE_FLAGS = ''

    AUTHORIZED_CHATS = environ.get('AUTHORIZED_CHATS', '')
    if len(AUTHORIZED_CHATS) != 0:
        aid = AUTHORIZED_CHATS.split()
        for id_ in aid:
            chat_id, *topic_ids = id_.split(':')
            chat_id = int(chat_id)
            user_data.setdefault(chat_id, {'is_auth': True})
            if topic_ids:
                user_data[chat_id].setdefault('topic_ids', []).extend(map(int, topic_ids))

    SUDO_USERS = environ.get('SUDO_USERS', '')
    if len(SUDO_USERS) != 0:
        aid = SUDO_USERS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {'is_sudo': True}
            
    BLACKLIST_USERS = environ.get('BLACKLIST_USERS', '')
    if len(BLACKLIST_USERS) != 0:
        aid = BLACKLIST_USERS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {'is_blacklist': True}

    EXTENSION_FILTER = environ.get('EXTENSION_FILTER', '')
    if len(EXTENSION_FILTER) > 0:
        fx = EXTENSION_FILTER.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.extend(['aria2', '!qB'])
        for x in fx:
            x = x.lstrip('.')
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())

    MEGA_EMAIL = environ.get('MEGA_EMAIL', '')
    MEGA_PASSWORD = environ.get('MEGA_PASSWORD', '')
    if len(MEGA_EMAIL) == 0 or len(MEGA_PASSWORD) == 0:
        MEGA_EMAIL = ''
        MEGA_PASSWORD = ''

    METADATA = environ.get('METADATA', '')
    if len(METADATA) == 0:
        METADATA = ''

    ATTACHMENT = environ.get('ATTACHMENT', '')
    if len(ATTACHMENT) == 0:
        ATTACHMENT = ''
      
    GDTOT_CRYPT = environ.get('GDTOT_CRYPT', '')
    if len(GDTOT_CRYPT) == 0:
        GDTOT_CRYPT = ''
        
    JIODRIVE_TOKEN = environ.get('JIODRIVE_TOKEN', '')
    if len(JIODRIVE_TOKEN) == 0:
        JIODRIVE_TOKEN = ''

    REAL_DEBRID_API = environ.get('REAL_DEBRID_API', '')
    if len(REAL_DEBRID_API) == 0:
        REAL_DEBRID_API = ''
        
    DEBRID_LINK_API = environ.get('DEBRID_LINK_API', '')
    if len(DEBRID_LINK_API) == 0:
        DEBRID_LINK_API = ''

    INDEX_URL = environ.get('INDEX_URL', '').rstrip("/")
    if len(INDEX_URL) == 0:
        INDEX_URL = ''

    SEARCH_API_LINK = environ.get('SEARCH_API_LINK', '').rstrip("/")
    if len(SEARCH_API_LINK) == 0:
        SEARCH_API_LINK = ''

    CAP_FONT = environ.get('CAP_FONT', 'b').lower().strip()
    if CAP_FONT not in ['b', 'i', 'u', 's', 'spoiler', 'code']:
        CAP_FONT = 'b'
        
    LEECH_FILENAME_PREFIX = environ.get('LEECH_FILENAME_PREFIX', '')
    if len(LEECH_FILENAME_PREFIX) == 0:
        LEECH_FILENAME_PREFIX = ''

    LEECH_FILENAME_SUFFIX = environ.get('LEECH_FILENAME_SUFFIX', '')
    if len(LEECH_FILENAME_SUFFIX) == 0:
        LEECH_FILENAME_SUFFIX = ''

    LEECH_FILENAME_CAPTION = environ.get('LEECH_FILENAME_CAPTION', '')
    if len(LEECH_FILENAME_CAPTION) == 0:
        LEECH_FILENAME_CAPTION = ''

    LEECH_FILENAME_REMNAME = environ.get('LEECH_FILENAME_REMNAME', '')
    if len(LEECH_FILENAME_REMNAME) == 0:
        LEECH_FILENAME_REMNAME = ''

    MIRROR_FILENAME_PREFIX = environ.get('MIRROR_FILENAME_PREFIX', '')
    if len(MIRROR_FILENAME_PREFIX) == 0:
        MIRROR_FILENAME_PREFIX = ''

    MIRROR_FILENAME_SUFFIX = environ.get('MIRROR_FILENAME_SUFFIX', '')
    if len(MIRROR_FILENAME_SUFFIX) == 0:
        MIRROR_FILENAME_SUFFIX = ''

    MIRROR_FILENAME_REMNAME = environ.get('MIRROR_FILENAME_REMNAME', '')
    if len(MIRROR_FILENAME_REMNAME) == 0:
        MIRROR_FILENAME_REMNAME = ''
        
    SEARCH_PLUGINS = environ.get('SEARCH_PLUGINS', '')
    if len(SEARCH_PLUGINS) == 0:
        SEARCH_PLUGINS = ''

    MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

    LEECH_SPLIT_SIZE = environ.get('LEECH_SPLIT_SIZE', '')
    if len(LEECH_SPLIT_SIZE) == 0 or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE:
        LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
    else:
        LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

    STATUS_UPDATE_INTERVAL = environ.get('STATUS_UPDATE_INTERVAL', '')
    if len(STATUS_UPDATE_INTERVAL) == 0:
        STATUS_UPDATE_INTERVAL = 5
    else:
        STATUS_UPDATE_INTERVAL = int(STATUS_UPDATE_INTERVAL)
    if len(download_dict) != 0:
        async with status_reply_dict_lock:
            if Interval:
                Interval[0].cancel()
                Interval.clear()
                Interval.append(setInterval(STATUS_UPDATE_INTERVAL, update_all_messages))

    import re as _re_w, json as _json_w, ast as _ast_w
    def _parse_w(raw):
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        raw = str(raw or '').strip()
        if not raw:
            return []
        if raw.startswith('['):
            try:
                arr = _json_w.loads(raw)
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr if str(x).strip()]
            except:
                pass
            try:
                arr = _ast_w.literal_eval(raw)
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr if str(x).strip()]
            except:
                pass
        return [p.strip() for p in _re_w.split(r'[,\s]+', raw) if p.strip()]
    _wall_def = ['https://api.aniwallpaper.workers.dev/random?type=girls','https://api.icatw.site/api/v1/images/random.jpg?category=anime&orientation=landscape','https://api.waifu.im/images?IncludedTags=waifu&Orientation=LANDSCAPE','https://picsum.photos/1920/1080']
    WALLPAPER_URL = _parse_w(environ.get('WALLPAPER_URL', '')) or _wall_def
    WALLPAPER_MODE = []
    WALLPAPER_MULTIPLIER = environ.get('WALLPAPER_MULTIPLIER', '')
    if len(WALLPAPER_MULTIPLIER) == 0:
        WALLPAPER_MULTIPLIER = 2
    else:
        WALLPAPER_MULTIPLIER = int(WALLPAPER_MULTIPLIER)

    AUTO_DELETE_MESSAGE_DURATION = environ.get(
        'AUTO_DELETE_MESSAGE_DURATION', '')
    if len(AUTO_DELETE_MESSAGE_DURATION) == 0:
        AUTO_DELETE_MESSAGE_DURATION = 30
    else:
        AUTO_DELETE_MESSAGE_DURATION = int(AUTO_DELETE_MESSAGE_DURATION)

    YT_DLP_OPTIONS = environ.get('YT_DLP_OPTIONS', '')
    if len(YT_DLP_OPTIONS) == 0:
        YT_DLP_OPTIONS = ''

    SEARCH_LIMIT = environ.get('SEARCH_LIMIT', '')
    SEARCH_LIMIT = 0 if len(SEARCH_LIMIT) == 0 else int(SEARCH_LIMIT)

    STATUS_LIMIT = environ.get('STATUS_LIMIT', '')
    STATUS_LIMIT = 10 if len(STATUS_LIMIT) == 0 else int(STATUS_LIMIT)

    RSS_CHAT = environ.get('RSS_CHAT', '')
    RSS_CHAT = '' if len(RSS_CHAT) == 0 else int(RSS_CHAT)

    RSS_DELAY = environ.get('RSS_DELAY', '')
    RSS_DELAY = 900 if len(RSS_DELAY) == 0 else int(RSS_DELAY)

    CMD_SUFFIX = environ.get('CMD_SUFFIX', '')

    USER_SESSION_STRING = environ.get('USER_SESSION_STRING', '')

    # Helper Config — dedupe + pause
    HELPER_TOKENS = environ.get('HELPER_TOKENS', '')
    if HELPER_TOKENS is None:
        HELPER_TOKENS = ''
    else:
        HELPER_TOKENS = str(HELPER_TOKENS).strip()
    # silent dedupe preserve order
    if HELPER_TOKENS:
        _seen = set()
        _deduped = []
        for _t in str(HELPER_TOKENS).split():
            _t = _t.strip()
            if _t and _t not in _seen:
                _seen.add(_t)
                _deduped.append(_t)
        HELPER_TOKENS = " ".join(_deduped)
        environ['HELPER_TOKENS'] = HELPER_TOKENS
        config_dict['HELPER_TOKENS'] = HELPER_TOKENS
    HELPER_PAUSE_RAW = environ.get('HELPER_PAUSE', '')
    if isinstance(HELPER_PAUSE_RAW, str):
        HELPER_PAUSE = HELPER_PAUSE_RAW.strip().lower() in ('1', 'true', 'yes', 'on', 'pause', 'paused')
        if not HELPER_PAUSE_RAW.strip():
            HELPER_PAUSE = bool(config_dict.get('HELPER_PAUSE', False))
    else:
        HELPER_PAUSE = bool(HELPER_PAUSE_RAW) if HELPER_PAUSE_RAW != '' else bool(config_dict.get('HELPER_PAUSE', False))

    TORRENT_TIMEOUT = environ.get('TORRENT_TIMEOUT', '')
    downloads = aria2.get_downloads()
    if len(TORRENT_TIMEOUT) == 0:
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(aria2.client.change_option, download.gid, {'bt-stop-timeout': '0'})
                except Exception as e:
                    LOGGER.error(e)
        aria2_options['bt-stop-timeout'] = '0'
        if DATABASE_URL:
            await DbManger().update_aria2('bt-stop-timeout', '0')
        TORRENT_TIMEOUT = ''
    else:
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(aria2.client.change_option, download.gid, {'bt-stop-timeout': TORRENT_TIMEOUT})
                except Exception as e:
                    LOGGER.error(e)
        aria2_options['bt-stop-timeout'] = TORRENT_TIMEOUT
        if DATABASE_URL:
            await DbManger().update_aria2('bt-stop-timeout', TORRENT_TIMEOUT)
        TORRENT_TIMEOUT = int(TORRENT_TIMEOUT)

    QUEUE_ALL = environ.get('QUEUE_ALL', '')
    QUEUE_ALL = '' if len(QUEUE_ALL) == 0 else int(QUEUE_ALL)

    QUEUE_DOWNLOAD = environ.get('QUEUE_DOWNLOAD', '')
    QUEUE_DOWNLOAD = '' if len(QUEUE_DOWNLOAD) == 0 else int(QUEUE_DOWNLOAD)

    QUEUE_UPLOAD = environ.get('QUEUE_UPLOAD', '')
    QUEUE_UPLOAD = '' if len(QUEUE_UPLOAD) == 0 else int(QUEUE_UPLOAD)

    INCOMPLETE_TASK_NOTIFIER = environ.get('INCOMPLETE_TASK_NOTIFIER', '')
    INCOMPLETE_TASK_NOTIFIER = INCOMPLETE_TASK_NOTIFIER.lower() == 'true'
    if not INCOMPLETE_TASK_NOTIFIER and DATABASE_URL:
        await DbManger().trunc_table('tasks')

    STOP_DUPLICATE = environ.get('STOP_DUPLICATE', '')
    STOP_DUPLICATE = STOP_DUPLICATE.lower() == 'true'

    IS_TEAM_DRIVE = environ.get('IS_TEAM_DRIVE', '')
    IS_TEAM_DRIVE = IS_TEAM_DRIVE.lower() == 'true'

    USE_SERVICE_ACCOUNTS = environ.get('USE_SERVICE_ACCOUNTS', '')
    USE_SERVICE_ACCOUNTS = USE_SERVICE_ACCOUNTS.lower() == 'true'

    WEB_PINCODE = environ.get('WEB_PINCODE', '')
    WEB_PINCODE = WEB_PINCODE.lower() == 'true'

    AS_DOCUMENT = environ.get('AS_DOCUMENT', 'true')
    AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'
    
    USER_TD_MODE = environ.get('USER_TD_MODE', '')
    USER_TD_MODE = USER_TD_MODE.lower() == 'true'

    USER_TD_SA = environ.get('USER_TD_SA', '')
    USER_TD_SA = USER_TD_SA.lower() if len(USER_TD_SA) != 0 else ''

    SHOW_MEDIAINFO = environ.get('SHOW_MEDIAINFO', '')
    SHOW_MEDIAINFO = SHOW_MEDIAINFO.lower() == 'true'
    
    SHOW_MEDIAINFO = environ.get('SHOW_MEDIAINFO', '')
    SHOW_MEDIAINFO = SHOW_MEDIAINFO.lower() == 'true'
    
    SOURCE_LINK = environ.get('SOURCE_LINK', '')
    SOURCE_LINK = SOURCE_LINK.lower() == 'true'

    DELETE_LINKS = environ.get('DELETE_LINKS', '')
    DELETE_LINKS = DELETE_LINKS.lower() == 'true'

    EQUAL_SPLITS = environ.get('EQUAL_SPLITS', '')
    EQUAL_SPLITS = EQUAL_SPLITS.lower() == 'true'

    MEDIA_GROUP = environ.get('MEDIA_GROUP', '')
    MEDIA_GROUP = MEDIA_GROUP.lower() == 'true'

    BASE_URL_PORT = environ.get('BASE_URL_PORT', '')
    BASE_URL_PORT = 80 if len(BASE_URL_PORT) == 0 else int(BASE_URL_PORT)

    RCLONE_SERVE_URL = environ.get('RCLONE_SERVE_URL', '')
    if len(RCLONE_SERVE_URL) == 0:
        RCLONE_SERVE_URL = ''

    RCLONE_SERVE_PORT = environ.get('RCLONE_SERVE_PORT', '')
    RCLONE_SERVE_PORT = 8080 if len(
        RCLONE_SERVE_PORT) == 0 else int(RCLONE_SERVE_PORT)

    RCLONE_SERVE_USER = environ.get('RCLONE_SERVE_USER', '')
    if len(RCLONE_SERVE_USER) == 0:
        RCLONE_SERVE_USER = ''

    RCLONE_SERVE_PASS = environ.get('RCLONE_SERVE_PASS', '')
    if len(RCLONE_SERVE_PASS) == 0:
        RCLONE_SERVE_PASS = ''

    from web.aio_wserver import restart_web_server, stop_web_server
    BASE_URL = environ.get('BASE_URL', '').rstrip("/")
    if len(BASE_URL) == 0:
        BASE_URL = ''
        await stop_web_server()
    else:
        # PORT (Heroku router) set ho to wahi authoritative hai — warna server us
        # port pe chala jaata jahan platform route hi nahi karta.
        _port_override = _parse_port(environ.get('PORT'), 'PORT', 0)
        await restart_web_server(_port_override or BASE_URL_PORT)

    UPSTREAM_REPO = environ.get('UPSTREAM_REPO', '')
    if len(UPSTREAM_REPO) == 0:
        UPSTREAM_REPO = 'https://github.com/IamElite/D2.git'

    UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', '')
    if len(UPSTREAM_BRANCH) == 0:
        UPSTREAM_BRANCH = 'srmlx'

    UPGRADE_PACKAGES = environ.get('UPGRADE_PACKAGES', '')
    UPGRADE_PACKAGES = UPGRADE_PACKAGES.lower() == 'true'

    STORAGE_THRESHOLD = environ.get('STORAGE_THRESHOLD', '')
    STORAGE_THRESHOLD = '' if len(
        STORAGE_THRESHOLD) == 0 else float(STORAGE_THRESHOLD)

    TORRENT_LIMIT = environ.get('TORRENT_LIMIT', '')
    TORRENT_LIMIT = '' if len(TORRENT_LIMIT) == 0 else float(TORRENT_LIMIT)

    DIRECT_LIMIT = environ.get('DIRECT_LIMIT', '')
    DIRECT_LIMIT = '' if len(DIRECT_LIMIT) == 0 else float(DIRECT_LIMIT)

    YTDLP_LIMIT = environ.get('YTDLP_LIMIT', '')
    YTDLP_LIMIT = '' if len(YTDLP_LIMIT) == 0 else float(YTDLP_LIMIT)

    GDRIVE_LIMIT = environ.get('GDRIVE_LIMIT', '')
    GDRIVE_LIMIT = '' if len(GDRIVE_LIMIT) == 0 else float(GDRIVE_LIMIT)

    CLONE_LIMIT = environ.get('CLONE_LIMIT', '')
    CLONE_LIMIT = '' if len(CLONE_LIMIT) == 0 else float(CLONE_LIMIT)

    MEGA_LIMIT = environ.get('MEGA_LIMIT', '')
    MEGA_LIMIT = '' if len(MEGA_LIMIT) == 0 else float(MEGA_LIMIT)

    LEECH_LIMIT = environ.get('LEECH_LIMIT', '')
    LEECH_LIMIT = '' if len(LEECH_LIMIT) == 0 else float(LEECH_LIMIT)

    FSUB_IDS = environ.get('FSUB_IDS', '')
    if len(FSUB_IDS) == 0:
        FSUB_IDS = ''
    
    LINKS_LOG_ID = environ.get('LINKS_LOG_ID', '')
    LINKS_LOG_ID = '' if len(LINKS_LOG_ID) == 0 else int(LINKS_LOG_ID)

    MIRROR_LOG_ID = environ.get('MIRROR_LOG_ID', '')
    if len(MIRROR_LOG_ID) == 0:
        MIRROR_LOG_ID = ''
        
    LEECH_LOG_ID = environ.get('LEECH_LOG_ID', '')
    if len(LEECH_LOG_ID) == 0:
        LEECH_LOG_ID = ''
        
    EXCEP_CHATS = environ.get('EXCEP_CHATS', '')
    if len(EXCEP_CHATS) == 0:
        EXCEP_CHATS = ''

    USER_MAX_TASKS = environ.get('USER_MAX_TASKS', '')
    USER_MAX_TASKS = int(USER_MAX_TASKS) if USER_MAX_TASKS.isdigit() else ''

    USER_TIME_INTERVAL = environ.get('USER_TIME_INTERVAL', '')
    USER_TIME_INTERVAL = int(USER_TIME_INTERVAL) if USER_TIME_INTERVAL.isdigit() else 0

    PLAYLIST_LIMIT = environ.get('PLAYLIST_LIMIT', '')
    PLAYLIST_LIMIT = '' if len(PLAYLIST_LIMIT) == 0 else int(PLAYLIST_LIMIT)

    BOT_PM = environ.get('BOT_PM', 'true')
    BOT_PM = BOT_PM.lower() == 'true'

    DAILY_TASK_LIMIT = environ.get('DAILY_TASK_LIMIT', '')
    DAILY_TASK_LIMIT = '' if len(DAILY_TASK_LIMIT) == 0 else int(DAILY_TASK_LIMIT)

    DAILY_MIRROR_LIMIT = environ.get('DAILY_MIRROR_LIMIT', '')
    DAILY_MIRROR_LIMIT = '' if len(DAILY_MIRROR_LIMIT) == 0 else float(DAILY_MIRROR_LIMIT)

    DAILY_LEECH_LIMIT = environ.get('DAILY_LEECH_LIMIT', '')
    DAILY_LEECH_LIMIT = '' if len(DAILY_LEECH_LIMIT) == 0 else float(DAILY_LEECH_LIMIT)

    DISABLE_DRIVE_LINK = environ.get('DISABLE_DRIVE_LINK', '')
    DISABLE_DRIVE_LINK = DISABLE_DRIVE_LINK.lower() == 'true'

    BOT_THEME = environ.get('BOT_THEME', '')
    if len(BOT_THEME) == 0:
        BOT_THEME = 'minimal'

    IMG_SEARCH = environ.get('IMG_SEARCH', '')
    IMG_SEARCH = (IMG_SEARCH.replace("'", '').replace('"', '').replace('[', '').replace(']', '').replace(",", "")).split()
    
    IMG_PAGE = environ.get('IMG_PAGE', '')
    IMG_PAGE = int(IMG_PAGE) if IMG_PAGE.isdigit() else ''

    IMAGES = environ.get('IMAGES', '')
    IMAGES = (IMAGES.replace("'", '').replace('"', '').replace('[', '').replace(']', '').replace(",", "")).split()

    AUTHOR_NAME = environ.get('AUTHOR_NAME', '')
    if len(AUTHOR_NAME) == 0:
        AUTHOR_NAME = 'sʏɴᴛᴀx ʀᴇᴀʟᴍ'

    AUTHOR_URL = environ.get('AUTHOR_URL', '')
    if len(AUTHOR_URL) == 0:
        AUTHOR_URL = 'https://t.me/SyntaxRealm'

    TITLE_NAME = environ.get('TITLE_NAME', '')
    if len(TITLE_NAME) == 0:
        TITLE_NAME = 'sʏɴᴛᴀx ʀᴇᴀʟᴍ'
        
    COVER_IMAGE = environ.get('COVER_IMAGE', '')
    if len(COVER_IMAGE) == 0:
        COVER_IMAGE = 'https://graph.org/file/0ff9d5e94a070fe4154c0.jpg'

    GD_INFO = environ.get('GD_INFO', '')
    if len(GD_INFO) == 0:
        GD_INFO = 'Syntax Realm Leech Bot'

    SAVE_MSG = environ.get('SAVE_MSG', '')
    SAVE_MSG = SAVE_MSG.lower() == 'true'

    SET_COMMANDS = environ.get('SET_COMMANDS', '')
    SET_COMMANDS = SET_COMMANDS.lower() == 'true'
    
    SAFE_MODE = environ.get('SAFE_MODE', '')
    SAFE_MODE = SAFE_MODE.lower() == 'true'
    
    SCREENSHOTS_MODE = environ.get('SCREENSHOTS_MODE', '')
    SCREENSHOTS_MODE = SCREENSHOTS_MODE.lower() == 'true'

    CLEAN_LOG_MSG = environ.get('CLEAN_LOG_MSG', '')
    CLEAN_LOG_MSG = CLEAN_LOG_MSG.lower() == 'true'
    
    SHOW_EXTRA_CMDS = environ.get('SHOW_EXTRA_CMDS', '')
    SHOW_EXTRA_CMDS = SHOW_EXTRA_CMDS.lower() == 'true'
    
    TOKEN_TIMEOUT = environ.get('TOKEN_TIMEOUT', '')
    TOKEN_TIMEOUT = int(TOKEN_TIMEOUT) if TOKEN_TIMEOUT.isdigit() else ''

    LOGIN_PASS = environ.get('LOGIN_PASS', '')
    if len(LOGIN_PASS) == 0:
        LOGIN_PASS = None

    FILELION_API = environ.get('FILELION_API', '')
    if len(FILELION_API) == 0:
        FILELION_API = ''

    DEF_IMDB_TEMP  = environ.get('IMDB_TEMPLATE', '')
    if len(DEF_IMDB_TEMP) == 0:
        DEF_IMDB_TEMP = '''<b>Title: </b> {title} [{year}]
<b>Also Known As:</b> {aka}
<b>Rating ⭐️:</b> <i>{rating}</i>
<b>Release Info: </b> <a href="{url_releaseinfo}">{release_date}</a>
<b>Genre: </b>{genres}
<b>IMDb URL:</b> {url}
<b>Language: </b>{languages}
<b>Country of Origin : </b> {countries}

<b>Story Line: </b><code>{plot}</code>

<a href="{url_cast}">Read More ...</a>'''

    DEF_ANI_TEMP  = environ.get('ANIME_TEMPLATE', '')
    if len(DEF_ANI_TEMP) == 0:
        DEF_ANI_TEMP = '''<b>{ro_title}</b>({na_title})
<b>Format</b>: <code>{format}</code>
<b>Status</b>: <code>{status}</code>
<b>Start Date</b>: <code>{startdate}</code>
<b>End Date</b>: <code>{enddate}</code>
<b>Season</b>: <code>{season}</code>
<b>Country</b>: {country}
<b>Episodes</b>: <code>{episodes}</code>
<b>Duration</b>: <code>{duration}</code>
<b>Average Score</b>: <code>{avgscore}</code>
<b>Genres</b>: {genres}
<b>Hashtag</b>: {hashtag}
<b>Studios</b>: {studios}

<b>Description</b>: <i>{description}</i>'''

    MDL_TEMPLATE = environ.get('MDL_TEMPLATE', '')
    if len(MDL_TEMPLATE) == 0:
        MDL_TEMPLATE = '''<b>Title:</b> {title}
<b>Also Known As:</b> {aka}
<b>Rating ⭐️:</b> <i>{rating}</i>
<b>Release Info:</b> {aired_date}
<b>Genre:</b> {genres}
<b>MyDramaList URL:</b> {url}
<b>Language:</b> #Korean
<b>Country of Origin:</b> {country}

<b>Story Line:</b> {synopsis}

<a href='{url}'>Read More ...</a>'''
    
    TIMEZONE = environ.get('TIMEZONE', '')
    if len(TIMEZONE) == 0:
        TIMEZONE = 'Asia/Kolkata'
        
    list_drives_dict.clear()
    if GDRIVE_ID:
        list_drives_dict['Main'] = {"drive_id": GDRIVE_ID, "index_link": INDEX_URL}
        categories_dict['Root'] = {"drive_id": GDRIVE_ID, "index_link": INDEX_URL}

    if await aiopath.exists('list_drives.txt'):
        async with aiopen('list_drives.txt', 'r+') as f:
            lines = await f.readlines()
            for line in lines:
                sep = 2 if line.strip().split()[-1].startswith('http') else 1
                temp = line.strip().rsplit(maxsplit=sep)
                name = "Main Custom" if temp[0].casefold() == "Main" else temp[0]
                list_drives_dict[name] = {'drive_id': temp[1], 'index_link': (temp[2] if sep == 2 else '')}

    categories_dict.clear()
    if await aiopath.exists('categories.txt'):
        async with aiopen('categories.txt', 'r+') as f:
            lines = await f.readlines()
            for line in lines:
                sep = 2 if line.strip().split()[-1].startswith('http') else 1
                temp = line.strip().rsplit(maxsplit=sep)
                name = "Root Custom" if temp[0].casefold() == "Root" else temp[0]
                categories_dict[name] = {'drive_id': temp[1], 'index_link': (temp[2] if sep == 2 else '')}

    extra_buttons.clear()
    if await aiopath.exists('buttons.txt'):
        async with aiopen('buttons.txt', 'r+') as f:
            lines = await f.readlines()
            for line in lines:
                temp = line.strip().split()
                if len(extra_buttons.keys()) == 4:
                    break
                if len(temp) == 2:
                    extra_buttons[temp[0].replace("_", " ")] = temp[1]

    shorteners_list.clear()
    if await aiopath.exists('shorteners.txt'):
        async with aiopen('shorteners.txt', 'r+') as f:
            lines = await f.readlines()
            for line in lines:
                temp = line.strip().split()
                if len(temp) == 2:
                    shorteners_list.append({'domain': temp[0],'api_key': temp[1]})

    config_dict.update({'ANIME_TEMPLATE': DEF_ANI_TEMP,
                        'AS_DOCUMENT': AS_DOCUMENT,
                        'AUTHORIZED_CHATS': AUTHORIZED_CHATS,
                        'AUTO_DELETE_MESSAGE_DURATION': AUTO_DELETE_MESSAGE_DURATION,
                        'BASE_URL': BASE_URL,
                        'BASE_URL_PORT': BASE_URL_PORT,
                        'BLACKLIST_USERS': BLACKLIST_USERS,
                        'BOT_TOKEN': BOT_TOKEN,
                        'BOT_MAX_TASKS': BOT_MAX_TASKS,
                        'CAP_FONT': CAP_FONT,
                        'CMD_SUFFIX': CMD_SUFFIX,
                        'DATABASE_URL': DATABASE_URL,
                        'REAL_DEBRID_API': REAL_DEBRID_API,
                        'DEBRID_LINK_API': DEBRID_LINK_API,
                        'FILELION_API': FILELION_API,
                        'DELETE_LINKS': DELETE_LINKS,
                        'DEFAULT_UPLOAD': DEFAULT_UPLOAD,
                        'DOWNLOAD_DIR': DOWNLOAD_DIR,
                        'EXCEP_CHATS': EXCEP_CHATS,
                        'STORAGE_THRESHOLD': STORAGE_THRESHOLD,
                        'TORRENT_LIMIT': TORRENT_LIMIT,
                        'DIRECT_LIMIT': DIRECT_LIMIT,
                        'YTDLP_LIMIT': YTDLP_LIMIT,
                        'GDRIVE_LIMIT': GDRIVE_LIMIT,
                        'CLONE_LIMIT': CLONE_LIMIT,
                        'MEGA_LIMIT': MEGA_LIMIT,
                        'LEECH_LIMIT': LEECH_LIMIT,
                        'FSUB_IDS': FSUB_IDS,
                        'USER_MAX_TASKS': USER_MAX_TASKS,
                        'USER_TIME_INTERVAL': USER_TIME_INTERVAL,
                        'PLAYLIST_LIMIT': PLAYLIST_LIMIT,
                        'DAILY_TASK_LIMIT': DAILY_TASK_LIMIT,
                        'DAILY_MIRROR_LIMIT': DAILY_MIRROR_LIMIT,
                        'DAILY_LEECH_LIMIT': DAILY_LEECH_LIMIT,
                        'MIRROR_LOG_ID': MIRROR_LOG_ID,
                        'LEECH_LOG_ID': LEECH_LOG_ID,
                        'LINKS_LOG_ID': LINKS_LOG_ID,
                        'BOT_PM': BOT_PM,
                        'DISABLE_DRIVE_LINK': DISABLE_DRIVE_LINK,
                        'BOT_THEME': BOT_THEME,
                        'IMAGES': IMAGES,
                        'IMG_SEARCH': IMG_SEARCH,
                        'IMG_PAGE': IMG_PAGE,
                        'IMDB_TEMPLATE': DEF_IMDB_TEMP,
                        'AUTHOR_NAME': AUTHOR_NAME,
                        'AUTHOR_URL': AUTHOR_URL,
                        'COVER_IMAGE': COVER_IMAGE,
                        'TITLE_NAME': TITLE_NAME,
                        'GD_INFO': GD_INFO,
                        'GDTOT_CRYPT': GDTOT_CRYPT,
                        'JIODRIVE_TOKEN': JIODRIVE_TOKEN,
                        'EQUAL_SPLITS': EQUAL_SPLITS,
                        'EXTENSION_FILTER': EXTENSION_FILTER,
                        'GDRIVE_ID': GDRIVE_ID,
                        'INCOMPLETE_TASK_NOTIFIER': INCOMPLETE_TASK_NOTIFIER,
                        'INDEX_URL': INDEX_URL,
                        'IS_TEAM_DRIVE': IS_TEAM_DRIVE,
                        'METADATA': METADATA,
                        'ATTACHMENT': ATTACHMENT,
                        'LEECH_FILENAME_PREFIX': LEECH_FILENAME_PREFIX,
                        'LEECH_FILENAME_SUFFIX': LEECH_FILENAME_SUFFIX,
                        'LEECH_FILENAME_CAPTION': LEECH_FILENAME_CAPTION,
                        'LEECH_FILENAME_REMNAME': LEECH_FILENAME_REMNAME,
                        'MIRROR_FILENAME_PREFIX': MIRROR_FILENAME_PREFIX,
                        'MIRROR_FILENAME_SUFFIX': MIRROR_FILENAME_SUFFIX,
                        'MIRROR_FILENAME_REMNAME': MIRROR_FILENAME_REMNAME,
                        'LEECH_SPLIT_SIZE': LEECH_SPLIT_SIZE,
                        'LOGIN_PASS': LOGIN_PASS,
                        'TOKEN_TIMEOUT': TOKEN_TIMEOUT,
                        'MEDIA_GROUP': MEDIA_GROUP,
                        'MEGA_EMAIL': MEGA_EMAIL,
                        'MEGA_PASSWORD': MEGA_PASSWORD,
                        'MDL_TEMPLATE': MDL_TEMPLATE,
                        'OWNER_ID': OWNER_ID,
                        'QUEUE_ALL': QUEUE_ALL,
                        'QUEUE_DOWNLOAD': QUEUE_DOWNLOAD,
                        'QUEUE_UPLOAD': QUEUE_UPLOAD,
                        'RCLONE_FLAGS': RCLONE_FLAGS,
                        'RCLONE_PATH': RCLONE_PATH,
                        'RCLONE_SERVE_URL': RCLONE_SERVE_URL,
                        'RCLONE_SERVE_USER': RCLONE_SERVE_USER,
                        'RCLONE_SERVE_PASS': RCLONE_SERVE_PASS,
                        'RCLONE_SERVE_PORT': RCLONE_SERVE_PORT,
                        'RSS_CHAT': RSS_CHAT,
                        'RSS_DELAY': RSS_DELAY,
                        'SAVE_MSG': SAVE_MSG,
                        'SAFE_MODE': SAFE_MODE,
                        'SEARCH_API_LINK': SEARCH_API_LINK,
                        'SEARCH_LIMIT': SEARCH_LIMIT,
                        'SEARCH_PLUGINS': SEARCH_PLUGINS,
                        'SET_COMMANDS': SET_COMMANDS,
                        'SHOW_MEDIAINFO': SHOW_MEDIAINFO,
                        'SCREENSHOTS_MODE': SCREENSHOTS_MODE,
                        'CLEAN_LOG_MSG': CLEAN_LOG_MSG,
                        'SHOW_EXTRA_CMDS': SHOW_EXTRA_CMDS,
                        'SOURCE_LINK': SOURCE_LINK,
                        'STATUS_LIMIT': STATUS_LIMIT,
                        'STATUS_UPDATE_INTERVAL': STATUS_UPDATE_INTERVAL,
                        'WALLPAPER_MULTIPLIER': WALLPAPER_MULTIPLIER,
                        'WALLPAPER_URL': WALLPAPER_URL,
                        'WALLPAPER_MODE': WALLPAPER_MODE,
                        'STOP_DUPLICATE': STOP_DUPLICATE,
                        'SUDO_USERS': SUDO_USERS,
                        'TELEGRAM_API': TELEGRAM_API,
                        'TELEGRAM_HASH': TELEGRAM_HASH,
                        'TIMEZONE': TIMEZONE,
                        'TORRENT_TIMEOUT': TORRENT_TIMEOUT,
                        'UPSTREAM_REPO': UPSTREAM_REPO,
                        'UPSTREAM_BRANCH': UPSTREAM_BRANCH,
                        'UPGRADE_PACKAGES': UPGRADE_PACKAGES,
                        'USER_SESSION_STRING': USER_SESSION_STRING,
                        'HELPER_TOKENS': HELPER_TOKENS,
                        'HELPER_PAUSE': HELPER_PAUSE,
                        'USER_TD_MODE':USER_TD_MODE,
                        'USER_TD_SA': USER_TD_SA,
                        'USE_SERVICE_ACCOUNTS': USE_SERVICE_ACCOUNTS,
                        'WEB_PINCODE': WEB_PINCODE,
                        'YT_DLP_OPTIONS': YT_DLP_OPTIONS})

    if DATABASE_URL:
        await DbManger().update_config(config_dict)
    await gather(initiate_search_tools(), start_from_queued(), rclone_serve_booter())


def _mask_token(tok):
    tok = (tok or "").strip()
    if not tok:
        return "—"
    # bot token: 123456:AAH... -> mask as 12345…
    # user session string: long base64 -> mask first 6 + last 4
    if ":" in tok:
        return f"{tok.split(':', 1)[0][:5]}…"
    # user string session
    t = tok.strip()
    if len(t) <= 12:
        return f"{t[:5]}…"
    return f"{t[:6]}…{t[-4:]}"


def _is_helper_paused():
    return bool(config_dict.get("HELPER_PAUSE", False))


def _dedupe_tokens(tokens):
    # preserve order, silently drop duplicates (exact string match)
    seen = set()
    out = []
    for t in tokens:
        tt = t.strip()
        if not tt:
            continue
        if tt in seen:
            continue
        seen.add(tt)
        out.append(tt)
    return out


def _helper_list():
    raw = config_dict.get("HELPER_TOKENS") or ""
    # raw is space-separated, but also handle newlines (bulk paste stored as spaces)
    toks = [t.strip() for t in str(raw).split() if t.strip()]
    # dedupe silently for display (storage is deduped on persist)
    return _dedupe_tokens(toks)


def _classify_token(tok):
    tok = (tok or "").strip()
    if not tok:
        return "unknown"
    if ":" in tok and tok.split(":", 1)[0].isdigit():
        # basic bot token shape: numeric_id:token
        return "bot"
    # heuristic: user string session is long, no colon, often starts with BQ... or contains alphanumeric + -_
    if len(tok) > 30 and ":" not in tok and " " not in tok:
        return "user"
    if ":" in tok:
        return "bot"
    return "user"


def _split_helpers():
    toks = _helper_list()
    bots = []  # list of (orig_idx, token)
    users = []
    for idx, tok in enumerate(toks, 1):
        if _classify_token(tok) == "bot":
            bots.append((idx, tok))
        else:
            users.append((idx, tok))
    return bots, users, toks


async def _set_helper_pause(paused: bool):
    paused = bool(paused)
    config_dict['HELPER_PAUSE'] = paused
    environ['HELPER_PAUSE'] = str(paused)
    if DATABASE_URL:
        try:
            await DbManger().update_config({'HELPER_PAUSE': paused})
        except Exception as e:
            LOGGER.error("DbManger HELPER_PAUSE: %s", e)


async def _hyper_menu_text_buttons():
    # Direct Hyper Tokens dashboard — no extra Helper Bot button, top Active/Pause toggle
    buttons = ButtonMaker()
    bots, users, toks = _split_helpers()
    paused = _is_helper_paused()
    # try get live usernames for bots/users
    try:
        from ..helper.ext_utils.hyperul_utils import helper_bots
    except Exception:
        helper_bots = {}
    try:
        from ..helper.telegram_helper.tg_transfer import helper_users
    except Exception:
        helper_users = {}

    status_emoji = "⏸️ Pause" if not paused else "▶️ Active"
    status_text = "▶️ Active" if not paused else "⏸️ Paused"
    status_hint = "live — add/remove will restart helpers" if not paused else "frozen — batch edits calm, no restart until Active"

    lines = []
    lines.append("<b>Hyper Tokens</b>\n")
    # compute active vs added for dashboard (how many added/active vs inactive)
    try:
        active_bots = len([c for n, c in helper_bots.items() if n != 0 and c and getattr(c, 'me', None)])
    except Exception:
        active_bots = max(0, len(helper_bots) - (1 if 0 in helper_bots else 0))
    try:
        active_users = len([c for n, c in helper_users.items() if c and getattr(c, 'me', None)])
    except Exception:
        active_users = len(helper_users)
    total_added = len(toks)
    total_active = active_bots + active_users
    lines.append(f"Status: <b>{status_text}</b> — <i>{status_hint}</i>\n")
    lines.append(f"Added: <code>{total_added}</code> | Active: <code>{total_active}</code> | Inactive: <code>{max(0, total_added - total_active)}</code>\n")
    if paused:
        lines.append("<i>Tip: Keep <b>Paused</b> while batch adding/removing, then tap <b>Active</b> once — final list starts deduplicated.</i>\n")
    lines.append(f"\n<b>Helper Bots</b>  <code>{len(bots)}</code> added / <code>{active_bots}</code> active\n")
    if not bots:
        lines.append("<i>No helper bots yet. Use Add Helper below.</i>\n")
    else:
        for orig_idx, tok in bots:
            hid = tok.split(":", 1)[0]
            uname, uid = "?", hid
            try:
                # helper_bots indexing is 1-based in hyperul (enumerate start=1)
                cl = helper_bots.get(orig_idx) or helper_bots.get(bots.index((orig_idx, tok)) + 1)
                if cl and getattr(cl, "me", None):
                    uname = cl.me.username or cl.me.first_name or "?"
                    uid = cl.me.id
                else:
                    # fallback try any helper_bots with matching id prefix
                    for c in helper_bots.values():
                        if c and getattr(c, "me", None) and str(getattr(c.me, "id", "")) == hid:
                            uname = c.me.username or c.me.first_name or "?"
                            uid = c.me.id
                            break
            except Exception:
                pass
            lines.append(f"#{orig_idx} @{uname} | <code>{uid}</code> | <code>{_mask_token(tok)}</code>\n")

    lines.append(f"\n<b>Helper Users</b>  <code>{len(users)}</code> added / <code>{active_users}</code> active\n")
    lines.append("<i>User string sessions for premium 4GB uploads.</i>\n")
    if not users:
        lines.append("<i>No helper users yet.</i>\n")
    else:
        for orig_idx, tok in users:
            uname, uid = "?", "user"
            try:
                # helper_users dict is keyed by 1..n
                cl = None
                # try mapping: user tokens order -> helper_users order
                # helper_users is populated by hyperul if any
                if helper_users:
                    # find by position in users list
                    pos = [u for _, u in users].index(tok) + 1
                    cl = helper_users.get(pos)
                if cl and getattr(cl, "me", None):
                    uname = cl.me.username or cl.me.first_name or "?"
                    uid = cl.me.id
            except Exception:
                pass
            lines.append(f"U#{orig_idx} @{uname} | <code>{uid}</code> | <code>{_mask_token(tok)}</code>\n")

    lines.append("\n<i> Add accepts BotFather <code>BOT_TOKEN</code> or user string session — paste one or many (space/newline separated). Duplicates are silently ignored.</i>")

    # Buttons: Toggle, Add, per-item remove
    toggle_label = "⏸️ Pause" if not paused else "▶️ Activate"
    buttons.ibutton(toggle_label, "botset hyper toggle")
    buttons.ibutton("Add Helper", "botset hyper add")

    # Remove buttons — two per row, using original indices
    for orig_idx, _ in bots:
        buttons.ibutton(f"Remove Bot #{orig_idx}", f"botset hyper rmbot {orig_idx}")
    for orig_idx, _ in users:
        buttons.ibutton(f"Remove User #{orig_idx}", f"botset hyper rmbot {orig_idx}")

    buttons.ibutton("Back", "botset back")
    buttons.ibutton("Close", "botset close")
    return "".join(lines), buttons.build_menu(2)


async def _hyper_bots_menu():
    # Backward compat: previously \"Helper Bots\" sub-menu — now same unified clean view
    # Keep separate function but delegate to unified menu so old callbacks still work
    return await _hyper_menu_text_buttons()


async def _persist_helpers(joined, *, allow_restart=True):
    # dedupe silently before persist
    toks = [t.strip() for t in str(joined or "").split() if t.strip()]
    toks = _dedupe_tokens(toks)
    joined = " ".join(toks)
    config_dict['HELPER_TOKENS'] = joined
    environ['HELPER_TOKENS'] = joined
    if DATABASE_URL:
        try:
            await DbManger().update_config({'HELPER_TOKENS': joined})
        except Exception as e:
            LOGGER.error("DbManger HELPER_TOKENS: %s", e)
    # frozen Pause -> no background restart (calm batch edits)
    if _is_helper_paused() and allow_restart:
        LOGGER.info("Helper Pause active — _persist_helpers skipped start_helper_bots (frozen)")
        return
    if not allow_restart:
        # called from toggle-to-Pause path where we don't want restart
        return
    try:
        from ..helper.ext_utils.hyperul_utils import start_helper_bots
        await start_helper_bots(joined)
    except Exception as e:
        LOGGER.error("start_helper_bots: %s", e)


async def _save_helper_token(_, message, pre_message):
    handler_dict[message.chat.id] = False
    raw = (message.text or "").strip()
    await deleteMessage(message)
    if not raw:
        await update_buttons(pre_message, 'hyper')
        return
    # bulk paste: split by any whitespace (space, newline, tab) — handles 10 tokens pasted together
    pasted = [t.strip() for t in str(raw).split() if t.strip()]
    if not pasted:
        await update_buttons(pre_message, 'hyper')
        return
    existing = _helper_list()
    existing_set = set(existing)
    added = []
    skipped_dup = 0
    for tok in pasted:
        # normalize: strip surrounding quotes if any
        tok = tok.strip().strip('"').strip("'").strip()
        if not tok:
            continue
        # silently skip duplicates already in list (no error)
        if tok in existing_set:
            skipped_dup += 1
            continue
        # also skip duplicate within this paste itself
        if tok in added:
            skipped_dup += 1
            continue
        # accept both bot token (contains :) and user string session (long no-colon)
        # we don't reject any long token; only reject obviously invalid very short garbage
        if len(tok) < 10:
            # too short to be token or session — ignore silently
            continue
        added.append(tok)
        existing_set.add(tok)
    if added:
        new_list = existing + added
        # dedupe final
        new_list = _dedupe_tokens(new_list)
        await _persist_helpers(" ".join(new_list))
        if skipped_dup:
            LOGGER.info(f"_save_helper_token: added {len(added)}, skipped duplicate {skipped_dup}")
    else:
        if skipped_dup:
            LOGGER.info(f"_save_helper_token: all {skipped_dup} token(s) were duplicates — silently ignored")
        # no new tokens, but still refresh UI (no restart happened)
    await update_buttons(pre_message, 'hyper')


async def get_buttons(key=None, edit_type=None, edit_mode=None, mess=None):
    buttons = ButtonMaker()
    if key is None:
        buttons.ibutton('Config Variables', "botset var")
        buttons.ibutton('Private Files', "botset private")
        buttons.ibutton('Hyper Tokens', "botset hyper")
        buttons.ibutton('Qbit Settings', "botset qbit")
        buttons.ibutton('Aria2c Settings', "botset aria")
        buttons.ibutton('Close', "botset close")
        msg = '<b><i>Bot Settings:</i></b>'
    elif key == 'hyper':
        return await _hyper_menu_text_buttons()
    elif key == 'hyperbots':
        return await _hyper_bots_menu()
    elif key == 'var':
        _hidden_vars = {'HELPER_TOKENS', 'HELPER_PAUSE'}
        _all_keys = [k for k in OrderedDict(sorted(config_dict.items())).keys() if k not in _hidden_vars]
        for k in _all_keys[START:10+START]:
            if k == 'WALLPAPER_URL':
                buttons.ibutton(k, f"botset editvar {k}")
            elif STATE == 'view':
                buttons.ibutton(k, f"botset showvar {k}")
            else:
                buttons.ibutton(k, f"botset editvar {k} edit")
        if STATE == 'view':
            buttons.ibutton('Edit', "botset edit var")
        else:
            buttons.ibutton('View', "botset view var")
        buttons.ibutton('Back', "botset back")
        buttons.ibutton('Close', "botset close")
        for x in range(0, len(_all_keys)-1, 10):
            buttons.ibutton(f'{int(x/10)+1}', f"botset start var {x}", position='footer')
        msg = f'<b>Config Variables</b> | <b>Page: {int(START/10)+1}</b> | <b>State: {STATE}</b>'
    elif key == 'private':
        buttons.ibutton('Back', "botset back")
        buttons.ibutton('Close', "botset close")
        msg = '''<u>Send any of these private files:</u>
        
<code>config.env, token.pickle, accounts.zip, list_drives.txt, categories.txt, shorteners.txt, cookies.txt, terabox.txt, .netrc or any other file!</code>

<i>To delete private file send only the file name as text message with or without extension.</i>
<b>NOTE:</b> Changing .netrc will not take effect for aria2c until restart.

<b>Timeout:</b> 60 sec'''
    elif key == 'aria':
        for k in list(aria2_options.keys())[START:10+START]:
            buttons.ibutton(k, f"botset editaria {k}")
        if STATE == 'view':
            buttons.ibutton('Edit', "botset edit aria")
        else:
            buttons.ibutton('View', "botset view aria")
        buttons.ibutton('Add New key', "botset editaria newkey")
        buttons.ibutton('Back', "botset back")
        buttons.ibutton('Close', "botset close")
        for x in range(0, len(aria2_options)-1, 10):
            buttons.ibutton(f'{int(x/10)+1}', f"botset start aria {x}", position='footer')
        msg = f'Aria2c Options | Page: {int(START/10)+1} | State: {STATE}'
    elif key == 'qbit':
        for k in list(qbit_options.keys())[START:10+START]:
            buttons.ibutton(k, f"botset editqbit {k}")
        if STATE == 'view':
            buttons.ibutton('Edit', "botset edit qbit")
        else:
            buttons.ibutton('View', "botset view qbit")
        buttons.ibutton('Back', "botset back")
        buttons.ibutton('Close', "botset close")
        for x in range(0, len(qbit_options)-1, 10):
            buttons.ibutton(
                f'{int(x/10)+1}', f"botset start qbit {x}", position='footer')
        msg = f'Qbittorrent Options | Page: {int(START/10)+1} | State: {STATE}'
    elif key == 'wallitem':
        urls = [str(x).strip() for x in (config_dict.get('WALLPAPER_URL') or []) if str(x).strip()]
        modes = config_dict.get('WALLPAPER_MODE') or []
        i = WALL_IDX if 0 <= WALL_IDX < len(urls) else 0
        globals()['WALL_IDX'] = i
        url = urls[i] if urls else ''
        on = bool(url) and not (i < len(modes) and modes[i] == 'disable')
        msg = '㊂ <b><u>Wallpaper URL Settings :</u></b>\n\n'
        msg += f'➲ <b>URL :</b> <code>{escape(url)}</code>\n'
        msg += f'➲ <b>Status :</b> <i>{"Enabled" if on else "Disabled"}</i>\n\n'
        msg += '➲ <b>Description :</b> <i>Random wallpaper source used for status preview.</i>'
        if edit_mode:
            msg += '\n\n<i>Send a valid URL (http/https). <b>Timeout:</b> 60 sec</i>'
            buttons.ibutton('Stop Change', f'botset wallchg {i}', position='header')
        else:
            buttons.ibutton('View URL', f'botset wallview {i}', position='header')
            buttons.ibutton('Change URL', f'botset wallchg {i} edit')
        buttons.ibutton('↻ Delete', f'botset walldel {i}')
        buttons.ibutton('Back', 'botset editvar WALLPAPER_URL', position='footer')
        buttons.ibutton('Close', 'botset close', position='footer')
    elif edit_type == 'editvar':
        if key == 'WALLPAPER_URL' and not edit_mode:
            msg = '㊂ <b><u>WALLPAPER_URL :</u></b>\n\n'
            msg += '➲ <b>Description :</b> <i>Random wallpaper source for status preview.</i>\n\n'
            buttons.ibutton(f'Mode: {WALL_MODE.capitalize()}', 'botset wallmode', position='header')
            urls = [str(x).strip() for x in (config_dict.get('WALLPAPER_URL') or []) if str(x).strip()]
            modes = config_dict.get('WALLPAPER_MODE') or []
            if WALL_START >= len(urls):
                globals()['WALL_START'] = 0
            page = urls[WALL_START:WALL_START + 12]
            for offset, u in enumerate(page):
                gi = WALL_START + offset
                mark = '❌' if gi < len(modes) and modes[gi] == 'disable' else '✅'
                h = u.split('//', 1)[-1].split('/')[0].split('?')[0]
                p = h.split('.')
                if p and p[0] in ('api', 'www'):
                    p = p[1:]
                lab = p[0] if p else h
                cb = f'botset wallitem {gi}' if WALL_MODE == 'edit' else f'botset walltgl {gi}'
                buttons.ibutton(f'{mark} {lab}', cb)
            if len(urls) > 12:
                for x in range(0, len(urls), 12):
                    buttons.ibutton(f'{x // 12 + 1}', f'botset wallpage {x // 12}', position='footer')
            buttons.ibutton('Back', "botset back var", position="footer")
            buttons.ibutton('Reset', f"botset resetvar {key}")
            buttons.ibutton('Close', "botset close", position="footer")
        else:
            value = config_dict.get(key, "None")
            if value == "":
                value = "None"
            if isinstance(value, list):
                value = ", ".join(str(x) for x in value)
            msg = f'<b>Variable:</b> <code>{key}</code>\n\n'
            msg += f'<b>Description:</b> {default_desp.get(key, "No Description Provided")}\n\n'
            msg += f'<b>Current Value:</b> <code>{escape(str(value))}</code>\n\n'
            buttons.ibutton('View Value', f"botset showvar {key}", position="header")
            buttons.ibutton('Back', "botset back var", position="footer")
            if key not in bool_vars:
                if not edit_mode:
                    buttons.ibutton('Edit Value', f"botset editvar {key} edit")
                else:
                    buttons.ibutton('Stop Edit', f"botset editvar {key}")
            if key not in ['TELEGRAM_HASH', 'TELEGRAM_API', 'OWNER_ID', 'BOT_TOKEN', 'USER_SESSION_STRING'] and key not in bool_vars:
                buttons.ibutton('Reset', f"botset resetvar {key}")
            buttons.ibutton('Close', "botset close", position="footer")
            if edit_mode and key in ['SUDO_USERS', 'CMD_SUFFIX', 'OWNER_ID', 'USER_SESSION_STRING', 'TELEGRAM_HASH',
                                     'TELEGRAM_API', 'AUTHORIZED_CHATS', 'DATABASE_URL', 'BOT_TOKEN', 'DOWNLOAD_DIR']:
                msg += '<b>Note:</b> Restart required for this edit to take effect!\n\n'
            if edit_mode and key not in bool_vars:
                msg += '<i>Send a valid value for the above Var.</i> <b>Timeout:</b> 60 sec'
            if key in bool_vars:
                msg += '<i>Choose a valid value for the above Var</i>'
                buttons.ibutton('True', f"botset boolvar {key} on")
                buttons.ibutton('False', f"botset boolvar {key} off")
    elif edit_type == 'editaria':
        buttons.ibutton('Back', "botset back aria")
        if key != 'newkey':
            buttons.ibutton('Default', f"botset resetaria {key}")
            buttons.ibutton('Empty String', f"botset emptyaria {key}")
        buttons.ibutton('Close', "botset close")
        if key == 'newkey':
            msg = 'Send a key with value. Example: https-proxy-user:value'
        else:
            msg = f'Send a valid value for {key}. Timeout: 60 sec'
    elif edit_type == 'editqbit':
        buttons.ibutton('Back', "botset back qbit")
        buttons.ibutton('Empty String', f"botset emptyqbit {key}")
        buttons.ibutton('Close', "botset close")
        msg = f'Send a valid value for {key}. Timeout: 60 sec'
    button = buttons.build_menu(1) if key is None else buttons.build_menu(2)
    return msg, button


async def update_buttons(message, key=None, edit_type=None, edit_mode=None):
    msg, button = await get_buttons(key, edit_type, edit_mode, message)
    await editMessage(message, msg, button)


async def edit_variable(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if key == 'RSS_DELAY':
        value = int(value)
        addJob(value)
    elif key == 'DOWNLOAD_DIR':
        if not value.endswith('/'):
            value += '/'
    elif key in ['LINKS_LOG_ID', 'RSS_CHAT']:
        value = int(value)
    elif key == 'STATUS_UPDATE_INTERVAL':
        value = int(value)
        if len(download_dict) != 0:
            async with status_reply_dict_lock:
                if Interval:
                    Interval[0].cancel()
                    Interval.clear()
                    Interval.append(setInterval(value, update_all_messages))
    elif key == 'TORRENT_TIMEOUT':
        value = int(value)
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(aria2.client.change_option, download.gid, {'bt-stop-timeout': f'{value}'})
                except Exception as e:
                    LOGGER.error(e)
        aria2_options['bt-stop-timeout'] = f'{value}'
    elif key == 'LEECH_SPLIT_SIZE':
        value = min(int(value), MAX_SPLIT_SIZE)
    elif key == 'BOT_THEME':
        if not value.strip() in AVL_THEMES.keys():
            value = 'minimal'
    elif key == 'CAP_FONT':
        value = value.strip().lower()
        if value not in ['b', 'i', 'u', 's', 'spoiler', 'code']:
            value = 'code'
    elif key == 'BASE_URL_PORT':
        # Khaali value pe purana value hi rehne do — warna 0 store ho kar server
        # kisi random ephemeral port pe bind ho jaata.
        value = _parse_port(value, 'BASE_URL_PORT', config_dict['BASE_URL_PORT'])
        if config_dict['BASE_URL']:
            from web.aio_wserver import restart_web_server
            # Boot jaisa hi rule: PORT (Heroku) precedence, warna BASE_URL_PORT.
            await restart_web_server(_parse_port(environ.get('PORT'), 'PORT', 0) or value)
    elif key == 'EXTENSION_FILTER':
        fx = value.split()
        GLOBAL_EXTENSION_FILTER.clear()
        GLOBAL_EXTENSION_FILTER.extend(['aria2', '!qB'])
        for x in fx:
            if x.strip().startswith('.'):
                x = x.lstrip('.')
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())
    elif key == 'GDRIVE_ID':
        list_drives_dict['Main'] = {"drive_id": value, "index_link": config_dict['INDEX_URL']}
        categories_dict['Root'] = {"drive_id": value, "index_link": config_dict['INDEX_URL']}
    elif key == 'INDEX_URL':
        list_drives_dict['Main'] = {"drive_id": config_dict['GDRIVE_ID'], "index_link": value}
        categories_dict['Root'] = {"drive_id": config_dict['GDRIVE_ID'], "index_link": value}
    elif key == 'WALLPAPER_MULTIPLIER':
        value = int(value)
        if value < 1:
            value = 1
    elif key == 'WALLPAPER_URL':
        import re as _re_w2, json as _json_w2, ast as _ast_w2
        raw = str(value).strip()
        lst = []
        if raw.startswith('['):
            try:
                arr = _json_w2.loads(raw)
                if isinstance(arr, list):
                    lst = [str(x).strip() for x in arr if str(x).strip()]
            except:
                pass
            if not lst:
                try:
                    arr = _ast_w2.literal_eval(raw)
                    if isinstance(arr, list):
                        lst = [str(x).strip() for x in arr if str(x).strip()]
                except:
                    pass
        if not lst:
            lst = [p.strip() for p in _re_w2.split(r'[,\s]+', raw) if p.strip()]
        value = lst or ['https://api.aniwallpaper.workers.dev/random?type=girls']
    elif value.isdigit():
        value = int(value)
    config_dict[key] = value
    await update_buttons(pre_message, key, 'editvar', False)
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManger().update_config({key: value})
    if key == 'WALLPAPER_URL':
        modes = list(config_dict.get('WALLPAPER_MODE') or [])
        while len(modes) < len(value):
            modes.append('enable')
        modes = modes[:len(value)]
        if modes != list(config_dict.get('WALLPAPER_MODE') or []):
            config_dict['WALLPAPER_MODE'] = modes
            if DATABASE_URL:
                await DbManger().update_config({'WALLPAPER_MODE': modes})
    if key in ['SEARCH_PLUGINS', 'SEARCH_API_LINK']:
        await initiate_search_tools()
    elif key in ['QUEUE_ALL', 'QUEUE_DOWNLOAD', 'QUEUE_UPLOAD']:
        await start_from_queued()
    elif key == 'HELPER_TOKENS':
        # dedupe silently, respect Pause
        v = str(value or "")
        toks = [t.strip() for t in v.split() if t.strip()]
        seen = set()
        deduped = []
        for t in toks:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        v = " ".join(deduped)
        # ensure config_dict/environ reflect deduped
        config_dict['HELPER_TOKENS'] = v
        environ['HELPER_TOKENS'] = v
        if _is_helper_paused():
            LOGGER.info("HELPER_TOKENS edit while Paused — skip start_helper_bots")
        else:
            from ..helper.ext_utils.hyperul_utils import start_helper_bots
            await start_helper_bots(v)
    elif key in ['RCLONE_SERVE_URL', 'RCLONE_SERVE_PORT', 'RCLONE_SERVE_USER', 'RCLONE_SERVE_PASS']:
        await rclone_serve_booter()


async def edit_wall_url(_, message, pre_message, index):
    handler_dict[message.chat.id] = False
    new = (message.text or '').strip()
    await deleteMessage(message)
    urls = [str(x).strip() for x in (config_dict.get('WALLPAPER_URL') or []) if str(x).strip()]
    if not new.startswith(('http://', 'https://')) or not (0 <= index < len(urls)):
        await update_buttons(pre_message, 'wallitem', None, False)
        return
    urls[index] = new
    config_dict['WALLPAPER_URL'] = urls
    await update_buttons(pre_message, 'wallitem', None, False)
    if DATABASE_URL:
        await DbManger().update_config({'WALLPAPER_URL': urls})


async def edit_aria(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if key == 'newkey':
        key, value = [x.strip() for x in value.split(':', 1)]
    elif value.lower() == 'true':
        value = "true"
    elif value.lower() == 'false':
        value = "false"
    if key in aria2c_global:
        await sync_to_async(aria2.set_global_options, {key: value})
    else:
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(aria2.client.change_option, download.gid, {key: value})
                except Exception as e:
                    LOGGER.error(e)
    aria2_options[key] = value
    await update_buttons(pre_message, 'aria')
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManger().update_aria2(key, value)


async def edit_qbit(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if value.lower() == 'true':
        value = True
    elif value.lower() == 'false':
        value = False
    elif key == 'max_ratio':
        value = float(value)
    elif value.isdigit():
        value = int(value)
    await sync_to_async(ensure_qbit)
    await sync_to_async(get_client().app_set_preferences, {key: value})
    qbit_options[key] = value
    await update_buttons(pre_message, 'qbit')
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManger().update_qbittorrent(key, value)


async def update_private_file(_, message, pre_message):
    handler_dict[message.chat.id] = False
    if not message.media and (file_name := message.text):
        path = file_name
        fn = file_name.rsplit('.zip', 1)[0]
        if await aiopath.isfile(fn) and file_name != 'config.env':
            await remove(fn)
        if fn == 'accounts':
            if await aiopath.exists('accounts'):
                await aiormtree('accounts')
            if await aiopath.exists('rclone_sa'):
                await aiormtree('rclone_sa')
            config_dict['USE_SERVICE_ACCOUNTS'] = False
            if DATABASE_URL:
                await DbManger().update_config({'USE_SERVICE_ACCOUNTS': False})
        elif file_name in ['.netrc', 'netrc']:
            await (await create_subprocess_exec("touch", ".netrc")).wait()
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
        elif file_name.startswith('syntax_'):
            path = f"bot/helper/themes/{file_name.rsplit('.py', 1)[0]}.py"
            if await aiopath.isfile(path):
                await remove(path)
        elif file_name in ['buttons.txt', 'buttons']:
            extra_buttons.clear()
        elif file_name in ['categories.txt', 'categories']:
            categories_dict.clear()
            if GDRIVE_ID := config_dict['GDRIVE_ID']:
                categories_dict['Root'] = {"drive_id": GDRIVE_ID, "index_link": config_dict['INDEX_URL']}
        elif file_name in ['list_drives.txt', 'list_drives']:
            list_drives_dict.clear()
            if GDRIVE_ID := config_dict['GDRIVE_ID']:
                list_drives_dict['Main'] = {"drive_id": GDRIVE_ID, "index_link": config_dict['INDEX_URL']}
        elif file_name in ['shorteners.txt', 'shorteners']:
            shorteners_list.clear()
        await deleteMessage(message)
    elif doc := message.document:
        file_name = doc.file_name
        path = file_name
        if file_name.startswith('syntax_') and file_name.endswith('.py'):
            path = f'bot/helper/themes/{file_name}'
        await message.download(file_name=f'{getcwd()}/{path}')
        if file_name == 'accounts.zip':
            if await aiopath.exists('accounts'):
                await aiormtree('accounts')
            if await aiopath.exists('rclone_sa'):
                await aiormtree('rclone_sa')
            await (await create_subprocess_exec("7z", "x", "-o.", "-aoa", "accounts.zip", "accounts/*.json")).wait()
            await (await create_subprocess_exec("chmod", "-R", "777", "accounts")).wait()
        elif file_name == 'list_drives.txt':
            list_drives_dict.clear()
            if GDRIVE_ID := config_dict['GDRIVE_ID']:
                list_drives_dict['Main'] = {"drive_id": GDRIVE_ID, "index_link": config_dict['INDEX_URL']}
            async with aiopen('list_drives.txt', 'r+') as f:
                lines = await f.readlines()
                for line in lines:
                    sep = 2 if line.strip().split()[-1].startswith('http') else 1
                    temp = line.strip().rsplit(maxsplit=sep)
                    name = "Main Custom" if temp[0].casefold() == "Main" else temp[0]
                    list_drives_dict[name] = {'drive_id': temp[1], 'index_link': (temp[2] if sep == 2 else '')}
        elif file_name == 'categories.txt':
            categories_dict.clear()
            if GDRIVE_ID := config_dict['GDRIVE_ID']:
                categories_dict['Root'] = {"drive_id": GDRIVE_ID, "index_link": config_dict['INDEX_URL']}
            async with aiopen('categories.txt', 'r+') as f:
                lines = await f.readlines()
                for line in lines:
                    sep = 2 if line.strip().split()[-1].startswith('http') else 1
                    temp = line.strip().rsplit(maxsplit=sep)
                    name = "Root Custom" if temp[0].casefold() == "Root" else temp[0]
                    categories_dict[name] = {'drive_id': temp[1], 'index_link': (temp[2] if sep == 2 else '')}
        elif file_name == 'buttons.txt':
            extra_buttons.clear()
            async with aiopen('buttons.txt', 'r+') as f:
                lines = await f.readlines()
                for line in lines:
                    temp = line.strip().rsplit(maxsplit=1)
                    if len(extra_buttons.keys()) >= 20:
                        break
                    elif temp[1].startswith('http'):
                        extra_buttons[temp[0]] = temp[1]
        elif file_name == 'shorteners.txt':
            shorteners_list.clear()
            async with aiopen('shorteners.txt', 'r+') as f:
                lines = await f.readlines()
                for line in lines:
                    temp = line.strip().split()
                    if len(temp) == 2:
                        shorteners_list.append({'domain': temp[0],'api_key': temp[1]})
        elif file_name in ['.netrc', 'netrc']:
            if file_name == 'netrc':
                await rename('netrc', '.netrc')
                file_name = '.netrc'
            await (await create_subprocess_exec("chmod", "600", ".netrc")).wait()
            await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
        elif file_name == 'config.env':
            load_dotenv('config.env', override=True)
            await load_config()
        if '@github.com' in config_dict['UPSTREAM_REPO']:
            buttons = ButtonMaker()
            msg = '<i>Do you want to Upload (Git Push) your file to <b>UPSTREAM_REPO</b> ?</i>'
            buttons.ibutton('Yes!', f"botset push {file_name}")
            buttons.ibutton('No!', "botset close")
            await sendMessage(message, msg, buttons.build_menu(2))
        else:
            await deleteMessage(message)
    if file_name == 'wcl.conf':
        await rclone_serve_booter()
    await update_buttons(pre_message)
    if DATABASE_URL:
        await DbManger().update_private_file(path)
    if await aiopath.exists('accounts.zip'):
        await remove('accounts.zip')


async def event_handler(client, query, pfunc, rfunc, document=False):
    chat_id = query.message.chat.id
    handler_dict[chat_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        user = event.from_user or event.sender_chat
        return bool(user.id == query.from_user.id and event.chat.id == chat_id and (event.text or event.document and document))
    handler = client.add_handler(MessageHandler(
        pfunc, filters=create(event_filter)), group=-1)
    while handler_dict[chat_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[chat_id] = False
            await rfunc()
    client.remove_handler(*handler)


@new_thread
async def edit_bot_settings(client, query):
    data = query.data.split()
    message = query.message
    if data[1] == 'close':
        handler_dict[message.chat.id] = False
        globals()['WALL_MODE'] = 'normal'
        globals()['WALL_START'] = 0
        await query.answer()
        await deleteMessage(message)
        await deleteMessage(message.reply_to_message)
    elif data[1] == 'back':
        handler_dict[message.chat.id] = False
        globals()['WALL_MODE'] = 'normal'
        globals()['WALL_START'] = 0
        await query.answer()
        key = data[2] if len(data) == 3 else None
        if key is None:
            globals()['START'] = 0
        await update_buttons(message, key)
    elif data[1] in ['var', 'aria', 'qbit']:
        await query.answer()
        await update_buttons(message, data[1])
    elif data[1] == 'wallmode':
        handler_dict[message.chat.id] = False
        globals()['WALL_MODE'] = 'edit' if WALL_MODE == 'normal' else 'normal'
        await query.answer(f'Mode: {WALL_MODE.capitalize()}')
        await update_buttons(message, 'WALLPAPER_URL', 'editvar', False)
    elif data[1] == 'walltgl':
        handler_dict[message.chat.id] = False
        urls = [str(x).strip() for x in (config_dict.get('WALLPAPER_URL') or []) if str(x).strip()]
        i = int(data[2])
        if 0 <= i < len(urls):
            modes = list(config_dict.get('WALLPAPER_MODE') or [])
            while len(modes) <= i:
                modes.append('enable')
            modes[i] = 'disable' if modes[i] != 'disable' else 'enable'
            config_dict['WALLPAPER_MODE'] = modes
            await query.answer('Enabled' if modes[i] == 'enable' else 'Disabled')
            if DATABASE_URL:
                await DbManger().update_config({'WALLPAPER_MODE': modes})
        else:
            await query.answer('Invalid', show_alert=True)
        await update_buttons(message, 'WALLPAPER_URL', 'editvar', False)
    elif data[1] == 'wallpage':
        await query.answer()
        globals()['WALL_START'] = int(data[2]) * 12
        await update_buttons(message, 'WALLPAPER_URL', 'editvar', False)
    elif data[1] == 'wallitem':
        handler_dict[message.chat.id] = False
        await query.answer()
        globals()['WALL_IDX'] = int(data[2])
        await update_buttons(message, 'wallitem')
    elif data[1] == 'wallview':
        urls = [str(x).strip() for x in (config_dict.get('WALLPAPER_URL') or []) if str(x).strip()]
        i = int(data[2])
        if not (0 <= i < len(urls)):
            return await query.answer('Invalid', show_alert=True)
        url = urls[i]
        if len(url) > 200:
            await query.answer()
            await sendMessage(message, f'<code>{escape(url)}</code>')
        else:
            await query.answer(url, show_alert=True)
    elif data[1] == 'wallchg':
        handler_dict[message.chat.id] = False
        edit_mode = len(data) == 4
        await query.answer()
        await update_buttons(message, 'wallitem', None, edit_mode)
        if not edit_mode:
            return
        pfunc = partial(edit_wall_url, pre_message=message, index=WALL_IDX)
        rfunc = partial(update_buttons, message, 'wallitem', None, False)
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == 'walldel':
        handler_dict[message.chat.id] = False
        urls = [str(x).strip() for x in (config_dict.get('WALLPAPER_URL') or []) if str(x).strip()]
        i = int(data[2])
        if 0 <= i < len(urls):
            urls.pop(i)
            if not urls:
                urls = ['https://api.aniwallpaper.workers.dev/random?type=girls']
            config_dict['WALLPAPER_URL'] = urls
            modes = list(config_dict.get('WALLPAPER_MODE') or [])
            if i < len(modes):
                modes.pop(i)
            config_dict['WALLPAPER_MODE'] = modes
            await query.answer('Deleted')
            if DATABASE_URL:
                await DbManger().update_config({'WALLPAPER_URL': urls, 'WALLPAPER_MODE': modes})
        else:
            await query.answer('Invalid', show_alert=True)
        await update_buttons(message, 'WALLPAPER_URL', 'editvar', False)
    elif data[1] == 'hyper':
        handler_dict[message.chat.id] = False
        await query.answer()
        sub = data[2] if len(data) > 2 else None
        if sub is None:
            await update_buttons(message, 'hyper')
        elif sub == 'bots':
            # backward compat — old \"Helper Bots\" button now same as unified Helper Config
            await update_buttons(message, 'hyper')
        elif sub in ('addbot', 'add'):
            # Unified Add — accepts both BOT_TOKEN and user string session, bulk paste supported
            await editMessage(message, "<i>Send <b>BOT_TOKEN</b> (@BotFather) or <b>user string session</b>.\nYou can paste multiple (space/newline separated). Duplicates are silently ignored.\nTimeout: 60s</i>")
            pfunc = partial(_save_helper_token, pre_message=message)
            rfunc = partial(update_buttons, message, 'hyper')
            await event_handler(client, query, pfunc, rfunc)
        elif sub == 'toggle':
            # Active <-> Pause toggle (frozen batch edits)
            currently_paused = _is_helper_paused()
            new_paused = not currently_paused
            await _set_helper_pause(new_paused)
            if new_paused:
                # going to Paused — freeze, no restart
                LOGGER.info("Helper toggle: Paused (frozen)")
                await query.answer("⏸️ Paused — batch edits frozen", show_alert=False)
                await update_buttons(message, 'hyper')
            else:
                # going to Active — start final deduplicated list once
                toks = _helper_list()
                joined = " ".join(_dedupe_tokens(toks))
                # persist already deduped (update DB) but ensure start
                config_dict['HELPER_TOKENS'] = joined
                environ['HELPER_TOKENS'] = joined
                if DATABASE_URL:
                    try:
                        await DbManger().update_config({'HELPER_TOKENS': joined, 'HELPER_PAUSE': False})
                    except Exception as e:
                        LOGGER.error("toggle active db: %s", e)
                try:
                    from ..helper.ext_utils.hyperul_utils import start_helper_bots
                    await start_helper_bots(joined)
                    LOGGER.info(f"Helper toggle: Active — started {len(_helper_list())} helper(s) deduplicated")
                    await query.answer("▶️ Active — helpers started (deduplicated)", show_alert=False)
                except Exception as e:
                    LOGGER.error("toggle active start: %s", e)
                    await query.answer(f"Active but start failed: {e}", show_alert=True)
                await update_buttons(message, 'hyper')
        elif sub == 'rmbot' and len(data) > 3:
            try:
                idx = int(data[3])
            except Exception:
                idx = 0
            toks = _helper_list()
            if 1 <= idx <= len(toks):
                removed = toks[idx-1]
                toks.pop(idx - 1)
                # _persist_helpers respects Pause (no restart when frozen)
                await _persist_helpers(" ".join(toks))
                LOGGER.info(f"Helper remove #{idx} ({_mask_token(removed)}) — paused={_is_helper_paused()}")
                await query.answer(f"Removed #{idx}", show_alert=False)
            else:
                await query.answer("Invalid index", show_alert=True)
            await update_buttons(message, 'hyper')
    elif data[1] == 'resetvar':
        if data[2] == 'USER_SESSION_STRING':
            await query.answer('USER_SESSION_STRING is not reset from here.', show_alert=True)
            return
        handler_dict[message.chat.id] = False
        await query.answer('Reset Done!', show_alert=True)
        value = ''
        if data[2] in default_values:
            value = default_values[data[2]]
            if data[2] == "STATUS_UPDATE_INTERVAL" and len(download_dict) != 0:
                async with status_reply_dict_lock:
                    if Interval:
                        Interval[0].cancel()
                        Interval.clear()
                        Interval.append(setInterval(
                            value, update_all_messages))
        elif data[2] == 'EXTENSION_FILTER':
            GLOBAL_EXTENSION_FILTER.clear()
            GLOBAL_EXTENSION_FILTER.extend(['aria2', '!qB'])
        elif data[2] == 'TORRENT_TIMEOUT':
            downloads = await sync_to_async(aria2.get_downloads)
            for download in downloads:
                if not download.is_complete:
                    try:
                        await sync_to_async(aria2.client.change_option, download.gid, {'bt-stop-timeout': '0'})
                    except Exception as e:
                        LOGGER.error(e)
            aria2_options['bt-stop-timeout'] = '0'
            if DATABASE_URL:
                await DbManger().update_aria2('bt-stop-timeout', '0')
        elif data[2] == 'BASE_URL':
            await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
        elif data[2] == 'BASE_URL_PORT':
            value = 80
            if config_dict['BASE_URL']:
                await (await create_subprocess_exec("pkill", "-9", "-f", "gunicorn")).wait()
                await create_subprocess_shell("gunicorn web.wserver:app --bind 0.0.0.0:80 --worker-class gevent")
        elif data[2] == 'GDRIVE_ID':
            if 'Main' in list_drives_dict:
                del list_drives_dict['Main']
            if 'Root' in categories_dict:
                del categories_dict['Root']
        elif data[2] == 'INDEX_URL':
            if (GDRIVE_ID := config_dict['GDRIVE_ID']) and 'Main' in list_drives_dict:
                list_drives_dict['Main'] = {"drive_id": GDRIVE_ID, "index_link": ''}
            if (GDRIVE_ID := config_dict['GDRIVE_ID']) and 'Root' in categories_dict:
                categories_dict['Root'] = {"drive_id": GDRIVE_ID, "index_link": ''}
        elif data[2] == 'INCOMPLETE_TASK_NOTIFIER' and DATABASE_URL:
            await DbManger().trunc_table('tasks')
        config_dict[data[2]] = value
        await update_buttons(message, data[2], 'editvar', False)
        if DATABASE_URL:
            await DbManger().update_config({data[2]: value})
        if data[2] in ['SEARCH_PLUGINS', 'SEARCH_API_LINK']:
            await initiate_search_tools()
        elif data[2] in ['QUEUE_ALL', 'QUEUE_DOWNLOAD', 'QUEUE_UPLOAD']:
            await start_from_queued()
        elif data[2] == 'HELPER_TOKENS':
            # reset — respect Pause, dedupe
            v = str(value or "")
            toks = [t.strip() for t in v.split() if t.strip()]
            seen = set()
            deduped = []
            for t in toks:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            v = " ".join(deduped)
            config_dict['HELPER_TOKENS'] = v
            environ['HELPER_TOKENS'] = v
            if _is_helper_paused():
                LOGGER.info("HELPER_TOKENS reset while Paused — skip start")
            else:
                from ..helper.ext_utils.hyperul_utils import start_helper_bots
                await start_helper_bots(v)
        elif data[2] in ['RCLONE_SERVE_URL', 'RCLONE_SERVE_PORT', 'RCLONE_SERVE_USER', 'RCLONE_SERVE_PASS']:
            await rclone_serve_booter()
    elif data[1] == 'resetaria':
        handler_dict[message.chat.id] = False
        aria2_defaults = await sync_to_async(aria2.client.get_global_option)
        if aria2_defaults[data[2]] == aria2_options[data[2]]:
            await query.answer('Value already same as you added in aria.sh!')
            return
        await query.answer()
        value = aria2_defaults[data[2]]
        aria2_options[data[2]] = value
        await update_buttons(message, 'aria')
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(aria2.client.change_option, download.gid, {data[2]: value})
                except Exception as e:
                    LOGGER.error(e)
        if DATABASE_URL:
            await DbManger().update_aria2(data[2], value)
    elif data[1] == 'emptyaria':
        handler_dict[message.chat.id] = False
        await query.answer()
        aria2_options[data[2]] = ''
        await update_buttons(message, 'aria')
        downloads = await sync_to_async(aria2.get_downloads)
        for download in downloads:
            if not download.is_complete:
                try:
                    await sync_to_async(aria2.client.change_option, download.gid, {data[2]: ''})
                except Exception as e:
                    LOGGER.error(e)
        if DATABASE_URL:
            await DbManger().update_aria2(data[2], '')
    elif data[1] == 'emptyqbit':
        handler_dict[message.chat.id] = False
        await query.answer()
        await sync_to_async(ensure_qbit)
        await sync_to_async(get_client().app_set_preferences, {data[2]: value})
        qbit_options[data[2]] = ''
        await update_buttons(message, 'qbit')
        if DATABASE_URL:
            await DbManger().update_qbittorrent(data[2], '')
    elif data[1] == 'private':
        handler_dict[message.chat.id] = False
        await query.answer()
        await update_buttons(message, data[1])
        pfunc = partial(update_private_file, pre_message=message)
        rfunc = partial(update_buttons, message)
        await event_handler(client, query, pfunc, rfunc, True)
    elif data[1] == 'boolvar':
        handler_dict[message.chat.id] = False
        value = data[3] == "on"
        await query.answer(f'Successfully Var changed to {value}!', show_alert=True)
        config_dict[data[2]] = value
        if not value and data[2] == 'INCOMPLETE_TASK_NOTIFIER' and DATABASE_URL:
            await DbManger().trunc_table('tasks')
        await update_buttons(message, data[2], 'editvar', False)
        if DATABASE_URL:
            await DbManger().update_config({data[2]: value})
    elif data[1] == 'editvar':
        handler_dict[message.chat.id] = False
        await query.answer()
        edit_mode = len(data) == 4
        await update_buttons(message, data[2], data[1], edit_mode)
        if data[2] in bool_vars or not edit_mode:
            return
        pfunc = partial(edit_variable, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, data[2], data[1], edit_mode)
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == 'showvar':
        value = config_dict[data[2]]
        if len(str(value)) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == '':
            value = None
        await query.answer(f'{value}', show_alert=True)
    elif data[1] == 'editaria' and (STATE == 'edit' or data[2] == 'newkey'):
        handler_dict[message.chat.id] = False
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_aria, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, 'aria')
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == 'editaria' and STATE == 'view':
        value = aria2_options[data[2]]
        if len(str(value)) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == '':
            value = None
        await query.answer(f'{value}', show_alert=True)
    elif data[1] == 'editqbit' and STATE == 'edit':
        handler_dict[message.chat.id] = False
        await query.answer()
        await update_buttons(message, data[2], data[1])
        pfunc = partial(edit_qbit, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, 'var')
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == 'editqbit' and STATE == 'view':
        value = qbit_options[data[2]]
        if len(str(value)) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == '':
            value = None
        await query.answer(f'{value}', show_alert=True)
    elif data[1] == 'edit':
        await query.answer()
        globals()['STATE'] = 'edit'
        await update_buttons(message, data[2])
    elif data[1] == 'view':
        await query.answer()
        globals()['STATE'] = 'view'
        await update_buttons(message, data[2])
    elif data[1] == 'start':
        await query.answer()
        if START != int(data[3]):
            globals()['START'] = int(data[3])
            await update_buttons(message, data[2])
    elif data[1] == 'push':
        await query.answer()
        filename = data[2].rsplit('.zip', 1)[0]
        if await aiopath.exists(filename):
            await (await create_subprocess_shell(f"git add -f {filename} \
                                                   && git commit -sm botsettings -q \
                                                   && git push origin {config_dict['UPSTREAM_BRANCH']} -qf")).wait()
        else:
            await (await create_subprocess_shell(f"git rm -r --cached {filename} \
                                                   && git commit -sm botsettings -q \
                                                   && git push origin {config_dict['UPSTREAM_BRANCH']} -qf")).wait()
        await deleteMessage(message)
        await deleteMessage(message.reply_to_message)


async def bot_settings(_, message):
    msg, button = await get_buttons()
    globals()['START'] = 0
    await sendMessage(message, msg, button, 'IMAGES')


bot.add_handler(MessageHandler(bot_settings, filters=command(
    BotCommands.BotSetCommand) & CustomFilters.sudo))
bot.add_handler(CallbackQueryHandler(edit_bot_settings,
                filters=regex("^botset") & CustomFilters.sudo))
