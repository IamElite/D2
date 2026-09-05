<div align="center">

<!-- Animated Title (Typing Effect using Readme Typing SVG) -->
<a href="https://github.com/Sourovislam637/Project-X">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=700&size=30&pause=1000&color=00BFFF&center=true&vCenter=true&width=600&lines=🌌+Project-X;Ultimate+Multi-Cloud+Bot;Download+Anything.;Upload+Everywhere.+🔥" alt="Typing SVG" />
</a>

<p>
    <a href="https://github.com/Sourovislam637/Project-X">
        <kbd>
            <img src="https://i.ibb.co/zTHm92cG/image.jpg" width="600" alt="Project-X Logo" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">
        </kbd>
    </a>
</p>

<!-- Upgraded Dynamic GitHub Stats Badges -->
<p align="center">
  <a href="https://github.com/Sourovislam637/Project-X/stargazers">
    <img alt="Stars" src="https://img.shields.io/github/stars/Sourovislam637/Project-X?style=for-the-badge&logo=apachespark&logoColor=white&color=FFD700&labelColor=2C2F33">
  </a>
  <a href="https://github.com/Sourovislam637/Project-X/fork">
    <img alt="Forks" src="https://img.shields.io/github/forks/Sourovislam637/Project-X?style=for-the-badge&logo=git&logoColor=white&color=FF6F00&labelColor=2C2F33">
  </a>
  <a href="https://github.com/Sourovislam637/Project-X/issues">
    <img alt="Issues" src="https://img.shields.io/github/issues/Sourovislam637/Project-X?style=for-the-badge&logo=github&logoColor=white&color=FF4500&labelColor=2C2F33">
  </a>
</p>

---

<!-- Upgraded Deploy Button with Animation Effect via SVG -->
### <a href="https://colab.research.google.com/drive/1ntoqoj3jDq2FtU2-joizh0DO64uoec9q"><img src="https://img.shields.io/badge/🚀_Deploy_Quickly_on-Google_Colab-F9AB00?style=for-the-badge&logo=googlecolab&logoColor=white&labelColor=2C2F33" alt="Deploy Link"></a>

</div>

---

## 📌 Key Highlights

<details>
  <summary><strong>✨ View All Features (Click to Expand)</strong></summary>

---

_Project-X is designed to make file management seamless, fast, and flexible._

- **🌐 Universal Downloader** - Supports torrents, Mega, Google Drive, direct links, and all `yt-dlp` sites.  
- **☁️ Cloud Uploader** - Upload files to Google Drive, Telegram Cloud, Rclone, or DDL servers with ease.  
- **📦 Smart File Handling** - Automatic renaming, metadata tagging, and organization.  
- **🧠 Intelligent Automation** - Auto-resume, retry, and cleanup for 24×7 reliability.  
- **⚙️ Advanced Controls** - Manage downloads, uploads, and settings directly from Telegram (`/bs`, `/mirror`, `/leech`).  
- **🎯 Multi-Deployment Ready** - Deploy on Heroku, Docker, VPS, or Google Colab.  
- **🔐 Secure & Private** - Owner-only commands, user whitelisting, and access control.  
- **💨 Lightweight Performance** - Optimized Python & Pyrogram async engine for speed.  
- **💬 Active Community Support** - Join **[@Rare_Bots_Hub](https://t.me/Rare_Bots_Hub)** for updates and help.

</details>

---

## 🚀 Deployment Guide (VPS)

<details>
  <summary><strong>⚙️ View VPS Setup Steps (Click to Expand)</strong></summary>

---

### 1. Prerequisites
- **Tutorial Video from A to Z (Latest Video)**
- Special thanks to [Wiszky](https://github.com/vishnoe115)

[![See Video](https://img.shields.io/badge/▶_Watch_Tutorial_Video-YouTube-FF0000?style=for-the-badge&logo=YouTube&logoColor=white&labelColor=2C2F33)](https://youtu.be/xzLOLyKYl54)

---

### 2. Installing Requirements

Clone this repository:

```bash
git clone [https://github.com/Sourovislam637/Project-X](https://github.com/Sourovislam637/Project-X) project-x && cd project-x
```

Setting up config file:
    
```bash
cp config_sample.env config.env
```

- Remove the first line saying:

```env
_____REMOVE_THIS_LINE_____=True
```

_Fill up the rest of the fields. Meaning of each field is discussed below._
**NOTE**: All values must be filled between quotes, even if it's `Int`, `Bool` or `List`.

---

### 3. Build and Run the Docker Image

*Make sure you mount the app folder and install Docker following the official documentation.*

#### 3.1 Using Official Docker Commands

- **Start Docker daemon** (skip if already running):
  ```bash
  sudo dockerd
  ```
- **Build the Docker image:**
  ```bash
  sudo docker build . -t d2
  ```
- **Run the image:**
  ```bash
  sudo docker run -p 80:80 -p 8080:8080 d2
  ```
- **To stop the running image:**
  ```bash
  sudo docker ps
  sudo docker stop <container_id>
  ```

---

#### 3.2 Using docker-compose (Recommended)

**Note:** If you want to use ports other than `80` and `8080`, update them in `docker-compose.yml`.

- **Install docker-compose:**
  ```bash
  sudo apt install docker-compose
  ```
- **Build and run the Docker image:**
  ```bash
  sudo docker-compose up
  ```
- **Rebuild after editing files:**
  ```bash
  sudo docker-compose up --build
  ```
- **Stop or Restart the image:**
  ```bash
  sudo docker-compose stop
  sudo docker-compose start
  ```

[![See Video](https://img.shields.io/badge/▶_Docker_Compose_Tutorial-YouTube-FF0000?style=for-the-badge&logo=YouTube&logoColor=white&labelColor=2C2F33)](https://youtu.be/c8_TU1sPK08)

#### 📝 Docker Notes
1. Set `BASE_URL_PORT` and `RCLONE_SERVE_PORT` variables to any port you want to use. Default is `80` and `8080` respectively.
2. Stop the running image before deleting the container. Delete the container before the image.
3. To delete the container: `sudo docker container prune`
4. To delete images: `sudo docker image prune -a`
5. Edit `AsyncIOThreadsCount` in qBittorrent.conf depending on your processing units.

</details>

---

## 🚀 Deployment Guide (Heroku CLI)

<details>
  <summary><strong>☁️ View Heroku Setup Steps (Click to Expand)</strong></summary>
  
---
  
**Step 1:** Git clone this Repo and change directory

> Make sure git is Installed in your system or quick run `apt-get install git pip curl -y`

```shell
git clone [https://github.com/Sourovislam637/Project-X](https://github.com/Sourovislam637/Project-X) project-x && cd project-x 
```

**Step 2:** Install Heroku in your System

> For Android : Use `termux` (Download via FDroid) for CLI usage

```shell
curl [https://cli-assets.heroku.com/install.sh](https://cli-assets.heroku.com/install.sh) | sh
```
*(Check official Heroku docs for Ubuntu `apt-get` or Windows installation)*

**Step 3:** Login into Heroku via CLI

```shell
heroku login -i
```
- Put `Heroku Email` and `Heroku API Key` (Get from [Here](https://dashboard.heroku.com/account))

**Step 4:** Create Heroku App

```shell
heroku create --region us --stack container APP_NAME
```
*(Copy the `BASE_URL` generated after App creation for `config.env`)*

**Step 5:** Set up configuration files

**To Edit Inside CLI (nano Editor):** 

```shell
nano config.env
```

- **Sample config.env** _(Copy these and Paste in Editor and Fill Up)_
  ```env
  BOT_TOKEN = "YOUR_BOT_TOKEN"
  TELEGRAM_API = "YOUR_API_ID"
  TELEGRAM_HASH = "YOUR_API_HASH"
  OWNER_ID = "YOUR_ID"
  DATABASE_URL = "MONGODB_URL"
  BASE_URL = "APP_URL"
  SET_COMMANDS = "True"
  UPSTREAM_REPO = "[https://github.com/Sourovislam637/Project-X](https://github.com/Sourovislam637/Project-X)"
  UPSTREAM_BRANCH = "main"
  ```
- Exit from Editor via `CTRL + X`, followed via `y` and `Enter`.

**Step 6:** Set Local git remote for Heroku

```shell
git add . -f
git commit -m "Heroku Setup"
heroku git:remote -a APP_NAME
```

**Step 7:** Push to Heroku

```shell
git push heroku main -f
```

**Heroku Logs:** Use this command for Live Stream Logs:

```shell
heroku logs -a APP_NAME -t
```
</details>

---

## 🛠️ Variables Descriptions

<details>
  <summary><b>⚙️ View All Variables (Click to Expand)</b></summary>

- `BOT_TOKEN`: Telegram Bot Token that you got from [BotFather](https://t.me/BotFather). `Str`
- `OWNER_ID`: Telegram User ID (not username) of the Owner of the bot. `Int`
- `TELEGRAM_API`: This is to authenticate your Telegram account for downloading Telegram files. You can get this from <https://my.telegram.org>. `Int`
- `TELEGRAM_HASH`: This is to authenticate your Telegram account for downloading Telegram files. You can get this from <https://my.telegram.org>. `Str`
- `BASE_URL`: Valid BASE URL where the bot is deployed to use torrent web files selection.
  - ***Heroku Deployment***: `https://app-name-random_code.herokuapp.com/` `Str`
  - ***VPS Deployment***: `http://myip` or `http://myip:port`. `Str`
- `DATABASE_URL`: Database URL of MongoDb to store all your files and Vars. `Str`
- `UPSTREAM_REPO`: GitHub repository URL. `https://github.com/Sourovislam637/Project-X` `Str`
- `UPSTREAM_BRANCH`: Upstream branch for update. Default is `main` or your designated branch. `Str`

</details>

---

## 🌟 Credits & Official Channels

<p align="center">
  <a href="https://t.me/Sourov_Nobita">
    <img alt="Owner Telegram" src="https://img.shields.io/badge/👑_Owner_Contact-Telegram-0088CC?style=for-the-badge&logo=telegram&logoColor=white&labelColor=2C2F33">
  </a>
  <a href="https://github.com/Sourov-Nobita">
    <img alt="Owner GitHub" src="https://img.shields.io/badge/👨‍💻_Owner_Profile-GitHub-181717?style=for-the-badge&logo=github&logoColor=white&labelColor=2C2F33">
  </a>
</p>

<p align="center">
  <a href="https://t.me/Rare_Bots_Hub">
    <img alt="Update Channel" src="https://img.shields.io/badge/🚀_Powered_By_&_Updates-Rare_Bots_Hub-28A745?style=for-the-badge&logo=telegram&logoColor=white&labelColor=2C2F33">
  </a>
  <a href="https://t.me/Rare_Leech_Mirror_Hub">
    <img alt="Leech Mirror Channel" src="https://img.shields.io/badge/🗂️_Official_Group-Rare_Leech_Mirror_Hub-FFC107?style=for-the-badge&logo=telegram&logoColor=black&labelColor=2C2F33">
  </a>
</p>

<p align="center">
  <a href="https://github.com/Sourovislam637/Project-X">
    <img alt="Source Repo" src="https://img.shields.io/badge/🌐_Main_Source_Repo-Project--X-0052CC?style=for-the-badge&logo=github&logoColor=white&labelColor=2C2F33">
  </a>
</p>
