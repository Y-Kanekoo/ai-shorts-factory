"""
AI Shorts Factory - データモデル

Pydanticを使用したリクエスト/レスポンススキーマ
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# === 台本関連 ===


class NarrationItem(BaseModel):
    """ナレーション項目"""

    text: str = Field(..., description="ナレーションテキスト")
    duration: float = Field(default=3.0, description="表示時間（秒）")
    image_prompt: str = Field(default="", description="画像生成用プロンプト（英語）")


class ScriptMetadata(BaseModel):
    """台本メタデータ"""

    theme: str = Field(..., description="動画のテーマ")
    keywords: list[str] = Field(default_factory=list, description="関連キーワード")
    target_audience: str = Field(default="一般視聴者", description="ターゲット視聴者")
    target_duration: int = Field(default=30, description="目標動画長（秒）")
    model: str = Field(default="", description="使用したLLMモデル")


class ScriptData(BaseModel):
    """台本データ"""

    title: str = Field(..., description="動画タイトル")
    hook: str = Field(default="", description="冒頭の掴み")
    narration: list[NarrationItem] = Field(default_factory=list, description="ナレーションリスト")
    tags: list[str] = Field(default_factory=list, description="動画タグ")
    description: str = Field(default="", description="動画説明文")
    metadata: ScriptMetadata | None = Field(default=None, description="メタデータ")


# === 音声関連 ===


class AudioFileInfo(BaseModel):
    """音声ファイル情報"""

    index: int = Field(..., description="インデックス")
    filepath: str = Field(..., description="ファイルパス")
    text: str = Field(default="", description="元テキスト")
    duration: float = Field(default=0.0, description="音声長（秒）")
    image_prompt: str = Field(default="", description="対応する画像プロンプト")


class AudioMetadata(BaseModel):
    """音声メタデータ"""

    script_title: str = Field(default="", description="台本タイトル")
    total_duration: float = Field(default=0.0, description="合計時間（秒）")
    files: list[AudioFileInfo] = Field(default_factory=list, description="ファイル情報リスト")
    settings: dict[str, Any] = Field(default_factory=dict, description="音声設定")


# === 画像関連 ===


class ImageFileInfo(BaseModel):
    """画像ファイル情報"""

    index: int = Field(..., description="インデックス")
    filepath: str | None = Field(default=None, description="ファイルパス")
    prompt: str = Field(default="", description="画像プロンプト")
    text: str = Field(default="", description="対応するナレーションテキスト")
    error: str | None = Field(default=None, description="エラーメッセージ")


class ImageMetadata(BaseModel):
    """画像メタデータ"""

    script_title: str = Field(default="", description="台本タイトル")
    files: list[ImageFileInfo] = Field(default_factory=list, description="ファイル情報リスト")
    settings: dict[str, Any] = Field(default_factory=dict, description="画像設定")


# === 動画素材関連 ===


class MediaFileInfo(BaseModel):
    """動画素材ファイル情報"""

    index: int = Field(..., description="インデックス")
    query: str = Field(default="", description="検索キーワード")
    filepath: str | None = Field(default=None, description="ファイルパス")
    pexels_id: int | None = Field(default=None, description="Pexels動画ID")
    duration: float | None = Field(default=None, description="動画長（秒）")
    width: int | None = Field(default=None, description="幅")
    height: int | None = Field(default=None, description="高さ")
    quality: str | None = Field(default=None, description="品質")
    photographer: str | None = Field(default=None, description="撮影者")
    pexels_url: str | None = Field(default=None, description="Pexels URL")
    error: str | None = Field(default=None, description="エラーメッセージ")


class MediaMetadata(BaseModel):
    """動画素材メタデータ"""

    files: list[MediaFileInfo] = Field(default_factory=list, description="ファイル情報リスト")
    total_fetched: int = Field(default=0, description="取得成功数")


# === 最終動画関連 ===


class VideoResult(BaseModel):
    """動画生成結果"""

    filepath: str = Field(..., description="ファイルパス")
    duration: float = Field(default=0.0, description="動画長（秒）")
    file_size_mb: float = Field(default=0.0, description="ファイルサイズ（MB）")
    resolution: str = Field(default="", description="解像度")
    fps: int = Field(default=30, description="フレームレート")


# === YouTube投稿関連 ===


class YouTubeUploadRequest(BaseModel):
    """YouTube投稿リクエスト"""

    video_path: str = Field(..., description="動画ファイルパス")
    title: str = Field(..., description="動画タイトル")
    description: str = Field(default="", description="動画説明文")
    tags: list[str] = Field(default_factory=list, description="タグ")
    category_id: str = Field(default="22", description="カテゴリID")
    privacy_status: str = Field(default="private", description="公開状態")


class YouTubeUploadResponse(BaseModel):
    """YouTube投稿レスポンス"""

    video_id: str = Field(..., description="動画ID")
    video_url: str = Field(..., description="動画URL")
    status: str = Field(default="uploaded", description="ステータス")
