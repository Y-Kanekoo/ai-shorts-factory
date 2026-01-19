"""
AI Shorts Factory - 共通設定・定数管理

環境変数とアプリケーション設定を一元管理
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """アプリケーション設定"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === パス設定 ===
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    OUTPUT_DIR: Path = Field(default=Path("output"))

    @property
    def scripts_output_dir(self) -> Path:
        """台本出力ディレクトリ"""
        return self.BASE_DIR / self.OUTPUT_DIR / "scripts"

    @property
    def audio_output_dir(self) -> Path:
        """音声出力ディレクトリ"""
        return self.BASE_DIR / self.OUTPUT_DIR / "audio"

    @property
    def images_output_dir(self) -> Path:
        """画像出力ディレクトリ"""
        return self.BASE_DIR / self.OUTPUT_DIR / "images"

    @property
    def videos_output_dir(self) -> Path:
        """動画出力ディレクトリ"""
        return self.BASE_DIR / self.OUTPUT_DIR / "videos"

    @property
    def temp_dir(self) -> Path:
        """一時ファイルディレクトリ"""
        return self.BASE_DIR / self.OUTPUT_DIR / "temp"

    # === Hugging Face設定 ===
    HUGGINGFACE_API_TOKEN: str = Field(default="")
    HF_MODEL_ID: str = Field(default="Qwen/Qwen2.5-72B-Instruct")
    HF_MAX_TOKENS: int = Field(default=2048)

    # === VOICEVOX設定 ===
    VOICEVOX_BASE_URL: str = Field(default="http://localhost:50021")
    VOICEVOX_SPEAKER_ID: int = Field(default=3)  # デフォルト: ずんだもん
    VOICEVOX_TIMEOUT: int = Field(default=60)

    # === 画像生成設定 ===
    FLUX_SPACE_ID: str = Field(default="black-forest-labs/FLUX.1-schnell")
    IMAGE_WIDTH: int = Field(default=1080)
    IMAGE_HEIGHT: int = Field(default=1920)

    # === Pexels設定 ===
    PEXELS_API_KEY: str = Field(default="")
    PEXELS_BASE_URL: str = Field(default="https://api.pexels.com/v1")
    PEXELS_VIDEOS_URL: str = Field(default="https://api.pexels.com/videos")

    # === 動画設定 ===
    VIDEO_WIDTH: int = Field(default=1080)
    VIDEO_HEIGHT: int = Field(default=1920)
    VIDEO_FPS: int = Field(default=30)
    VIDEO_CODEC: str = Field(default="libx264")
    AUDIO_CODEC: str = Field(default="aac")

    # === YouTube設定 ===
    YOUTUBE_CLIENT_SECRETS_FILE: str = Field(default="client_secrets.json")
    YOUTUBE_TOKEN_FILE: str = Field(default="youtube_token.json")
    YOUTUBE_SCOPES: list[str] = Field(
        default=["https://www.googleapis.com/auth/youtube.upload"]
    )

    # === ログ設定 ===
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    LOG_FORMAT: str = Field(
        default="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    )

    def ensure_directories(self) -> None:
        """必要なディレクトリを作成"""
        directories = [
            self.scripts_output_dir,
            self.audio_output_dir,
            self.images_output_dir,
            self.videos_output_dir,
            self.temp_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# シングルトンインスタンス
config = Config()
