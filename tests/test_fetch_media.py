"""
AI Shorts Factory - 動画素材取得テスト
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scripts.fetch_media import MediaFetcher


class TestMediaFetcher:
    """MediaFetcherクラスのテスト"""

    @pytest.fixture
    def fetcher(self):
        """テスト用フェッチャーを作成"""
        return MediaFetcher(api_key="test_api_key")

    @pytest.fixture
    def mock_httpx_client(self):
        """モックhttpxクライアントを作成"""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        return mock_client

    def test_get_headers(self, fetcher):
        """ヘッダーが正しく生成される"""
        headers = fetcher._get_headers()
        assert headers["Authorization"] == "test_api_key"

    @pytest.mark.asyncio
    async def test_search_videos(self, fetcher, mock_httpx_client):
        """動画検索が正しく動作する"""
        mock_response_data = {
            "videos": [
                {
                    "id": 123,
                    "duration": 30,
                    "video_files": [
                        {"id": 1, "quality": "hd", "width": 1080, "height": 1920}
                    ],
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)

        # 永続クライアントを直接差し替え
        fetcher._client = mock_httpx_client

        result = await fetcher.search_videos("nature")

        assert len(result) == 1
        assert result[0]["id"] == 123
        mock_httpx_client.get.assert_called_once()

    def test_select_best_video_file_portrait(self, fetcher):
        """縦長動画が優先される"""
        video_files = [
            {"id": 1, "quality": "hd", "width": 1920, "height": 1080},
            {"id": 2, "quality": "hd", "width": 1080, "height": 1920},
            {"id": 3, "quality": "sd", "width": 720, "height": 1280},
        ]

        result = fetcher._select_best_video_file(video_files)

        assert result["id"] == 2
        assert result["height"] > result["width"]

    def test_select_best_video_file_hd_priority(self, fetcher):
        """HD品質が優先される"""
        video_files = [
            {"id": 1, "quality": "sd", "width": 720, "height": 1280},
            {"id": 2, "quality": "hd", "width": 1920, "height": 1080},
        ]

        result = fetcher._select_best_video_file(video_files)

        assert result["quality"] == "hd"

    def test_select_best_video_file_empty(self, fetcher):
        """空リストの場合Noneを返す"""
        result = fetcher._select_best_video_file([])
        assert result is None

    @pytest.mark.asyncio
    async def test_download_video(self, fetcher, tmp_path):
        """動画ダウンロードが正しく動作する"""
        output_path = tmp_path / "test_video.mp4"

        # ストリーミングレスポンスのモック
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        async def mock_aiter_bytes(chunk_size=8192):
            yield b"fake_video_data"

        mock_response.aiter_bytes = mock_aiter_bytes

        # ストリームコンテキストマネージャーのモック
        mock_stream_context = AsyncMock()
        mock_stream_context.__aenter__.return_value = mock_response
        mock_stream_context.__aexit__.return_value = None

        # AsyncClientのモック
        mock_async_client = AsyncMock()
        mock_async_client.stream.return_value = mock_stream_context

        # AsyncClientコンテキストマネージャーのモック
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__.return_value = mock_async_client
        mock_client_context.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client_context):
            with patch("httpx.Timeout"):
                result = await fetcher.download_video(
                    "https://example.com/video.mp4",
                    output_path,
                )

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == b"fake_video_data"

    @pytest.mark.asyncio
    async def test_fetch_video(self, fetcher, tmp_path):
        """動画取得フローが正しく動作する"""
        mock_videos = [
            {
                "id": 456,
                "duration": 25,
                "url": "https://pexels.com/video/456",
                "user": {"name": "Photographer"},
                "video_files": [
                    {
                        "id": 1,
                        "quality": "hd",
                        "width": 1080,
                        "height": 1920,
                        "link": "https://example.com/video.mp4",
                    }
                ],
            }
        ]

        with patch.object(fetcher, "search_videos", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_videos

            with patch.object(
                fetcher, "download_video", new_callable=AsyncMock
            ) as mock_download:
                output_path = tmp_path / "output.mp4"
                mock_download.return_value = output_path

                result = await fetcher.fetch_video("nature", output_path)

        assert result["pexels_id"] == 456
        assert result["filepath"] == str(output_path)

    @pytest.mark.asyncio
    async def test_fetch_video_not_found(self, fetcher):
        """動画が見つからない場合エラー"""
        with patch.object(fetcher, "search_videos", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            with pytest.raises(ValueError, match="動画が見つかりませんでした"):
                await fetcher.fetch_video("nonexistent")

    @pytest.mark.asyncio
    async def test_fetch_from_script(self, fetcher, sample_script_data, test_output_dir):
        """台本から動画素材を取得"""
        with patch.object(fetcher, "fetch_multiple_videos", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"metadata_path": "test.json", "files": []}

            result = await fetcher.fetch_from_script(sample_script_data)

        assert "metadata_path" in result
