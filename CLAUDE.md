# AI Shorts Factory

YouTube Shorts / TikTok 向けのAI動画自動生成パイプライン

## プロジェクト概要

### 目的
- AIを活用してショート動画を自動生成
- YouTube Shorts / TikTok への自動投稿
- 無料ツールで構築（初期コスト¥0）

### ターゲットコンテンツ（検討中）
- 雑学・豆知識
- 名言・モチベーション
- 日本の文化・観光
- その他（要検討）

---

## 技術構成

### アーキテクチャ
```
ネタDB（Notion / Google Sheets）
    ↓
n8n（セルフホスト・自動化）
    ├─ 台本生成: Hugging Face Llama
    ├─ 音声生成: VOICEVOX（ローカル）
    ├─ 画像生成: FLUX.1 schnell（HF Spaces）
    ├─ 動画素材: Pexels API
    ├─ 動画合成: FFmpeg
    ├─ 字幕生成: Whisper
    └─ 投稿: YouTube Data API
```

### 使用ツール・サービス

| 役割 | ツール | コスト | 備考 |
|------|--------|--------|------|
| 自動化 | n8n（セルフホスト） | ¥0 | Docker推奨 |
| 台本生成 | Hugging Face Inference API | ¥0 | Llama/Qwen |
| 音声生成 | VOICEVOX | ¥0 | 日本語特化、商用OK |
| 画像生成 | FLUX.1 schnell | ¥0 | Apache 2.0ライセンス |
| 動画素材 | Pexels API | ¥0 | 著作権フリー |
| 動画合成 | FFmpeg | ¥0 | ローカル実行 |
| 字幕生成 | Whisper | ¥0 | ローカル実行 |
| 投稿 | YouTube Data API | ¥0 | OAuth2認証 |

### 実行環境
- 開発: MacBook Pro M4 48GB
- 重い処理（VOICEVOX等）: Windows デスクトップ（RTX 4070 Ti）

---

## ワークフロー設計

### W1: Orchestrator（オーケストレーター）
```
Cron/Trigger → ネタ取得 → 台本生成(LLM) → 保存
```

### W2: Content Generator（コンテンツ生成）
```
台本取得 → 音声生成(VOICEVOX) → 画像生成(FLUX.1) → 保存
```

### W3: Video Composer（動画合成）
```
素材取得 → FFmpeg合成 → 字幕追加 → 最終動画保存
```

### W4: Publisher（投稿）
```
完成動画取得 → YouTube API投稿 → ステータス更新
```

---

## ディレクトリ構成（予定）

```
ai-shorts-factory/
├── n8n/                    # n8nワークフロー設定
│   └── workflows/
├── scripts/                # 各種スクリプト
│   ├── generate_script.py  # 台本生成
│   ├── generate_voice.py   # 音声生成
│   ├── generate_image.py   # 画像生成
│   └── compose_video.py    # 動画合成
├── templates/              # 動画テンプレート
├── output/                 # 生成物
│   ├── scripts/
│   ├── audio/
│   ├── images/
│   └── videos/
├── docker-compose.yml      # n8n + 関連サービス
├── requirements.txt        # Python依存
└── README.md
```

---

## 開発フェーズ

### Phase 1: 基盤構築
- [ ] プロジェクト初期化
- [ ] Docker環境構築（n8n）
- [ ] 各APIの認証設定

### Phase 2: パイプライン実装
- [ ] 台本生成スクリプト
- [ ] 音声生成スクリプト（VOICEVOX連携）
- [ ] 画像生成スクリプト（FLUX.1連携）
- [ ] 動画合成スクリプト（FFmpeg）

### Phase 3: 自動化
- [ ] n8nワークフロー構築
- [ ] YouTube API連携
- [ ] スケジュール実行設定

### Phase 4: 改善
- [ ] コンテンツ品質向上
- [ ] エラーハンドリング強化
- [ ] モニタリング追加

---

## 注意事項

### 著作権・利用規約
- 素材の利用規約を必ず確認
- AI生成コンテンツの開示が必要な場合あり
- YouTubeコミュニティガイドラインを遵守

### API制限
- Hugging Face: 無料枠はレート制限あり
- YouTube Data API: 1日10,000ユニット
- Pexels: 200リクエスト/時間

---

## 将来の拡張（有料化時）

| アップグレード | ツール | 効果 |
|----------------|--------|------|
| 動画生成 | Sora（ChatGPT Plus $20/月） | 高品質AI動画 |
| 音声生成 | ElevenLabs | より自然な音声 |
| 自動化 | n8n Cloud | サーバー管理不要 |
