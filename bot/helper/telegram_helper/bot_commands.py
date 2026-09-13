from ... import CMD_SUFFIX, config_dict

_ALL_SUFFIX_ALIASES = {'ra', 'aa', 'uaa', 'asa', 'rsa', 'bsa', 'sa', 'sta', 'usa'}

class CommandList(list):
    def __str__(self):
        return self[0] if self else ''

def _build_cmd(cmd):
    if not cmd:
        return cmd
    if cmd.endswith('all') or cmd in _ALL_SUFFIX_ALIASES:
        return cmd
    return f'{cmd}{CMD_SUFFIX}'

def _build_cmds(cmds):
    if isinstance(cmds, list):
        return CommandList(dict.fromkeys(_build_cmd(c) for c in cmds if c != ''))
    return _build_cmd(cmds)

class _BotCommands:
    def __init__(self):
        self.StartCommand = 'start'
        self.MirrorCommand = _build_cmds(['mirror', 'm'])
        self.QbMirrorCommand = _build_cmds(['qbmirror', 'qm'])
        self.YtdlCommand = _build_cmds(['ytdl', 'y'])
        self.LeechCommand = _build_cmds(['leech', 'l'])
        self.QbLeechCommand = _build_cmds(['qbleech', 'ql'])
        self.YtdlLeechCommand = _build_cmds(['ytdlleech', 'yl'])
        if config_dict['SHOW_EXTRA_CMDS']:
            self.MirrorCommand.extend([_build_cmd(x) for x in ['unzipmirror', 'uzm', 'zipmirror', 'zm']])
            self.QbMirrorCommand.extend([_build_cmd(x) for x in ['qbunzipmirror', 'quzm', 'qbzipmirror', 'qzm']])
            self.YtdlCommand.extend([_build_cmd(x) for x in ['ytdlzip', 'yz']])
            self.LeechCommand.extend([_build_cmd(x) for x in ['unzipleech', 'uzl', 'zipleech', 'zl']])
            self.QbLeechCommand.extend([_build_cmd(x) for x in ['qbunzipleech', 'quzl', 'qbzipleech', 'qzl']])
            self.YtdlLeechCommand.extend([_build_cmd(x) for x in ['ytdlzipleech', 'yzl']])
        self.CloneCommand = _build_cmds(['clone', 'c'])
        self.CountCommand = _build_cmd('count')
        self.DeleteCommand = _build_cmd('del')
        self.CancelMirror = _build_cmd('cancel')
        self.CancelAllCommand = _build_cmds([f'cancelall{CMD_SUFFIX}', 'cancelall', 'call', 'cancellallbot'])
        self.ForceStartCommand = _build_cmds(['forcestart', 'fs'])
        self.ListCommand = _build_cmd('list')
        self.SearchCommand = _build_cmd('search')
        self.StatusCommand = _build_cmds(['status', 's', 'statusall', 'sa'])
        self.UsersCommand = _build_cmd('users')
        self.AuthorizeCommand = _build_cmds(['authorize', 'a', 'authorizeall', 'aa'])
        self.UnAuthorizeCommand = _build_cmds(['unauthorize', 'ua', 'unauthorizeall', 'uaa'])
        self.AddBlackListCommand = _build_cmds(['blacklist', 'bl'])
        self.RmBlackListCommand = _build_cmds(['rmblacklist', 'rbl'])
        self.AddSudoCommand = _build_cmds(['addsudo', 'as', 'addsudoall', 'asa'])
        self.RmSudoCommand = _build_cmds(['rmsudo', 'rs', 'rmsudoall', 'rsa'])
        self.PingCommand = _build_cmds(['ping', 'p'])
        self.RestartCommand = _build_cmds(['restart', 'r', 'restartall', 'ra'])
        self.StatsCommand = _build_cmds(['stats', 'st'])
        self.HelpCommand = _build_cmd('help')
        self.LogCommand = _build_cmd('log')
        self.ShellCommand = _build_cmd('shell')
        self.EvalCommand = _build_cmd('eval')
        self.ExecCommand = _build_cmd('exec')
        self.ClearLocalsCommand = _build_cmd('clearlocals')
        self.BotSetCommand = _build_cmds(['bsetting', 'bs', 'bsettingall', 'bsa'])
        self.UserSetCommand = _build_cmds(['usetting', 'us', 'usettingsall', 'usall', 'usa'])
        self.BtSelectCommand = _build_cmd('btsel')
        self.CategorySelect = _build_cmd('ctsel')
        self.SpeedCommand = _build_cmds(['speedtest', 'sp', 'speedtestall', 'sta'])
        self.RssCommand = _build_cmd('rss')
        self.LoginCommand = 'login'
        self.AddImageCommand = _build_cmd('addimg')
        self.ImagesCommand = _build_cmd('images')
        self.IMDBCommand = _build_cmd('imdb')
        self.AniListCommand = _build_cmd('anime')
        self.AnimeHelpCommand = _build_cmd('animehelp')
        self.MediaInfoCommand = _build_cmds(['mediainfo', 'mi'])
        self.MyDramaListCommand = _build_cmd('mdl')
        self.PosterCommand = _build_cmd('poster')
        self.GDCleanCommand = _build_cmds(['gdclean', 'gc'])
        self.AutoRenameCommand = _build_cmd('autorename')     
        self.BroadcastCommand = _build_cmds(['broadcast', 'bc'])

BotCommands = _BotCommands()
