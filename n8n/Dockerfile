# AI Shorts Factory - n8n カスタムイメージ
# Python統合用

FROM docker.n8n.io/n8nio/n8n:latest

USER root

# Python環境のインストール
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg

# Pythonパッケージのインストール
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

USER node

WORKDIR /home/node
