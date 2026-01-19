# AI Shorts Factory

YouTube Shorts / TikTok向けのAI動画自動生成パイプライン

## 概要

AIを活用してショート動画を自動生成し、YouTube Shortsへ自動投稿するシステムです。

### 主な機能

- **台本生成**: Hugging Face Inference API (Llama/Qwen) による台本自動生成
- **音声生成**: VOICEVOX によるナレーション音声合成
- **画像生成**: FLUX.1 schnell による背景画像生成
- **動画素材**: Pexels API による著作権フリー素材取得
- **動画合成**: MoviePy + FFmpeg による動画合成
- **字幕生成**: Whisper による自動字幕生成
- **YouTube投稿**: YouTube Data API v3 による自動アップロード

## 必要環境

- Python 3.11+
- Docker / Docker Compose
- VOICEVOX Engine（Windows推奨）
- FFmpeg

## クイックスタート

### 1. 環境変数の設定

```bash
cp .env.example .env
# .envファイルを編集してAPIキーを設定
```

必要なAPIキー:
- `HUGGINGFACE_API_TOKEN`: [Hugging Face](https://huggingface.co/settings/tokens)
- `PEXELS_API_KEY`: [Pexels](https://www.pexels.com/api/)
- YouTube認証: OAuth2クライアント認証情報

### 2. n8n + PostgreSQL の起動

```bash
docker-compose up -d
```

n8nダッシュボード: http://localhost:5678

### 3. VOICEVOX Engine の起動（Windows）

VOICEVOXをダウンロード・起動: https://voicevox.hiroshiba.jp/

デフォルトURL: http://localhost:50021

### 4. スクリプトの実行

```bash
# 台本生成
python -m scripts.generate_script --theme "日本の雑学" --keywords "文化" "歴史"

# 音声生成
python -m scripts.generate_voice --script output/scripts/script_xxx.json

# 画像生成
python -m scripts.generate_image --script output/scripts/script_xxx.json

# 動画素材取得
python -m scripts.fetch_media --query "japanese culture"

# 動画合成
python -m scripts.compose_video --audio-metadata output/audio/xxx_metadata.json --image-metadata output/images/xxx_metadata.json

# YouTube投稿
python -m scripts.publish_video --video output/videos/final.mp4 --script output/scripts/script_xxx.json
```

## ディレクトリ構成

```
ai-shorts-factory/
├── scripts/                # Pythonスクリプト
│   ├── generate_script.py  # 台本生成
│   ├── generate_voice.py   # 音声生成
│   ├── generate_image.py   # 画像生成
│   ├── fetch_media.py      # 動画素材取得
│   ├── compose_video.py    # 動画合成
│   ├── publish_video.py    # YouTube投稿
│   └── utils/              # ユーティリティ
├── n8n/                    # n8n設定
│   ├── Dockerfile
│   └── workflows/          # ワークフロー定義
├── templates/              # 動画テンプレート
├── output/                 # 生成物
│   ├── scripts/
│   ├── audio/
│   ├── images/
│   └── videos/
├── tests/                  # テスト
├── docker-compose.yml
├── requirements.txt        # 全依存（開発含む）
└── requirements-prod.txt   # 本番依存のみ
```

## n8n ワークフロー

| ワークフロー | 説明 |
|-------------|------|
| W1: Orchestrator | Cron → ネタ取得 → 台本生成 |
| W2: Content Generator | 台本 → 音声 → 画像 |
| W3: Video Composer | 素材 → 動画合成 → 字幕 |
| W4: Publisher | 動画 → YouTube投稿 |

## 開発

### セットアップ

```bash
# 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存インストール
pip install -r requirements.txt
```

### テスト実行

```bash
pytest tests/ -v
```

### コード品質チェック

```bash
ruff check scripts tests
mypy scripts
```

## API制限

| サービス | 制限 |
|----------|------|
| Hugging Face | 無料枠: レート制限あり |
| Pexels | 200リクエスト/時間 |
| YouTube | 10,000ユニット/日 |

## ライセンス

- FLUX.1 schnell: Apache 2.0
- Pexels素材: 著作権フリー
- VOICEVOX: 商用利用可（キャラクターごとの利用規約あり）

## 注意事項

- AI生成コンテンツの開示が必要な場合があります
- YouTubeコミュニティガイドラインを遵守してください
- 素材の利用規約を必ず確認してください
