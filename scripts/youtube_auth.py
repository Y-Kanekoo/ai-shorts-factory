"""
AI Shorts Factory - YouTube認証モジュール

YouTube Data API v3のOAuth2認証を管理
"""

import json
import os
import stat
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from scripts.config import config
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger

logger = get_logger(__name__)


class YouTubeAuthError(Exception):
    """YouTube認証エラー"""

    pass


class YouTubeAuth:
    """YouTube認証管理クラス"""

    def __init__(
        self,
        client_secrets_file: str | Path | None = None,
        token_file: str | Path | None = None,
        scopes: list[str] | None = None,
    ):
        """
        Args:
            client_secrets_file: OAuth2クライアント認証情報ファイルのパス
            token_file: トークン保存ファイルのパス
            scopes: 要求するスコープ
        """
        self.client_secrets_file = Path(
            client_secrets_file or config.YOUTUBE_CLIENT_SECRETS_FILE
        )
        self.token_file = Path(token_file or config.YOUTUBE_TOKEN_FILE)
        self.scopes = scopes or config.YOUTUBE_SCOPES
        self._credentials = None
        self._service = None

    def _load_credentials(self) -> Credentials | None:
        """保存されたトークンを読み込み"""
        if not self.token_file.exists():
            return None

        # ファイルパーミッションをチェック、安全でなければ自動修正
        if not FileHandler.check_file_permissions(self.token_file):
            logger.warning(
                f"トークンファイルのパーミッションを修正します: {self.token_file}"
            )
            os.chmod(self.token_file, stat.S_IRUSR | stat.S_IWUSR)  # 0o600

        try:
            with open(self.token_file, encoding="utf-8") as f:
                token_data = json.load(f)
            return Credentials.from_authorized_user_info(token_data, self.scopes)
        except Exception as e:
            logger.warning(f"トークンの読み込みに失敗: {e}")
            return None

    def _save_credentials(self, credentials: Credentials) -> None:
        """トークンを安全に保存（パーミッション0o600）"""
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes) if credentials.scopes else [],
            # expiryを保存（リフレッシュ判定に必要）
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }
        # セキュアなファイル保存（所有者のみ読み書き可能）
        FileHandler.save_secure_json(token_data, self.token_file)
        logger.info(f"トークンを安全に保存しました: {self.token_file}")

    def authenticate(self, force_reauth: bool = False) -> Credentials:
        """
        認証を行い、認証情報を取得

        Args:
            force_reauth: 強制的に再認証を行う

        Returns:
            認証情報
        """
        credentials = None

        if not force_reauth:
            credentials = self._load_credentials()

        # トークンが有効かチェック
        if credentials and credentials.valid:
            logger.info("既存の有効なトークンを使用")
            self._credentials = credentials
            return credentials

        # トークンをリフレッシュ
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                logger.info("トークンをリフレッシュ中")
                credentials.refresh(Request())
                self._save_credentials(credentials)
                self._credentials = credentials
                return credentials
            except Exception as e:
                logger.warning(f"トークンのリフレッシュに失敗: {e}")

        # 新規認証が必要
        if not self.client_secrets_file.exists():
            raise FileNotFoundError(
                f"クライアント認証情報ファイルが見つかりません: {self.client_secrets_file}"
            )

        logger.info("新規認証を開始（ブラウザが開きます）")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.client_secrets_file),
            self.scopes,
        )
        credentials = flow.run_local_server(port=0)
        self._save_credentials(credentials)
        self._credentials = credentials

        return credentials

    def get_service(self):
        """
        YouTube APIサービスオブジェクトを取得

        Returns:
            YouTube APIサービス
        """
        if self._service is not None:
            return self._service

        if self._credentials is None:
            self.authenticate()

        self._service = build("youtube", "v3", credentials=self._credentials)
        return self._service

    def check_quota(self) -> dict:
        """
        APIクォータの使用状況を確認（概算）

        注意: 正確なクォータ情報はGoogle Cloud Consoleで確認が必要

        Returns:
            クォータ情報
        """
        return {
            "daily_limit": 10000,
            "upload_cost": 1600,
            "note": "正確な使用量はGoogle Cloud Consoleで確認してください",
        }
