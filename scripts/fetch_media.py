"""
AI Shorts Factory - 動画素材取得スクリプト（Track D）

Pexels APIを使用して背景動画素材を取得
"""

import argparse
import asyncio
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import aiofiles
import httpx

from scripts.config import config
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger
from scripts.utils.retry import with_retry

logger = get_logger(__name__)

# リトライ設定
MAX_RETRY_ATTEMPTS = 3
RETRY_MIN_WAIT = 1.0
RETRY_MAX_WAIT = 10.0


class MediaFetchError(Exception):
    """動画素材取得エラー"""

    pass


class MediaFetcher:
    """
    動画素材取得クラス

    コネクションプールを再利用して効率的にリクエストを処理。
    async with文で使用するか、手動でclose()を呼び出す。
    """

    def __init__(self, api_key: str | None = None):
        """
        Args:
            api_key: Pexels APIキー
        """
        self.api_key = api_key or config.PEXELS_API_KEY
        self._validate_config()
        self.base_url = config.PEXELS_VIDEOS_URL
        self._client: httpx.AsyncClient | None = None
        self._download_client: httpx.AsyncClient | None = None

    def _validate_config(self) -> None:
        """設定を検証"""
        if not self.api_key:
            raise MediaFetchError(
                "PEXELS_API_KEYが設定されていません。.envファイルを確認してください。"
            )

    async def _get_client(self) -> httpx.AsyncClient:
        """永続クライアントを取得（遅延初期化）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30,
                headers=self._get_headers(),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def _get_download_client(self) -> httpx.AsyncClient:
        """ダウンロード用クライアントを取得（長いタイムアウト設定）"""
        if self._download_client is None or self._download_client.is_closed:
            self._download_client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._download_client

    async def close(self) -> None:
        """クライアントを閉じる"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        if self._download_client is not None and not self._download_client.is_closed:
            await self._download_client.aclose()
            self._download_client = None

    async def __aenter__(self) -> Self:
        """コンテキストマネージャーのエントリ"""
        await self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストマネージャーの終了"""
        await self.close()

    def _get_headers(self) -> dict[str, str]:
        """APIヘッダーを取得"""
        return {"Authorization": self.api_key}

    @with_retry(max_attempts=MAX_RETRY_ATTEMPTS, min_wait=RETRY_MIN_WAIT, max_wait=RETRY_MAX_WAIT)
    async def search_videos(
        self,
        query: str,
        orientation: str = "portrait",
        size: str = "medium",
        per_page: int = 5,
    ) -> list[dict[str, Any]]:
        """
        動画を検索

        Args:
            query: 検索キーワード
            orientation: 向き（portrait/landscape/square）
            size: サイズ（large/medium/small）
            per_page: 取得件数

        Returns:
            動画情報のリスト
        """
        logger.info(f"動画素材を検索中: {query}")

        params = {
            "query": query,
            "orientation": orientation,
            "size": size,
            "per_page": per_page,
        }

        client = await self._get_client()
        response = await client.get(f"{self.base_url}/search", params=params)
        response.raise_for_status()
        data = response.json()

        videos = data.get("videos", [])
        logger.info(f"{len(videos)}件の動画が見つかりました")

        return videos

    def _calculate_video_score(
        self,
        video: dict[str, Any],
        video_file: dict[str, Any],
    ) -> float:
        """
        動画のスコアを計算（高いほど良い）

        Args:
            video: 動画情報
            video_file: 動画ファイル情報

        Returns:
            スコア（0-100）
        """
        score = 0.0
        width = video_file.get("width", 0)
        height = video_file.get("height", 0)
        quality = video_file.get("quality", "")
        duration = video.get("duration", 0)

        # 縦長ボーナス（最重要）: +40点
        if height > width:
            score += 40.0
            # 9:16に近いほど追加ボーナス（最大+10点）
            aspect_ratio = height / width if width > 0 else 0
            target_ratio = 16 / 9
            ratio_diff = abs(aspect_ratio - target_ratio)
            score += max(0, 10 - ratio_diff * 5)

        # 品質ボーナス: HD=+20点, SD=+10点
        if quality == "hd":
            score += 20.0
        elif quality == "sd":
            score += 10.0

        # 解像度ボーナス（最大+15点）
        if height >= 1080:
            score += 15.0
        elif height >= 720:
            score += 10.0
        elif height >= 480:
            score += 5.0

        # 長さボーナス（15-60秒が理想）: 最大+15点
        if 15 <= duration <= 60:
            score += 15.0
        elif 10 <= duration <= 90:
            score += 10.0
        elif 5 <= duration <= 120:
            score += 5.0

        return score

    def _select_best_video(
        self,
        videos: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """
        検索結果から最適な動画とファイルを選択

        Args:
            videos: 動画情報のリスト

        Returns:
            (最適な動画, 最適なファイル) のタプル、見つからない場合はNone
        """
        if not videos:
            return None

        best_video = None
        best_file = None
        best_score = -1.0

        for video in videos:
            video_files = video.get("video_files", [])
            for vf in video_files:
                score = self._calculate_video_score(video, vf)
                if score > best_score:
                    best_score = score
                    best_video = video
                    best_file = vf

        if best_video and best_file:
            logger.debug(f"最適な動画を選択: スコア={best_score:.1f}")
            return best_video, best_file

        return None

    def _select_best_video_file(
        self,
        video_files: list[dict[str, Any]],
        target_width: int = 1080,
        target_height: int = 1920,
    ) -> dict[str, Any] | None:
        """
        最適な動画ファイルを選択（後方互換性のため維持）

        Args:
            video_files: 動画ファイル情報のリスト
            target_width: 目標の幅
            target_height: 目標の高さ

        Returns:
            最適な動画ファイル情報
        """
        if not video_files:
            return None

        # HDまたはSD品質を優先、縦長を優先
        for quality in ["hd", "sd"]:
            for vf in video_files:
                if vf.get("quality") == quality:
                    # 縦長かどうかをチェック
                    if vf.get("height", 0) > vf.get("width", 0):
                        return vf

        # 縦長がなければ最初のHD/SDを選択
        for quality in ["hd", "sd"]:
            for vf in video_files:
                if vf.get("quality") == quality:
                    return vf

        # それでもなければ最初のファイルを返す
        return video_files[0] if video_files else None

    @with_retry(max_attempts=MAX_RETRY_ATTEMPTS, min_wait=RETRY_MIN_WAIT, max_wait=RETRY_MAX_WAIT)
    async def download_video(
        self,
        video_url: str,
        output_path: Path,
    ) -> Path:
        """
        動画をストリーミングダウンロード

        Args:
            video_url: 動画のURL
            output_path: 保存先パス

        Returns:
            保存したファイルのパス
        """
        logger.info(f"動画をダウンロード中: {video_url[:50]}...")

        # 永続ダウンロードクライアントを使用（コネクションプール再利用）
        client = await self._get_download_client()
        async with client.stream("GET", video_url) as response:
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # 非同期ファイル書き込み（イベントループをブロックしない）
            async with aiofiles.open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    await f.write(chunk)

        logger.info(f"動画を保存しました: {output_path}")
        return output_path

    async def fetch_video(
        self,
        query: str,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        キーワードから動画を検索してダウンロード

        Args:
            query: 検索キーワード
            output_path: 保存先パス

        Returns:
            動画情報（パス、メタデータ）
        """
        # 動画を検索
        videos = await self.search_videos(query, orientation="portrait")

        if not videos:
            raise ValueError(f"動画が見つかりませんでした: {query}")

        # 検索結果全体から最適な動画を選択（スコアリング）
        result = self._select_best_video(videos)
        if result is None:
            raise ValueError("適切な動画ファイルが見つかりませんでした")

        video, best_file = result

        # 出力パスを決定
        if output_path is None:
            config.ensure_directories()
            filename = FileHandler.generate_filename("media", "mp4")
            output_path = config.videos_output_dir / filename

        # ダウンロード
        await self.download_video(best_file["link"], output_path)

        return {
            "filepath": str(output_path),
            "pexels_id": video.get("id"),
            "duration": video.get("duration"),
            "width": best_file.get("width"),
            "height": best_file.get("height"),
            "quality": best_file.get("quality"),
            "photographer": video.get("user", {}).get("name"),
            "pexels_url": video.get("url"),
        }

    async def fetch_multiple_videos(
        self,
        queries: list[str],
        output_prefix: str | None = None,
    ) -> dict[str, Any]:
        """
        複数のキーワードから動画を取得

        Args:
            queries: 検索キーワードのリスト
            output_prefix: 出力ファイル名のプレフィックス

        Returns:
            取得結果
        """
        config.ensure_directories()

        if output_prefix is None:
            timestamp = FileHandler.generate_filename("media", "")[:-1]
            output_prefix = timestamp

        results = []
        for i, query in enumerate(queries):
            try:
                filename = f"{output_prefix}_{i:02d}.mp4"
                output_path = config.videos_output_dir / filename
                result = await self.fetch_video(query, output_path)
                result["index"] = i
                result["query"] = query
                results.append(result)
            except Exception as e:
                logger.error(f"動画取得エラー: query={query}, error={e}")
                results.append(
                    {
                        "index": i,
                        "query": query,
                        "filepath": None,
                        "error": str(e),
                    }
                )

        # メタデータを保存
        metadata = {
            "files": results,
            "total_fetched": len([r for r in results if r.get("filepath")]),
        }

        metadata_path = config.videos_output_dir / f"{output_prefix}_metadata.json"
        FileHandler.save_json(metadata, metadata_path)

        logger.info(f"動画素材取得完了: {metadata['total_fetched']}/{len(queries)}件")

        return {
            "metadata_path": str(metadata_path),
            "files": results,
        }

    async def fetch_from_script(
        self,
        script_data: dict[str, Any],
        output_prefix: str | None = None,
    ) -> dict[str, Any]:
        """
        台本から動画素材を取得

        Args:
            script_data: 台本データ
            output_prefix: 出力ファイル名のプレフィックス

        Returns:
            取得結果
        """
        # 台本からキーワードを抽出
        keywords = script_data.get("metadata", {}).get("keywords", [])
        tags = script_data.get("tags", [])

        # キーワードがなければタグを使用
        queries = keywords if keywords else tags

        if not queries:
            raise ValueError("検索キーワードがありません")

        return await self.fetch_multiple_videos(queries, output_prefix)


async def main():
    """CLI実行用"""
    parser = argparse.ArgumentParser(description="Pexelsから動画素材を取得")
    parser.add_argument("--query", "-q", help="検索キーワード")
    parser.add_argument("--queries", "-Q", nargs="+", help="複数の検索キーワード")
    parser.add_argument("--script", "-s", help="台本JSONファイルのパス")
    parser.add_argument("--output", "-o", help="出力ファイル名/プレフィックス")

    args = parser.parse_args()

    # async withでリソースを確実に解放
    async with MediaFetcher() as fetcher:
        if args.query:
            # 単一検索
            result = await fetcher.fetch_video(
                query=args.query,
                output_path=Path(args.output) if args.output else None,
            )
            print(f"動画を保存しました: {result['filepath']}")
        elif args.queries:
            # 複数検索
            result = await fetcher.fetch_multiple_videos(
                queries=args.queries,
                output_prefix=args.output,
            )
            print(f"メタデータを保存しました: {result['metadata_path']}")
        elif args.script:
            # 台本から検索
            script_data = FileHandler.load_json(Path(args.script))
            result = await fetcher.fetch_from_script(
                script_data=script_data,
                output_prefix=args.output,
            )
            print(f"メタデータを保存しました: {result['metadata_path']}")
        else:
            parser.error("--query, --queries, または --script が必要です")


if __name__ == "__main__":
    asyncio.run(main())
