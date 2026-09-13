from ... import CMD_SUFFIX, config_dict

_ALL_SUFFIX_ALIASES = {'ra', 'aa', 'uaa', 'asa', 'rsa', 'bsa', 'sa', 'sta', 'usa', 'cancellallbot'}

class CommandList(list):
    def __str__(self):
        return self[0] if self else ''

def _fmt(cmd):
    if not cmd or (CMD_SUFFIX and cmd.endswith(CMD_SUFFIX)) or (cmd.endswith('all') and cmd != 'cancelall') or cmd in _ALL_SUFFIX_ALIASES:
        return cmd
    return f'{cmd}{CMD_SUFFIX}'

class _BotCommands:
    StartCommand = 'start'
    LoginCommand = 'login'

    _COMMANDS = {
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
    }

    _EXTRA_COMMANDS = {
        'Mirror': ['unzipmirror', 'uzm', 'zipmirror', 'zm'],
        'QbMirror': ['qbunzipmirror', 'quzm', 'qbzipmirror', 'qzm'],
        'Ytdl': ['ytdlzip', 'yz'],
        'Leech': ['unzipleech', 'uzl', 'zipleech', 'zl'],
        'QbLeech': ['qbunzipleech', 'quzl', 'qbzipleech', 'qzl'],
        'YtdlLeech': ['ytdlzipleech', 'yzl'],
    }

    def __init__(self):
        show_extra = config_dict.get('SHOW_EXTRA_CMDS', False)
        for key, cmds in self._COMMANDS.items():
            attr = key if key in ('CancelMirror', 'CategorySelect') or key.endswith('Command') else f'{key}Command'
            if isinstance(cmds, list):
                cmd_list = list(cmds)
                if show_extra and key in self._EXTRA_COMMANDS:
                    cmd_list.extend(self._EXTRA_COMMANDS[key])
                setattr(self, attr, CommandList(dict.fromkeys(_fmt(c) for c in cmd_list if c)))
            else:
                setattr(self, attr, _fmt(cmds))

BotCommands = _BotCommands()
