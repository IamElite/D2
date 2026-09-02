FROM python:3.11.9-slim-bookworm

# System tools — D2 ko chahiye: aria2 (DL engine), qBittorrent-nox (BT),
# ffmpeg/mediainfo (remux/media), 7z + rar (archives), tzdata (timezone sync)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        qbittorrent-nox \
        p7zip-full \
        unrar-free \
        mediainfo \
        tzdata \
        bash \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

# Build-time hi dependencies fix — runtime pe koi network-install nahi (fast + reliable boot)
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade setuptools pip uv \
    && uv pip install --system --no-cache -r requirements.txt \
    && uv pip install --system --no-cache pymediainfo pyaes

# Code image me fresh — runtime git-pull ki zaroorat nahi (update.py ka self-refresh belt-and-suspenders hi rahega)
COPY . .

ENTRYPOINT ["bash", "start.sh"]
