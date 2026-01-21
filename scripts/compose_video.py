"""
AI Shorts Factory - 動画合成スクリプト（Track E）

MoviePyを使用して最終動画を合成
"""

import argparse
import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)

from scripts.config import config
from scripts.constants import (
    DEFAULT_SUBTITLE_FONT,
    JAPANESE_FONTS,
    SUBTITLE_FONT_SIZE,
    SUBTITLE_MARGIN_BOTTOM,
    SUBTITLE_PADDING,
    SUBTITLE_STROKE_WIDTH,
)
from scripts.utils.file_handler import FileHandler
from scripts.utils.logger import get_logger

logger = get_logger(__name__)


def _find_available_font() -> str:
    """
    システムで利用可能な日本語フォントを検索

    Returns:
        利用可能なフォント名（見つからない場合はデフォルト）
    """
    try:
        from matplotlib import font_manager

        # システムフォントを取得
        system_fonts = {f.name for f in font_manager.fontManager.ttflist}

        for font in JAPANESE_FONTS:
            # ハイフンをスペースに変換して検索
            font_name = font.replace("-", " ")
            if font_name in system_fonts or font in system_fonts:
                logger.debug(f"利用可能なフォントを検出: {font}")
                return font

    except ImportError:
        logger.debug("matplotlibが利用不可、デフォルトフォントを使用")
    except Exception as e:
        logger.debug(f"フォント検索エラー: {e}")

    logger.debug(f"デフォルトフォントを使用: {DEFAULT_SUBTITLE_FONT}")
    return DEFAULT_SUBTITLE_FONT


class ClipManager:
    """MoviePyクリップのリソース管理"""

    def __init__(self):
        self._clips: list[Any] = []

    def track(self, clip: Any) -> Any:
        """クリップを追跡対象に追加"""
        self._clips.append(clip)
        return clip

    def close_all(self) -> None:
        """追跡中の全クリップを解放"""
        for clip in self._clips:
            try:
                if hasattr(clip, "close"):
                    clip.close()
            except Exception as e:
                logger.debug(f"クリップ解放エラー（無視）: {e}")
        self._clips.clear()


@contextmanager
def managed_clips() -> Generator[ClipManager, None, None]:
    """クリップのリソース管理コンテキストマネージャー"""
    manager = ClipManager()
    try:
        yield manager
    finally:
        manager.close_all()


class VideoComposer:
    """動画合成クラス"""

    def __init__(
        self,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
        font: str | None = None,
    ):
        """
        Args:
            width: 動画の幅
            height: 動画の高さ
            fps: フレームレート
            font: 字幕用フォント名
        """
        self.width = width or config.VIDEO_WIDTH
        self.height = height or config.VIDEO_HEIGHT
        self.fps = fps or config.VIDEO_FPS
        self.font = font or _find_available_font()
        logger.info(f"VideoComposer初期化: {self.width}x{self.height}@{self.fps}fps, font={self.font}")

    def _create_background_clip(
        self,
        source_path: Path,
        duration: float,
    ) -> VideoFileClip | ImageClip:
        """背景クリップを作成（動画または画像）"""
        suffix = source_path.suffix.lower()

        if suffix in [".mp4", ".mov", ".avi", ".webm"]:
            clip = VideoFileClip(str(source_path))
            # ループして必要な長さにする
            if clip.duration < duration:
                loops = int(duration / clip.duration) + 1
                clip = concatenate_videoclips([clip] * loops)
            clip = clip.subclipped(0, duration)
        else:
            clip = ImageClip(str(source_path))
            clip = clip.with_duration(duration)

        # リサイズ（カバーするようにフィット）
        clip = clip.resized(height=self.height)
        if clip.w < self.width:
            clip = clip.resized(width=self.width)

        # 中央でクロップ
        x_center = clip.w / 2
        y_center = clip.h / 2
        clip = clip.cropped(
            x1=x_center - self.width / 2,
            y1=y_center - self.height / 2,
            x2=x_center + self.width / 2,
            y2=y_center + self.height / 2,
        )

        return clip

    def _create_subtitle_clip(
        self,
        text: str,
        duration: float,
        fontsize: int = SUBTITLE_FONT_SIZE,
        color: str = "white",
        stroke_color: str = "black",
        stroke_width: int = SUBTITLE_STROKE_WIDTH,
    ) -> TextClip:
        """字幕クリップを作成"""
        clip = TextClip(
            text=text,
            font=self.font,
            font_size=fontsize,
            color=color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            method="caption",
            size=(self.width - SUBTITLE_PADDING, None),
            text_align="center",
        )
        clip = clip.with_duration(duration)
        clip = clip.with_position(("center", self.height - SUBTITLE_MARGIN_BOTTOM))
        return clip

    async def compose_from_assets(
        self,
        audio_files: list[dict[str, Any]],
        image_files: list[dict[str, Any]],
        background_path: Path | None = None,
        clip_manager: ClipManager | None = None,
    ) -> CompositeVideoClip:
        """
        アセットから動画を合成

        Args:
            audio_files: 音声ファイル情報のリスト
            image_files: 画像ファイル情報のリスト
            background_path: 背景動画/画像のパス
            clip_manager: クリップ管理（リソース解放用）

        Returns:
            合成された動画クリップ
        """
        logger.info("動画合成を開始")

        # クリップ管理がなければダミーを作成
        track = clip_manager.track if clip_manager else lambda x: x

        clips = []
        audio_clips = []
        current_time = 0.0

        # 音声と画像のペアからクリップを作成
        for audio_info in audio_files:
            audio_path = Path(audio_info["filepath"])
            duration = audio_info.get("duration", 3.0)
            index = audio_info.get("index", 0)
            text = audio_info.get("text", "")

            # 対応する画像を探す
            image_info = next(
                (img for img in image_files if img.get("index") == index),
                None,
            )

            # 背景クリップを作成
            if background_path and background_path.exists():
                bg_clip = track(self._create_background_clip(background_path, duration))
            elif image_info and image_info.get("filepath"):
                # 画像を背景として使用
                bg_clip = track(
                    self._create_background_clip(
                        Path(image_info["filepath"]),
                        duration,
                    )
                )
            else:
                # 黒背景
                from moviepy import ColorClip

                bg_clip = track(
                    ColorClip(
                        size=(self.width, self.height),
                        color=(0, 0, 0),
                    ).with_duration(duration)
                )

            # 字幕を追加
            if text:
                subtitle_clip = track(self._create_subtitle_clip(text, duration))
                composite = track(CompositeVideoClip([bg_clip, subtitle_clip]))
            else:
                composite = bg_clip

            composite = composite.with_start(current_time)
            clips.append(composite)

            # 音声クリップ
            audio_clip = track(AudioFileClip(str(audio_path)))
            audio_clips.append(audio_clip)

            current_time += duration

        # クリップを結合
        if clips:
            final_video = track(CompositeVideoClip(clips, size=(self.width, self.height)))
        else:
            raise ValueError("合成するクリップがありません")

        # 音声を結合
        if audio_clips:
            final_audio = track(concatenate_audioclips(audio_clips))
            final_video = final_video.with_audio(final_audio)

        logger.info(f"動画合成完了: 長さ{current_time:.2f}秒")
        return final_video

    async def compose_and_save(
        self,
        audio_metadata_path: Path,
        image_metadata_path: Path,
        background_path: Path | None = None,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        メタデータから動画を合成してファイルに保存

        Args:
            audio_metadata_path: 音声メタデータJSONのパス
            image_metadata_path: 画像メタデータJSONのパス
            background_path: 背景動画/画像のパス
            output_path: 出力ファイルパス

        Returns:
            保存結果
        """
        config.ensure_directories()

        # メタデータを読み込み
        audio_metadata = FileHandler.load_json(audio_metadata_path)
        image_metadata = FileHandler.load_json(image_metadata_path)

        audio_files = audio_metadata.get("files", [])
        image_files = image_metadata.get("files", [])

        # 出力パスを決定
        if output_path is None:
            filename = FileHandler.generate_filename("video", "mp4")
            output_path = config.videos_output_dir / filename

        # ClipManagerを使ってリソースを確実に解放
        with managed_clips() as clip_manager:
            # 動画を合成
            video = await self.compose_from_assets(
                audio_files=audio_files,
                image_files=image_files,
                background_path=background_path,
                clip_manager=clip_manager,
            )

            # 動画を書き出し
            logger.info(f"動画を書き出し中: {output_path}")
            video.write_videofile(
                str(output_path),
                fps=self.fps,
                codec=config.VIDEO_CODEC,
                audio_codec=config.AUDIO_CODEC,
                threads=4,
                logger=None,  # MoviePyのログを抑制
            )
            # with文終了時に全クリップが自動解放される

        file_size = FileHandler.get_file_size_mb(output_path)
        logger.info(f"動画を保存しました: {output_path} ({file_size:.2f}MB)")

        return {
            "filepath": str(output_path),
            "duration": audio_metadata.get("total_duration", 0),
            "file_size_mb": file_size,
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
        }


async def main():
    """CLI実行用"""
    parser = argparse.ArgumentParser(description="動画を合成")
    parser.add_argument(
        "--audio-metadata", "-a", help="音声メタデータJSONのパス"
    )
    parser.add_argument(
        "--image-metadata", "-i", help="画像メタデータJSONのパス"
    )
    parser.add_argument("--background", "-b", help="背景動画/画像のパス")
    parser.add_argument("--output", "-o", help="出力ファイルパス")
    parser.add_argument("--width", "-W", type=int, default=1080, help="動画の幅")
    parser.add_argument("--height", "-H", type=int, default=1920, help="動画の高さ")
    parser.add_argument("--fps", type=int, default=30, help="フレームレート")
    parser.add_argument("--input-json", help="入力パラメータJSONファイルのパス（n8n連携用）")

    args = parser.parse_args()

    # JSONファイルからパラメータを読み込み（n8n連携用）
    if args.input_json:
        import json

        with open(args.input_json, encoding="utf-8") as f:
            params = json.load(f)
        args.audio_metadata = params.get("audio_metadata_path")
        args.image_metadata = params.get("image_metadata_path")
        args.output = params.get("output_path")
        args.background = params.get("background_path")

    if not args.audio_metadata or not args.image_metadata:
        parser.error("--audio-metadata と --image-metadata、または --input-json が必要です")

    composer = VideoComposer(
        width=args.width,
        height=args.height,
        fps=args.fps,
    )

    result = await composer.compose_and_save(
        audio_metadata_path=Path(args.audio_metadata),
        image_metadata_path=Path(args.image_metadata),
        background_path=Path(args.background) if args.background else None,
        output_path=Path(args.output) if args.output else None,
    )

    print(f"動画を保存しました: {result['filepath']}")
    print(f"長さ: {result['duration']:.2f}秒")
    print(f"サイズ: {result['file_size_mb']:.2f}MB")


if __name__ == "__main__":
    asyncio.run(main())
