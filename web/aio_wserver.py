#!/usr/bin/env python3
# In-bot web server (aiohttp) — gunicorn/flask/gevent process ka replacement (CI).
# Bot process ke andar chalta hai: ~85MB RAM saving, aiohttp pehle se loaded (+0MB).
# Blocking engine calls (aria2p/qbittorrent-api sync) to_thread me — event-loop kabhi block nahi.
# Routes legacy web.wserver jaise hi: GET / , GET+POST /app/files/{id}

from asyncio import to_thread, sleep as asyncio_sleep
from logging import getLogger
from time import sleep

from aiohttp import web
from aria2p import API as ariaAPI, Client as ariaClient
from qbittorrentapi import Client as qbClient, NotFound404Error

from web.pages import page, code_page, home_page
from web.nodes import make_tree

LOGGER = getLogger(__name__)

aria2 = ariaAPI(ariaClient(host="http://localhost", port=6800, secret=""))

runner = None


# ---------- blocking helpers (to_thread targets, kabhi direct call na karein) ----------

def _qbit_files(hash_):
    client = qbClient(host="localhost", port="8090")
    try:
        return make_tree(client.torrents_files(torrent_hash=hash_))
    finally:
        client.auth_log_out()


def _aria_files(gid):
    res = aria2.client.get_files(gid)
    return make_tree(res, True)


def _qbit_set_priority(id_, data):
    pause = ""
    resume = ""
    for i, value in data.items():
        if "filenode" in i:
            node_no = i.split("_")[-1]
            if value == "on":
                resume += f"{node_no}|"
            else:
                pause += f"{node_no}|"
    pause = pause.strip("|")
    resume = resume.strip("|")

    client = qbClient(host="localhost", port="8090")
    try:
        try:
            client.torrents_file_priority(torrent_hash=id_, file_ids=pause, priority=0)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in paused")
        try:
            client.torrents_file_priority(torrent_hash=id_, file_ids=resume, priority=1)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in resumed")
        sleep(1)
        if not re_verify(pause, resume, client, id_):
            LOGGER.error(f"Verification Failed! Hash: {id_}")
    finally:
        client.auth_log_out()


def _aria_set_select(id_, resume):
    res = aria2.client.change_option(id_, {'select-file': resume})
    if res == "OK":
        LOGGER.info(f"Verified! GID: {id_}")
    else:
        LOGGER.info(f"Verification Failed! Report! GID: {id_}")


def re_verify(paused, resumed, client, hash_id):
    paused = paused.strip()
    resumed = resumed.strip()
    if paused:
        paused = paused.split("|")
    if resumed:
        resumed = resumed.split("|")

    k = 0
    while True:
        res = client.torrents_files(torrent_hash=hash_id)
        verify = True
        for i in res:
            if str(i.id) in paused and i.priority != 0:
                verify = False
                break
            if str(i.id) in resumed and i.priority == 0:
                verify = False
                break
        if verify:
            break
        LOGGER.info("Reverification Failed! Correcting stuff...")
        client.auth_log_out()
        sleep(1)
        client = qbClient(host="localhost", port="8090")
        try:
            client.torrents_file_priority(torrent_hash=hash_id, file_ids=paused, priority=0)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in reverification paused!")
        try:
            client.torrents_file_priority(torrent_hash=hash_id, file_ids=resumed, priority=1)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in reverification resumed!")
        k += 1
        if k > 5:
            return False
    LOGGER.info(f"Verified! Hash: {hash_id}")
    return True


# ---------- async handlers ----------

async def homepage(request):
    return web.Response(text=home_page, content_type='text/html')


async def list_contents(request):
    id_ = request.match_info['id_']
    if "pin_code" not in request.query:
        return web.Response(text=code_page.replace("{form_url}", f"/app/files/{id_}"),
                            content_type='text/html')

    pincode = ""
    for nbr in id_:
        if nbr.isdigit():
            pincode += nbr
        if len(pincode) == 4:
            break
    if request.query["pin_code"] != pincode:
        return web.Response(text="<h1>Incorrect pin code</h1>", content_type='text/html')

    try:
        if len(id_) > 20:
            cont = await to_thread(_qbit_files, id_)
        else:
            cont = await to_thread(_aria_files, id_)
    except NotFound404Error:
        raise web.HTTPNotFound from None
    except Exception as e:
        LOGGER.error(f"{e} Errored in list_torrent_contents!")
        raise web.HTTPInternalServerError(text=str(e)) from None
    full = page.replace("{My_content}", cont[0]).replace(
        "{form_url}", f"/app/files/{id_}?pin_code={pincode}")
    return web.Response(text=full, content_type='text/html')


async def set_priority(request):
    id_ = request.match_info['id_']
    data = dict(await request.post())
    try:
        if len(id_) > 20:
            await to_thread(_qbit_set_priority, id_, data)
        else:
            resume = ""
            for i, value in data.items():
                if "filenode" in i and value == "on":
                    resume += f'{i.split("_")[-1]},'
            resume = resume.strip(",")
            await to_thread(_aria_set_select, id_, resume)
    except NotFound404Error:
        raise web.HTTPNotFound from None
    except Exception as e:
        LOGGER.error(f"{e} Errored in set_priority!")
        raise web.HTTPInternalServerError(text=str(e)) from None
    return await list_contents(request)


# ---------- lifecycle ----------

async def start_web_server(port):
    global runner
    app = web.Application()
    app.router.add_get('/', homepage)
    app.router.add_get('/app/files/{id_}', list_contents)
    app.router.add_post('/app/files/{id_}', set_priority)
    new_runner = web.AppRunner(app, access_log=None)   # access_log off = less CPU/IO
    await new_runner.setup()
    last_exc = None
    for attempt in range(3):                           # cleanup→rebind race guard
        try:
            site = web.TCPSite(new_runner, '0.0.0.0', int(port), reuse_address=True)
            await site.start()
            runner = new_runner
            LOGGER.info(f"Web server (in-bot aiohttp) started on :{port}")
            return
        except OSError as e:
            last_exc = e
            await asyncio_sleep(0.5)
    runner = new_runner
    raise last_exc


async def stop_web_server():
    global runner
    if runner is not None:
        old_runner, runner = runner, None
        await old_runner.cleanup()
        await asyncio_sleep(0.1)                       # OS socket-release settle
        LOGGER.info("Web server (in-bot aiohttp) stopped")


async def restart_web_server(port):
    await stop_web_server()
    await start_web_server(port)
