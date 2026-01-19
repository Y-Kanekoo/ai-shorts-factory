"""
AI Shorts Factory - ファイルハンドラーテスト
"""

import json
import os
import stat
from pathlib import Path

import pytest

from scripts.utils.file_handler import FileHandler


class TestFileHandler:
    """FileHandlerのテスト"""

    def test_generate_filename(self):
        """ファイル名生成のテスト"""
        filename = FileHandler.generate_filename("test", "json")

        assert filename.startswith("test_")
        assert filename.endswith(".json")
        # タイムスタンプ形式のチェック: test_YYYYMMDD_HHMMSS.json
        parts = filename.replace("test_", "").replace(".json", "").split("_")
        assert len(parts) == 2
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS

    def test_save_json(self, tmp_path):
        """JSON保存のテスト"""
        data = {"key": "value", "number": 123}
        filepath = tmp_path / "test.json"

        result = FileHandler.save_json(data, filepath)

        assert result == filepath
        assert filepath.exists()

        # 内容を確認
        with open(filepath, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_json_creates_parent_dir(self, tmp_path):
        """親ディレクトリ作成のテスト"""
        data = {"test": "data"}
        filepath = tmp_path / "nested" / "dir" / "test.json"

        FileHandler.save_json(data, filepath)

        assert filepath.exists()
        assert filepath.parent.exists()

    def test_save_json_unicode(self, tmp_path):
        """日本語を含むJSON保存のテスト"""
        data = {"title": "テスト", "description": "日本語の説明文"}
        filepath = tmp_path / "unicode.json"

        FileHandler.save_json(data, filepath)

        with open(filepath, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["title"] == "テスト"

    def test_load_json(self, tmp_path):
        """JSON読み込みのテスト"""
        data = {"key": "value"}
        filepath = tmp_path / "test.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded = FileHandler.load_json(filepath)
        assert loaded == data

    def test_load_json_unicode(self, tmp_path):
        """日本語を含むJSON読み込みのテスト"""
        data = {"title": "日本語タイトル"}
        filepath = tmp_path / "test.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        loaded = FileHandler.load_json(filepath)
        assert loaded["title"] == "日本語タイトル"

    @pytest.mark.asyncio
    async def test_save_json_async(self, tmp_path):
        """非同期JSON保存のテスト"""
        data = {"async": True}
        filepath = tmp_path / "async.json"

        result = await FileHandler.save_json_async(data, filepath)

        assert result == filepath
        assert filepath.exists()

        with open(filepath, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    @pytest.mark.asyncio
    async def test_load_json_async(self, tmp_path):
        """非同期JSON読み込みのテスト"""
        data = {"async": True}
        filepath = tmp_path / "async.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded = await FileHandler.load_json_async(filepath)
        assert loaded == data

    @pytest.mark.asyncio
    async def test_save_binary_async(self, tmp_path):
        """非同期バイナリ保存のテスト"""
        data = b"binary content"
        filepath = tmp_path / "test.bin"

        result = await FileHandler.save_binary_async(data, filepath)

        assert result == filepath
        assert filepath.exists()
        assert filepath.read_bytes() == data

    def test_get_file_size_mb(self, tmp_path):
        """ファイルサイズ取得のテスト"""
        filepath = tmp_path / "test.bin"
        # 1MBのファイルを作成
        filepath.write_bytes(b"x" * (1024 * 1024))

        size = FileHandler.get_file_size_mb(filepath)
        assert abs(size - 1.0) < 0.01

    def test_copy_file(self, tmp_path):
        """ファイルコピーのテスト"""
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst" / "copy.txt"

        src.write_text("content")

        result = FileHandler.copy_file(src, dst)

        assert result == dst
        assert dst.exists()
        assert dst.read_text() == "content"


class TestFileHandlerSecurity:
    """FileHandlerのセキュリティ機能テスト"""

    def test_save_secure_json(self, tmp_path):
        """セキュアなJSON保存のテスト"""
        data = {"token": "secret_value"}
        filepath = tmp_path / "secure.json"

        result = FileHandler.save_secure_json(data, filepath)

        assert result == filepath
        assert filepath.exists()

        # パーミッションを確認（所有者のみ読み書き可能）
        mode = filepath.stat().st_mode
        assert mode & stat.S_IRUSR  # 所有者読み取り可
        assert mode & stat.S_IWUSR  # 所有者書き込み可
        assert not (mode & stat.S_IRGRP)  # グループ読み取り不可
        assert not (mode & stat.S_IWGRP)  # グループ書き込み不可
        assert not (mode & stat.S_IROTH)  # その他読み取り不可
        assert not (mode & stat.S_IWOTH)  # その他書き込み不可

        # 内容を確認
        with open(filepath, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_secure_json_overwrites_existing(self, tmp_path):
        """既存ファイルの上書きテスト"""
        filepath = tmp_path / "secure.json"

        # 最初のファイルを作成（通常のパーミッション）
        filepath.write_text('{"old": "data"}')
        os.chmod(filepath, 0o644)

        # セキュアに上書き
        new_data = {"new": "data"}
        FileHandler.save_secure_json(new_data, filepath)

        # パーミッションが変更されていることを確認
        mode = filepath.stat().st_mode
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IROTH)

        # 内容が更新されていることを確認
        with open(filepath, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == new_data

    def test_check_file_permissions_safe(self, tmp_path):
        """安全なパーミッションのチェックテスト"""
        filepath = tmp_path / "safe.json"
        filepath.write_text("{}")
        os.chmod(filepath, 0o600)

        result = FileHandler.check_file_permissions(filepath)
        assert result is True

    def test_check_file_permissions_unsafe_group_read(self, tmp_path):
        """グループ読み取り可能な場合のテスト"""
        filepath = tmp_path / "unsafe.json"
        filepath.write_text("{}")
        os.chmod(filepath, 0o640)

        result = FileHandler.check_file_permissions(filepath)
        assert result is False

    def test_check_file_permissions_unsafe_other_read(self, tmp_path):
        """その他読み取り可能な場合のテスト"""
        filepath = tmp_path / "unsafe.json"
        filepath.write_text("{}")
        os.chmod(filepath, 0o604)

        result = FileHandler.check_file_permissions(filepath)
        assert result is False

    def test_check_file_permissions_nonexistent(self, tmp_path):
        """存在しないファイルのテスト"""
        filepath = tmp_path / "nonexistent.json"

        result = FileHandler.check_file_permissions(filepath)
        assert result is True  # 存在しないファイルは安全とみなす


class TestFileHandlerCleanup:
    """FileHandlerのクリーンアップ機能テスト"""

    def test_cleanup_temp_files_empty_dir(self, tmp_path, monkeypatch):
        """空のディレクトリでのクリーンアップテスト"""
        from scripts import config as config_module

        # configのtemp_dirをモック
        monkeypatch.setattr(config_module.config, "temp_dir", tmp_path / "temp")
        (tmp_path / "temp").mkdir()

        deleted = FileHandler.cleanup_temp_files()
        assert deleted == 0

    def test_cleanup_temp_files_nonexistent_dir(self, tmp_path, monkeypatch):
        """存在しないディレクトリでのクリーンアップテスト"""
        from scripts import config as config_module

        monkeypatch.setattr(config_module.config, "temp_dir", tmp_path / "nonexistent")

        deleted = FileHandler.cleanup_temp_files()
        assert deleted == 0
