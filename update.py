from sys import exit
from importlib import import_module
from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info, getLogger, ERROR
from os import path, remove, environ
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from subprocess import run as srun, call as scall

getLogger("pymongo").setLevel(ERROR)

var_list = [
    "BOT_TOKEN", "TELEGRAM_API", "TELEGRAM_HASH", "OWNER_ID",
    "DATABASE_URL", "BASE_URL", "UPSTREAM_REPO", "UPSTREAM_BRANCH", "UPDATE_PKGS",
]

if path.exists("log.txt"):
    with open("log.txt", "r+") as f:
        f.truncate(0)
if path.exists("rlog.txt"):
    remove("rlog.txt")

basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

load_dotenv('config.env', override=True)

config_file = {}
try:
    settings = import_module("config")
    config_file = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in vars(settings).items() if not key.startswith("__")
    }
except ModuleNotFoundError:
    pass

env_updates = {
    key: value.strip() if isinstance(value, str) else value
    for key, value in environ.items() if key in var_list
}

if env_updates:
    config_file.update(env_updates)

log_info("Config loaded from config.env, config.py and/or ENVs!")

BOT_TOKEN = config_file.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

BOT_ID = BOT_TOKEN.split(":", 1)[0]

if DATABASE_URL := config_file.get("DATABASE_URL", "").strip():
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn.beast
        old_config = db.settings.deployConfig.find_one({"_id": BOT_ID}, {"_id": 0})
        config_dict = db.settings.config.find_one({"_id": BOT_ID})
        if (old_config is not None and old_config == config_file or old_config is None) and config_dict is not None:
            config_file["UPSTREAM_REPO"] = config_dict["UPSTREAM_REPO"]
            config_file["UPSTREAM_BRANCH"] = config_dict.get("UPSTREAM_BRANCH", "arnv1")
            config_file["UPDATE_PKGS"] = config_dict.get("UPDATE_PKGS", "True")
        conn.close()
    except Exception as e:
        log_error(f"Database ERROR: {e}")

UPSTREAM_REPO = str(config_file.get("UPSTREAM_REPO", "")).strip()
UPSTREAM_BRANCH = str(config_file.get("UPSTREAM_BRANCH", "")).strip() or "arnv1"

if UPSTREAM_REPO and "github.com" in UPSTREAM_REPO and "@" in UPSTREAM_REPO:
    if "x-access-token:" not in UPSTREAM_REPO:
        UPSTREAM_REPO = UPSTREAM_REPO.replace("https://", "https://x-access-token:", 1)

if UPSTREAM_REPO:
    if path.exists(".git"):
        srun(["rm", "-rf", ".git"])

    git_cmd = (
        f"git init -q "
        f"&& git config --global user.email SyntaxRealm@gmail.com "
        f"&& git config --global user.name SyntaxRealm "
        f"&& git add . "
        f"&& git commit -sm update -q "
        f"&& git remote add origin {UPSTREAM_REPO} "
        f"&& git fetch origin -q "
        f"&& git reset --hard origin/{UPSTREAM_BRANCH} -q"
    )
    
    update = srun(git_cmd, shell=True)
    
    clean_url = "https://" + UPSTREAM_REPO.split("@")[-1] if "@" in UPSTREAM_REPO else UPSTREAM_REPO
        
    if update.returncode == 0:
        log_info("Successfully updated with Latest Updates !")
    else:
        log_error("Something went Wrong ! Recheck your details or Ask Support !")
    
    log_info(f"UPSTREAM_REPO: {clean_url} | UPSTREAM_BRANCH: {UPSTREAM_BRANCH}")

UPDATE_PKGS = str(config_file.get("UPDATE_PKGS", "True")).strip().lower()
if UPDATE_PKGS == "true":
    if path.exists("requirements.txt"):
        log_info("Updating packages... This might take a minute.")
        py = environ.get("PYTHON", "") or "python3"
        update_cmd = (
            f"UV_SYSTEM_PYTHON=1 uv pip install --system --python {py} -U -r requirements.txt "
            f"|| {py} -m pip install -U -r requirements.txt "
            f"|| pip3 install -U -r requirements.txt"
        )
        rc = scall(update_cmd, shell=True)
        if rc == 0:
            log_info("Successfully Updated all the Packages!")
        else:
            log_error(f"Package update failed (rc={rc}, uv/pip). Bot will continue with existing packages.")
    else:
        log_info("requirements.txt not found in repo. Skipping package update.")
