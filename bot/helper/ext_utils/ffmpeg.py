from os import path as os_path
import logging
from re import sub as re_sub
from aioshutil import move
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from ... import LOGGER, bot_cache
from .fs_utils import clean_target

LOGGER = logging.getLogger(__name__)

########-------- Metadata -------------#########
async def edit_metadata(listener, base_dir: str, media_file: str, outfile: str, metadata: str = ''):
    file_name = os_path.basename(media_file)
    basename = os_path.splitext(file_name)[0]
    basenameX = re_sub(r'www\S+', '', basename)
    basenameX = re_sub(r'(^\s*-\s*|(\s*-\s*){2,})', '', basenameX)

    file_ext = os_path.splitext(file_name)[-1].lower()
    if file_ext not in ('.mkv', '.mp4'):
        return

    cmd = [bot_cache['pkgs'][2], '-hide_banner', '-loglevel', 'error',
           '-i', media_file, '-map', '0', '-map_metadata', '0']

    # মাল্টি মেটাডেটা পার্সিং ইঞ্জিন
    meta_dict = {}
    if metadata and ':' in metadata:
        pairs = metadata.split('|')
        for pair in pairs:
            if ':' in pair:
                k, v = pair.split(':', 1)
                meta_dict[k.strip().lower()] = v.strip()

    if meta_dict:
        # Title লজিক হ্যান্ডেলিং
        title_val = meta_dict.get('title', '')
        if title_val:
            if basename.strip().lower().startswith("www"):
                title_metadata = f"{title_val} - {basenameX}"
            elif basename.strip().lower().startswith("@"):
                title_metadata = f"{basenameX}"
            else:
                title_metadata = title_val
        else:
            title_metadata = basenameX

        cmd.extend(['-metadata', f'title={title_metadata}'])

        # ডাটা ম্যাপিং ডিকশনারি
        mapping = {
            'author': 'author',
            'artist': 'artist',
            'comment': 'comment',
            'copyright': 'copyright',
            'publisher': 'publisher',
            'encoder': 'encoder',
            'studio': 'studio',
            'audio': 'audio',
            'subtitle': 'subtitle',
            'video': 'video',
            'encoded by': 'encoded_by',
            'custom tag': 'custom_tag',
            'dubbed by': 'dubbed_by',
            'channel': 'channel',
            'website': 'website',
            'source': 'source',
            'official site': 'official_site'
        }

        for user_key, ff_key in mapping.items():
            if val := meta_dict.get(user_key):
                cmd.extend(['-metadata', f'{ff_key}={val}'])

        # স্ট্রিম ওয়াইজ টাইটেল ইনজেকশন
        fallback_stream_title = meta_dict.get('title') or meta_dict.get('channel') or meta_dict.get('author') or ""
        if fallback_stream_title:
            cmd.extend([
                '-metadata:s:v', f'title={meta_dict.get("video", fallback_stream_title)}',
                '-metadata:s:a', f'title={meta_dict.get("audio", fallback_stream_title)}',
                '-metadata:s:s', f'title={meta_dict.get("subtitle", fallback_stream_title)}'
            ])
    else:
        # ওল্ড সিঙ্গেল স্ট্রিং ফরম্যাটের ব্যাকওয়ার্ড কম্প্যাটিবিলিটি
        if metadata:
            if basename.strip().lower().startswith("www"):
                title_metadata = f"{metadata} - {basenameX}"
            elif basename.strip().lower().startswith("@"):
                title_metadata = f"{basenameX}"
            else:
                title_metadata = metadata
        else:
            title_metadata = basenameX

        cmd.extend([
            '-metadata', f'title={title_metadata}',
            '-metadata:s:v', f'title={metadata or title_metadata}',
            '-metadata:s:a', f'title={metadata or title_metadata}',
            '-metadata:s:s', f'title={metadata or title_metadata}'
        ])

    cmd.extend(['-c', 'copy', outfile])
  
    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()
    
    if code == 0:
        await clean_target(media_file)
        listener.seed = False
        await move(outfile, base_dir)
    else:
        await clean_target(outfile)
        LOGGER.error('%s. Changing metadata failed, Path %s', await listener.suproc.stderr.read().decode(), media_file)


########-------- Attachment -------------#########
async def edit_attachment(listener, base_dir: str, media_file: str, outfile: str, attachment: str = ''):
    file_name = os_path.basename(media_file)

    file_ext = os_path.splitext(file_name)[-1].lower()
    if file_ext != '.mkv':
        return

    omg = "photo"  
    attachment_ext = attachment.split(".")[-1].lower()   
    mime_type = "application/octet-stream"
    if attachment_ext in ["jpg", "jpeg"]:
        mime_type = "image/jpeg"
    elif attachment_ext == "png":
        mime_type = "image/png"
        
    cmd = [
        bot_cache['pkgs'][2], '-hide_banner', '-loglevel', 'error', '-progress', 'pipe:1',
        '-i', media_file,
        '-attach', attachment,
        '-metadata:s:t', f'mimetype={mime_type}',
        '-metadata:s:t', f'filename={omg}.{attachment_ext}',
        '-disposition:t', 'default',
        '-c', 'copy', 
        '-map', '0', 
        '-map', '0:t?', 
        outfile
    ]  
    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()
    if code == 0:
        await clean_target(media_file)
        listener.seed = False
        await move(outfile, base_dir)
    else:
        await clean_target(outfile)
        LOGGER.error('%s. Changing failed, Path %s', await listener.suproc.stderr.read().decode(), media_file)
