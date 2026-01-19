"""
AI Shorts Factory - YouTube投稿スクリプト（Track F）

YouTube Data API v3を使用して動画をアップロード
"""

import argparse
import asyncio
from pathlib import Path
from typing import Any

from googleapiclient.http import MediaFileUpload

from scripts.config import config
from scripts.constants import (
    YOUTUBE_CATEGORY_PEOPLE_BLOGS,
    YOUTUBE_SHORTS_ASPECT_RATIO,
    YOUTUBE_SHORTS_MAX_DURATION,
    YOUTUBE_SHORTS_MIN_DURATION,
)
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger
from scripts.youtube_auth import YouTubeAuth

logger = get_logger(__name__)


class PublishError(Exception):
    """投稿エラー"""

    pass


class VideoPublisher:
    """YouTube動画投稿クラス"""

    # YouTube Shortsの要件（定数から参照）
    MAX_DURATION_SECONDS = YOUTUBE_SHORTS_MAX_DURATION
    MIN_DURATION_SECONDS = YOUTUBE_SHORTS_MIN_DURATION
    REQUIRED_ASPECT_RATIO = YOUTUBE_SHORTS_ASPECT_RATIO

    def __init__(
        self,
        client_secrets_file: str | Path | None = None,
        token_file: str | Path | None = None,
    ):
        """
        Args:
            client_secrets_file: OAuth2クライアント認証情報ファイルのパス
            token_file: トークン保存ファイルのパス
        """
        self.auth = YouTubeAuth(
            client_secrets_file=client_secrets_file,
            token_file=token_file,
        )

    def _get_video_metadata(self, video_path: Path) -> dict[str, Any]:
        """
        動画ファイルからメタデータを取得

        Args:
            video_path: 動画ファイルのパス

        Returns:
            メタデータ（duration, width, height, aspect_ratio）
        """
        try:
            from moviepy import VideoFileClip

            with VideoFileClip(str(video_path)) as clip:
                return {
                    "duration": clip.duration,
                    "width": clip.size[0],
                    "height": clip.size[1],
                    "aspect_ratio": clip.size[1] / clip.size[0] if clip.size[0] > 0 else 0,
                    "fps": clip.fps,
                }
        except Exception as e:
            logger.warning(f"動画メタデータ取得エラー: {e}")
            return {}

    def _validate_for_shorts(
        self,
        video_path: Path,
        duration: float | None = None,
    ) -> dict[str, Any]:
        """
        YouTube Shorts要件を検証

        Args:
            video_path: 動画ファイルのパス
            duration: 動画の長さ（秒）、省略時は動画から取得

        Returns:
            検証結果
        """
        warnings = []
        errors = []

        # ファイル存在チェック
        if not video_path.exists():
            errors.append(f"動画ファイルが見つかりません: {video_path}")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # 動画メタデータを取得
        metadata = self._get_video_metadata(video_path)

        # duration引数がなければメタデータから取得
        actual_duration = duration if duration is not None else metadata.get("duration")

        # 長さチェック
        if actual_duration is not None:
            if actual_duration > self.MAX_DURATION_SECONDS:
                errors.append(
                    f"動画が長すぎます: {actual_duration:.1f}秒（最大{self.MAX_DURATION_SECONDS}秒）"
                )
            elif actual_duration < self.MIN_DURATION_SECONDS:
                warnings.append(
                    f"動画が短すぎる可能性があります: {actual_duration:.1f}秒（推奨{self.MIN_DURATION_SECONDS}秒以上）"
                )

        # アスペクト比チェック（縦長であること）
        aspect_ratio = metadata.get("aspect_ratio")
        if aspect_ratio is not None:
            if aspect_ratio < self.REQUIRED_ASPECT_RATIO * 0.9:  # 10%の許容誤差
                warnings.append(
                    f"縦長動画ではありません: アスペクト比 {aspect_ratio:.2f}（推奨: {self.REQUIRED_ASPECT_RATIO}以上）"
                )

        # 解像度チェック
        width = metadata.get("width")
        height = metadata.get("height")
        if width and height:
            if width < 540 or height < 960:
                warnings.append(
                    f"解像度が低い可能性があります: {width}x{height}（推奨: 1080x1920）"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "metadata": metadata,
        }

    async def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None = None,
        category_id: str = YOUTUBE_CATEGORY_PEOPLE_BLOGS,
        privacy_status: str = "private",
        is_shorts: bool = True,
        duration: float | None = None,
        skip_validation: bool = False,
    ) -> dict[str, Any]:
        """
        動画をYouTubeにアップロード

        Args:
            video_path: 動画ファイルのパス
            title: 動画タイトル
            description: 動画の説明
            tags: タグのリスト
            category_id: カテゴリID
            privacy_status: 公開設定（private/unlisted/public）
            is_shorts: Shortsとしてアップロードするか
            duration: 動画の長さ（秒）、検証用
            skip_validation: 検証をスキップするか

        Returns:
            アップロード結果

        Raises:
            PublishError: 検証に失敗した場合
        """
        video_path = Path(video_path)
        logger.info(f"動画アップロードを開始: {title}")

        # Shorts要件の検証
        if is_shorts and not skip_validation:
            validation = self._validate_for_shorts(video_path, duration)
            if not validation["valid"]:
                errors = ", ".join(validation["errors"])
                raise PublishError(f"Shorts要件を満たしていません: {errors}")
            for warning in validation.get("warnings", []):
                logger.warning(warning)

        # Shorts用のタイトル・説明調整
        if is_shorts:
            if "#shorts" not in title.lower() and "#shorts" not in description.lower():
                description = f"{description}\n\n#Shorts"
            if tags is None:
                tags = []
            if "Shorts" not in tags:
                tags.append("Shorts")

        # APIサービスを取得
        youtube = self.auth.get_service()

        # メタデータを設定
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # 動画ファイルをアップロード
        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
        )

        # 別スレッドで実行（ブロッキング操作）
        loop = asyncio.get_event_loop()

        def do_upload():
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"アップロード進捗: {int(status.progress() * 100)}%")
            return response

        response = await loop.run_in_executor(None, do_upload)

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        shorts_url = f"https://www.youtube.com/shorts/{video_id}"

        logger.info(f"動画をアップロードしました: {video_url}")

        return {
            "video_id": video_id,
            "video_url": video_url,
            "shorts_url": shorts_url if is_shorts else None,
            "title": title,
            "privacy_status": privacy_status,
        }

    async def upload_from_metadata(
        self,
        video_path: Path,
        script_metadata_path: Path,
        privacy_status: str = "private",
    ) -> dict[str, Any]:
        """
        台本メタデータから動画をアップロード

        Args:
            video_path: 動画ファイルのパス
            script_metadata_path: 台本JSONファイルのパス
            privacy_status: 公開設定

        Returns:
            アップロード結果
        """
        # 台本を読み込み
        script_data = FileHandler.load_json(script_metadata_path)

        title = script_data.get("title", "Untitled")
        description = script_data.get("description", "")
        tags = script_data.get("tags", [])

        return await self.upload(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            is_shorts=True,
        )

    async def update_video(
        self,
        video_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        privacy_status: str | None = None,
    ) -> dict[str, Any]:
        """
        投稿済み動画の情報を更新

        Args:
            video_id: 動画ID
            title: 新しいタイトル
            description: 新しい説明
            tags: 新しいタグ
            privacy_status: 新しい公開設定

        Returns:
            更新結果
        """
        logger.info(f"動画情報を更新: {video_id}")

        youtube = self.auth.get_service()

        # 現在の情報を取得
        loop = asyncio.get_event_loop()

        def get_video():
            return (
                youtube.videos()
                .list(part="snippet,status", id=video_id)
                .execute()
            )

        current = await loop.run_in_executor(None, get_video)

        if not current.get("items"):
            raise ValueError(f"動画が見つかりません: {video_id}")

        video = current["items"][0]

        # 更新するフィールドを設定
        body = {
            "id": video_id,
            "snippet": {
                "title": title or video["snippet"]["title"],
                "description": description or video["snippet"]["description"],
                "tags": tags or video["snippet"].get("tags", []),
                "categoryId": video["snippet"]["categoryId"],
            },
        }

        if privacy_status:
            body["status"] = {"privacyStatus": privacy_status}

        # 更新を実行
        def do_update():
            parts = "snippet"
            if privacy_status:
                parts += ",status"
            return (
                youtube.videos()
                .update(part=parts, body=body)
                .execute()
            )

        response = await loop.run_in_executor(None, do_update)

        logger.info(f"動画情報を更新しました: {video_id}")

        return {
            "video_id": video_id,
            "title": response["snippet"]["title"],
            "updated": True,
        }


async def main():
    """CLI実行用"""
    parser = argparse.ArgumentParser(description="YouTubeに動画をアップロード")
    parser.add_argument("--video", "-v", required=True, help="動画ファイルのパス")
    parser.add_argument("--title", "-t", help="動画タイトル")
    parser.add_argument("--description", "-d", help="動画の説明")
    parser.add_argument("--tags", nargs="+", help="タグ")
    parser.add_argument("--script", "-s", help="台本JSONファイルのパス（メタデータとして使用）")
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
        help="公開設定",
    )
    parser.add_argument("--auth", action="store_true", help="認証のみ実行")

    args = parser.parse_args()

    publisher = VideoPublisher()

    if args.auth:
        # 認証のみ
        publisher.auth.authenticate(force_reauth=True)
        print("認証が完了しました")
        return

    video_path = Path(args.video)

    if args.script:
        # 台本からメタデータを使用
        result = await publisher.upload_from_metadata(
            video_path=video_path,
            script_metadata_path=Path(args.script),
            privacy_status=args.privacy,
        )
    else:
        # 直接指定
        if not args.title:
            parser.error("--title または --script が必要です")

        result = await publisher.upload(
            video_path=video_path,
            title=args.title,
            description=args.description or "",
            tags=args.tags,
            privacy_status=args.privacy,
        )

    print(f"動画をアップロードしました:")
    print(f"  Video ID: {result['video_id']}")
    print(f"  URL: {result['video_url']}")
    if result.get("shorts_url"):
        print(f"  Shorts URL: {result['shorts_url']}")


if __name__ == "__main__":
    asyncio.run(main())
