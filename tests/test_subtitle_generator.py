"""
AI Shorts Factory - 字幕生成テスト
"""

import pytest

from scripts.subtitle_generator import SubtitleGenerator


class TestSubtitleGenerator:
    """SubtitleGeneratorのテスト"""

    def test_init_default(self):
        """デフォルト初期化のテスト"""
        generator = SubtitleGenerator()
        assert generator.model_size == "base"
        assert generator._model is None

    def test_init_custom_model_size(self):
        """カスタムモデルサイズでの初期化テスト"""
        generator = SubtitleGenerator(model_size="tiny")
        assert generator.model_size == "tiny"

    def test_create_subtitle_data(self):
        """字幕データ作成のテスト"""
        generator = SubtitleGenerator()

        whisper_result = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "text": "  こんにちは  ",
                    "words": [{"word": "こんにちは", "start": 0.0, "end": 1.0}],
                },
                {
                    "start": 2.5,
                    "end": 5.0,
                    "text": "元気ですか",
                    "words": [],
                },
            ]
        }

        subtitles = generator.create_subtitle_data(whisper_result)

        assert len(subtitles) == 2
        assert subtitles[0]["start"] == 0.0
        assert subtitles[0]["end"] == 2.5
        assert subtitles[0]["text"] == "こんにちは"  # 空白がトリムされる
        assert subtitles[1]["text"] == "元気ですか"

    def test_create_subtitle_data_empty(self):
        """空のWhisper結果のテスト"""
        generator = SubtitleGenerator()

        subtitles = generator.create_subtitle_data({})
        assert subtitles == []

        subtitles = generator.create_subtitle_data({"segments": []})
        assert subtitles == []

    def test_create_from_narration(self, sample_script_data):
        """ナレーションから字幕作成のテスト"""
        generator = SubtitleGenerator()

        narration_data = sample_script_data["narration"]
        subtitles = generator.create_from_narration(narration_data)

        assert len(subtitles) == 3

        # 最初の字幕
        assert subtitles[0]["start"] == 0.0
        assert subtitles[0]["end"] == 2.5
        assert subtitles[0]["text"] == "みなさん、これ知ってました？"

        # 2番目の字幕（最初の後から開始）
        assert subtitles[1]["start"] == 2.5
        assert subtitles[1]["end"] == 5.5
        assert subtitles[1]["text"] == "実は猫は1日に16時間も寝るんです"

        # 3番目の字幕
        assert subtitles[2]["start"] == 5.5
        assert subtitles[2]["end"] == 7.5

    def test_create_from_narration_empty(self):
        """空のナレーションデータのテスト"""
        generator = SubtitleGenerator()

        subtitles = generator.create_from_narration([])
        assert subtitles == []

    def test_create_from_narration_no_text(self):
        """テキストなしのナレーションのテスト"""
        generator = SubtitleGenerator()

        narration_data = [
            {"text": "", "duration": 2.0},
            {"text": "テスト", "duration": 3.0},
            {"duration": 1.0},  # textキーなし
        ]

        subtitles = generator.create_from_narration(narration_data)

        # テキストがあるのは1つだけ
        assert len(subtitles) == 1
        assert subtitles[0]["text"] == "テスト"
        # 空のテキスト2秒の後から開始
        assert subtitles[0]["start"] == 2.0

    def test_to_srt(self):
        """SRT形式変換のテスト"""
        generator = SubtitleGenerator()

        subtitles = [
            {"start": 0.0, "end": 2.5, "text": "こんにちは"},
            {"start": 2.5, "end": 5.0, "text": "元気ですか"},
        ]

        srt = generator.to_srt(subtitles)

        lines = srt.strip().split("\n")

        # 最初の字幕
        assert lines[0] == "1"
        assert lines[1] == "00:00:00,000 --> 00:00:02,500"
        assert lines[2] == "こんにちは"
        assert lines[3] == ""

        # 2番目の字幕
        assert lines[4] == "2"
        assert lines[5] == "00:00:02,500 --> 00:00:05,000"
        assert lines[6] == "元気ですか"

    def test_to_srt_empty(self):
        """空の字幕リストのSRT変換テスト"""
        generator = SubtitleGenerator()

        srt = generator.to_srt([])
        assert srt == ""

    def test_format_srt_time(self):
        """SRT時間フォーマットのテスト"""
        generator = SubtitleGenerator()

        # 0秒
        assert generator._format_srt_time(0.0) == "00:00:00,000"

        # 1.5秒
        assert generator._format_srt_time(1.5) == "00:00:01,500"

        # 61秒（1分1秒）
        assert generator._format_srt_time(61.0) == "00:01:01,000"

        # 3661.123秒（1時間1分1.123秒）
        assert generator._format_srt_time(3661.123) == "01:01:01,123"

        # 小数点以下の丸め
        assert generator._format_srt_time(1.9999) == "00:00:01,999"

    def test_format_srt_time_edge_cases(self):
        """SRT時間フォーマットの境界値テスト"""
        generator = SubtitleGenerator()

        # 59.999秒
        assert generator._format_srt_time(59.999) == "00:00:59,999"

        # 60秒（1分）
        assert generator._format_srt_time(60.0) == "00:01:00,000"

        # 3599.999秒（59分59.999秒）- 浮動小数点誤差を考慮
        result = generator._format_srt_time(3599.999)
        assert result in ["00:59:59,999", "00:59:59,998"]  # 浮動小数点誤差を許容

        # 3600秒（1時間）
        assert generator._format_srt_time(3600.0) == "01:00:00,000"


class TestSubtitleGeneratorIntegration:
    """SubtitleGeneratorの統合テスト（Whisperを使用）"""

    @pytest.mark.skip(reason="Whisperモデルのダウンロードが必要")
    @pytest.mark.asyncio
    async def test_transcribe(self, tmp_path):
        """音声転写のテスト（要Whisperモデル）"""
        # このテストは実際のWhisperモデルが必要なためスキップ
        pass

    @pytest.mark.skip(reason="Whisperモデルのダウンロードが必要")
    @pytest.mark.asyncio
    async def test_generate_and_save(self, tmp_path):
        """字幕生成・保存のテスト（要Whisperモデル）"""
        # このテストは実際のWhisperモデルが必要なためスキップ
        pass
