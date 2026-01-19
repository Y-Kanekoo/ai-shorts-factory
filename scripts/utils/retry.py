"""
AI Shorts Factory - リトライユーティリティ

外部API呼び出しのリトライ機構
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from scripts.utils.logger import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# リトライ対象の例外（ネットワークエラー）
RETRYABLE_NETWORK_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)

# HTTPステータスコードでリトライ対象
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# 後方互換性のため維持
RETRYABLE_EXCEPTIONS = RETRYABLE_NETWORK_EXCEPTIONS


class RetryableHTTPError(Exception):
    """リトライ可能なHTTPエラー"""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


def should_retry_response(response: httpx.Response) -> bool:
    """レスポンスがリトライ対象かどうかを判定"""
    return response.status_code in RETRYABLE_STATUS_CODES


def should_retry_exception(exception: BaseException) -> bool:
    """
    例外がリトライ対象かどうかを判定

    Args:
        exception: 発生した例外

    Returns:
        リトライすべき場合True
    """
    # ネットワークエラー
    if isinstance(exception, RETRYABLE_NETWORK_EXCEPTIONS):
        return True

    # カスタムリトライ可能エラー
    if isinstance(exception, RetryableHTTPError):
        return True

    # HTTPステータスエラー（429, 5xx）
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRYABLE_STATUS_CODES

    return False


async def retry_async(
    func: Callable[P, T],
    *args: P.args,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    **kwargs: P.kwargs,
) -> T:
    """
    非同期関数をリトライ付きで実行

    Args:
        func: 実行する関数
        *args: 関数の位置引数
        max_attempts: 最大試行回数
        min_wait: 最小待機秒数
        max_wait: 最大待機秒数
        **kwargs: 関数のキーワード引数

    Returns:
        関数の戻り値

    Raises:
        RetryError: 全試行が失敗した場合
    """
    attempt = 0

    async for attempt_info in AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception(should_retry_exception),
        reraise=True,
    ):
        with attempt_info:
            attempt += 1
            if attempt > 1:
                logger.warning(f"リトライ中: 試行 {attempt}/{max_attempts}")
            return await func(*args, **kwargs)

    # この行には到達しないはずだが、型チェッカーのために記述
    raise RetryError(None)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    リトライ機能を追加するデコレータ

    Args:
        max_attempts: 最大試行回数
        min_wait: 最小待機秒数
        max_wait: 最大待機秒数

    Usage:
        @with_retry(max_attempts=3)
        async def call_external_api():
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_async(
                func,
                *args,
                max_attempts=max_attempts,
                min_wait=min_wait,
                max_wait=max_wait,
                **kwargs,
            )

        return wrapper

    return decorator


async def check_response_and_raise(response: httpx.Response) -> None:
    """
    レスポンスをチェックし、リトライ可能な場合は例外を発生させる

    Args:
        response: HTTPレスポンス

    Raises:
        RetryableHTTPError: リトライ可能なエラーの場合
        httpx.HTTPStatusError: リトライ不可能なエラーの場合
    """
    if response.is_success:
        return

    if should_retry_response(response):
        raise RetryableHTTPError(
            response.status_code,
            f"サーバーエラー: {response.text[:200]}",
        )

    # リトライ不可能なエラー
    response.raise_for_status()
