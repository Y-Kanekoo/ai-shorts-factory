"""
AI Shorts Factory - YouTube投稿テスト
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.publish_video import VideoPublisher


class TestVideoPublisher:
    """VideoPublisherクラスのテスト"""

    @pytest.fixture
    def publisher(self):
        """テスト用パブリッシャーを作成"""
        with patch("scripts.publish_video.YouTubeAuth"):
            return VideoPublisher()

    def test_validate_for_shorts_valid(self, publisher, tmp_path):
        """有効な動画の検証"""
        video_path = tmp_path / "valid.mp4"
        video_path.write_bytes(b"fake_video")

        result = publisher._validate_for_shorts(video_path, duration=30)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_for_shorts_too_long(self, publisher, tmp_path):
        """長すぎる動画の検証"""
        video_path = tmp_path / "long.mp4"
        video_path.write_bytes(b"fake_video")

        result = publisher._validate_for_shorts(video_path, duration=90)

        assert result["valid"] is False
        assert any("長すぎます" in e for e in result["errors"])

    def test_validate_for_shorts_too_short(self, publisher, tmp_path):
        """短すぎる動画の検証（警告のみ）"""
        video_path = tmp_path / "short.mp4"
        video_path.write_bytes(b"fake_video")

        result = publisher._validate_for_shorts(video_path, duration=10)

        assert result["valid"] is True  # エラーではなく警告
        assert len(result["warnings"]) > 0

    def test_validate_for_shorts_not_found(self, publisher, tmp_path):
        """存在しない動画の検証"""
        video_path = tmp_path / "nonexistent.mp4"

        result = publisher._validate_for_shorts(video_path)

        assert result["valid"] is False
        assert any("見つかりません" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_upload(self, publisher, tmp_path):
        """動画アップロード"""
        video_path = tmp_path / "upload.mp4"
        video_path.write_bytes(b"fake_video")

        mock_service = MagicMock()
        mock_insert = MagicMock()
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {"id": "abc123"})
        mock_insert.return_value = mock_request
        mock_service.videos.return_value.insert = mock_insert
        publisher.auth.get_service = MagicMock(return_value=mock_service)

        result = await publisher.upload(
            video_path=video_path,
            title="テスト動画",
            description="テスト説明",
            tags=["test"],
            privacy_status="private",
        )

        assert result["video_id"] == "abc123"
        assert "video_url" in result
        assert "shorts_url" in result

    @pytest.mark.asyncio
    async def test_upload_adds_shorts_tag(self, publisher, tmp_path):
        """Shortsタグが自動追加される"""
        video_path = tmp_path / "shorts.mp4"
        video_path.write_bytes(b"fake_video")

        mock_service = MagicMock()
        mock_insert = MagicMock()
        mock_request = MagicMock()
        mock_request.next_chunk.return_value = (None, {"id": "xyz789"})
        mock_insert.return_value = mock_request
        mock_service.videos.return_value.insert = mock_insert
        publisher.auth.get_service = MagicMock(return_value=mock_service)

        await publisher.upload(
            video_path=video_path,
            title="テスト",
            description="説明",
            is_shorts=True,
        )

        # insertが呼ばれた際のbodyを確認
        call_args = mock_insert.call_args
        body = call_args[1]["body"]
        assert "Shorts" in body["snippet"]["tags"]

    @pytest.mark.asyncio
    async def test_upload_from_metadata(self, publisher, tmp_path):
        """メタデータからのアップロード"""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake_video")

        script_path = tmp_path / "script.json"
        import json

        with open(script_path, "w") as f:
            json.dump(
                {
                    "title": "メタデータタイトル",
                    "description": "メタデータ説明",
                    "tags": ["tag1", "tag2"],
                },
                f,
            )

        with patch.object(publisher, "upload", new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = {"video_id": "meta123", "video_url": "url"}

            result = await publisher.upload_from_metadata(
                video_path=video_path,
                script_metadata_path=script_path,
            )

        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args[1]["title"] == "メタデータタイトル"

    @pytest.mark.asyncio
    async def test_update_video(self, publisher):
        """動画情報の更新"""
        mock_service = MagicMock()

        # 現在の動画情報を返すモック
        mock_list = MagicMock()
        mock_list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "update123",
                    "snippet": {
                        "title": "古いタイトル",
                        "description": "古い説明",
                        "categoryId": "22",
                        "tags": [],
                    },
                }
            ]
        }
        mock_service.videos.return_value.list = mock_list

        # 更新のモック
        mock_update = MagicMock()
        mock_update.return_value.execute.return_value = {
            "id": "update123",
            "snippet": {"title": "新しいタイトル"},
        }
        mock_service.videos.return_value.update = mock_update

        publisher.auth.get_service = MagicMock(return_value=mock_service)

        result = await publisher.update_video(
            video_id="update123",
            title="新しいタイトル",
        )

        assert result["video_id"] == "update123"
        assert result["updated"] is True

    def test_validate_aspect_ratio_portrait(self, publisher, tmp_path):
        """縦長動画のアスペクト比検証"""
        video_path = tmp_path / "portrait.mp4"
        video_path.write_bytes(b"fake_video")

        # 1080x1920の縦長動画をシミュレート
        with patch.object(publisher, "_get_video_metadata") as mock_meta:
            mock_meta.return_value = {
                "duration": 30,
                "width": 1080,
                "height": 1920,
                "aspect_ratio": 1920 / 1080,  # ≈1.78
                "fps": 30,
            }

            result = publisher._validate_for_shorts(video_path)

        assert result["valid"] is True
        # 縦長なので警告なし
        assert not any("縦長動画ではありません" in w for w in result.get("warnings", []))

    def test_validate_aspect_ratio_landscape(self, publisher, tmp_path):
        """横長動画のアスペクト比検証（警告）"""
        video_path = tmp_path / "landscape.mp4"
        video_path.write_bytes(b"fake_video")

        # 1920x1080の横長動画をシミュレート
        with patch.object(publisher, "_get_video_metadata") as mock_meta:
            mock_meta.return_value = {
                "duration": 30,
                "width": 1920,
                "height": 1080,
                "aspect_ratio": 1080 / 1920,  # ≈0.56
                "fps": 30,
            }

            result = publisher._validate_for_shorts(video_path)

        # エラーではなく警告
        assert result["valid"] is True
        assert any("縦長動画ではありません" in w for w in result.get("warnings", []))

    def test_validate_aspect_ratio_square(self, publisher, tmp_path):
        """正方形動画のアスペクト比検証（警告）"""
        video_path = tmp_path / "square.mp4"
        video_path.write_bytes(b"fake_video")

        # 1080x1080の正方形動画をシミュレート
        with patch.object(publisher, "_get_video_metadata") as mock_meta:
            mock_meta.return_value = {
                "duration": 30,
                "width": 1080,
                "height": 1080,
                "aspect_ratio": 1.0,
                "fps": 30,
            }

            result = publisher._validate_for_shorts(video_path)

        # エラーではなく警告
        assert result["valid"] is True
        assert any("縦長動画ではありません" in w for w in result.get("warnings", []))
