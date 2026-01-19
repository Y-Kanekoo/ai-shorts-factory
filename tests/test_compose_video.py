"""
AI Shorts Factory - 動画合成テスト
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.compose_video import VideoComposer


class TestVideoComposer:
    """VideoComposerクラスのテスト"""

    @pytest.fixture
    def composer(self):
        """テスト用コンポーザーを作成"""
        return VideoComposer(width=1080, height=1920, fps=30)

    def test_init(self, composer):
        """初期化が正しく行われる"""
        assert composer.width == 1080
        assert composer.height == 1920
        assert composer.fps == 30

    def test_create_subtitle_clip(self, composer):
        """字幕クリップが作成される"""
        with patch("scripts.compose_video.TextClip") as mock_text_clip:
            mock_clip = MagicMock()
            mock_clip.with_duration.return_value = mock_clip
            mock_clip.with_position.return_value = mock_clip
            mock_text_clip.return_value = mock_clip

            result = composer._create_subtitle_clip("テスト字幕", 3.0)

            mock_text_clip.assert_called_once()
            assert result == mock_clip

    @pytest.mark.asyncio
    async def test_compose_from_assets(self, composer, tmp_path):
        """アセットからの動画合成"""
        # テストデータを準備
        audio_files = [
            {
                "filepath": str(tmp_path / "audio_00.wav"),
                "duration": 3.0,
                "index": 0,
                "text": "テスト1",
            },
            {
                "filepath": str(tmp_path / "audio_01.wav"),
                "duration": 2.0,
                "index": 1,
                "text": "テスト2",
            },
        ]

        image_files = [
            {"filepath": str(tmp_path / "image_00.png"), "index": 0},
            {"filepath": str(tmp_path / "image_01.png"), "index": 1},
        ]

        # ダミーファイルを作成
        (tmp_path / "audio_00.wav").write_bytes(b"audio1")
        (tmp_path / "audio_01.wav").write_bytes(b"audio2")

        # 画像を作成
        from PIL import Image

        for img_file in image_files:
            img = Image.new("RGB", (1080, 1920), color="blue")
            img.save(img_file["filepath"])

        with patch("scripts.compose_video.AudioFileClip") as mock_audio:
            mock_audio_clip = MagicMock()
            mock_audio.return_value = mock_audio_clip

            with patch("scripts.compose_video.ImageClip") as mock_image:
                mock_image_clip = MagicMock()
                mock_image_clip.with_duration.return_value = mock_image_clip
                mock_image_clip.resized.return_value = mock_image_clip
                mock_image_clip.cropped.return_value = mock_image_clip
                mock_image_clip.w = 1080
                mock_image_clip.h = 1920
                mock_image.return_value = mock_image_clip

                with patch("scripts.compose_video.CompositeVideoClip") as mock_composite:
                    mock_video = MagicMock()
                    mock_video.with_start.return_value = mock_video
                    mock_video.with_audio.return_value = mock_video
                    mock_composite.return_value = mock_video

                    with patch("scripts.compose_video.concatenate_audioclips") as mock_concat:
                        mock_concat.return_value = mock_audio_clip

                        with patch("scripts.compose_video.TextClip") as mock_text:
                            mock_text_clip = MagicMock()
                            mock_text_clip.with_duration.return_value = mock_text_clip
                            mock_text_clip.with_position.return_value = mock_text_clip
                            mock_text.return_value = mock_text_clip

                            result = await composer.compose_from_assets(
                                audio_files=audio_files,
                                image_files=image_files,
                            )

        assert result is not None

    @pytest.mark.asyncio
    async def test_compose_and_save(self, composer, test_output_dir, tmp_path):
        """動画合成と保存"""
        # メタデータを準備
        audio_metadata = {
            "files": [
                {
                    "filepath": str(tmp_path / "audio.wav"),
                    "duration": 3.0,
                    "index": 0,
                    "text": "テスト",
                }
            ],
            "total_duration": 3.0,
        }

        image_metadata = {
            "files": [{"filepath": str(tmp_path / "image.png"), "index": 0}]
        }

        # メタデータファイルを作成
        import json

        audio_meta_path = tmp_path / "audio_metadata.json"
        image_meta_path = tmp_path / "image_metadata.json"

        with open(audio_meta_path, "w") as f:
            json.dump(audio_metadata, f)
        with open(image_meta_path, "w") as f:
            json.dump(image_metadata, f)

        # ダミーファイルを作成
        (tmp_path / "audio.wav").write_bytes(b"audio")
        from PIL import Image

        img = Image.new("RGB", (1080, 1920), color="red")
        img.save(tmp_path / "image.png")

        with patch.object(
            composer, "compose_from_assets", new_callable=AsyncMock
        ) as mock_compose:
            mock_video = MagicMock()
            mock_video.write_videofile = MagicMock()
            mock_video.close = MagicMock()
            mock_compose.return_value = mock_video

            with patch("scripts.compose_video.config") as mock_config:
                mock_config.videos_output_dir = test_output_dir / "videos"
                mock_config.ensure_directories = lambda: None
                mock_config.VIDEO_CODEC = "libx264"
                mock_config.AUDIO_CODEC = "aac"

                with patch(
                    "scripts.compose_video.FileHandler.get_file_size_mb"
                ) as mock_size:
                    mock_size.return_value = 5.0

                    # 出力ファイルを事前に作成（存在チェック用）
                    output_path = test_output_dir / "videos" / "test_output.mp4"
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(b"fake_video")

                    result = await composer.compose_and_save(
                        audio_metadata_path=audio_meta_path,
                        image_metadata_path=image_meta_path,
                        output_path=output_path,
                    )

        assert "filepath" in result
        assert result["file_size_mb"] == 5.0
