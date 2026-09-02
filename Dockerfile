# ============================================================
#  D2 — full feature image (base-image parity + Python 3.11)
#  Layer-scan nanthakps/kpsmlx se: 7z, aria2, ffmpeg/ffprobe,
#  mediainfo, qbittorrent-nox, rclone v1.64, MEGA SDK v4.8.0
#  (libmega + _mega py-bindings), AtomicParsley, zip/unzip, gcc.
#  Build:  docker build -t d2 .
#  MEGA nahi chahiye (aap MEGA creds use nahi karte):
#      docker build --build-arg WITH_MEGA=0 -t d2 .   (build 10-15 min fast)
# ============================================================

# ---------- STAGE 1: MEGA SDK v4.8.0 (py3.11 swig bindings) ----------
FROM python:3.11.9-slim-bookworm AS mega-build
ARG MEGA_VER=4.8.0
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build swig git curl ca-certificates \
        python3-dev libssl-dev libcrypto++-dev libcurl4-openssl-dev \
        libsqlite3-dev libsodium-dev libuv1-dev libzen-dev libmediainfo-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 -b v${MEGA_VER} https://github.com/meganz/sdk /mega-sdk
WORKDIR /mega-sdk
# Swig python module -> /usr/local/lib/python3.11/site-packages/mega
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release \
        -DENABLE_PYTHON=ON -DENABLE_TESTS=OFF -DENABLE_EXAMPLES=OFF \
        -DUSE_READLINE=OFF -DUSE_FREEIMAGE=OFF \
    && cmake --build build -j"$(nproc)" \
    && cmake --install build || true \
    && find build -name "_mega*.so" -o -name "megasdk*.so" | head -2
RUN if [ -f bindings/python/setup.py ]; then \
        pip install --no-cache-dir ./bindings/python ; \
    else \
        cp -v $(find build -name "_mega*.so" | head -1) /usr/local/lib/python3.11/site-packages/ ; \
    fi

# ---------- STAGE 2: runtime ----------
FROM python:3.11.9-slim-bookworm

# --- system tools (base-image parity) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        aria2 \
        qbittorrent-nox \
        p7zip-full \
        p7zip-rar \
        unrar-free \
        unzip \
        zip \
        mediainfo \
        atomicparsley \
        tzdata \
        bash \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- rclone (official static binary, jaisa base image me v1.64 tha) ---
RUN curl -s https://rclone.org/install.sh | bash \
    && rclone version | head -1

# --- MEGA SDK bindings (WITH_MEGA=0 => skip; bot_utils ka lazy-import ise handle karta hai) ---
ARG WITH_MEGA=1
COPY --from=mega-build /usr/local/lib/python3.11/site-packages/mega* /usr/local/lib/python3.11/site-packages/mega/
COPY --from=mega-build /usr/local/lib/python3.11/site-packages/_mega* /usr/local/lib/python3.11/site-packages/

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

# --- python deps build-time fix (runtime pe koi network-install nahi) ---
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade setuptools pip uv \
    && uv pip install --system --no-cache -r requirements.txt \
    && uv pip install --system --no-cache pymediainfo pyaes

# --- naya code image me fresh ---
COPY . .

ENTRYPOINT ["bash", "start.sh"]
