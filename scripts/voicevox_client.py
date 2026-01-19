"""
AI Shorts Factory - VOICEVOX クライアント

VOICEVOX Engine APIとの通信を管理（コネクションプール再利用）
"""

import io
import wave
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx

from scripts.config import config
from scripts.utils.logger import get_logger
from scripts.utils.retry import with_retry


def get_wav_duration(audio_data: bytes) -> float:
    """
    WAVデータから実際の音声長を取得

    Args:
        audio_data: WAV形式のバイナリデータ

    Returns:
        音声の長さ（秒）
    """
    with io.BytesIO(audio_data) as audio_buffer:
        with wave.open(audio_buffer, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)

logger = get_logger(__name__)

# リトライ設定
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 1.0
RETRY_MAX_WAIT = 10.0


class VoicevoxError(Exception):
    """VOICEVOXエラー"""

    pass


@dataclass
class VoiceSettings:
    """音声設定"""

    speaker_id: int = 3  # デフォルト: ずんだもん
    speed: float = 1.0
    pitch: float = 0.0
    intonation: float = 1.0
    volume: float = 1.0


class VoicevoxClient:
    """
    VOICEVOX Engine APIクライアント

    コネクションプールを再利用して効率的にリクエストを処理。
    async with文で使用するか、手動でclose()を呼び出す。

    Usage:
        async with VoicevoxClient() as client:
            audio, duration = await client.text_to_speech("こんにちは")
    """

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        """
        Args:
            base_url: VOICEVOX EngineのベースURL
            timeout: タイムアウト秒数
        """
        self.base_url = (base_url or config.VOICEVOX_BASE_URL).rstrip("/")
        self.timeout = timeout or config.VOICEVOX_TIMEOUT
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """永続クライアントを取得（遅延初期化）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """クライアントを閉じる"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        """コンテキストマネージャーのエントリ"""
        await self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストマネージャーの終了"""
        await self.close()

    async def check_health(self) -> bool:
        """
        VOICEVOXエンジンの稼働状況を確認

        Returns:
            稼働中の場合True
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/version")
            if response.is_success:
                logger.info(f"VOICEVOX Engine バージョン: {response.text}")
                return True
        except httpx.RequestError as e:
            logger.error(f"VOICEVOX Engineに接続できません: {e}")
        return False

    async def get_speakers(self) -> list[dict[str, Any]]:
        """
        利用可能な話者一覧を取得

        Returns:
            話者情報のリスト
        """
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/speakers")
        response.raise_for_status()
        return response.json()

    @with_retry(
        max_attempts=MAX_RETRY_ATTEMPTS,
        min_wait=RETRY_MIN_WAIT,
        max_wait=RETRY_MAX_WAIT,
    )
    async def create_audio_query(
        self,
        text: str,
        speaker_id: int,
    ) -> dict[str, Any]:
        """
        音声合成用のクエリを作成

        Args:
            text: 合成するテキスト
            speaker_id: 話者ID

        Returns:
            音声合成クエリ

        Raises:
            VoicevoxError: クエリ作成に失敗した場合
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/audio_query",
                params={"text": text, "speaker": speaker_id},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise VoicevoxError(f"音声クエリの作成に失敗しました: {e}") from e

    @with_retry(
        max_attempts=MAX_RETRY_ATTEMPTS,
        min_wait=RETRY_MIN_WAIT,
        max_wait=RETRY_MAX_WAIT,
    )
    async def synthesize(
        self,
        audio_query: dict[str, Any],
        speaker_id: int,
    ) -> bytes:
        """
        音声を合成

        Args:
            audio_query: 音声合成クエリ
            speaker_id: 話者ID

        Returns:
            WAV形式の音声データ

        Raises:
            VoicevoxError: 音声合成に失敗した場合
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/synthesis",
                params={"speaker": speaker_id},
                json=audio_query,
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise VoicevoxError(f"音声合成に失敗しました: {e}") from e

    async def text_to_speech(
        self,
        text: str,
        settings: VoiceSettings | None = None,
    ) -> tuple[bytes, float]:
        """
        テキストから音声を生成

        Args:
            text: 合成するテキスト
            settings: 音声設定（省略時はデフォルト設定）

        Returns:
            (WAV形式の音声データ, 音声の長さ（秒）)
        """
        if settings is None:
            settings = VoiceSettings(speaker_id=config.VOICEVOX_SPEAKER_ID)

        logger.debug(f"音声合成を開始: speaker_id={settings.speaker_id}")

        # クエリを作成
        audio_query = await self.create_audio_query(text, settings.speaker_id)

        # 設定を適用
        audio_query["speedScale"] = settings.speed
        audio_query["pitchScale"] = settings.pitch
        audio_query["intonationScale"] = settings.intonation
        audio_query["volumeScale"] = settings.volume

        # 音声を合成
        audio_data = await self.synthesize(audio_query, settings.speaker_id)

        # 実際の音声長を取得（WAVファイルから正確に計測）
        duration = get_wav_duration(audio_data)

        logger.debug(f"音声合成完了: 長さ{duration:.2f}秒")

        return audio_data, duration

    async def get_speaker_info(self, speaker_id: int) -> dict[str, Any] | None:
        """
        話者の詳細情報を取得

        Args:
            speaker_id: 話者ID

        Returns:
            話者情報（見つからない場合はNone）
        """
        speakers = await self.get_speakers()
        for speaker in speakers:
            for style in speaker.get("styles", []):
                if style.get("id") == speaker_id:
                    return {
                        "name": speaker.get("name"),
                        "style_name": style.get("name"),
                        "speaker_id": speaker_id,
                    }
        return None
