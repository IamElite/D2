#!/usr/bin/env python3
import re
import time
from asyncio import sleep, gather

from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from aiohttp import ClientSession, ClientTimeout
from html import escape
from urllib.parse import quote
from difflib import SequenceMatcher

from .. import bot, LOGGER, config_dict, get_client
from ..helper.telegram_helper.message_utils import editMessage, sendMessage
from ..helper.ext_utils.telegraph_helper import telegraph
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.ext_utils.bot_utils import get_readable_file_size, sync_to_async, new_task, checking_access
from ..helper.telegram_helper.button_build import ButtonMaker

PLUGINS = []
SITES = None
TELEGRAPH_LIMIT = 300
SUGGEST_API = 'https://v2.sg.media-imdb.com/suggestion/'
GOOGLE_SUGGEST_API = 'https://suggestqueries.google.com/complete/search'
ALLOWED_QIDS = {'movie', 'tvMovie', 'tvSeries', 'tvMiniSeries',
                'tvSpecial', 'tvShort', 'short', 'video', 'videoGame'}
QB_ENGINE_BASE = 'https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/'
COMMUNITY_ENGINES = (
    'https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaasi.py',
    'https://raw.githubusercontent.com/AlaaBrahim/qBitTorrent-animetosho-search-plugin/main/animetosho.py',
    'https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/torrentdownload.py',
    'https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/snowfl.py',
    'https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/pirateiro.py',
    'https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/academictorrents.py',
    'https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/torrentdownloads.py',
    'https://raw.githubusercontent.com/BurningMop/qBittorrent-Search-Plugins/refs/heads/main/therarbg.py',
    'https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/linuxtracker.py',
    'https://raw.githubusercontent.com/Ashalda/sktorrent-qbt/refs/heads/main/sktorrent.py',
)
DEFAULT_SEARCH_PLUGINS = str([f'{QB_ENGINE_BASE}{n}.py' for n in (
    'limetorrents', 'piratebay', 'torlock', 'torrentproject', 'torrentscsv')] + list(COMMUNITY_ENGINES))


async def initiate_search_tools():
    from ..helper.ext_utils.engine_lifecycle import ensure_qbit
    global SITES
    if SEARCH_API_LINK := config_dict['SEARCH_API_LINK']:
        try:
            async with ClientSession(trust_env=True) as c:
                async with c.get(f'{SEARCH_API_LINK}/api/v1/sites') as res:
                    data = await res.json()
            SITES = {str(site): str(site).capitalize()
                     for site in data['supported_sites']}
            SITES['all'] = 'All'
        except Exception as e:
            LOGGER.error(
                f"{e} Can't fetching sites from SEARCH_API_LINK make sure use latest version of API")
            SITES = None
    search_plugins = config_dict['SEARCH_PLUGINS']
    if not search_plugins and SITES is None:
        search_plugins = DEFAULT_SEARCH_PLUGINS
        config_dict['SEARCH_PLUGINS'] = DEFAULT_SEARCH_PLUGINS
        LOGGER.info('Search: no API/PLUGINS configured — installing default qBit search engines')
    try:
        await sync_to_async(ensure_qbit)
        qbclient = await sync_to_async(get_client)
        qb_plugins = await sync_to_async(qbclient.search_plugins)
        if search_plugins:
            globals()['PLUGINS'] = []
            src_plugins = eval(search_plugins)
            if qb_plugins:
                names = [plugin['name'] for plugin in qb_plugins]
                await sync_to_async(qbclient.search_uninstall_plugin, names=names)
            await sync_to_async(qbclient.search_install_plugin, src_plugins)
        elif qb_plugins:
            for plugin in qb_plugins:
                await sync_to_async(qbclient.search_uninstall_plugin, names=plugin['name'])
            globals()['PLUGINS'] = []
        await sync_to_async(qbclient.auth_log_out)
    except Exception as e:
        LOGGER.error(f'Search tools init failed: {e}')


async def __suggestions(session, query):
    query = query.strip().lower()
    if not query or not query[0].isalnum():
        return []
    url = f"{SUGGEST_API}{query[0]}/{quote(query, safe='')}.json"
    async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as res:
        data = await res.json(content_type=None)
    items = []
    for item in data.get('d', []):
        if not str(item.get('id', '')).startswith('tt'):
            continue
        qid = item.get('qid')
        if qid is not None and qid not in ALLOWED_QIDS:
            continue
        title = item.get('l')
        if title:
            items.append((title.strip(), item.get('y'), item.get('rank', 10**9)))
    return items


async def __spellCorrect(key):
    query = key.strip().lower()
    if len(query) < 4 or not query[0].isalnum():
        return None
    try:
        async with ClientSession(trust_env=True, timeout=ClientTimeout(total=6)) as session:
            items = await __suggestions(session, query)
            if not items:
                await sleep(1)
                items = await __suggestions(session, query)
    except Exception as e:
        LOGGER.error(f'Spell check failed: {e}')
        return None
    titles = []
    for title, year, _rank in items:
        titles.append(title)
        if year:
            titles.append(f'{title} {year}')
    if not titles:
        return None
    normalized_titles = [t.lower() for t in titles]
    alnum_query = ''.join(filter(str.isalnum, query))
    if any(''.join(filter(str.isalnum, t)) == alnum_query for t in normalized_titles):
        return None
    for title, normalized in zip(titles, normalized_titles):
        if normalized in query or query in normalized:
            continue
        if ''.join(filter(str.isalnum, normalized)) == alnum_query:
            continue
        if SequenceMatcher(None, query, normalized).ratio() > 0.85:
            return title
    return None


async def __googleSuggestions(session, query):
    query = ' '.join(query.strip().lower().split())
    if not query:
        return []
    params = {'client': 'firefox', 'q': query, 'hl': 'en'}
    async with session.get(GOOGLE_SUGGEST_API, params=params,
                           headers={'User-Agent': 'Mozilla/5.0'}) as res:
        data = await res.json(content_type=None)
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return []
    return [' '.join(str(c).strip().lower().split()) for c in data[1] if c]


def __googleWordPick(token, prefix, suffixes, completions, min_score):
    token_l = token.lower()
    cands = {}
    for pos, completion in enumerate(completions):
        if prefix and not completion.startswith(prefix):
            continue
        base_rest = completion[len(prefix):].strip() if prefix else completion
        if base_rest == token_l or base_rest.startswith(token_l + ' '):
            return None, True
        rests = {base_rest}
        for suffix in suffixes:
            if suffix and base_rest.endswith(f' {suffix}'):
                rests.add(base_rest[:-len(suffix) - 1].strip())
        for rest in rests:
            words = rest.split()
            if len(words) != 1:
                continue
            wl = words[0].strip(',:-!?()')
            if not wl.isalpha():
                continue
            if wl == token_l or wl + 's' == token_l or wl + 'es' == token_l:
                return None, True
            if len(wl) <= 4:
                continue
            if abs(len(wl) - len(token_l)) > 3:
                continue
            score = SequenceMatcher(None, token_l, wl).ratio()
            if score >= min_score:
                prev = cands.get(wl)
                if prev is None or (score, -pos) > (prev[1], -prev[0]):
                    cands[wl] = (pos, score, wl)
    if not cands:
        return None, False
    return max(cands.values(), key=lambda v: (v[1], -v[0]))[2], True


def __pickWord(token, items, min_score):
    token_l = token.lower()
    stem = token_l.rstrip('s')
    known = False
    cands = {}
    for title, _year, rank in items:
        words = ''.join(c if c.isalnum() or c == ' ' else ' ' for c in title).split()
        for w in words:
            wl = w.lower()
            if wl == token_l or wl.rstrip('s') == stem:
                known = True
                continue
            if len(wl) > 4 and abs(len(wl) - len(token_l)) <= 3:
                score = SequenceMatcher(None, token_l, wl).ratio()
                if score >= min_score:
                    old = cands.get(wl)
                    if old is None or rank < old[1]:
                        cands[wl] = (w, rank, score)
    if known or not cands:
        return None
    best = min(cands.values(), key=lambda v: (v[1], -v[2]))
    return best[0]


async def __wordCorrect(key):
    tokens = key.split()
    if len(tokens) < 2:
        return None
    jobs = []
    for i, token in enumerate(tokens):
        if len(token) < 4 or not token.isalpha():
            continue
        prefix = ' '.join(tokens[:i]).lower()
        suffix = ' '.join(tokens[i + 1:]).lower()
        suffix_words = suffix.split()
        svars = list(dict.fromkeys((suffix, suffix_words[0] if suffix_words else '', '')))
        gprobes = []
        for cut in dict.fromkeys((token[:4], token[:3])):
            for sv in svars:
                gprobes.append(' '.join(p for p in (prefix, cut, sv) if p))
        gprobes = list(dict.fromkeys(gprobes))
        iprobes = list(dict.fromkeys(' '.join(p for p in (prefix, c) if p)
                                     for c in (token[:4], token[:3], token)))
        jobs.append((i, token, prefix, svars, gprobes, iprobes))
    if not jobs:
        return None
    gflat = [p for job in jobs for p in job[4]]
    iflat = [p for job in jobs for p in job[5]]
    try:
        async with ClientSession(trust_env=True, timeout=ClientTimeout(total=6)) as session:
            gres, ires = await gather(
                gather(*(__googleSuggestions(session, p) for p in gflat), return_exceptions=True),
                gather(*(__suggestions(session, p) for p in iflat), return_exceptions=True))
            gres = [[] if isinstance(x, BaseException) else x for x in gres]
            ires = [[] if isinstance(x, BaseException) else x for x in ires]
    except Exception as e:
        LOGGER.error(f'Word spell check failed: {e}')
        return None
    fixed = list(tokens)
    changed = False
    gpos = 0
    ipos = 0
    for i, token, prefix, svars, gprobes, iprobes in jobs:
        gcomp = []
        for _ in gprobes:
            gcomp.extend(gres[gpos])
            gpos += 1
        iitems = []
        seen = set()
        for _ in iprobes:
            for entry in ires[ipos]:
                if entry[0] not in seen:
                    seen.add(entry[0])
                    iitems.append(entry)
            ipos += 1
        min_score = 0.8 if len(token) >= 9 else 0.7
        word, decided = __googleWordPick(token, prefix, svars, gcomp, min_score)
        if not decided:
            word = __pickWord(token, iitems, min_score)
        if word:
            fixed[i] = word
            changed = True
    if not changed:
        return None
    corrected = ' '.join(fixed)
    return corrected if corrected.lower() != key.lower() else None


def __searchVariants(key):
    season = None
    ep = None
    m = re.search(r'\bs(\d{1,2})\s*e(\d{1,3})\b', key, re.I)
    if m:
        season, ep = m.group(1), m.group(2)
    else:
        m = re.search(r'\bseasons?\s*(\d{1,2})\b', key, re.I)
        if m:
            season = m.group(1)
        m = re.search(r'\b(?:episodes?|eps?)\s*\.?\s*(\d{1,4})\b', key, re.I)
        if m:
            ep = m.group(1)
    if season is None and ep is None:
        return [], None, None
    if season:
        tag = f'S{int(season):02d}' + (f'E{int(ep):02d}' if ep else '')
    else:
        tag = str(int(ep))
    cleaned = re.sub(r'\bs\d{1,2}\s*e\d{1,3}\b', ' ', key, flags=re.I)
    cleaned = re.sub(r'\bseasons?\s*\d{1,2}\b', ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\b(?:episodes?|eps?)\s*\.?\s*\d{1,4}\b', ' ', cleaned, flags=re.I)
    cleaned = ' '.join(cleaned.split())
    base_v = f'{cleaned} {tag}'.strip()
    variants = [base_v]
    if season and not ep:
        bare = f'{cleaned} {int(season)}'.strip()
        if bare not in variants:
            variants.append(bare)
    v2 = ' '.join(w for w in base_v.split() if w.lower() not in ('arc', 'saga'))
    if v2 not in variants:
        variants.append(v2)
    core = [w for w in v2.split() if w != tag]
    stopwords = {'of', 'the', 'a', 'an', 'and', 'in', 'on', 'to', 'for', 'my'}
    if len(core) > 2 and core[0].lower() not in stopwords and core[1].lower() not in stopwords:
        v3 = ' '.join(core[:2] + [tag])
        if v3 not in variants:
            variants.append(v3)
    broad = ' '.join(core[:4]) if core else None
    variants = [v for v in variants[:3] if v.lower() != key.lower()]
    if broad and broad.lower() == key.lower():
        broad = None
    return variants, ep, broad


def __epNote(results, method, ep, words=()):
    if not ep:
        return None
    epn = int(ep)
    exact_pat = re.compile(rf'(?<!\d)0*{epn}(?!\d)')
    scan_pat = re.compile(r'(?<!\d)(\d{2,4})(?!\d)')
    exact = 0
    nums = set()
    for r in results:
        name = (r.get('name') or '') if method.startswith('api') else (getattr(r, 'fileName', '') or '')
        name_l = name.lower()
        if words and not any(w in name_l for w in words):
            continue
        if exact_pat.search(name):
            exact += 1
        for n in scan_pat.findall(name):
            nums.add(int(n))
    if exact:
        return None
    qual = {480, 576, 720, 1080, 2160, 4320, 264, 265, 100, 10}
    near = [n for n in nums if n != epn and abs(n - epn) <= 60 and n not in qual
            and not (1900 <= n <= 2099 and not (1900 <= epn <= 2099))]
    if near:
        closest = min(near, key=lambda n: (abs(n - epn), -n))
        return f"⚠️ <b>Episode {epn} not found</b> — closest available: <b>{closest}</b>"
    return f"⚠️ <b>Episode {epn} not found in these results</b>"


async def __finishResults(search_results, total, key, site, message, method, note=None):
    site_label = SITES.get(site) if method.startswith('api') else str(site).capitalize()
    if method == 'apitrend':
        msg = f"🔥 <b>Found {min(total, TELEGRAPH_LIMIT)} trending result(s)</b>\n📍 <b>Site:</b> <i>{site_label}</i>"
    elif method == 'apirecent':
        msg = f"🆕 <b>Found {min(total, TELEGRAPH_LIMIT)} recent result(s)</b>\n📍 <b>Site:</b> <i>{site_label}</i>"
    else:
        msg = f"✅ <b>Found {min(total, TELEGRAPH_LIMIT)} result(s)</b>\n🔎 <code>{escape(str(key))}</code>\n📍 <b>Site:</b> <i>{site_label}</i>"
    if note:
        msg = f'{note}\n{msg}'
    link = await __getResult(search_results, key, message, method)
    buttons = ButtonMaker()
    buttons.ubutton("🔎 VIEW", link)
    button = buttons.build_menu(1)
    await editMessage(message, msg, button)


def __qbMulti(client, keys, site):
    jobs = {}
    for k in keys:
        jobs[k] = client.search_start(pattern=k, plugins=site, category='all').id
    for _ in range(120):
        running = False
        for sid in jobs.values():
            try:
                if client.search_status(search_id=sid)[0].status == 'Running':
                    running = True
                    break
            except Exception:
                pass
        if not running:
            break
        time.sleep(1)
    out = {}
    for k, sid in jobs.items():
        try:
            r = client.search_results(search_id=sid, limit=TELEGRAPH_LIMIT)
            out[k] = (r.total, r.results)
        except Exception:
            out[k] = (0, [])
        try:
            client.search_delete(search_id=sid)
        except Exception:
            pass
    return out


async def __apiMulti(keys, site):
    SEARCH_API_LINK = config_dict['SEARCH_API_LINK']
    SEARCH_LIMIT = config_dict['SEARCH_LIMIT']
    out = {}

    async def fetch(session, k):
        if site == 'all':
            api = f"{SEARCH_API_LINK}/api/v1/all/search?query={k}&limit={SEARCH_LIMIT}"
        else:
            api = f"{SEARCH_API_LINK}/api/v1/search?site={site}&query={k}&limit={SEARCH_LIMIT}"
        try:
            async with session.get(api) as res:
                data = await res.json()
            if 'error' in data:
                return k, (0, [])
            return k, (data.get('total', 0), data.get('data', []))
        except Exception:
            return k, (0, [])

    async with ClientSession(trust_env=True) as session:
        for k, v in await gather(*(fetch(session, k) for k in keys)):
            out[k] = v
    return out


async def __variantSearch(variants, broad, ep, ep_words, site, message, method):
    keys = list(dict.fromkeys([k for k in variants if k] + ([broad] if broad else [])))
    if not keys:
        return False
    await editMessage(message, "🔧 <b>Trying torrent-style queries...</b>\n⏳ <b>Please wait...</b>")
    try:
        if method.startswith('api'):
            results = await __apiMulti(keys, site)
        else:
            from ..helper.ext_utils.engine_lifecycle import ensure_qbit
            await sync_to_async(ensure_qbit)
            client = await sync_to_async(get_client)
            try:
                results = await sync_to_async(__qbMulti, client, keys, site)
            finally:
                try:
                    await sync_to_async(client.auth_log_out)
                except Exception:
                    pass
    except Exception as e:
        LOGGER.error(f'Variant search failed: {e}')
        return False
    for k in keys:
        if broad and k == broad:
            continue
        total, res = results.get(k, (0, []))
        if total > 0 and (not ep or __epNote(res, method, ep, ep_words) is None):
            await __finishResults(res, total, k, site, message, method)
            return True
    if ep and broad:
        pass2 = [broad] + [k for k in keys if k != broad]
    else:
        pass2 = keys
    for k in pass2:
        total, res = results.get(k, (0, []))
        if total > 0:
            note = __epNote(res, method, ep, ep_words) if ep else None
            await __finishResults(res, total, k, site, message, method, note=note)
            return True
    return False


async def __search(key, site, message, method):
    if not key or method not in ('apisearch', 'plugin'):
        await __doSearch(key, site, message, method)
        return
    struct_words = {'episode', 'episodes', 'ep', 'eps', 'season', 'seasons',
                    'arc', 'saga', 'full', 'complete'}
    variants, ep, broad = __searchVariants(key)
    ep_words = tuple(w.lower() for w in re.findall(r'[A-Za-z]{4,}', key)
                     if w.lower() not in struct_words)[:3]
    corrected = await __spellCorrect(key)
    if corrected is None:
        corrected = await __wordCorrect(key)
    if corrected:
        await editMessage(message, f"✏️ <b>Spelling Corrected</b>\n<s>{escape(str(key))}</s> ➜ <code>{escape(corrected)}</code>\n⏳ <b>Searching...</b>")
        c_variants, c_ep, c_broad = __searchVariants(corrected)
        if c_variants or c_broad:
            variants, broad = c_variants, c_broad
        c_words = tuple(w.lower() for w in re.findall(r'[A-Za-z]{4,}', corrected)
                        if w.lower() not in struct_words)[:3]
        if c_words:
            ep_words = c_words
    skip_base = bool(ep and variants and
                     not re.search(r'(?i)\bseasons?\s*\d|\bs\d{1,2}e\d', key))
    if not skip_base:
        if corrected:
            if await __doSearch(corrected, site, message, method, silent_miss=True, ep=ep, ep_words=ep_words):
                return
        else:
            if await __doSearch(key, site, message, method, silent_miss=True, ep=ep, ep_words=ep_words):
                return
    if (variants or broad) and await __variantSearch(variants, broad, ep, ep_words, site, message, method):
        return
    if corrected and not skip_base:
        await editMessage(message, f"🔁 <b>Correction gave no result</b>\n⏳ Searching original: <code>{escape(str(key))}</code>")
        if await __doSearch(key, site, message, method, silent_miss=True, ep=ep, ep_words=ep_words):
            return
    site_label = SITES.get(site) if method.startswith('api') else str(site).capitalize()
    hint = f"\n📺 <i>Episode {int(ep)} may not be released yet</i>" if ep else ''
    await editMessage(message, f"❌ <b>No Result Found</b>\n🔎 <code>{escape(str(key))}</code>\n📍 <b>Site:</b> <i>{site_label}</i>\n💡 <i>Try different or fewer keywords</i>{hint}")


async def __doSearch(key, site, message, method, silent_miss=False, ep=None, ep_words=()):
    if method.startswith('api'):
        SEARCH_API_LINK = config_dict['SEARCH_API_LINK']
        SEARCH_LIMIT = config_dict['SEARCH_LIMIT']
        if method == 'apisearch':
            LOGGER.info(f"API Searching: {key} from {site}")
            if site == 'all':
                api = f"{SEARCH_API_LINK}/api/v1/all/search?query={key}&limit={SEARCH_LIMIT}"
            else:
                api = f"{SEARCH_API_LINK}/api/v1/search?site={site}&query={key}&limit={SEARCH_LIMIT}"
        elif method == 'apitrend':
            LOGGER.info(f"API Trending from {site}")
            if site == 'all':
                api = f"{SEARCH_API_LINK}/api/v1/all/trending?limit={SEARCH_LIMIT}"
            else:
                api = f"{SEARCH_API_LINK}/api/v1/trending?site={site}&limit={SEARCH_LIMIT}"
        elif method == 'apirecent':
            LOGGER.info(f"API Recent from {site}")
            if site == 'all':
                api = f"{SEARCH_API_LINK}/api/v1/all/recent?limit={SEARCH_LIMIT}"
            else:
                api = f"{SEARCH_API_LINK}/api/v1/recent?site={site}&limit={SEARCH_LIMIT}"
        try:
            async with ClientSession(trust_env=True) as c:
                async with c.get(api) as res:
                    search_results = await res.json()
            if 'error' in search_results or search_results['total'] == 0:
                if not silent_miss:
                    site_label = SITES.get(site)
                    await editMessage(message, f"❌ <b>No Result Found</b>\n🔎 <code>{escape(str(key))}</code>\n📍 <b>Site:</b> <i>{site_label}</i>\n💡 <i>Try different or fewer keywords</i>")
                return False
            total = search_results['total']
            search_results = search_results['data']
        except Exception as e:
            await editMessage(message, f"⚠️ <b>Search failed</b>\n🔎 <code>{escape(str(key))}</code>\n<code>{str(e)[:200]}</code>")
            return False
    else:
        from ..helper.ext_utils.engine_lifecycle import ensure_qbit
        LOGGER.info(f"PLUGINS Searching: {key} from {site}")
        await sync_to_async(ensure_qbit)
        try:
            client = await sync_to_async(get_client)
            search = await sync_to_async(client.search_start, pattern=key, plugins=site, category='all')
            search_id = search.id
            while True:
                result_status = await sync_to_async(client.search_status, search_id=search_id)
                status = result_status[0].status
                if status != 'Running':
                    break
                await sleep(1)
            dict_search_results = await sync_to_async(client.search_results, search_id=search_id, limit=TELEGRAPH_LIMIT)
        except Exception as e:
            await editMessage(message, f"⚠️ <b>Search failed</b>\n🔎 <code>{escape(str(key))}</code>\n<code>{str(e)[:200]}</code>")
            return False
        search_results = dict_search_results.results
        total = dict_search_results.total
        if total == 0:
            if not silent_miss:
                await editMessage(message, f"❌ <b>No Result Found</b>\n🔎 <code>{escape(str(key))}</code>\n📍 <b>Site:</b> <i>{str(site).capitalize()}</i>\n💡 <i>Try different or fewer keywords</i>")
            return False
        try:
            await sync_to_async(client.search_delete, search_id=search_id)
        except Exception:
            pass
        try:
            await sync_to_async(client.auth_log_out)
        except Exception:
            pass
    note = __epNote(search_results, method, ep, ep_words) if ep else None
    if ep and note is not None:
        return False
    await __finishResults(search_results, total, key, site, message, method, note=note)
    return True


async def __getResult(search_results, key, message, method):
    telegraph_content = []
    if method == 'apirecent':
        msg = "<h4>API Recent Results</h4>"
    elif method == 'apisearch':
        msg = f"<h4>API Search Result(s) For {key}</h4>"
    elif method == 'apitrend':
        msg = "<h4>API Trending Results</h4>"
    else:
        msg = f"<h4>PLUGINS Search Result(s) For {key}</h4>"
    for index, result in enumerate(search_results, start=1):
        if method.startswith('api'):
            try:
                if 'name' in result.keys():
                    msg += f"<code><a href='{result['url']}'>{escape(result['name'])}</a></code><br>"
                if 'torrents' in result.keys():
                    for subres in result['torrents']:
                        msg += f"<b>Quality: </b>{subres['quality']} | <b>Type: </b>{subres['type']} | "
                        msg += f"<b>Size: </b>{subres['size']}<br>"
                        if 'torrent' in subres.keys():
                            msg += f"<a href='{subres['torrent']}'>Direct Link</a><br>"
                        elif 'magnet' in subres.keys():
                            msg += "<b>Share Magnet to</b> "
                            msg += f"<a href='http://t.me/share/url?url={subres['magnet']}'>Telegram</a><br>"
                    msg += '<br>'
                else:
                    msg += f"<b>Size: </b>{result['size']}<br>"
                    try:
                        msg += f"<b>Seeders: </b>{result['seeders']} | <b>Leechers: </b>{result['leechers']}<br>"
                    except Exception:
                        pass
                    if 'torrent' in result.keys():
                        msg += f"<a href='{result['torrent']}'>Direct Link</a><br><br>"
                    elif 'magnet' in result.keys():
                        msg += "<b>Share Magnet to</b> "
                        msg += f"<a href='http://t.me/share/url?url={quote(result['magnet'])}'>Telegram</a><br><br>"
                    else:
                        msg += '<br>'
            except:
                continue
        else:
            msg += f"<a href='{result.descrLink}'>{escape(result.fileName)}</a><br>"
            msg += f"<b>Size: </b>{get_readable_file_size(result.fileSize)}<br>"
            msg += f"<b>Seeders: </b>{result.nbSeeders} | <b>Leechers: </b>{result.nbLeechers}<br>"
            link = result.fileUrl
            if link.startswith('magnet:'):
                msg += f"<b>Share Magnet to</b> <a href='http://t.me/share/url?url={quote(link)}'>Telegram</a><br><br>"
            else:
                msg += f"<a href='{link}'>Direct Link</a><br><br>"

        if len(msg.encode('utf-8')) > 39000:
            telegraph_content.append(msg)
            msg = ""

        if index == TELEGRAPH_LIMIT:
            break

    if msg != "":
        telegraph_content.append(msg)

    await editMessage(message, f"<b>Creating</b> {len(telegraph_content)} <b>Telegraph pages.</b>")
    path = [(await telegraph.create_page(title=f"{config_dict['TITLE_NAME']} Torrent Search",
                                         content=content))["path"] for content in telegraph_content]
    if len(path) > 1:
        await editMessage(message, f"<b>Editing</b> {len(telegraph_content)} <b>Telegraph pages.</b>")
        await telegraph.edit_telegraph(path, telegraph_content)
    return f"https://telegra.ph/{path[0]}"


def __api_buttons(user_id, method):
    buttons = ButtonMaker()
    for data, name in SITES.items():
        buttons.ibutton(name, f"torser {user_id} {data} {method}")
    buttons.ibutton("Cancel", f"torser {user_id} cancel")
    return buttons.build_menu(2)


async def __plugin_buttons(user_id):
    from ..helper.ext_utils.engine_lifecycle import ensure_qbit
    buttons = ButtonMaker()
    if not PLUGINS:
        await sync_to_async(ensure_qbit)
        try:
            qbclient = await sync_to_async(get_client)
            pl = await sync_to_async(qbclient.search_plugins)
            for name in pl:
                PLUGINS.append(name['name'])
            await sync_to_async(qbclient.auth_log_out)
        except Exception as e:
            LOGGER.error(f'Search plugins list failed: {e}')
    for siteName in PLUGINS:
        buttons.ibutton(siteName.capitalize(),
                        f"torser {user_id} {siteName} plugin")
    buttons.ibutton('All', f"torser {user_id} all plugin")
    buttons.ibutton("Cancel", f"torser {user_id} cancel")
    return buttons.build_menu(2)


async def torrentSearch(_, message):
    user_id = message.from_user.id
    buttons = ButtonMaker()
    key = message.text.split() if message.text else ['/cmd']
    SEARCH_PLUGINS = config_dict['SEARCH_PLUGINS']
    msg, btn = await checking_access(user_id)
    if msg is not None:
        await sendMessage(message, msg, btn.build_menu(1))
        return
    if SITES is None and not SEARCH_PLUGINS:
        await sendMessage(message, "No API link or search PLUGINS added for this function")
    elif len(key) == 1 and SITES is None:
        await sendMessage(message, "Send a search key along with command")
    elif len(key) == 1:
        buttons.ibutton('Trending', f"torser {user_id} apitrend")
        buttons.ibutton('Recent', f"torser {user_id} apirecent")
        buttons.ibutton("Cancel", f"torser {user_id} cancel")
        button = buttons.build_menu(2)
        await sendMessage(message, "Send a search key along with command", button)
    elif SITES is not None and SEARCH_PLUGINS:
        buttons.ibutton('Api', f"torser {user_id} apisearch")
        buttons.ibutton('Plugins', f"torser {user_id} plugin")
        buttons.ibutton("Cancel", f"torser {user_id} cancel")
        button = buttons.build_menu(2)
        await sendMessage(message, 'Choose tool to search:', button)
    elif SITES is not None:
        button = __api_buttons(user_id, "apisearch")
        await sendMessage(message, 'Choose site to search | API:', button)
    else:
        button = await __plugin_buttons(user_id)
        await sendMessage(message, 'Choose site to search | Plugins:', button)


@new_task
async def torrentSearchUpdate(_, query):
    user_id = query.from_user.id
    message = query.message
    key = message.reply_to_message.text.split(maxsplit=1)
    key = key[1].strip() if len(key) > 1 else None
    data = query.data.split()
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2].startswith('api'):
        await query.answer()
        button = __api_buttons(user_id, data[2])
        await editMessage(message, 'Choose site:', button)
    elif data[2] == 'plugin':
        await query.answer()
        button = await __plugin_buttons(user_id)
        await editMessage(message, 'Choose site:', button)
    elif data[2] != "cancel":
        await query.answer()
        site = data[2]
        method = data[3]
        if method.startswith('api'):
            if key is None:
                if method == 'apirecent':
                    endpoint = 'Recent'
                elif method == 'apitrend':
                    endpoint = 'Trending'
                await editMessage(message, f"⏳ <b>Listing {endpoint} Items...</b>\n📍 <b>Site:</b> <i>{SITES.get(site)}</i>")
            else:
                await editMessage(message, f"⏳ <b>Searching...</b>\n🔎 <code>{escape(str(key))}</code>\n📍 <b>Site:</b> <i>{SITES.get(site)}</i>")
        else:
            await editMessage(message, f"⏳ <b>Searching...</b>\n🔎 <code>{escape(str(key))}</code>\n📍 <b>Site:</b> <i>{site.capitalize()}</i>")
        await __search(key, site, message, method)
    else:
        await query.answer()
        await editMessage(message, "Search has been canceled!")


bot.add_handler(MessageHandler(torrentSearch, filters=command(
    BotCommands.SearchCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
bot.add_handler(CallbackQueryHandler(
    torrentSearchUpdate, filters=regex("^torser")))
