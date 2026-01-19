"""
AI Shorts Factory - リトライユーティリティテスト
"""

import httpx
import pytest

from scripts.utils.retry import (
    RETRYABLE_STATUS_CODES,
    RetryableHTTPError,
    _is_hf_or_gradio_retryable,
    should_retry_exception,
    should_retry_response,
)


class TestShouldRetryResponse:
    """should_retry_response関数のテスト"""

    def test_retry_on_429(self):
        """429はリトライ対象"""
        response = httpx.Response(429)
        assert should_retry_response(response) is True

    def test_retry_on_500(self):
        """500はリトライ対象"""
        response = httpx.Response(500)
        assert should_retry_response(response) is True

    def test_retry_on_502(self):
        """502はリトライ対象"""
        response = httpx.Response(502)
        assert should_retry_response(response) is True

    def test_retry_on_503(self):
        """503はリトライ対象"""
        response = httpx.Response(503)
        assert should_retry_response(response) is True

    def test_retry_on_504(self):
        """504はリトライ対象"""
        response = httpx.Response(504)
        assert should_retry_response(response) is True

    def test_no_retry_on_200(self):
        """200はリトライ対象外"""
        response = httpx.Response(200)
        assert should_retry_response(response) is False

    def test_no_retry_on_400(self):
        """400はリトライ対象外"""
        response = httpx.Response(400)
        assert should_retry_response(response) is False

    def test_no_retry_on_401(self):
        """401（認証エラー）はリトライ対象外"""
        response = httpx.Response(401)
        assert should_retry_response(response) is False

    def test_no_retry_on_403(self):
        """403（権限エラー）はリトライ対象外"""
        response = httpx.Response(403)
        assert should_retry_response(response) is False

    def test_no_retry_on_404(self):
        """404はリトライ対象外"""
        response = httpx.Response(404)
        assert should_retry_response(response) is False


class TestShouldRetryException:
    """should_retry_exception関数のテスト"""

    def test_retry_on_timeout(self):
        """タイムアウトはリトライ対象"""
        exception = httpx.TimeoutException("timeout")
        assert should_retry_exception(exception) is True

    def test_retry_on_connect_error(self):
        """接続エラーはリトライ対象"""
        exception = httpx.ConnectError("connect failed")
        assert should_retry_exception(exception) is True

    def test_retry_on_read_error(self):
        """読み取りエラーはリトライ対象"""
        exception = httpx.ReadError("read failed")
        assert should_retry_exception(exception) is True

    def test_retry_on_retryable_http_error(self):
        """RetryableHTTPErrorはリトライ対象"""
        exception = RetryableHTTPError(500, "server error")
        assert should_retry_exception(exception) is True

    def test_retry_on_http_status_error_429(self):
        """HTTPStatusError 429はリトライ対象"""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(429, request=request)
        exception = httpx.HTTPStatusError("rate limit", request=request, response=response)
        assert should_retry_exception(exception) is True

    def test_retry_on_http_status_error_500(self):
        """HTTPStatusError 500はリトライ対象"""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        exception = httpx.HTTPStatusError("server error", request=request, response=response)
        assert should_retry_exception(exception) is True

    def test_no_retry_on_http_status_error_401(self):
        """HTTPStatusError 401はリトライ対象外"""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(401, request=request)
        exception = httpx.HTTPStatusError("unauthorized", request=request, response=response)
        assert should_retry_exception(exception) is False

    def test_no_retry_on_http_status_error_404(self):
        """HTTPStatusError 404はリトライ対象外"""
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        exception = httpx.HTTPStatusError("not found", request=request, response=response)
        assert should_retry_exception(exception) is False

    def test_no_retry_on_value_error(self):
        """ValueErrorはリトライ対象外"""
        exception = ValueError("invalid value")
        assert should_retry_exception(exception) is False

    def test_no_retry_on_key_error(self):
        """KeyErrorはリトライ対象外"""
        exception = KeyError("missing key")
        assert should_retry_exception(exception) is False


class MockHfHubHTTPError(Exception):
    """HfHubHTTPErrorのモック"""

    def __init__(self, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(f"HfHubHTTPError with status {status_code}")


class MockRepositoryNotFoundError(Exception):
    """RepositoryNotFoundErrorのモック"""

    pass


class MockGatedRepoError(Exception):
    """GatedRepoErrorのモック"""

    pass


class MockAppError(Exception):
    """gradio_client AppErrorのモック"""

    pass


class MockQueueError(Exception):
    """gradio_client QueueErrorのモック"""

    pass


class TestIsHfOrGradioRetryable:
    """_is_hf_or_gradio_retryable関数のテスト"""

    def test_hf_http_error_429_retryable(self):
        """HfHubHTTPError 429はリトライ対象"""
        # クラス名を動的に設定
        error = MockHfHubHTTPError(429)
        error.__class__.__name__ = "HfHubHTTPError"
        assert _is_hf_or_gradio_retryable(error) is True

    def test_hf_http_error_500_retryable(self):
        """HfHubHTTPError 500はリトライ対象"""
        error = MockHfHubHTTPError(500)
        error.__class__.__name__ = "HfHubHTTPError"
        assert _is_hf_or_gradio_retryable(error) is True

    def test_hf_http_error_401_not_retryable(self):
        """HfHubHTTPError 401はリトライ対象外"""
        error = MockHfHubHTTPError(401)
        error.__class__.__name__ = "HfHubHTTPError"
        assert _is_hf_or_gradio_retryable(error) is False

    def test_hf_http_error_403_not_retryable(self):
        """HfHubHTTPError 403はリトライ対象外"""
        error = MockHfHubHTTPError(403)
        error.__class__.__name__ = "HfHubHTTPError"
        assert _is_hf_or_gradio_retryable(error) is False

    def test_hf_http_error_404_not_retryable(self):
        """HfHubHTTPError 404はリトライ対象外"""
        error = MockHfHubHTTPError(404)
        error.__class__.__name__ = "HfHubHTTPError"
        assert _is_hf_or_gradio_retryable(error) is False

    def test_hf_http_error_no_status_not_retryable(self):
        """HfHubHTTPError ステータスコード不明はリトライ対象外"""
        error = MockHfHubHTTPError(None)
        error.__class__.__name__ = "HfHubHTTPError"
        assert _is_hf_or_gradio_retryable(error) is False

    def test_repository_not_found_not_retryable(self):
        """RepositoryNotFoundErrorはリトライ対象外"""
        error = MockRepositoryNotFoundError()
        error.__class__.__name__ = "RepositoryNotFoundError"
        assert _is_hf_or_gradio_retryable(error) is False

    def test_gated_repo_not_retryable(self):
        """GatedRepoErrorはリトライ対象外"""
        error = MockGatedRepoError()
        error.__class__.__name__ = "GatedRepoError"
        assert _is_hf_or_gradio_retryable(error) is False

    def test_gradio_app_error_retryable(self):
        """gradio AppErrorはリトライ対象"""
        error = MockAppError()
        error.__class__.__name__ = "AppError"
        assert _is_hf_or_gradio_retryable(error) is True

    def test_gradio_queue_error_retryable(self):
        """gradio QueueErrorはリトライ対象"""
        error = MockQueueError()
        error.__class__.__name__ = "QueueError"
        assert _is_hf_or_gradio_retryable(error) is True

    def test_unknown_exception_not_retryable(self):
        """不明な例外はリトライ対象外"""
        error = Exception("unknown error")
        assert _is_hf_or_gradio_retryable(error) is False


class TestRetryableStatusCodes:
    """リトライ対象ステータスコードの検証"""

    def test_contains_rate_limit(self):
        """429（レート制限）が含まれる"""
        assert 429 in RETRYABLE_STATUS_CODES

    def test_contains_server_errors(self):
        """5xxサーバーエラーが含まれる"""
        assert 500 in RETRYABLE_STATUS_CODES
        assert 502 in RETRYABLE_STATUS_CODES
        assert 503 in RETRYABLE_STATUS_CODES
        assert 504 in RETRYABLE_STATUS_CODES

    def test_does_not_contain_client_errors(self):
        """4xxクライアントエラーは含まれない（429除く）"""
        assert 400 not in RETRYABLE_STATUS_CODES
        assert 401 not in RETRYABLE_STATUS_CODES
        assert 403 not in RETRYABLE_STATUS_CODES
        assert 404 not in RETRYABLE_STATUS_CODES
        assert 422 not in RETRYABLE_STATUS_CODES
