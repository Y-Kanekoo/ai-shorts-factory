"""
AI Shorts Factory - 字幕生成モジュール

Whisperを使用した音声からの字幕生成
"""

import asyncio
from pathlib import Path
from typing import Any

from scripts.config import config
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger

logger = get_logger(__name__)


class SubtitleGenerator:
    """字幕生成クラス"""

    def __init__(self, model_size: str = "base"):
        """
        Args:
            model_size: Whisperモデルサイズ（tiny/base/small/medium/large）
        """
        self.model_size = model_size
        self._model = None

    def _get_model(self):
        """Whisperモデルを取得（遅延初期化）"""
        if self._model is None:
            import whisper

            logger.info(f"Whisperモデルを読み込み中: {self.model_size}")
            self._model = whisper.load_model(self.model_size)
        return self._model

    async def transcribe(
        self,
        audio_path: Path,
        language: str = "ja",
    ) -> dict[str, Any]:
        """
        音声ファイルから字幕を生成

        Args:
            audio_path: 音声ファイルのパス
            language: 言語コード

        Returns:
            Whisperの転写結果
        """
        logger.info(f"音声から字幕を生成中: {audio_path}")

        # Whisperはブロッキングなので別スレッドで実行
        loop = asyncio.get_running_loop()
        model = self._get_model()

        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(
                str(audio_path),
                language=language,
                word_timestamps=True,
            ),
        )

        logger.info(f"字幕生成完了: {len(result.get('segments', []))}セグメント")
        return result

    def create_subtitle_data(
        self,
        whisper_result: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Whisper結果から字幕データを作成

        Args:
            whisper_result: Whisperの転写結果

        Returns:
            字幕データのリスト
        """
        subtitles = []

        for segment in whisper_result.get("segments", []):
            subtitles.append(
                {
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"].strip(),
                    "words": segment.get("words", []),
                }
            )

        return subtitles

    def create_from_narration(
        self,
        narration_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        ナレーションデータから字幕を作成（Whisperを使わない場合）

        Args:
            narration_data: ナレーションデータ（text, duration含む）

        Returns:
            字幕データのリスト
        """
        subtitles = []
        current_time = 0.0

        for item in narration_data:
            text = item.get("text", "")
            duration = item.get("duration", 3.0)

            if text:
                subtitles.append(
                    {
                        "start": current_time,
                        "end": current_time + duration,
                        "text": text,
                    }
                )

            current_time += duration

        return subtitles

    def to_srt(self, subtitles: list[dict[str, Any]]) -> str:
        """
        字幕データをSRT形式に変換

        Args:
            subtitles: 字幕データのリスト

        Returns:
            SRT形式の文字列
        """
        srt_content = []

        for i, sub in enumerate(subtitles, 1):
            start = self._format_srt_time(sub["start"])
            end = self._format_srt_time(sub["end"])
            text = sub["text"]

            srt_content.append(f"{i}")
            srt_content.append(f"{start} --> {end}")
            srt_content.append(text)
            srt_content.append("")

        return "\n".join(srt_content)

    def _format_srt_time(self, seconds: float) -> str:
        """秒数をSRT時間形式に変換"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    async def generate_and_save(
        self,
        audio_path: Path,
        output_path: Path | None = None,
        language: str = "ja",
    ) -> dict[str, Any]:
        """
        音声から字幕を生成してファイルに保存

        Args:
            audio_path: 音声ファイルのパス
            output_path: 出力ファイルパス（省略時は自動生成）
            language: 言語コード

        Returns:
            生成結果
        """
        config.ensure_directories()

        # 転写
        result = await self.transcribe(audio_path, language)
        subtitles = self.create_subtitle_data(result)

        # 出力パスを決定
        if output_path is None:
            filename = FileHandler.generate_filename("subtitle", "srt")
            output_path = config.temp_dir / filename

        # SRT形式で保存
        srt_content = self.to_srt(subtitles)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(srt_content, encoding="utf-8")

        # JSONでも保存（詳細情報用）
        json_path = output_path.with_suffix(".json")
        FileHandler.save_json(
            {
                "audio_path": str(audio_path),
                "subtitles": subtitles,
                "language": language,
                "model_size": self.model_size,
            },
            json_path,
        )

        logger.info(f"字幕を保存しました: {output_path}")

        return {
            "srt_path": str(output_path),
            "json_path": str(json_path),
            "subtitles": subtitles,
        }
