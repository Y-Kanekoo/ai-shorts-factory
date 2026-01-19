"""
AI Shorts Factory - 台本生成スクリプト（Track A）

Hugging Face Inference APIを使用してショート動画の台本を生成
"""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any

from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

from scripts.config import config
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger
from scripts.utils.retry import with_retry

logger = get_logger(__name__)

# リトライ設定
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 2.0
RETRY_MAX_WAIT = 30.0


class ScriptGenerationError(Exception):
    """台本生成エラー"""

    pass


class ScriptGenerator:
    """台本生成クラス"""

    def __init__(self):
        """初期化"""
        self._validate_config()
        self.client = InferenceClient(token=config.HUGGINGFACE_API_TOKEN)
        self.model_id = config.HF_MODEL_ID
        self.prompt_template = self._load_prompt_template()

    def _validate_config(self) -> None:
        """設定を検証"""
        if not config.HUGGINGFACE_API_TOKEN:
            raise ScriptGenerationError(
                "HUGGINGFACE_API_TOKENが設定されていません。.envファイルを確認してください。"
            )

    def _load_prompt_template(self) -> str:
        """プロンプトテンプレートを読み込み"""
        template_path = config.BASE_DIR / "scripts" / "prompts" / "script_template.txt"
        if template_path.exists():
            with open(template_path, encoding="utf-8") as f:
                return f.read()
        # デフォルトテンプレート
        return """
あなたはYouTube Shorts向けの台本を作成するエキスパートです。

テーマ: {theme}
キーワード: {keywords}
動画の長さ: 約{duration}秒

以下のJSON形式で台本を作成してください：
{{
  "title": "動画タイトル",
  "hook": "最初の掴み",
  "narration": [
    {{"text": "ナレーション", "duration": 秒数, "image_prompt": "英語の画像プロンプト"}}
  ],
  "tags": ["タグ1", "タグ2"],
  "description": "説明文"
}}
"""

    def _build_prompt(
        self,
        theme: str,
        keywords: list[str],
        target_audience: str = "一般視聴者",
        duration: int = 30,
    ) -> str:
        """プロンプトを構築"""
        return self.prompt_template.format(
            theme=theme,
            keywords=", ".join(keywords),
            target_audience=target_audience,
            duration=duration,
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """テキストからJSONを抽出"""
        # コードブロック内のJSONを探す
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # コードブロックがない場合は全体をJSONとして解析
            json_str = text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            logger.debug(f"解析対象テキスト: {json_str[:500]}")
            raise ValueError(f"台本のJSON解析に失敗しました: {e}") from e

    async def generate(
        self,
        theme: str,
        keywords: list[str],
        target_audience: str = "一般視聴者",
        duration: int = 30,
    ) -> dict[str, Any]:
        """
        台本を生成

        Args:
            theme: 動画のテーマ
            keywords: 関連キーワード
            target_audience: ターゲット視聴者
            duration: 動画の長さ（秒）

        Returns:
            生成された台本データ

        Raises:
            ScriptGenerationError: 生成に失敗した場合
        """
        logger.info(f"台本生成を開始: テーマ={theme}", extra={"keywords": keywords})

        prompt = self._build_prompt(theme, keywords, target_audience, duration)

        # リトライ付きでAPI呼び出し
        response = await self._call_api_with_retry(prompt)

        logger.debug(f"LLM応答: {response[:500]}...")

        # JSONを抽出（失敗時はリトライ）
        script_data = await self._extract_json_with_retry(response, prompt)

        # メタデータを追加
        script_data["metadata"] = {
            "theme": theme,
            "keywords": keywords,
            "target_audience": target_audience,
            "target_duration": duration,
            "model": self.model_id,
        }

        logger.info("台本生成が完了しました", extra={"title": script_data.get("title")})
        return script_data

    @with_retry(max_attempts=MAX_RETRY_ATTEMPTS, min_wait=RETRY_MIN_WAIT, max_wait=RETRY_MAX_WAIT)
    async def _call_api_with_retry(self, prompt: str) -> str:
        """リトライ付きでAPIを呼び出し"""
        try:
            # run_in_executorで同期APIを非同期化
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.text_generation(
                    prompt,
                    model=self.model_id,
                    max_new_tokens=config.HF_MAX_TOKENS,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.1,
                ),
            )
            return response
        except HfHubHTTPError as e:
            logger.warning(f"Hugging Face APIエラー: {e}")
            raise
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            raise ScriptGenerationError(f"API呼び出しに失敗しました: {e}") from e

    async def _extract_json_with_retry(
        self, response: str, original_prompt: str, max_attempts: int = 2
    ) -> dict[str, Any]:
        """JSON抽出を試み、失敗時は再生成"""
        for attempt in range(max_attempts):
            try:
                return self._extract_json(response)
            except ValueError as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"JSON解析失敗、再生成を試みます: {e}")
                    # 再生成を促すプロンプト
                    retry_prompt = (
                        f"{original_prompt}\n\n"
                        "注意: 必ず有効なJSON形式で出力してください。"
                    )
                    response = await self._call_api_with_retry(retry_prompt)
                else:
                    raise ScriptGenerationError(f"台本の生成に失敗しました: {e}") from e
        raise ScriptGenerationError("台本の生成に失敗しました")

    async def generate_and_save(
        self,
        theme: str,
        keywords: list[str],
        target_audience: str = "一般視聴者",
        duration: int = 30,
        output_filename: str | None = None,
    ) -> Path:
        """
        台本を生成してファイルに保存

        Args:
            theme: 動画のテーマ
            keywords: 関連キーワード
            target_audience: ターゲット視聴者
            duration: 動画の長さ（秒）
            output_filename: 出力ファイル名（省略時は自動生成）

        Returns:
            保存したファイルのパス
        """
        config.ensure_directories()

        script_data = await self.generate(theme, keywords, target_audience, duration)

        # ファイル名を生成
        if output_filename is None:
            output_filename = FileHandler.generate_filename("script", "json")

        output_path = config.scripts_output_dir / output_filename
        FileHandler.save_json(script_data, output_path)

        return output_path


async def main():
    """CLI実行用"""
    parser = argparse.ArgumentParser(description="ショート動画の台本を生成")
    parser.add_argument("--theme", "-t", required=True, help="動画のテーマ")
    parser.add_argument(
        "--keywords", "-k", nargs="+", default=[], help="関連キーワード"
    )
    parser.add_argument(
        "--audience", "-a", default="一般視聴者", help="ターゲット視聴者"
    )
    parser.add_argument("--duration", "-d", type=int, default=30, help="動画の長さ（秒）")
    parser.add_argument("--output", "-o", help="出力ファイル名")

    args = parser.parse_args()

    generator = ScriptGenerator()
    output_path = await generator.generate_and_save(
        theme=args.theme,
        keywords=args.keywords,
        target_audience=args.audience,
        duration=args.duration,
        output_filename=args.output,
    )

    print(f"台本を保存しました: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
