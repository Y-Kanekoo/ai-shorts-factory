"""
AI Shorts Factory - ロギングユーティリティ

構造化ログとログレベル管理
"""

import logging
import re
import sys
from typing import Any

from scripts.config import config


def get_logger(name: str) -> logging.Logger:
    """
    ロガーを取得する

    Args:
        name: ロガー名（通常は__name__を使用）

    Returns:
        設定済みのロガー
    """
    logger = logging.getLogger(name)

    # 既に設定済みの場合はそのまま返す
    if logger.handlers:
        return logger

    logger.setLevel(config.LOG_LEVEL)

    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.LOG_LEVEL)

    # フォーマッタ
    formatter = logging.Formatter(config.LOG_FORMAT)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    # 親ロガーへの伝播を防ぐ
    logger.propagate = False

    return logger


class StructuredLogger:
    """
    構造化ログを出力するラッパークラス

    コンテキスト情報を付加してログを出力
    """

    def __init__(self, name: str):
        self._logger = get_logger(name)

    def _format_extra(self, extra: dict[str, Any] | None) -> str:
        """追加情報をフォーマット"""
        if not extra:
            return ""
        # 機密情報をマスキング
        masked = self._mask_sensitive(extra)
        return " " + str(masked)

    def _mask_sensitive(self, data: dict[str, Any]) -> dict[str, Any]:
        """機密情報をマスキング"""
        sensitive_keys = {
            "token",
            "password",
            "secret",
            "api_key",
            "key",
            "refresh_token",
            "access_token",
            "client_secret",
            "client_id",
            "authorization",
            "bearer",
            "credential",
            "auth",
        }
        # レスポンスボディはトランケート
        truncate_keys = {"body", "response", "content"}
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(s in key_lower for s in sensitive_keys):
                # 値の一部を残して末尾をマスク（デバッグしやすいように）
                if isinstance(value, str) and len(value) > 8:
                    masked[key] = f"{value[:4]}***{value[-4:]}"
                else:
                    masked[key] = "***"
            elif key_lower in truncate_keys:
                # レスポンスボディ等は長さ制限してトークン等をマスク
                if isinstance(value, str):
                    # 機密パターンを置換
                    masked_value = re.sub(
                        r'(token|key|secret|password|bearer)["\']?\s*[:=]\s*["\']?[\w\-\.]+',
                        r'\1=***',
                        value,
                        flags=re.IGNORECASE
                    )
                    # 長さ制限
                    if len(masked_value) > 200:
                        masked[key] = f"{masked_value[:200]}...[truncated]"
                    else:
                        masked[key] = masked_value
                else:
                    masked[key] = value
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive(value)
            elif isinstance(value, list):
                masked[key] = [
                    self._mask_sensitive(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        return masked

    def debug(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """DEBUGレベルログ"""
        self._logger.debug(f"{message}{self._format_extra(extra)}")

    def info(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """INFOレベルログ"""
        self._logger.info(f"{message}{self._format_extra(extra)}")

    def warning(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """WARNINGレベルログ"""
        self._logger.warning(f"{message}{self._format_extra(extra)}")

    def error(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """ERRORレベルログ"""
        self._logger.error(f"{message}{self._format_extra(extra)}")

    def exception(self, message: str, extra: dict[str, Any] | None = None) -> None:
        """例外情報付きERRORログ"""
        self._logger.exception(f"{message}{self._format_extra(extra)}")
