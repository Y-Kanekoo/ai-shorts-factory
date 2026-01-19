"""
AI Shorts Factory - 音声生成テスト
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scripts.generate_voice import VoiceGenerator
from scripts.voicevox_client import VoiceSettings, VoicevoxClient


class TestVoicevoxClient:
    """VoicevoxClientクラスのテスト"""

    @pytest.fixture
    def client(self):
        """テスト用クライアントを作成"""
        return VoicevoxClient(base_url="http://localhost:50021")

    @pytest.fixture
    def mock_httpx_client(self):
        """モックhttpxクライアントを作成"""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        return mock_client

    @pytest.mark.asyncio
    async def test_check_health_success(self, client, mock_httpx_client):
        """ヘルスチェックが成功する"""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.text = "0.14.0"
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # 永続クライアントを直接差し替え
        client._client = mock_httpx_client

        result = await client.check_health()
        assert result is True
        mock_httpx_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_failure(self, client, mock_httpx_client):
        """ヘルスチェックが失敗する"""
        mock_httpx_client.get = AsyncMock(
            side_effect=httpx.RequestError("Connection refused")
        )

        client._client = mock_httpx_client

        result = await client.check_health()
        assert result is False


class TestVoiceGenerator:
    """VoiceGeneratorクラスのテスト"""

    @pytest.fixture
    def generator(self):
        """テスト用ジェネレーターを作成"""
        return VoiceGenerator()

    @pytest.mark.asyncio
    async def test_generate_single(self, generator):
        """単一テキストの音声生成"""
        with patch.object(
            generator.client, "text_to_speech", new_callable=AsyncMock
        ) as mock_tts:
            mock_tts.return_value = (b"fake_audio_data", 2.5)

            audio_data, duration = await generator.generate_single("テスト")

            assert audio_data == b"fake_audio_data"
            assert duration == 2.5

    @pytest.mark.asyncio
    async def test_generate_from_script(self, generator, sample_script_data):
        """台本からの音声生成"""
        with patch.object(
            generator.client, "text_to_speech", new_callable=AsyncMock
        ) as mock_tts:
            mock_tts.return_value = (b"audio", 2.0)

            results = await generator.generate_from_script(sample_script_data)

            assert len(results) == 3
            assert all(r["audio_data"] == b"audio" for r in results)

    @pytest.mark.asyncio
    async def test_generate_and_save(
        self, generator, sample_script_data, test_output_dir
    ):
        """台本から音声生成と保存"""
        with patch.object(generator, "check_voicevox_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = True

            with patch.object(
                generator.client, "text_to_speech", new_callable=AsyncMock
            ) as mock_tts:
                mock_tts.return_value = (b"audio_data", 2.0)

                with patch("scripts.generate_voice.config") as mock_config:
                    mock_config.audio_output_dir = test_output_dir / "audio"
                    mock_config.ensure_directories = lambda: None
                    mock_config.VOICEVOX_SPEAKER_ID = 3

                    result = await generator.generate_and_save(
                        script_data=sample_script_data,
                        output_prefix="test_voice",
                    )

        assert "metadata_path" in result
        assert result["total_duration"] == 6.0  # 3 files * 2.0 seconds


class TestVoiceSettings:
    """VoiceSettingsクラスのテスト"""

    def test_default_settings(self):
        """デフォルト設定が正しい"""
        settings = VoiceSettings()
        assert settings.speaker_id == 3
        assert settings.speed == 1.0
        assert settings.pitch == 0.0

    def test_custom_settings(self):
        """カスタム設定が適用される"""
        settings = VoiceSettings(speaker_id=1, speed=1.2, pitch=0.1)
        assert settings.speaker_id == 1
        assert settings.speed == 1.2
        assert settings.pitch == 0.1
