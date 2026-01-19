"""
AI Shorts Factory - 画像生成スクリプト（Track C）

FLUX.1 schnell（Hugging Face Spaces）を使用して画像を生成
"""

import argparse
import asyncio
from pathlib import Path
from typing import Any

from gradio_client import Client
from PIL import Image

from scripts.config import config
from scripts.constants import (
    DEFAULT_MAX_RETRY_ATTEMPTS,
    DEFAULT_RETRY_MAX_WAIT,
    FLUX_MAX_HEIGHT,
    FLUX_MAX_WIDTH,
)
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger
from scripts.utils.retry import with_retry

logger = get_logger(__name__)

# リトライ設定
MAX_RETRY_ATTEMPTS = DEFAULT_MAX_RETRY_ATTEMPTS
RETRY_MIN_WAIT = 2.0
RETRY_MAX_WAIT = DEFAULT_RETRY_MAX_WAIT


class ImageGenerationError(Exception):
    """画像生成エラー"""

    pass


class ImageGenerator:
    """画像生成クラス"""

    def __init__(self, space_id: str | None = None):
        """
        Args:
            space_id: Hugging Face SpaceのID
        """
        self.space_id = space_id or config.FLUX_SPACE_ID
        self._client = None

    def _get_client(self) -> Client:
        """Gradioクライアントを取得（遅延初期化）"""
        if self._client is None:
            logger.info(f"FLUX.1 Spaceに接続中: {self.space_id}")
            try:
                self._client = Client(self.space_id)
            except Exception as e:
                raise ImageGenerationError(
                    f"FLUX.1 Spaceへの接続に失敗しました: {self.space_id} - {e}"
                ) from e
        return self._client

    def _resize_image(
        self,
        image_path: str,
        width: int,
        height: int,
    ) -> Image.Image:
        """
        画像をリサイズ（縦長ショート動画用）

        Args:
            image_path: 元画像のパス
            width: 目標の幅
            height: 目標の高さ

        Returns:
            リサイズ済み画像
        """
        with Image.open(image_path) as img:
            # アスペクト比を維持してカバーするようにリサイズ
            img_ratio = img.width / img.height
            target_ratio = width / height

            if img_ratio > target_ratio:
                # 横長の画像: 高さを合わせてから中央をクロップ
                new_height = height
                new_width = int(height * img_ratio)
            else:
                # 縦長または同比率: 幅を合わせてから中央をクロップ
                new_width = width
                new_height = int(width / img_ratio)

            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 中央からクロップ
            left = (new_width - width) // 2
            top = (new_height - height) // 2
            right = left + width
            bottom = top + height

            return img_resized.crop((left, top, right, bottom))

    @with_retry(
        max_attempts=MAX_RETRY_ATTEMPTS,
        min_wait=RETRY_MIN_WAIT,
        max_wait=RETRY_MAX_WAIT,
    )
    async def _call_flux_api(
        self,
        prompt: str,
        seed: int,
        randomize_seed: bool,
        width: int,
        height: int,
        num_inference_steps: int,
    ) -> str:
        """FLUX.1 APIを呼び出し（リトライ付き）"""
        loop = asyncio.get_event_loop()
        client = self._get_client()

        try:
            result = await loop.run_in_executor(
                None,
                lambda: client.predict(
                    prompt=prompt,
                    seed=seed,
                    randomize_seed=randomize_seed,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps,
                    api_name="/infer",
                ),
            )

            # 結果から画像パスを取得
            if isinstance(result, tuple):
                return result[0]
            return result
        except Exception as e:
            logger.warning(f"FLUX.1 API呼び出しエラー: {e}")
            # クライアントをリセットして再接続を試みる
            self._client = None
            raise

    async def generate(
        self,
        prompt: str,
        width: int | None = None,
        height: int | None = None,
        seed: int = 0,
        num_inference_steps: int = 4,
    ) -> Image.Image:
        """
        画像を生成

        Args:
            prompt: 画像生成プロンプト（英語推奨）
            width: 画像の幅（省略時は設定値）
            height: 画像の高さ（省略時は設定値）
            seed: シード値（0でランダム）
            num_inference_steps: 推論ステップ数

        Returns:
            生成された画像

        Raises:
            ImageGenerationError: 画像生成に失敗した場合
        """
        width = width or config.IMAGE_WIDTH
        height = height or config.IMAGE_HEIGHT

        logger.info(f"画像生成を開始: {prompt[:50]}...")

        try:
            # FLUX.1 schnellのAPI呼び出し（リトライ付き）
            image_path = await self._call_flux_api(
                prompt=prompt,
                seed=seed,
                randomize_seed=seed == 0,
                width=min(width, FLUX_MAX_WIDTH),
                height=min(height, FLUX_MAX_HEIGHT),
                num_inference_steps=num_inference_steps,
            )

            # 画像を読み込んでリサイズ
            image = self._resize_image(image_path, width, height)

            logger.info("画像生成が完了しました")
            return image
        except Exception as e:
            raise ImageGenerationError(f"画像生成に失敗しました: {e}") from e

    async def generate_from_script(
        self,
        script_data: dict[str, Any],
        width: int | None = None,
        height: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        台本から複数の画像を生成

        Args:
            script_data: 台本データ
            width: 画像の幅
            height: 画像の高さ

        Returns:
            画像情報のリスト
        """
        narrations = script_data.get("narration", [])
        results = []

        for i, narration in enumerate(narrations):
            prompt = narration.get("image_prompt", "")
            if not prompt:
                logger.warning(f"画像プロンプトがありません: index={i}")
                continue

            logger.info(f"画像生成中: {i + 1}/{len(narrations)}")

            try:
                image = await self.generate(prompt, width, height)
                results.append(
                    {
                        "index": i,
                        "prompt": prompt,
                        "image": image,
                        "text": narration.get("text", ""),
                    }
                )
            except Exception as e:
                logger.error(f"画像生成エラー: index={i}, error={e}")
                results.append(
                    {
                        "index": i,
                        "prompt": prompt,
                        "image": None,
                        "error": str(e),
                        "text": narration.get("text", ""),
                    }
                )

        return results

    async def generate_and_save(
        self,
        script_data: dict[str, Any],
        output_prefix: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> dict[str, Any]:
        """
        台本から画像を生成してファイルに保存

        Args:
            script_data: 台本データ
            output_prefix: 出力ファイル名のプレフィックス
            width: 画像の幅
            height: 画像の高さ

        Returns:
            生成結果（ファイルパス情報）
        """
        config.ensure_directories()

        # 画像を生成
        results = await self.generate_from_script(script_data, width, height)

        # プレフィックスを決定
        if output_prefix is None:
            timestamp = FileHandler.generate_filename("image", "")[:-1]
            output_prefix = timestamp

        # 各画像ファイルを保存
        output_files = []

        for result in results:
            if result.get("image") is None:
                output_files.append(
                    {
                        "index": result["index"],
                        "filepath": None,
                        "prompt": result["prompt"],
                        "error": result.get("error"),
                    }
                )
                continue

            filename = f"{output_prefix}_{result['index']:02d}.png"
            filepath = config.images_output_dir / filename

            # 画像を保存
            result["image"].save(filepath, "PNG")
            logger.info(f"画像を保存しました: {filepath}")

            output_files.append(
                {
                    "index": result["index"],
                    "filepath": str(filepath),
                    "prompt": result["prompt"],
                    "text": result["text"],
                }
            )

        # メタデータを保存
        metadata = {
            "script_title": script_data.get("title", ""),
            "files": output_files,
            "settings": {
                "width": width or config.IMAGE_WIDTH,
                "height": height or config.IMAGE_HEIGHT,
                "space_id": self.space_id,
            },
        }

        metadata_path = config.images_output_dir / f"{output_prefix}_metadata.json"
        FileHandler.save_json(metadata, metadata_path)

        logger.info(f"画像生成完了: {len([f for f in output_files if f.get('filepath')])}ファイル")

        return {
            "metadata_path": str(metadata_path),
            "files": output_files,
        }


async def main():
    """CLI実行用"""
    parser = argparse.ArgumentParser(description="台本から画像を生成")
    parser.add_argument("--script", "-s", help="台本JSONファイルのパス")
    parser.add_argument("--prompt", "-p", help="単一の画像プロンプト")
    parser.add_argument("--width", "-W", type=int, default=1080, help="画像の幅")
    parser.add_argument("--height", "-H", type=int, default=1920, help="画像の高さ")
    parser.add_argument("--output", "-o", help="出力ファイル名のプレフィックス")

    args = parser.parse_args()

    generator = ImageGenerator()

    if args.prompt:
        # 単一画像生成
        image = await generator.generate(
            prompt=args.prompt,
            width=args.width,
            height=args.height,
        )
        output_path = args.output or "generated_image.png"
        image.save(output_path, "PNG")
        print(f"画像を保存しました: {output_path}")
    elif args.script:
        # 台本から複数画像生成
        script_data = FileHandler.load_json(Path(args.script))
        result = await generator.generate_and_save(
            script_data=script_data,
            output_prefix=args.output,
            width=args.width,
            height=args.height,
        )
        print(f"画像ファイルを保存しました: {result['metadata_path']}")
    else:
        parser.error("--script または --prompt が必要です")


if __name__ == "__main__":
    asyncio.run(main())
