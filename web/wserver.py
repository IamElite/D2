from logging import getLogger, FileHandler, StreamHandler, INFO, basicConfig
from time import sleep
from qbittorrentapi import NotFound404Error, Client as qbClient
from aria2p import API as ariaAPI, Client as ariaClient
from flask import Flask, request

from web.nodes import make_tree

app = Flask(__name__)

aria2 = ariaAPI(ariaClient(host="http://localhost", port=6800, secret=""))

basicConfig(format="[%(asctime)s] [%(levelname)s] - %(message)s",
            datefmt="%d-%b-%y %I:%M:%S %p",
            handlers=[FileHandler('log.txt'), StreamHandler()],
            level=INFO)

LOGGER = getLogger(__name__)

from web.pages import page, code_page, home_page




def re_verfiy(paused, resumed, client, hash_id):

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
            client.torrents_file_priority(
                torrent_hash=hash_id, file_ids=paused, priority=0)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in reverification paused!")
        try:
            client.torrents_file_priority(
                torrent_hash=hash_id, file_ids=resumed, priority=1)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in reverification resumed!")
        k += 1
        if k > 5:
            return False
    LOGGER.info(f"Verified! Hash: {hash_id}")
    return True


@app.route('/app/files/<string:id_>', methods=['GET'])
def list_torrent_contents(id_):

    if "pin_code" not in request.args.keys():
        return code_page.replace("{form_url}", f"/app/files/{id_}")

    pincode = ""
    for nbr in id_:
        if nbr.isdigit():
            pincode += str(nbr)
        if len(pincode) == 4:
            break
    if request.args["pin_code"] != pincode:
        return "<h1>Incorrect pin code</h1>"

    if len(id_) > 20:
        client = qbClient(host="localhost", port="8090")
        res = client.torrents_files(torrent_hash=id_)
        cont = make_tree(res)
        client.auth_log_out()
    else:
        res = aria2.client.get_files(id_)
        cont = make_tree(res, True)
    return page.replace("{My_content}", cont[0]).replace("{form_url}", f"/app/files/{id_}?pin_code={pincode}")


@app.route('/app/files/<string:id_>', methods=['POST'])
def set_priority(id_):

    data = dict(request.form)
    resume = ""
    if len(id_) > 20:
        pause = ""

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
            client.torrents_file_priority(
                torrent_hash=id_, file_ids=pause, priority=0)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in paused")
        try:
            client.torrents_file_priority(
                torrent_hash=id_, file_ids=resume, priority=1)
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in resumed")
        sleep(1)
        if not re_verfiy(pause, resume, client, id_):
            LOGGER.error(f"Verification Failed! Hash: {id_}")
        client.auth_log_out()
    else:
        for i, value in data.items():
            if "filenode" in i and value == "on":
                node_no = i.split("_")[-1]
                resume += f'{node_no},'

        resume = resume.strip(",")

        res = aria2.client.change_option(id_, {'select-file': resume})
        if res == "OK":
            LOGGER.info(f"Verified! GID: {id_}")
        else:
            LOGGER.info(f"Verification Failed! Report! GID: {id_}")
    return list_torrent_contents(id_)


@app.route('/')
def homepage():
    return home_page


@app.errorhandler(Exception)
def page_not_found(e):
    return f"<h1>404: Torrent not found! Mostly wrong input. <br><br>Error: {e}</h2>", 404


if __name__ == "__main__":
    app.run()
