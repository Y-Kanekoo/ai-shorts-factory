"""
AI Shorts Factory - 台本生成テスト
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.generate_script import ScriptGenerator


class TestScriptGenerator:
    """ScriptGeneratorクラスのテスト"""

    @pytest.fixture
    def generator(self):
        """テスト用ジェネレーターを作成"""
        with patch("scripts.generate_script.InferenceClient"):
            return ScriptGenerator()

    def test_extract_json_from_code_block(self, generator):
        """コードブロックからJSONを抽出できる"""
        text = '''
        Here is the script:
        ```json
        {"title": "テスト", "hook": "驚き"}
        ```
        '''
        result = generator._extract_json(text)
        assert result["title"] == "テスト"
        assert result["hook"] == "驚き"

    def test_extract_json_without_code_block(self, generator):
        """コードブロックなしでもJSONを抽出できる"""
        text = '{"title": "テスト2", "narration": []}'
        result = generator._extract_json(text)
        assert result["title"] == "テスト2"

    def test_extract_json_invalid(self, generator):
        """無効なJSONでエラーを発生させる"""
        with pytest.raises(ValueError):
            generator._extract_json("This is not JSON")

    def test_build_prompt(self, generator):
        """プロンプトが正しく構築される"""
        prompt = generator._build_prompt(
            theme="日本の雑学",
            keywords=["日本", "文化"],
            target_audience="若者",
            duration=30,
        )
        assert "日本の雑学" in prompt
        assert "日本, 文化" in prompt
        assert "30" in prompt

    @pytest.mark.asyncio
    async def test_generate(self, generator):
        """台本生成が正しく動作する"""
        mock_response = '''
        ```json
        {
            "title": "テストタイトル",
            "hook": "えっ！",
            "narration": [
                {"text": "こんにちは", "duration": 3, "image_prompt": "hello"}
            ],
            "tags": ["テスト"],
            "description": "テスト説明"
        }
        ```
        '''
        generator.client.text_generation = MagicMock(return_value=mock_response)

        result = await generator.generate(
            theme="テスト",
            keywords=["テスト"],
        )

        assert result["title"] == "テストタイトル"
        assert result["hook"] == "えっ！"
        assert len(result["narration"]) == 1
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_generate_and_save(self, generator, tmp_path):
        """台本生成と保存が正しく動作する"""
        mock_response = '''
        ```json
        {"title": "保存テスト", "hook": "!", "narration": [], "tags": [], "description": ""}
        ```
        '''
        generator.client.text_generation = MagicMock(return_value=mock_response)

        with patch("scripts.generate_script.config") as mock_config:
            mock_config.scripts_output_dir = tmp_path
            mock_config.ensure_directories = MagicMock()

            output_path = await generator.generate_and_save(
                theme="テスト",
                keywords=["テスト"],
                output_filename="test_script.json",
            )

        assert output_path.exists()
        with open(output_path) as f:
            saved_data = json.load(f)
        assert saved_data["title"] == "保存テスト"
