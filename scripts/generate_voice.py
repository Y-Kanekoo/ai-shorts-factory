"""
AI Shorts Factory - 音声生成スクリプト（Track B）

VOICEVOXを使用してナレーション音声を生成
"""

import argparse
import asyncio
from pathlib import Path
from typing import Any

from scripts.config import config
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger
from scripts.voicevox_client import VoicevoxClient, VoiceSettings

logger = get_logger(__name__)


class VoiceGenerator:
    """
    音声生成クラス

    コネクションプールを再利用するため、async with文で使用するか、
    手動でclose()を呼び出してリソースを解放してください。
    """

    def __init__(self, voicevox_url: str | None = None):
        """
        Args:
            voicevox_url: VOICEVOX EngineのURL
        """
        self.client = VoicevoxClient(base_url=voicevox_url)

    async def close(self) -> None:
        """クライアントを閉じてリソースを解放"""
        await self.client.close()

    async def __aenter__(self) -> "VoiceGenerator":
        """コンテキストマネージャーのエントリ"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """コンテキストマネージャーの終了"""
        await self.close()

    async def check_voicevox_status(self) -> bool:
        """VOICEVOXの稼働状況を確認"""
        return await self.client.check_health()

    async def generate_single(
        self,
        text: str,
        settings: VoiceSettings | None = None,
    ) -> tuple[bytes, float]:
        """
        単一のテキストから音声を生成

        Args:
            text: ナレーションテキスト
            settings: 音声設定

        Returns:
            (音声データ, 音声の長さ)
        """
        return await self.client.text_to_speech(text, settings)

    async def generate_from_script(
        self,
        script_data: dict[str, Any],
        settings: VoiceSettings | None = None,
        output_dir: Path | None = None,
        output_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        台本から複数の音声を生成

        Args:
            script_data: 台本データ
            settings: 音声設定
            output_dir: 出力ディレクトリ（指定時は即座にファイル保存）
            output_prefix: 出力ファイル名のプレフィックス

        Returns:
            音声情報のリスト
        """
        narrations = script_data.get("narration", [])
        results = []

        for i, narration in enumerate(narrations):
            text = narration.get("text", "")
            if not text:
                continue

            logger.info(f"音声生成中: {i + 1}/{len(narrations)}")
            audio_data, duration = await self.generate_single(text, settings)

            result = {
                "index": i,
                "text": text,
                "duration": duration,
                "image_prompt": narration.get("image_prompt", ""),
            }

            # 出力ディレクトリが指定されている場合は即座に保存してメモリ解放
            if output_dir and output_prefix:
                filename = f"{output_prefix}_{i:02d}.wav"
                filepath = output_dir / filename
                await FileHandler.save_binary_async(audio_data, filepath)
                result["filepath"] = str(filepath)
            else:
                # 後方互換性のため、ディレクトリ未指定時はメモリに保持
                result["audio_data"] = audio_data

            results.append(result)

        return results

    async def generate_and_save(
        self,
        script_data: dict[str, Any],
        settings: VoiceSettings | None = None,
        output_prefix: str | None = None,
    ) -> dict[str, Any]:
        """
        台本から音声を生成してファイルに保存

        Args:
            script_data: 台本データ
            settings: 音声設定
            output_prefix: 出力ファイル名のプレフィックス

        Returns:
            生成結果（ファイルパスと音声長情報）
        """
        config.ensure_directories()

        if not await self.check_voicevox_status():
            raise ConnectionError("VOICEVOX Engineに接続できません")

        # プレフィックスを決定
        if output_prefix is None:
            timestamp = FileHandler.generate_filename("voice", "")[:-1]  # 拡張子を除去
            output_prefix = timestamp

        # 音声を生成（即座にファイル保存してメモリ解放）
        results = await self.generate_from_script(
            script_data,
            settings,
            output_dir=config.audio_output_dir,
            output_prefix=output_prefix,
        )

        # 出力ファイル情報を整理
        output_files = []
        total_duration = 0

        for result in results:
            output_files.append(
                {
                    "index": result["index"],
                    "filepath": result["filepath"],
                    "text": result["text"],
                    "duration": result["duration"],
                    "image_prompt": result["image_prompt"],
                }
            )
            total_duration += result["duration"]

        # メタデータを保存
        metadata = {
            "script_title": script_data.get("title", ""),
            "total_duration": total_duration,
            "files": output_files,
            "settings": {
                "speaker_id": settings.speaker_id if settings else config.VOICEVOX_SPEAKER_ID,
                "speed": settings.speed if settings else 1.0,
                "pitch": settings.pitch if settings else 0.0,
                "intonation": settings.intonation if settings else 1.0,
                "volume": settings.volume if settings else 1.0,
            },
        }

        metadata_path = config.audio_output_dir / f"{output_prefix}_metadata.json"
        FileHandler.save_json(metadata, metadata_path)

        logger.info(
            f"音声生成完了: {len(output_files)}ファイル, 合計{total_duration:.2f}秒"
        )

        return {
            "metadata_path": str(metadata_path),
            "total_duration": total_duration,
            "files": output_files,
        }


async def main():
    """CLI実行用"""
    parser = argparse.ArgumentParser(description="台本から音声を生成")
    parser.add_argument("--script", "-s", required=True, help="台本JSONファイルのパス")
    parser.add_argument("--speaker", type=int, default=3, help="話者ID（デフォルト: 3=ずんだもん）")
    parser.add_argument("--speed", type=float, default=1.0, help="話速（デフォルト: 1.0）")
    parser.add_argument("--pitch", type=float, default=0.0, help="ピッチ（デフォルト: 0.0）")
    parser.add_argument("--output", "-o", help="出力ファイル名のプレフィックス")
    parser.add_argument("--voicevox-url", help="VOICEVOX EngineのURL")

    args = parser.parse_args()

    # 台本を読み込み
    script_data = FileHandler.load_json(Path(args.script))

    # 設定を作成
    settings = VoiceSettings(
        speaker_id=args.speaker,
        speed=args.speed,
        pitch=args.pitch,
    )

    # 音声を生成（async withでリソースを確実に解放）
    async with VoiceGenerator(voicevox_url=args.voicevox_url) as generator:
        result = await generator.generate_and_save(
            script_data=script_data,
            settings=settings,
            output_prefix=args.output,
        )

    print(f"音声ファイルを保存しました: {result['metadata_path']}")
    print(f"合計時間: {result['total_duration']:.2f}秒")


if __name__ == "__main__":
    asyncio.run(main())
