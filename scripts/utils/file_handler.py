"""
AI Shorts Factory - ファイル操作ユーティリティ

ファイルの読み書き・管理
"""

import json
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from scripts.config import config
from scripts.utils.logger import get_logger

logger = get_logger(__name__)


class FileHandler:
    """ファイル操作を管理するクラス"""

    @staticmethod
    def generate_filename(prefix: str, extension: str) -> str:
        """
        タイムスタンプ付きのファイル名を生成

        Args:
            prefix: ファイル名のプレフィックス
            extension: 拡張子（ドットなし）

        Returns:
            生成されたファイル名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}.{extension}"

    @staticmethod
    def save_json(data: dict[str, Any], filepath: Path) -> Path:
        """
        JSONファイルを保存

        Args:
            data: 保存するデータ
            filepath: 保存先パス

        Returns:
            保存したファイルのパス
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"JSONファイルを保存しました: {filepath}")
        return filepath

    @staticmethod
    def load_json(filepath: Path) -> dict[str, Any]:
        """
        JSONファイルを読み込み

        Args:
            filepath: ファイルパス

        Returns:
            読み込んだデータ
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"JSONファイルを読み込みました: {filepath}")
        return data

    @staticmethod
    async def save_json_async(data: dict[str, Any], filepath: Path) -> Path:
        """
        JSONファイルを非同期で保存

        Args:
            data: 保存するデータ
            filepath: 保存先パス

        Returns:
            保存したファイルのパス
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, ensure_ascii=False, indent=2)
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            await f.write(content)
        logger.info(f"JSONファイルを保存しました: {filepath}")
        return filepath

    @staticmethod
    async def load_json_async(filepath: Path) -> dict[str, Any]:
        """
        JSONファイルを非同期で読み込み

        Args:
            filepath: ファイルパス

        Returns:
            読み込んだデータ
        """
        async with aiofiles.open(filepath, encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
        logger.debug(f"JSONファイルを読み込みました: {filepath}")
        return data

    @staticmethod
    async def save_binary_async(data: bytes, filepath: Path) -> Path:
        """
        バイナリファイルを非同期で保存

        Args:
            data: 保存するバイナリデータ
            filepath: 保存先パス

        Returns:
            保存したファイルのパス
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(data)
        logger.info(f"バイナリファイルを保存しました: {filepath}")
        return filepath

    @staticmethod
    def cleanup_temp_files(max_age_hours: int = 24) -> int:
        """
        古い一時ファイルを削除

        Args:
            max_age_hours: 削除対象とする経過時間（時間）

        Returns:
            削除したファイル数
        """
        temp_dir = config.temp_dir
        if not temp_dir.exists():
            return 0

        deleted_count = 0
        now = datetime.now()

        for filepath in temp_dir.iterdir():
            if filepath.is_file():
                file_age = now - datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_age.total_seconds() > max_age_hours * 3600:
                    filepath.unlink()
                    deleted_count += 1
                    logger.debug(f"一時ファイルを削除しました: {filepath}")

        if deleted_count > 0:
            logger.info(f"{deleted_count}個の一時ファイルを削除しました")
        return deleted_count

    @staticmethod
    def get_file_size_mb(filepath: Path) -> float:
        """
        ファイルサイズをMB単位で取得

        Args:
            filepath: ファイルパス

        Returns:
            ファイルサイズ（MB）
        """
        return filepath.stat().st_size / (1024 * 1024)

    @staticmethod
    def copy_file(src: Path, dst: Path) -> Path:
        """
        ファイルをコピー

        Args:
            src: コピー元
            dst: コピー先

        Returns:
            コピー先のパス
        """
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.debug(f"ファイルをコピーしました: {src} -> {dst}")
        return dst

    @staticmethod
    def save_secure_json(data: dict[str, Any], filepath: Path) -> Path:
        """
        機密情報を含むJSONファイルを安全に保存（パーミッション0o600）

        Args:
            data: 保存するデータ
            filepath: 保存先パス

        Returns:
            保存したファイルのパス
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 既存ファイルがあれば削除（新しいパーミッションで作成するため）
        if filepath.exists():
            filepath.unlink()

        # ファイルを作成してパーミッションを設定
        fd = os.open(
            filepath,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            stat.S_IRUSR | stat.S_IWUSR,  # 0o600: 所有者のみ読み書き可能
        )
        try:
            content = json.dumps(data, ensure_ascii=False, indent=2)
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)

        logger.info(f"機密ファイルを保存しました: {filepath} (パーミッション: 0600)")
        return filepath

    @staticmethod
    def check_file_permissions(filepath: Path) -> bool:
        """
        ファイルのパーミッションが安全かチェック（所有者のみ読み書き可能か）

        Args:
            filepath: チェックするファイルパス

        Returns:
            安全な場合True
        """
        if not filepath.exists():
            return True

        file_stat = filepath.stat()
        mode = file_stat.st_mode

        # グループとその他にアクセス権がないことを確認
        unsafe_bits = stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | \
                      stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH

        if mode & unsafe_bits:
            logger.warning(
                f"ファイルのパーミッションが安全ではありません: {filepath} "
                f"(現在: {oct(mode)}, 推奨: 0600)"
            )
            return False

        return True
