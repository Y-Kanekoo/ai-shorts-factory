"""
AI Shorts Factory - 画像生成テスト
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from scripts.generate_image import ImageGenerator


class TestImageGenerator:
    """ImageGeneratorクラスのテスト"""

    @pytest.fixture
    def generator(self):
        """テスト用ジェネレーターを作成"""
        with patch("scripts.generate_image.Client"):
            return ImageGenerator()

    def test_resize_image(self, generator, tmp_path):
        """画像リサイズが正しく動作する"""
        # テスト用画像を作成
        test_image = Image.new("RGB", (1024, 1024), color="red")
        image_path = tmp_path / "test.png"
        test_image.save(image_path)

        # リサイズ
        resized = generator._resize_image(str(image_path), 1080, 1920)

        assert resized.size == (1080, 1920)

    def test_resize_image_portrait(self, generator, tmp_path):
        """縦長画像のリサイズ"""
        test_image = Image.new("RGB", (720, 1280), color="blue")
        image_path = tmp_path / "portrait.png"
        test_image.save(image_path)

        resized = generator._resize_image(str(image_path), 1080, 1920)

        assert resized.size == (1080, 1920)

    def test_resize_image_landscape(self, generator, tmp_path):
        """横長画像のリサイズ"""
        test_image = Image.new("RGB", (1920, 1080), color="green")
        image_path = tmp_path / "landscape.png"
        test_image.save(image_path)

        resized = generator._resize_image(str(image_path), 1080, 1920)

        assert resized.size == (1080, 1920)

    @pytest.mark.asyncio
    async def test_generate(self, generator, tmp_path):
        """画像生成が正しく動作する"""
        # モックを設定
        test_image = Image.new("RGB", (1024, 1024), color="purple")
        image_path = tmp_path / "generated.png"
        test_image.save(image_path)

        mock_client = MagicMock()
        mock_client.predict.return_value = (str(image_path), 12345)
        generator._client = mock_client

        image = await generator.generate(
            prompt="test prompt",
            width=1080,
            height=1920,
        )

        assert image.size == (1080, 1920)

    @pytest.mark.asyncio
    async def test_generate_from_script(self, generator, sample_script_data, tmp_path):
        """台本からの画像生成"""
        # モックを設定
        test_image = Image.new("RGB", (1024, 1024), color="yellow")
        image_path = tmp_path / "generated.png"
        test_image.save(image_path)

        mock_client = MagicMock()
        mock_client.predict.return_value = (str(image_path), 12345)
        generator._client = mock_client

        results = await generator.generate_from_script(sample_script_data)

        assert len(results) == 3
        assert all(r.get("image") is not None for r in results)

    @pytest.mark.asyncio
    async def test_generate_from_script_with_error(
        self, generator, sample_script_data, tmp_path
    ):
        """画像生成エラー時の処理"""
        mock_client = MagicMock()
        mock_client.predict.side_effect = Exception("API Error")
        generator._client = mock_client

        results = await generator.generate_from_script(sample_script_data)

        assert len(results) == 3
        assert all(r.get("error") is not None for r in results)

    @pytest.mark.asyncio
    async def test_generate_and_save(
        self, generator, sample_script_data, test_output_dir, tmp_path
    ):
        """画像生成と保存"""
        test_image = Image.new("RGB", (1024, 1024), color="cyan")
        image_path = tmp_path / "generated.png"
        test_image.save(image_path)

        mock_client = MagicMock()
        mock_client.predict.return_value = (str(image_path), 12345)
        generator._client = mock_client

        with patch("scripts.generate_image.config") as mock_config:
            mock_config.images_output_dir = test_output_dir / "images"
            mock_config.ensure_directories = lambda: None
            mock_config.IMAGE_WIDTH = 1080
            mock_config.IMAGE_HEIGHT = 1920

            result = await generator.generate_and_save(
                script_data=sample_script_data,
                output_prefix="test_image",
            )

        assert "metadata_path" in result
        assert len(result["files"]) == 3
