"""
AI Shorts Factory - HTTPクライアントユーティリティ

共通のHTTPクライアント機能（コネクションプール再利用）
"""

from pathlib import Path
from types import TracebackType
from typing import Any, Self

import aiofiles
import httpx

from scripts.utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


class APIClient:
    """
    汎用HTTPクライアント

    コネクションプールを再利用して効率的にリクエストを処理。
    async with文で使用するか、手動でclose()を呼び出す。

    Usage:
        async with APIClient("https://api.example.com") as client:
            response = await client.get("/endpoint")
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        """
        Args:
            base_url: APIのベースURL
            headers: デフォルトヘッダー
            timeout: タイムアウト秒数
        """
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """永続クライアントを取得（遅延初期化）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self.headers,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """クライアントを閉じる"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

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

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        GETリクエスト

        Args:
            endpoint: エンドポイント（/で始まる）
            params: クエリパラメータ
            headers: 追加ヘッダー

        Returns:
            レスポンス
        """
        url = f"{self.base_url}{endpoint}"
        merged_headers = {**self.headers, **(headers or {})}
        client = await self._get_client()

        logger.debug(f"GET {url}", extra={"params": params})
        response = await client.get(url, params=params, headers=merged_headers)
        self._log_response(response)
        return response

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """
        POSTリクエスト

        Args:
            endpoint: エンドポイント
            data: フォームデータ
            json_data: JSONデータ
            headers: 追加ヘッダー

        Returns:
            レスポンス
        """
        url = f"{self.base_url}{endpoint}"
        merged_headers = {**self.headers, **(headers or {})}
        client = await self._get_client()

        logger.debug(f"POST {url}")
        response = await client.post(
            url, data=data, json=json_data, headers=merged_headers
        )
        self._log_response(response)
        return response

    async def download(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        """
        ファイルをダウンロード（小さいファイル向け）

        Args:
            url: ダウンロードURL（フルURL）
            headers: 追加ヘッダー

        Returns:
            ダウンロードしたバイナリデータ
        """
        merged_headers = {**self.headers, **(headers or {})}
        client = await self._get_client()

        logger.debug(f"DOWNLOAD {url}")
        response = await client.get(url, headers=merged_headers)
        response.raise_for_status()
        return response.content

    async def download_stream(
        self,
        url: str,
        output_path: Path,
        headers: dict[str, str] | None = None,
        chunk_size: int = 8192,
    ) -> Path:
        """
        ファイルをストリーミングダウンロード（大きいファイル向け）

        Args:
            url: ダウンロードURL（フルURL）
            output_path: 保存先パス
            headers: 追加ヘッダー
            chunk_size: チャンクサイズ（バイト）

        Returns:
            保存したファイルのパス
        """
        merged_headers = {**self.headers, **(headers or {})}
        client = await self._get_client()

        logger.debug(f"STREAM DOWNLOAD {url}")
        async with client.stream("GET", url, headers=merged_headers) as response:
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # 非同期ファイル書き込み（イベントループをブロックしない）
            async with aiofiles.open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size):
                    await f.write(chunk)

        logger.debug(f"Downloaded to {output_path}")
        return output_path

    def _log_response(self, response: httpx.Response) -> None:
        """レスポンスをログ出力"""
        if response.is_success:
            logger.debug(f"Response: {response.status_code}")
        else:
            logger.warning(
                f"Response: {response.status_code}",
                extra={"body": response.text[:500]},
            )
