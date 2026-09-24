#!/usr/bin/env python3
import aiohttp
import urllib.parse
import re
import asyncio
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from .. import bot, LOGGER
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.bot_commands import BotCommands
TMDB_API_KEY = "4b061466449ce519d5884948a9671e63"
PROVIDERS = {"netflix": {"id": 8, "cdn": "https://occ-0-2774-2773.1.nflxso.net/dnm/api/v6/BvY29xc2FyaW5n", "label": "Netflix"}, "prime": {"id": 1899, "cdn": "https://m.media-amazon.com/images/M", "label": "Prime"}, "crunchyroll": {"id": 283, "cdn": "https://img1.ak.crunchyroll.com/i/spire3", "label": "Crunchyroll"}}
async def fetch_json(url):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=7)) as r:
                if r.status == 200:
                    return await r.json()
    except Exception as e:
        LOGGER.error(e)
    return None
def _parse_smart_query(q):
    q = q.strip()
    season = None
    year = None
    for _ in range(2):
        m = re.search(r'(?i)(?:season|s)\s*[-:]?\s*0?(\d{1,2})\s*$', q)
        if m:
            season = int(m.group(1))
            q = q[:m.start()].strip()
            continue
        m = re.search(r'(?i)\bs0?(\d{1,2})(?:e\d+)?\s*$', q)
        if m and season is None:
            try:
                season = int(m.group(1))
                q = q[:m.start()].strip()
                continue
            except:
                pass
        m = re.search(r'\b(\d{4})\b\s*$', q)
        if m and 1900 <= int(m.group(1)) <= 2035:
            year = m.group(1)
            q = q[:m.start()].strip()
            continue
        break
    q = re.sub(r'\s+', ' ', q).strip()
    return q, season, year
def _detect_provider(q):
    ql = q.lower()
    if "crunchyroll" in ql or "img1.ak.crunchyroll" in ql:
        return "crunchyroll"
    if "netflix" in ql or "nflxso" in ql:
        return "netflix"
    if "prime" in ql or "amazon.com" in ql or "m.media-amazon" in ql:
        return "prime"
    return None
async def _tmdb_search(title, year=None):
    sq = urllib.parse.quote_plus(title)
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={sq}"
    if year:
        url += f"&year={year}"
    j = await fetch_json(url)
    if not j or not j.get("results"):
        return []
    out = []
    for it in j["results"]:
        if it.get("media_type") not in ["movie", "tv"]:
            continue
        t = it.get("name") or it.get("title") or ""
        if not t:
            continue
        out.append(it)
        if len(out) >= 8:
            break
    return out
async def _justwatch_search(title, provider):
    try:
        url = "https://apis.justwatch.com/content/titles/en_US/popular"
        payload = {"query": title, "content_types": ["movie", "show"], "providers": [provider]}
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=4)) as r:
                if r.status == 200:
                    j = await r.json()
                    items = j.get("items", [])[:3]
                    return [(it.get("title") or "").lower() for it in items if it.get("title")]
    except:
        pass
    return []
async def _provider_for_tmdb(media_type, tmdb_id):
    try:
        u = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers?api_key={TMDB_API_KEY}"
        j = await fetch_json(u)
        if not j:
            return None
        for region in ["IN", "US", "GB"]:
            provs = j.get("results", {}).get(region)
            if not provs:
                continue
            flat = provs.get("flatrate", []) + provs.get("free", []) + provs.get("ads", [])
            for p in flat:
                n = p.get("provider_name", "").lower()
                if "netflix" in n:
                    return "netflix"
                if "prime" in n or "amazon" in n:
                    return "prime"
                if "crunchyroll" in n:
                    return "crunchyroll"
    except:
        pass
    return None
async def _smart_search(raw_q):
    prov = _detect_provider(raw_q)
    clean_q = re.sub(r'(?i)https?://\S+|netflix|prime\s*video|crunchyroll|nflxso\.net|m\.media-amazon\.com|img1\.ak\.crunchyroll\.com', '', raw_q).strip()
    clean_q, season, year = _parse_smart_query(clean_q)
    if not clean_q:
        clean_q, season, year = _parse_smart_query(raw_q)
    tm_res = await _tmdb_search(clean_q, year)
    if not tm_res:
        return []
    tasks = [_provider_for_tmdb(it.get("media_type"), it["id"]) for it in tm_res]
    if prov is None:
        jw_tasks = [_justwatch_search(clean_q, p) for p in PROVIDERS]
        provs, jw_results = await asyncio.gather(asyncio.gather(*tasks), asyncio.gather(*jw_tasks))
        jw_map = {}
        for pname, titles in zip(PROVIDERS.keys(), jw_results):
            for t in titles:
                jw_map[t] = pname
    else:
        provs = await asyncio.gather(*tasks)
        jw_map = {}
    for it, pp in zip(tm_res, provs):
        it["_season"] = season
        it["_year"] = year
        if prov:
            it["_provider"] = prov if pp == prov or pp is None else pp
        else:
            if pp:
                it["_provider"] = pp
            else:
                lt = (it.get("name") or it.get("title") or "").lower()
                it["_provider"] = jw_map.get(lt)
                if not it["_provider"]:
                    for jt, jp in jw_map.items():
                        if jt and lt and (jt in lt or lt in jt):
                            it["_provider"] = jp
                            break
    if prov:
        filtered = [x for x in tm_res if x.get("_provider") == prov]
        return (filtered or tm_res)[:10]
    tm_res.sort(key=lambda x: (0 if x.get("_provider") else 1, -x.get("popularity", 0)))
    return tm_res[:10]
def _provider_label(p):
    if not p:
        return ""
    return f" [{PROVIDERS[p]['label']}]" if p in PROVIDERS else f" [{p}]"
async def get_poster_menu(client, message):
    if len(message.command) == 1:
        return await message.reply_text("<b>⚠️ ᴘʟᴇᴀꜱᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴍᴏᴠɪᴇ ᴏʀ ᴛᴠ ɴᴀᴍᴇ.\n\n📌 ᴇxᴀᴍᴘʟᴇ:</b> <code>/p naruto season 2</code> | <code>/p avengers 2019</code>")
    raw_q = " ".join(message.command[1:])
    short_q = re.sub(r'[^a-zA-Z0-9]+', '-', raw_q)[:20].strip('-')
    msg = await message.reply_text(f"<b>🔎 ꜱᴇᴀʀᴄʜɪɴɢ</b> <code>{raw_q}</code> <b>...</b>")
    try:
        results = await _smart_search(raw_q)
        if not results:
            return await msg.edit_text("<b>❌ ɴᴏ ʀᴇꜱᴜʟᴛꜱ ꜰᴏᴜɴᴅ!</b>")
        buttons = []
        for it in results[:10]:
            tmdb_id = it["id"]
            media_type = it.get("media_type") or ("tv" if it.get("object_type")=="show" else "movie")
            title = it.get("name") or it.get("title") or "ᴜɴᴋɴᴏᴡɴ"
            date_key = "first_air_date" if media_type == "tv" else "release_date"
            year = (it.get(date_key, "")[:4] if it.get(date_key) else it.get("_year") or "ɴ/ᴀ")[:4]
            prov = it.get("_provider")
            m_icon = "📺" if media_type == "tv" else "🎬"
            m_type = "ᴛᴠ" if media_type == "tv" else "ᴍᴏᴠɪᴇ"
            plabel = _provider_label(prov)
            btn_text = f"{m_icon} {title} ({year}) [{m_type}]{plabel}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"p_menu_{media_type}_{tmdb_id}_{short_q}")])
        buttons.append([InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="p_close")])
        await msg.edit_text(text=f"<b>✅ ꜰᴏᴜɴᴅ {len(results)} ꜰᴏʀ</b> <code>{raw_q}</code>\n\n<b>👇 ꜱᴇʟᴇᴄᴛ:</b>", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        LOGGER.error(e)
        await msg.edit_text(f"<b>⚠️ ᴇʀʀᴏʀ:</b> <code>{e}</code>")
async def handle_back_to_search(client, callback_query):
    short_q = callback_query.data.replace("p_search_", "").replace("-", " ")
    await callback_query.answer("🔎 ʟᴏᴀᴅɪɴɢ...")
    try:
        raw_q = short_q
        results = await _smart_search(raw_q)
        if not results:
            return await callback_query.answer("❌ ɴᴏ ʀᴇꜱᴜʟᴛꜱ!", show_alert=True)
        buttons = []
        cb_q = callback_query.data.replace("p_search_", "")
        for it in results[:10]:
            tmdb_id = it["id"]
            media_type = it.get("media_type") or "tv"
            title = it.get("name") or it.get("title") or "ᴜɴᴋɴᴏᴡɴ"
            date_key = "first_air_date" if media_type == "tv" else "release_date"
            year = (it.get(date_key, "")[:4] if it.get(date_key) else "ɴ/ᴀ")
            prov = it.get("_provider")
            m_icon = "📺" if media_type == "tv" else "🎬"
            m_type = "ᴛᴠ" if media_type == "tv" else "ᴍᴏᴠɪᴇ"
            plabel = _provider_label(prov)
            btn_text = f"{m_icon} {title} ({year}) [{m_type}]{plabel}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"p_menu_{media_type}_{tmdb_id}_{cb_q}")])
        buttons.append([InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="p_close")])
        text = f"<b>✅ ꜰᴏᴜɴᴅ ꜰᴏʀ</b> <code>{short_q}</code>\n\n<b>👇 ꜱᴇʟᴇᴄᴛ:</b>"
        if callback_query.message.photo:
            await client.send_message(chat_id=callback_query.message.chat.id, text=text, reply_markup=InlineKeyboardMarkup(buttons))
            try:
                await callback_query.message.delete()
            except:
                pass
        else:
            await callback_query.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        LOGGER.error(e)
        await callback_query.answer("⚠️ ᴇʀʀᴏʀ!", show_alert=True)
async def show_poster_categories(client, callback_query):
    data = callback_query.data.split("_")
    media_type = data[2]
    tmdb_id = data[3]
    short_q = data[4] if len(data) > 4 else ""
    await callback_query.answer("ɢᴇɴᴇʀᴀᴛɪɴɢ ᴍᴇɴᴜ...")
    try:
        details_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
        img_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images?api_key={TMDB_API_KEY}"
        prov_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers?api_key={TMDB_API_KEY}"
        details, images, prov_data = await asyncio.gather(fetch_json(details_url), fetch_json(img_url), fetch_json(prov_url))
        if not details or not images:
            return await callback_query.answer("⚠️ ꜰᴀɪʟᴇᴅ!", show_alert=True)
        title = details.get("name") or details.get("title", "ᴜɴᴋɴᴏᴡɴ")
        date_key = "first_air_date" if media_type == "tv" else "release_date"
        year = details.get(date_key, "")[:4] if details.get(date_key) else "ɴ/ᴀ"
        backdrops = images.get("backdrops", [])
        posters = images.get("posters", [])
        logos = images.get("logos", [])
        landscape = [x for x in backdrops if x.get("iso_639_1") not in (None, "xx")]
        landscape.sort(key=lambda x: (0 if x.get("iso_639_1") == 'en' else 1, x.get("iso_639_1", "")))
        clean_landscape = [x for x in backdrops if x.get("iso_639_1") in (None, "xx")]
        prov_label = ""
        try:
            provs = prov_data.get("results", {}).get("IN", {}) or prov_data.get("results", {}).get("US", {}) if prov_data else {}
            flat = provs.get("flatrate", [])
            names = [p.get("provider_name") for p in flat]
            for k, v in PROVIDERS.items():
                if v["label"].lower() in [n.lower() for n in names]:
                    prov_label = f"\n<b>📡 ᴘʀᴏᴠɪᴅᴇʀ:</b> {v['label']}"
                    break
        except:
            pass
        main_poster_path = details.get('poster_path') or (posters[0]['file_path'] if posters else None)
        main_poster = f"https://image.tmdb.org/t/p/w1280{main_poster_path}" if main_poster_path else "https://via.placeholder.com/800x1200?text=No+Poster"
        buttons = [
            [InlineKeyboardButton(f"🌄 Thumbnail ({len(landscape)})", callback_data=f"p_view_land_{media_type}_{tmdb_id}_0_{short_q}"), InlineKeyboardButton(f"🌌 Cover ({len(clean_landscape)})", callback_data=f"p_view_clean_{media_type}_{tmdb_id}_0_{short_q}")],
            [InlineKeyboardButton(f"📱 Portrait ({len(posters)})", callback_data=f"p_view_port_{media_type}_{tmdb_id}_0_{short_q}"), InlineKeyboardButton(f"✨ Logo ({len(logos)})", callback_data=f"p_view_logo_{media_type}_{tmdb_id}_0_{short_q}")]
        ]
        nav = []
        if short_q:
            nav.append(InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data=f"p_search_{short_q}"))
        nav.append(InlineKeyboardButton("❌ ᴄʟᴏꜱᴇ", callback_data="p_close"))
        buttons.append(nav)
        m_type_str = "ᴛᴠ ꜱᴇʀɪᴇꜱ" if media_type == "tv" else "ᴍᴏᴠɪᴇ"
        tmdb_link = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"
        caption = f"<b>🧿 ᴛɪᴛʟᴇ:</b> {title}\n<b>📅 ʏᴇᴀʀ:</b> {year}\n<b>🏷️ ᴛʏᴘᴇ:</b> {m_type_str}{prov_label}\n\n<b>🔗 ᴛᴍᴅʙ:</b> <a href=\"{tmdb_link}\">View</a>\n\n<b>👇 4 Assets — Select:</b>\n• Thumbnail = Cover + Logo combined\n• Cover = Textless background\n• Portrait = Vertical\n• Logo = PNG"
        if callback_query.message.photo:
            await callback_query.message.edit_media(media=InputMediaPhoto(media=main_poster, caption=caption), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await client.send_photo(chat_id=callback_query.message.chat.id, photo=main_poster, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
            try:
                await callback_query.message.delete()
            except:
                pass
    except Exception as e:
        LOGGER.error(e)
        await callback_query.answer("ᴇʀʀᴏʀ!", show_alert=True)
async def handle_poster_viewer(client, callback_query):
    data = callback_query.data.split("_")
    p_type = data[2]
    media_type = data[3]
    tmdb_id = data[4]
    current_index = int(data[5])
    short_q = data[6] if len(data) > 6 else ""
    await callback_query.answer("ꜰᴇᴛᴄʜɪɴɢ...")
    try:
        url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images?api_key={TMDB_API_KEY}"
        response = await fetch_json(url)
        if not response:
            return await callback_query.answer("⚠️ ᴀᴘɪ ᴇʀʀᴏʀ!", show_alert=True)
        backdrops = response.get("backdrops", [])
        if p_type == "land":
            images = [x for x in backdrops if x.get("iso_639_1") not in (None, "xx")]
            images.sort(key=lambda x: (0 if x.get("iso_639_1") == 'en' else 1, x.get("iso_639_1", "")))
            type_name = "Thumbnail"
        elif p_type == "port":
            images = response.get("posters", [])
            type_name = "Portrait"
        elif p_type == "logo":
            images = response.get("logos", [])
            type_name = "Logo"
        elif p_type == "clean":
            images = [x for x in backdrops if x.get("iso_639_1") in (None, "xx")]
            type_name = "Cover"
        else:
            images = []
        if not images:
            return await callback_query.answer(f"⚠️ ɴᴏ {p_type.upper()}!", show_alert=True)
        if current_index >= len(images):
            current_index = 0
        if current_index < 0:
            current_index = len(images) - 1
        img = images[current_index]
        base_path = img['file_path']
        if p_type == "logo":
            img_url = f"https://image.tmdb.org/t/p/w500{base_path}"
            original_url = f"https://image.tmdb.org/t/p/original{base_path}"
        elif p_type in ["land", "clean"]:
            img_url = f"https://image.tmdb.org/t/p/w1280{base_path}"
            original_url = f"https://image.tmdb.org/t/p/original{base_path}"
        else:
            img_url = f"https://image.tmdb.org/t/p/w780{base_path}"
            original_url = f"https://image.tmdb.org/t/p/original{base_path}"
        details_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}?api_key={TMDB_API_KEY}"
        details = await fetch_json(details_url)
        title = details.get("name") or details.get("title", "ᴜɴᴋɴᴏᴡɴ") if details else "ᴜɴᴋɴᴏᴡɴ"
        lang = img.get('iso_639_1')
        lang_display = lang.upper() if lang and lang != "xx" else 'ɴᴏɴᴇ'
        provider_note = ""
        if p_type == "land":
            provider_note = "\n<b>🖼️ Thumbnail:</b> Cover + Logo combined"
        elif p_type == "clean":
            provider_note = "\n<b>🌌 Cover:</b> Textless background"
        caption = f"<b>🧿 ᴛɪᴛʟᴇ:</b> {title}\n<b>🎨 ᴄᴀᴛᴇɢᴏʀʏ:</b> {type_name}{provider_note}\n<b>🌐 ʟᴀɴɢ:</b> {lang_display}\n<b>📏:</b> {img.get('width')}x{img.get('height')}\n\n<b>📥 Original:</b> <a href=\"{original_url}\">Download</a>"
        nav_btns = []
        if len(images) > 1:
            nav_btns.append(InlineKeyboardButton("⏮️", callback_data=f"p_view_{p_type}_{media_type}_{tmdb_id}_0_{short_q}"))
            nav_btns.append(InlineKeyboardButton("◀️", callback_data=f"p_view_{p_type}_{media_type}_{tmdb_id}_{current_index - 1}_{short_q}"))
        nav_btns.append(InlineKeyboardButton(f"{current_index + 1} / {len(images)}", callback_data="p_none"))
        if len(images) > 1:
            nav_btns.append(InlineKeyboardButton("▶️", callback_data=f"p_view_{p_type}_{media_type}_{tmdb_id}_{current_index + 1}_{short_q}"))
            nav_btns.append(InlineKeyboardButton("⏭️", callback_data=f"p_view_{p_type}_{media_type}_{tmdb_id}_{len(images) - 1}_{short_q}"))
        buttons = [nav_btns]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"p_menu_{media_type}_{tmdb_id}_{short_q}"), InlineKeyboardButton("❌ Close", callback_data="p_close")])
        try:
            await callback_query.message.edit_media(media=InputMediaPhoto(media=img_url, caption=caption), reply_markup=InlineKeyboardMarkup(buttons))
        except:
            small_url = f"https://image.tmdb.org/t/p/w780{base_path}"
            await callback_query.message.edit_media(media=InputMediaPhoto(media=small_url, caption=caption), reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        LOGGER.error(e)
        await callback_query.answer("ᴇʀʀᴏʀ!", show_alert=True)
async def ignore_callback(client, callback_query):
    await callback_query.answer()
async def close_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except:
        await callback_query.answer("⚠️ No delete permission!", show_alert=True)
bot.add_handler(MessageHandler(get_poster_menu, filters=command(BotCommands.PosterCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(handle_back_to_search, filters=regex(r"^p_search_")))
bot.add_handler(CallbackQueryHandler(show_poster_categories, filters=regex(r"^p_menu_")))
bot.add_handler(CallbackQueryHandler(handle_poster_viewer, filters=regex(r"^p_view_")))
bot.add_handler(CallbackQueryHandler(ignore_callback, filters=regex(r"^p_none$")))
bot.add_handler(CallbackQueryHandler(close_callback, filters=regex(r"^p_close$")))
