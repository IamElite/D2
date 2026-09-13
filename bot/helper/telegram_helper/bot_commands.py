from ... import CMD_SUFFIX, config_dict

_ALL_SUFFIX_ALIASES = {'ra', 'aa', 'uaa', 'asa', 'rsa', 'bsa', 'sa', 'sta', 'usa', 'cancellallbot'}

class CommandList(list):
    def __str__(self):
        return self[0] if self else ''

class BotCommands:
    StartCommand = 'start'
    LoginCommand = 'login'

    commands = {
        'Mirror': ['mirror', 'm'],
        'QbMirror': ['qbmirror', 'qm'],
        'Ytdl': ['ytdl', 'y'],
        'Leech': ['leech', 'l'],
        'QbLeech': ['qbleech', 'ql'],
        'YtdlLeech': ['ytdlleech', 'yl'],
        'Clone': ['clone', 'c'],
        'Count': 'count',
        'Delete': 'del',
        'CancelMirror': 'cancel',
        'CancelAll': ['cancelall', 'cancellallbot'],
        'ForceStart': ['forcestart', 'fs'],
        'List': 'list',
        'Search': 'search',
        'Status': ['status', 's', 'statusall', 'sa'],
        'Users': 'users',
        'Authorize': ['authorize', 'a', 'authorizeall', 'aa'],
        'UnAuthorize': ['unauthorize', 'ua', 'unauthorizeall', 'uaa'],
        'AddBlackList': ['blacklist', 'bl'],
        'RmBlackList': ['rmblacklist', 'rbl'],
        'AddSudo': ['addsudo', 'as', 'addsudoall', 'asa'],
        'RmSudo': ['rmsudo', 'rs', 'rmsudoall', 'rsa'],
        'Ping': ['ping', 'p'],
        'Restart': ['restart', 'r', 'restartall', 'ra'],
        'Stats': ['stats', 'st'],
        'Help': 'help',
        'Log': 'log',
        'Shell': 'shell',
        'Eval': 'eval',
        'Exec': 'exec',
        'ClearLocals': 'clearlocals',
        'BotSet': ['bsetting', 'bs', 'bsettingall', 'bsa'],
        'UserSet': ['usetting', 'us', 'usettingsall', 'usall', 'usa'],
        'BtSelect': 'btsel',
        'CategorySelect': 'ctsel',
        'Speed': ['speedtest', 'sp', 'speedtestall', 'sta'],
        'Rss': 'rss',
        'AddImage': 'addimg',
        'Images': 'images',
        'IMDB': 'imdb',
        'AniList': 'anime',
        'AnimeHelp': 'animehelp',
        'MediaInfo': ['mediainfo', 'mi'],
        'MyDramaList': 'mdl',
        'Poster': 'poster',
        'GDClean': ['gdclean', 'gc'],
        'AutoRename': 'autorename',
        'Broadcast': ['broadcast', 'bc'],
        'Id': 'id',
    }

    if config_dict.get('SHOW_EXTRA_CMDS'):
        commands['Mirror'].extend(['unzipmirror', 'uzm', 'zipmirror', 'zm'])
        commands['QbMirror'].extend(['qbunzipmirror', 'quzm', 'qbzipmirror', 'qzm'])
        commands['Ytdl'].extend(['ytdlzip', 'yz'])
        commands['Leech'].extend(['unzipleech', 'uzl', 'zipleech', 'zl'])
        commands['QbLeech'].extend(['qbunzipleech', 'quzl', 'qbzipleech', 'qzl'])
        commands['YtdlLeech'].extend(['ytdlzipleech', 'yzl'])

    for key, cmds in commands.items():
        attr = key if key in ('CancelMirror', 'CategorySelect') else f'{key}Command'
        vars()[attr] = (
            CommandList([
                cmd if not cmd or (cmd.endswith('all') and cmd != 'cancelall') or cmd in _ALL_SUFFIX_ALIASES else f'{cmd}{CMD_SUFFIX}'
                for cmd in cmds if cmd != ''
            ])
            if isinstance(cmds, list)
            else f'{cmds}{CMD_SUFFIX}'
        )

    del commands, key, cmds, attr
