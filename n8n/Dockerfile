# AI Shorts Factory - n8n カスタムイメージ
# Python統合用

FROM docker.n8n.io/n8nio/n8n:1.70.1

USER root

# Python環境と日本語フォントのインストール
RUN apk add --no-cache \
    python3 \
    py3-pip \
    ffmpeg \
    font-noto-cjk \
    fontconfig

# フォントキャッシュを更新
RUN fc-cache -fv

# Pythonパッケージのインストール（本番用のみ）
COPY ./requirements-prod.txt /tmp/requirements-prod.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-prod.txt --break-system-packages

# スクリプトディレクトリをコピー
COPY ./scripts /home/node/scripts
COPY ./templates /home/node/templates

# PYTHONPATH設定
ENV PYTHONPATH=/home/node

USER node

WORKDIR /home/node
