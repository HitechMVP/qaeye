FROM python:3.10-bullseye
ENV DEBIAN_FRONTEND=noninteractive

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-venv \
        python3-pip \
        libgpiod2 \
        udev \
        python3-tk \
        libatlas-base-dev \
        libprotobuf-dev \
        protobuf-compiler \
        libgl1 \
        libglib2.0-0 \
        libjpeg-dev \
        libpng-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libqt5gui5 \
        libqt5core5a \
        libqt5widgets5 \
        libx11-6 \
        libxext6 \
        libxrender1 \
        libxft2 \
        ffmpeg \
        x11-apps \
        cron \
        git \
        \
        build-essential \
        libgpiod-dev \
        swig \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/joan2937/lg.git /tmp/lg && \
    cd /tmp/lg && \
    make install && \
    ldconfig && \
    rm -rf /tmp/lg

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir -r requirements.txt
RUN apt-get update && apt-get install -y iw wireless-tools
RUN apt-get update && \
    apt-get install -y network-manager && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y cron && \
    touch /var/log/cron.log
    
ENV DISPLAY=:0
ENV QT_X11_NO_MITSHM=1

COPY cron.txt /etc/cron.d/cleanup-cron
RUN chmod 0644 /etc/cron.d/cleanup-cron
RUN crontab /etc/cron.d/cleanup-cron

COPY . /app

CMD service cron start && python main.py

