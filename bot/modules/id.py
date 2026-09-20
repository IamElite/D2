import html as _html
import logging
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from pyrogram.enums import ParseMode

from .. import bot
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters

# ── Diagnostic logger ──
_DBG = "[PREMIUM_EMOJI_DEBUG]"
LOGGER_D = logging.getLogger(__name__)
def _dlog(msg):
    try:
        # print ensures it appears in heroku logs even if LOGGER level filtered
        print(f"{_DBG} {msg}", flush=True)
        LOGGER_D.info(f"{_DBG} {msg}")
    except Exception:
        try:
            print(f"{_DBG} {msg}", flush=True)
        except Exception:
            pass

# Log WZGram version once at import
try:
    import importlib.metadata as _ilm
    _wz_ver = _ilm.version("wzgram")
except Exception:
    _wz_ver = "unknown"
try:
    from pyrogram.enums import MessageEntityType as _MET
    _has_custom = "CUSTOM_EMOJI" in dir(_MET)
except Exception:
    _has_custom = False
_dlog(f"WZGram version: {_wz_ver} | CUSTOM_EMOJI in MessageEntityType: {_has_custom}")
try:
    from pyrogram.types import MessageEntity as _ME
    import inspect as _insp
    _dlog(f"MessageEntity fields: custom_emoji_id in __init__={('custom_emoji_id' in _insp.signature(_ME.__init__).parameters)}")
except Exception as e:
    _dlog(f"MessageEntity inspect failed: {e}")
try:
    from pyrogram.parser.html import HTML as _HTML
    _dlog(f"WZGram HTML parser supports <tg-emoji> & <emoji>: tag in ['emoji','tg-emoji'] with attrs emoji-id/id")
except Exception as e:
    _dlog(f"HTML parser inspect failed: {e}")

MEDIA_TYPES = (
    ('document', 'ᴅᴏᴄᴜᴍᴇɴᴛ'),
    ('photo', 'ᴘʜᴏᴛᴏ'),
    ('video', 'ᴠɪᴅᴇᴏ'),
    ('animation', 'ɢɪғ'),
    ('sticker', 'sᴛɪᴄᴋᴇʀ'),
    ('audio', 'ᴀᴜᴅɪᴏ'),
    ('voice', 'ᴠᴏɪᴄᴇ'),
    ('video_note', 'ᴠɪᴅᴇᴏ ɴᴏᴛᴇ'),
)

# ── Premium/Custom Emoji helpers (existing logic preserved, only extension) ──
def _get_fallback(text, offset, length):
    """Extract UTF-16 slice for custom emoji placeholder. Fallback to 😀."""
    try:
        raw = str(text) if text is not None else ""
        if not raw:
            _dlog(f"Fallback resolution: empty text -> 😀")
            return "😀"
        b = raw.encode('utf-16-le')
        # offset/length are in UTF-16 code units
        start = int(offset) * 2
        end = start + int(length) * 2
        if start < 0 or end > len(b) or start >= end:
            _dlog(f"Fallback resolution: out of bounds text_len={len(b)//2} offset={offset} length={length} -> 😀")
            return "😀"
        fb = b[start:end].decode('utf-16-le')
        if fb and fb.strip():
            _dlog(f"Fallback resolution: text='{raw[:50]}' offset={offset} length={length} -> fallback='{fb}'")
            return fb
    except Exception as e:
        _dlog(f"Fallback resolution exception: {e} -> 😀")
        pass
    return "😀"

def _collect_premium_emojis(reply):
    """
    Scan reply message for Premium/Custom Emojis.
    Returns dict {custom_emoji_id: fallback_char} unique by ID, order = detection order.
    Covers:
    - text + entities
    - caption + caption_entities
    - inline/reply buttons icon_custom_emoji_id
    """
    out = {}
    if not reply or getattr(reply, "empty", True):
        _dlog("ID extraction: reply is None or empty -> no premium")
        return out

    _dlog(f"===== START =====")
    _dlog(f"Source message ID: {getattr(reply, 'id', 'unknown')}")
    _dlog(f"Chat ID: {getattr(getattr(reply, 'chat', None), 'id', 'unknown') or getattr(reply, 'chat', 'nochat')}")
    _dlog(f"Source text/caption: text='{str(getattr(reply, 'text', None) or '')[:200]}' caption='{str(getattr(reply, 'caption', None) or '')[:200]}'")
    _dlog(f"Source entities: {getattr(reply, 'entities', None)}")
    _dlog(f"Source caption_entities: {getattr(reply, 'caption_entities', None)}")
    try:
        mk = getattr(reply, 'reply_markup', None)
        _dlog(f"Source reply_markup: {mk} | inline_keyboard={getattr(mk,'inline_keyboard',None) if mk else None} | keyboard={getattr(mk,'keyboard',None) if mk else None}")
    except Exception as e:
        _dlog(f"Source reply_markup inspect fail: {e}")

    # --- 1) text / caption entities ---
    def process(text, entities, label):
        if not text or not entities:
            _dlog(f"process({label}): no text or no entities (text={bool(text)}, entities={bool(entities)})")
            return
        _dlog(f"process({label}): scanning {len(entities)} entities in text='{str(text)[:100]}'")
        for idx, ent in enumerate(entities):
            try:
                _dlog(f"  Entity #{idx}: type={getattr(getattr(ent,'type',None),'name',str(getattr(ent,'type','')))} offset={getattr(ent,'offset',None)} length={getattr(ent,'length',None)} custom_emoji_id={getattr(ent,'custom_emoji_id',None)} full={ent}")
                # robust type check across pyrogram/wzgram versions
                is_custom = False
                try:
                    from pyrogram.enums import MessageEntityType
                    is_custom = ent.type == MessageEntityType.CUSTOM_EMOJI
                except Exception:
                    # fallback string compare
                    tname = getattr(getattr(ent, "type", None), "name", str(getattr(ent, "type", "")))
                    is_custom = str(tname).upper() == "CUSTOM_EMOJI"
                _dlog(f"    is_custom={is_custom}")
                if not is_custom:
                    continue
                cid = getattr(ent, "custom_emoji_id", None)
                _dlog(f"    Extracted custom_emoji_id: {cid}")
                if not cid:
                    _dlog(f"    FAIL: custom_emoji_id missing -> skip")
                    continue
                cid = str(cid)
                if cid in out:
                    _dlog(f"    Duplicate cid {cid} -> skip")
                    continue
                fb = _get_fallback(text, getattr(ent, "offset", 0), getattr(ent, "length", 2))
                _dlog(f"    Fallback/alt emoji: '{fb}' for cid {cid}")
                out[cid] = fb
                _dlog(f"    --> Collected {cid} -> '{fb}'")
            except Exception as e:
                _dlog(f"    Exception in process: {e}")
                import traceback
                _dlog(f"    {traceback.format_exc()[:500]}")
                continue

    try:
        process(getattr(reply, "text", None), getattr(reply, "entities", None), "text")
        process(getattr(reply, "caption", None), getattr(reply, "caption_entities", None), "caption")
    except Exception as e:
        _dlog(f"process overall exception: {e}")

    # --- 2) buttons (inline + reply) ---
    try:
        markup = getattr(reply, "reply_markup", None)
        if markup:
            kb = None
            kb_type = None
            if hasattr(markup, "inline_keyboard") and getattr(markup, "inline_keyboard"):
                kb = markup.inline_keyboard
                kb_type = "inline_keyboard"
            elif hasattr(markup, "keyboard") and getattr(markup, "keyboard"):
                kb = markup.keyboard
                kb_type = "keyboard"
            _dlog(f"Buttons: type={kb_type} rows={len(kb) if kb else 0}")
            if kb:
                for r_idx, row in enumerate(kb):
                    for b_idx, btn in enumerate(row or []):
                        try:
                            _dlog(f"  Button [{r_idx}][{b_idx}]: text='{getattr(btn,'text','')[:50]}' icon_custom_emoji_id={getattr(btn,'icon_custom_emoji_id',None)} full={btn}")
                            cid = getattr(btn, "icon_custom_emoji_id", None)
                            if cid and str(cid) not in out:
                                out[str(cid)] = "🖼"  # generic fallback for button icon
                                _dlog(f"    --> Collected button cid {cid} -> '🖼'")
                            elif cid:
                                _dlog(f"    Duplicate button cid {cid} -> skip")
                            else:
                                _dlog(f"    No icon_custom_emoji_id")
                        except Exception as e:
                            _dlog(f"    Button exception: {e}")
                            continue
            else:
                _dlog("Buttons: no keyboard found")
        else:
            _dlog("Buttons: reply_markup is None")
    except Exception as e:
        _dlog(f"Buttons overall exception: {e}")

    _dlog(f"Collected premium emojis final: {out} (count={len(out)})")
    return out

async def universal_id(client, message):
    _dlog("===== universal_id called =====")
    _dlog(f"Incoming message ID: {getattr(message,'id',None)} chat={getattr(getattr(message,'chat',None),'id',None)} from_user={getattr(getattr(message,'from_user',None),'id',None)}")
    _dlog(f"message.text='{str(getattr(message,'text',''))[:200]}' command={getattr(message,'command',None)}")
    try:
        _dlog(f"WZGram send_message impl: {client.send_message if hasattr(client,'send_message') else 'no client'}")
        _dlog(f"message.reply_text impl: {getattr(message,'reply_text',None)}")
    except Exception as e:
        _dlog(f"impl inspect fail: {e}")

    chat = message.chat
    your_id = message.from_user.id if message.from_user else chat.id
    reply = message.reply_to_message
    _dlog(f"Reply exists: {bool(reply and not getattr(reply,'empty',True))} reply_id={getattr(reply,'id',None) if reply else None}")

    # Build main ID text as HTML (so we can send single message with tg-emoji)
    # HTML keeps same visual: <b> for bold, <code> for code, <a> for links
    text = f'<b><a href="{message.link}">ᴍᴇssᴀɢᴇ ɪᴅ:</a></b> <code>{message.id}</code>\n'
    text += f'<b><a href="tg://user?id={your_id}">ʏᴏᴜʀ ɪᴅ:</a></b> <code>{your_id}</code>\n'

    if len(message.command) > 1:
        try:
            target = message.text.split(None, 1)[1].strip()
            user_obj = await client.get_users(target)
            text += f'<b><a href="tg://user?id={user_obj.id}">ᴜsᴇʀ ɪᴅ:</a></b> <code>{user_obj.id}</code>\n'
        except Exception:
            return await message.reply_text("ᴛʜɪs ᴜsᴇʀ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ.", quote=True)

    if chat.username:
        text += f'<b><a href="https://t.me/{chat.username}">ᴄʜᴀᴛ ɪᴅ:</a></b> <code>{chat.id}</code>\n\n'
    else:
        text += f'<b>ᴄʜᴀᴛ ɪᴅ:</b> <code>{chat.id}</code>\n\n'

    if reply and not getattr(reply, "empty", True):
        text += f'<b><a href="{reply.link}">ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:</a></b> <code>{reply.id}</code>\n'
        if reply.from_user:
            text += f'<b><a href="tg://user?id={reply.from_user.id}">ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ ɪᴅ:</a></b> <code>{reply.from_user.id}</code>\n\n'

        fwd_chat = getattr(getattr(reply, "forward_origin", None), "chat", None) or getattr(reply, "forward_from_chat", None)
        if fwd_chat:
            title = _html.escape(getattr(fwd_chat, 'title', '') or '')
            text += f'ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴄʜᴀᴛ, <b>{title}</b>, ʜᴀs ᴀɴ ɪᴅ ᴏғ <code>{fwd_chat.id}</code>\n\n'

        fwd_user = getattr(getattr(reply, "forward_origin", None), "sender_user", None) or getattr(reply, "forward_from", None)
        if fwd_user:
            fname = _html.escape(getattr(fwd_user, 'first_name', '') or '')
            text += f'ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴜsᴇʀ, <b>{fname}</b>, ʜᴀs ᴀɴ ɪᴅ ᴏғ <code>{fwd_user.id}</code>\n\n'

        if reply.sender_chat:
            text += f'ɪᴅ ᴏғ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴄʜᴀᴛ/ᴄʜᴀɴɴᴇʟ ɪs <code>{reply.sender_chat.id}</code>\n\n'

        if getattr(reply, "message_thread_id", None):
            text += f'<b>ᴛᴏᴘɪᴄ / ᴛʜʀᴇᴀᴅ ɪᴅ:</b> <code>{reply.message_thread_id}</code>\n\n'

        for attr, label in MEDIA_TYPES:
            media = getattr(reply, attr, None)
            if media:
                f_id = getattr(media, 'file_id', None)
                if f_id:
                    text += f'<b>{label} ғɪʟᴇ ɪᴅ:</b> <code>{f_id}</code>\n'
                    if getattr(media, "file_unique_id", None):
                        text += f'<b>{label} ᴜɴɪǫᴜᴇ ɪᴅ:</b> <code>{media.file_unique_id}</code>\n\n'
                    break

        if reply.poll:
            text += f'<b>ᴘᴏʟʟ ɪᴅ:</b> <code>{reply.poll.id}</code>\n\n'
        if reply.contact:
            c_id = reply.contact.user_id or reply.contact.phone_number
            text += f'<b>ᴄᴏɴᴛᴀᴄᴛ ɪᴅ:</b> <code>{c_id}</code>\n\n'
        if reply.location:
            text += f'<b>ʟᴏᴄᴀᴛɪᴏɴ:</b> <code>{reply.location.latitude}, {reply.location.longitude}</code>\n\n'
        if reply.dice:
            dice_e = _html.escape(getattr(reply.dice, 'emoji', '') or '')
            text += f'<b>ᴅɪᴄᴇ:</b> <code>{dice_e} -&gt; {reply.dice.value}</code>\n\n'

    _dlog(f"Base ID text built (first 500 chars): {text[:500]}")

    # --- Premium/Custom Emoji: append numbered list to SAME message with actual CUSTOM_EMOJI entity (WZGram <tg-emoji emoji-id="">) ---
    premium = {}
    id_extraction_pass = False
    fallback_pass = False
    entity_construction_pass = False
    try:
        premium = _collect_premium_emojis(reply) if (reply and not getattr(reply, "empty", True)) else {}
        _dlog(f"ID extraction: found {len(premium)} premium emojis -> {premium}")
        id_extraction_pass = True
        if premium:
            # Check fallback resolution
            try:
                for cid, fb in premium.items():
                    _dlog(f"Fallback check: cid={cid} fallback='{fb}' len={len(fb)} utf16_len={len(fb.encode('utf-16-le'))//2}")
                fallback_pass = True
            except Exception as e:
                _dlog(f"Fallback check fail: {e}")
                fallback_pass = False

            # Ensure separator: existing text already ends with \n\n if reply block, else \n\n
            if not text.endswith("\n"):
                text += "\n"
            if not text.endswith("\n\n"):
                text += "\n"
            text += "<b>Premium Emojis:</b>\n"
            markup_generated = []
            for idx, (cid, fallback) in enumerate(premium.items(), start=1):
                fb_raw = fallback.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                line = f'{idx}. <tg-emoji emoji-id="{cid}">{fb_raw}</tg-emoji> - <code>{cid}</code>\n'
                markup_generated.append(line)
                text += line
            _dlog(f"===== OUTGOING BUILD =====")
            _dlog(f"Output text (first 1000 chars): {text[:1000]}")
            _dlog(f"Output parse_mode: {ParseMode.HTML}")
            _dlog(f"Output text length: {len(text)}")
            _dlog(f"Custom Emoji markup generated ({len(markup_generated)} lines):")
            for i, m in enumerate(markup_generated, 1):
                _dlog(f"  markup #{i}: {m.strip()}")
            _dlog(f"Custom Emoji entities found: {len(premium)}")

            # HTML parser preview (WZGram)
            try:
                from pyrogram.parser.html import HTML as _HTMLP
                import asyncio as _aio
                # Need client for parser; try using provided client
                parser = _HTMLP(client if hasattr(client,'parser') else None)
                # Use client.parser if available
                if hasattr(client, 'parser') and hasattr(client.parser, 'parse'):
                    _dlog(f"HTML parser input (first 500): {text[:500]}")
                    # We can't easily await here without making it async, but we are already async
                    parsed = await client.parser.parse(text, ParseMode.HTML)
                    _dlog(f"HTML parser output entities: {parsed.get('entities')}")
                    if parsed.get('entities'):
                        for ei, ent in enumerate(parsed['entities']):
                            _dlog(f"  Parsed entity #{ei}: {ent} type={getattr(ent,'_','')} offset={getattr(ent,'offset',None)} length={getattr(ent,'length',None)} doc_id={getattr(ent,'document_id',None)}")
                            if hasattr(ent, 'document_id'):
                                _dlog(f"    -> CUSTOM_EMOJI entity #{ei}: type=MessageEntityCustomEmoji offset={ent.offset} length={ent.length} custom_emoji_id/document_id={ent.document_id}")
                        custom_count = len([e for e in parsed['entities'] if hasattr(e,'document_id')])
                        _dlog(f"Parsed custom emoji entity count: {custom_count}")
                        entity_construction_pass = custom_count == len(premium)
                        if entity_construction_pass:
                            _dlog(f"Entity construction: PASS ({custom_count}/{len(premium)} entities constructed)")
                        else:
                            _dlog(f"Entity construction: FAIL (expected {len(premium)}, got {custom_count})")
                    else:
                        _dlog(f"HTML parser output entities: None")
                        entity_construction_pass = False
                else:
                    _dlog(f"HTML parser: client.parser not available, trying direct HTML()")
                    parsed2 = await _HTMLP(None).parse(text)
                    _dlog(f"Direct HTML parser entities: {parsed2.get('entities')}")
            except Exception as e:
                _dlog(f"HTML parser preview failed: {e}")
                import traceback
                _dlog(traceback.format_exc()[:1000])
        else:
            _dlog(f"No premium emojis found -> no Premium Emojis section")
            id_extraction_pass = True
            fallback_pass = True
            entity_construction_pass = True
    except Exception as e:
        _dlog(f"Premium collection/build exception: {e}")
        import traceback
        _dlog(traceback.format_exc()[:1000])

    # Inspect actual WZGram send path
    _dlog(f"===== BEFORE SEND =====")
    _dlog(f"Function: message.reply_text")
    _dlog(f"text (first 1000): {text[:1000]}")
    _dlog(f"parse_mode: {ParseMode.HTML} (value={ParseMode.HTML.value})")
    _dlog(f"text length: {len(text)}")
    # Try to inspect entities that will be sent (via parser)
    try:
        if hasattr(client, 'parser'):
            parsed_before = await client.parser.parse(text, ParseMode.HTML)
            ents = parsed_before.get('entities') or []
            _dlog(f"entities (parser preview): {ents}")
            _dlog(f"entity count: {len(ents)}")
            custom_before = [e for e in ents if hasattr(e,'document_id')]
            _dlog(f"custom emoji entity count: {len(custom_before)}")
            for i, ce in enumerate(custom_before, 1):
                _dlog(f"Custom Emoji entity #{i}: type=MessageEntityCustomEmoji offset={ce.offset} length={ce.length} custom_emoji_id/document_id={ce.document_id}")
            if custom_before:
                _dlog(f"Entity present before WZGram send: PASS ({len(custom_before)} entities)")
            else:
                if premium:
                    _dlog(f"Entity present before WZGram send: FAIL (premium {premium} but 0 custom entities parsed)")
                else:
                    _dlog(f"Entity present before WZGram send: PASS (no premium expected)")
        else:
            _dlog(f"BEFORE SEND: client.parser not available")
    except Exception as e:
        _dlog(f"BEFORE SEND parser inspect failed: {e}")
        import traceback
        _dlog(traceback.format_exc()[:500])

    # Check for any project wrapper that might strip entities
    try:
        _dlog(f"Inspecting message.reply_text wrapper: {getattr(message,'reply_text',None)}")
        _dlog(f"Inspecting bot.send_message: {getattr(bot,'send_message',None)}")
    except Exception as e:
        _dlog(f"wrapper inspect fail: {e}")

    # ---- Actual send ----
    sent_msg = None
    try:
        _dlog(f"Sending via message.reply_text with parse_mode=HTML...")
        sent_msg = await message.reply_text(
            text,
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )
        _dlog(f"Send succeeded, returned: {sent_msg}")
    except Exception as e:
        _dlog(f"WZGRAM/API ERROR: {e}")
        _dlog(f"Exception type: {type(e).__name__}")
        import traceback
        _dlog(traceback.format_exc()[:1000])
        raise

    # ---- After send inspection ----
    _dlog(f"===== AFTER SEND =====")
    try:
        if sent_msg:
            _dlog(f"Sent message ID: {getattr(sent_msg,'id',None)}")
            _dlog(f"Returned text (first 500): {str(getattr(sent_msg,'text',None) or getattr(sent_msg,'caption',None) or '')[:500]}")
            returned_entities = getattr(sent_msg, 'entities', None) or getattr(sent_msg, 'caption_entities', None)
            _dlog(f"Returned entities: {returned_entities}")
            if returned_entities:
                for ei, ent in enumerate(returned_entities):
                    _dlog(f"  Returned entity #{ei}: type={getattr(getattr(ent,'type',None),'name',str(getattr(ent,'type','')))} offset={getattr(ent,'offset',None)} length={getattr(ent,'length',None)} custom_emoji_id={getattr(ent,'custom_emoji_id',None)} doc_id={getattr(ent,'document_id',None) if hasattr(ent,'document_id') else 'N/A'} full={ent}")
                custom_returned = []
                for ent in returned_entities:
                    try:
                        from pyrogram.enums import MessageEntityType
                        if ent.type == MessageEntityType.CUSTOM_EMOJI:
                            custom_returned.append(ent)
                    except Exception:
                        if str(getattr(getattr(ent,'type',None),'name','')).upper() == "CUSTOM_EMOJI":
                            custom_returned.append(ent)
                _dlog(f"Returned custom emoji entities: {custom_returned} count={len(custom_returned)}")
                for i, ce in enumerate(custom_returned, 1):
                    _dlog(f"Returned Custom Emoji entity #{i}: type={getattr(getattr(ce,'type',None),'name',str(getattr(ce,'type','')))} offset={ce.offset} length={ce.length} custom_emoji_id/document_id={getattr(ce,'custom_emoji_id', getattr(ce,'document_id',None))}")
                if custom_returned:
                    _dlog(f"Entity present after send: PASS ({len(custom_returned)} entities)")
                else:
                    if premium:
                        _dlog(f"Entity present after send: FAIL (expected {len(premium)} but 0 returned)")
                        _dlog(f"RESULT: CUSTOM_EMOJI ENTITY LOST AFTER SEND")
                    else:
                        _dlog(f"Entity present after send: PASS (no premium expected)")
            else:
                _dlog(f"Returned entities: None/empty")
                if premium:
                    _dlog(f"RESULT: CUSTOM_EMOJI ENTITY LOST AFTER SEND (no entities returned)")
                else:
                    _dlog(f"RESULT: No premium expected, no entities is ok")
        else:
            _dlog(f"Sent message is None -> UNKNOWN")
    except Exception as e:
        _dlog(f"AFTER SEND inspect failed: {e}")
        import traceback
        _dlog(traceback.format_exc()[:800])

    # ---- Diagnostic summary ----
    try:
        _dlog(f"===== DIAGNOSTIC SUMMARY =====")
        _dlog(f"ID extraction: {'PASS' if id_extraction_pass else 'FAIL'} (found {len(premium) if 'premium' in locals() else 'unknown'} ids)")
        _dlog(f"Fallback emoji resolution: {'PASS' if fallback_pass else 'FAIL'}")
        _dlog(f"Entity construction: {'PASS' if entity_construction_pass else 'FAIL'}")
        # Before send check already logged, summarize again
        try:
            if 'premium' in locals() and premium:
                # Re-parse to check
                if hasattr(client, 'parser'):
                    parsed = await client.parser.parse(text, ParseMode.HTML)
                    ents = parsed.get('entities') or []
                    custom_before = [e for e in ents if hasattr(e,'document_id')]
                    _dlog(f"Entity present before WZGram send: {'PASS' if len(custom_before)==len(premium) else 'FAIL'} ({len(custom_before)}/{len(premium)})")
                else:
                    _dlog(f"Entity present before WZGram send: UNKNOWN (no parser)")
            else:
                _dlog(f"Entity present before WZGram send: PASS (no premium)")
        except Exception as e:
            _dlog(f"Entity present before WZGram send: UNKNOWN ({e})")

        # After send
        try:
            if sent_msg and (getattr(sent_msg,'entities',None) or getattr(sent_msg,'caption_entities',None)):
                re_ents = getattr(sent_msg,'entities',None) or getattr(sent_msg,'caption_entities',None)
                from pyrogram.enums import MessageEntityType as _MET2
                c_ret = [e for e in re_ents if getattr(getattr(e,'type',None),'name','').upper()=="CUSTOM_EMOJI"]
                if 'premium' in locals() and premium:
                    _dlog(f"Entity present after send: {'PASS' if len(c_ret)==len(premium) else 'FAIL'} ({len(c_ret)}/{len(premium)})")
                else:
                    _dlog(f"Entity present after send: PASS (no premium)")
            else:
                if 'premium' in locals() and premium:
                    _dlog(f"Entity present after send: FAIL (0 entities, expected {len(premium)})")
                else:
                    _dlog(f"Entity present after send: PASS (no premium)")
        except Exception as e:
            _dlog(f"Entity present after send: UNKNOWN ({e})")

        _dlog(f"WZGram serialization: UNKNOWN (needs before/after comparison)")
        # Determine suspected layer
        suspected = "UNKNOWN"
        try:
            if not id_extraction_pass:
                suspected = "1. Incoming Telegram message/entity parsing OR 2. Custom Emoji ID extraction"
            elif not fallback_pass:
                suspected = "3. Fallback/alt emoji resolution"
            elif not entity_construction_pass:
                suspected = "5. WZGram HTML/markup parsing OR 4. WZGram MessageEntity construction OR 6. Our message-building/helper function"
            else:
                # Check before/after
                if 'premium' in locals() and premium:
                    if hasattr(client, 'parser'):
                        parsed = await client.parser.parse(text, ParseMode.HTML)
                        before = len([e for e in (parsed.get('entities') or []) if hasattr(e,'document_id')])
                        after = 0
                        if sent_msg and (getattr(sent_msg,'entities',None) or getattr(sent_msg,'caption_entities',None)):
                            re_ents = getattr(sent_msg,'entities',None) or getattr(sent_msg,'caption_entities',None)
                            after = len([e for e in re_ents if str(getattr(getattr(e,'type',None),'name','')).upper()=="CUSTOM_EMOJI"])
                        if before==len(premium) and after==0:
                            suspected = "9. WZGram serialization into MTProto request OR 10. Telegram rejecting/ignoring CUSTOM_EMOJI entity"
                        elif before==0:
                            suspected = "7. ParseMode conversion OR 5. WZGram HTML/markup parsing"
                        elif before!=len(premium):
                            suspected = "4. WZGram MessageEntity construction / 6. Helper function"
                        elif after!=len(premium):
                            suspected = "9/10/11 - entity lost inside WZGram/Telegram (see BEFORE/AFTER logs)"
                        else:
                            suspected = "None - should be rendering, check client"
                    else:
                        suspected = "8. send_message() - cannot verify without parser"
                else:
                    suspected = "No premium - no failure"
            _dlog(f"Final rendering diagnosis: {'Premium should render' if suspected=='None - should be rendering, check client' else 'Fallback Unicode shown - entity lost'}")
        except Exception as e:
            _dlog(f"Suspected layer calc fail: {e}")
            suspected = "UNKNOWN"
        _dlog(f"Suspected failure layer: {suspected}")

        if premium and custom_before if 'custom_before' in locals() else False:
            pass
        # Explicit result messages per spec
        try:
            if 'premium' in locals() and premium:
                # Check if entity never constructed
                if not entity_construction_pass:
                    _dlog(f"RESULT: ENTITY WAS NEVER CONSTRUCTED BY OUR CODE")
                # Check lost inside wzgram
                if hasattr(client, 'parser'):
                    parsed = await client.parser.parse(text, ParseMode.HTML)
                    before = len([e for e in (parsed.get('entities') or []) if hasattr(e,'document_id')])
                    after = 0
                    if sent_msg and (getattr(sent_msg,'entities',None) or getattr(sent_msg,'caption_entities',None)):
                        re_ents = getattr(sent_msg,'entities',None) or getattr(sent_msg,'caption_entities',None)
                        after = len([e for e in re_ents if str(getattr(getattr(e,'type',None),'name','')).upper()=="CUSTOM_EMOJI"])
                        if before>0 and after==0:
                            _dlog(f"RESULT: ENTITY LOST INSIDE WZGRAM/SERIALIZATION PATH")
                        elif before==0 and after==0:
                            _dlog(f"RESULT: ENTITY WAS NEVER CONSTRUCTED BY OUR CODE")
        except Exception:
            pass

    except Exception as e:
        _dlog(f"DIAGNOSTIC SUMMARY fail: {e}")
        import traceback
        _dlog(traceback.format_exc()[:500])

bot.add_handler(MessageHandler(universal_id, filters=command(BotCommands.IdCommand) & (CustomFilters.authorized | CustomFilters.sudo)))
