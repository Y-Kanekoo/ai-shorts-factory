"""
AI Shorts Factory - YouTube認証テスト
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.youtube_auth import YouTubeAuth, YouTubeAuthError


class TestYouTubeAuth:
    """YouTubeAuthのテスト"""

    def test_init_default(self, tmp_path):
        """デフォルト初期化のテスト"""
        auth = YouTubeAuth()
        assert auth._credentials is None
        assert auth._service is None

    def test_init_custom_paths(self, tmp_path):
        """カスタムパスでの初期化テスト"""
        secrets_file = tmp_path / "custom_secrets.json"
        token_file = tmp_path / "custom_token.json"

        auth = YouTubeAuth(
            client_secrets_file=secrets_file,
            token_file=token_file,
        )

        assert auth.client_secrets_file == secrets_file
        assert auth.token_file == token_file

    def test_init_custom_scopes(self, tmp_path):
        """カスタムスコープでの初期化テスト"""
        custom_scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
        ]

        auth = YouTubeAuth(scopes=custom_scopes)
        assert auth.scopes == custom_scopes

    def test_load_credentials_no_file(self, tmp_path):
        """トークンファイルが存在しない場合のテスト"""
        auth = YouTubeAuth(token_file=tmp_path / "nonexistent.json")
        credentials = auth._load_credentials()
        assert credentials is None

    def test_load_credentials_invalid_json(self, tmp_path):
        """無効なJSONファイルのテスト"""
        token_file = tmp_path / "invalid.json"
        token_file.write_text("invalid json content")

        auth = YouTubeAuth(token_file=token_file)
        credentials = auth._load_credentials()
        assert credentials is None

    @patch("scripts.youtube_auth.FileHandler.check_file_permissions")
    @patch("scripts.youtube_auth.Credentials.from_authorized_user_info")
    def test_load_credentials_success(
        self, mock_from_info, mock_check_perms, tmp_path
    ):
        """正常なトークン読み込みのテスト"""
        token_file = tmp_path / "token.json"
        token_data = {
            "token": "test_token",
            "refresh_token": "test_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/youtube.upload"],
        }
        token_file.write_text(json.dumps(token_data))

        mock_credentials = MagicMock()
        mock_from_info.return_value = mock_credentials

        auth = YouTubeAuth(token_file=token_file)
        credentials = auth._load_credentials()

        assert credentials == mock_credentials
        mock_check_perms.assert_called_once_with(token_file)

    @patch("scripts.youtube_auth.FileHandler.save_secure_json")
    def test_save_credentials(self, mock_save_secure, tmp_path):
        """トークン保存のテスト"""
        token_file = tmp_path / "token.json"
        auth = YouTubeAuth(token_file=token_file)

        mock_credentials = MagicMock()
        mock_credentials.token = "test_token"
        mock_credentials.refresh_token = "test_refresh"
        mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
        mock_credentials.client_id = "test_client_id"
        mock_credentials.client_secret = "test_client_secret"
        mock_credentials.scopes = ["https://www.googleapis.com/auth/youtube.upload"]

        auth._save_credentials(mock_credentials)

        mock_save_secure.assert_called_once()
        call_args = mock_save_secure.call_args
        saved_data = call_args[0][0]

        assert saved_data["token"] == "test_token"
        assert saved_data["refresh_token"] == "test_refresh"
        assert saved_data["client_id"] == "test_client_id"

    def test_save_credentials_none_scopes(self, tmp_path):
        """スコープがNoneの場合のトークン保存テスト"""
        with patch("scripts.youtube_auth.FileHandler.save_secure_json") as mock_save:
            token_file = tmp_path / "token.json"
            auth = YouTubeAuth(token_file=token_file)

            mock_credentials = MagicMock()
            mock_credentials.token = "test_token"
            mock_credentials.refresh_token = "test_refresh"
            mock_credentials.token_uri = "https://oauth2.googleapis.com/token"
            mock_credentials.client_id = "test_client_id"
            mock_credentials.client_secret = "test_client_secret"
            mock_credentials.scopes = None

            auth._save_credentials(mock_credentials)

            call_args = mock_save.call_args
            saved_data = call_args[0][0]
            assert saved_data["scopes"] == []

    def test_authenticate_valid_credentials(self, tmp_path):
        """有効な既存認証情報を使用するテスト"""
        auth = YouTubeAuth(token_file=tmp_path / "token.json")

        mock_credentials = MagicMock()
        mock_credentials.valid = True

        with patch.object(auth, "_load_credentials", return_value=mock_credentials):
            result = auth.authenticate()

        assert result == mock_credentials
        assert auth._credentials == mock_credentials

    def test_authenticate_expired_refresh(self, tmp_path):
        """期限切れトークンのリフレッシュテスト"""
        auth = YouTubeAuth(token_file=tmp_path / "token.json")

        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "test_refresh"

        with patch.object(auth, "_load_credentials", return_value=mock_credentials):
            with patch.object(auth, "_save_credentials"):
                result = auth.authenticate()

        mock_credentials.refresh.assert_called_once()
        assert result == mock_credentials

    def test_authenticate_force_reauth(self, tmp_path):
        """強制再認証のテスト"""
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({
            "installed": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }))

        auth = YouTubeAuth(
            client_secrets_file=secrets_file,
            token_file=tmp_path / "token.json",
        )

        mock_flow = MagicMock()
        mock_credentials = MagicMock()
        mock_flow.run_local_server.return_value = mock_credentials

        with patch("scripts.youtube_auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            with patch.object(auth, "_save_credentials"):
                result = auth.authenticate(force_reauth=True)

        assert result == mock_credentials
        mock_flow.run_local_server.assert_called_once()

    def test_authenticate_no_secrets_file(self, tmp_path):
        """認証情報ファイルが存在しない場合のテスト"""
        auth = YouTubeAuth(
            client_secrets_file=tmp_path / "nonexistent.json",
            token_file=tmp_path / "token.json",
        )

        with patch.object(auth, "_load_credentials", return_value=None):
            with pytest.raises(FileNotFoundError):
                auth.authenticate()

    def test_get_service(self, tmp_path):
        """APIサービス取得のテスト"""
        auth = YouTubeAuth(token_file=tmp_path / "token.json")

        mock_credentials = MagicMock()
        mock_service = MagicMock()

        auth._credentials = mock_credentials

        with patch("scripts.youtube_auth.build", return_value=mock_service):
            result = auth.get_service()

        assert result == mock_service
        assert auth._service == mock_service

    def test_get_service_cached(self, tmp_path):
        """キャッシュされたサービスの取得テスト"""
        auth = YouTubeAuth(token_file=tmp_path / "token.json")

        mock_service = MagicMock()
        auth._service = mock_service

        result = auth.get_service()
        assert result == mock_service

    def test_get_service_authenticate_first(self, tmp_path):
        """認証後にサービス取得するテスト"""
        auth = YouTubeAuth(token_file=tmp_path / "token.json")

        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_service = MagicMock()

        with patch.object(auth, "_load_credentials", return_value=mock_credentials):
            with patch("scripts.youtube_auth.build", return_value=mock_service):
                result = auth.get_service()

        assert result == mock_service

    def test_check_quota(self, tmp_path):
        """クォータ情報取得のテスト"""
        auth = YouTubeAuth(token_file=tmp_path / "token.json")

        quota_info = auth.check_quota()

        assert "daily_limit" in quota_info
        assert "upload_cost" in quota_info
        assert quota_info["daily_limit"] == 10000
        assert quota_info["upload_cost"] == 1600


class TestYouTubeAuthError:
    """YouTubeAuthErrorのテスト"""

    def test_error_creation(self):
        """エラー作成のテスト"""
        error = YouTubeAuthError("テストエラー")
        assert str(error) == "テストエラー"

    def test_error_inheritance(self):
        """エラーの継承関係テスト"""
        error = YouTubeAuthError("テスト")
        assert isinstance(error, Exception)
