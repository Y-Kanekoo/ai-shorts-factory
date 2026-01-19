"""
AI Shorts Factory - Pytest設定・共通フィクスチャ
"""

import os
from pathlib import Path

import pytest

# テスト時は.envを読み込まないように設定
os.environ.setdefault("HUGGINGFACE_API_TOKEN", "test_token")
os.environ.setdefault("PEXELS_API_KEY", "test_key")


@pytest.fixture
def project_root() -> Path:
    """プロジェクトルートディレクトリ"""
    return Path(__file__).parent.parent


@pytest.fixture
def test_output_dir(tmp_path: Path) -> Path:
    """テスト用出力ディレクトリ"""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scripts").mkdir()
    (output_dir / "audio").mkdir()
    (output_dir / "images").mkdir()
    (output_dir / "videos").mkdir()
    (output_dir / "temp").mkdir()
    return output_dir


@pytest.fixture
def sample_script_data() -> dict:
    """サンプル台本データ"""
    return {
        "title": "知らないと損する雑学",
        "hook": "え、マジで？",
        "narration": [
            {
                "text": "みなさん、これ知ってました？",
                "duration": 2.5,
                "image_prompt": "curious person looking at camera, bright background",
            },
            {
                "text": "実は猫は1日に16時間も寝るんです",
                "duration": 3.0,
                "image_prompt": "cute sleeping cat, soft lighting, cozy atmosphere",
            },
            {
                "text": "いいねとフォローお願いします！",
                "duration": 2.0,
                "image_prompt": "like and subscribe button animation, social media icons",
            },
        ],
        "tags": ["雑学", "豆知識", "猫"],
        "description": "猫の睡眠時間についての雑学動画です",
    }


@pytest.fixture
def sample_voice_settings() -> dict:
    """サンプル音声設定"""
    return {
        "speaker_id": 3,  # ずんだもん
        "speed": 1.0,
        "pitch": 0.0,
        "intonation": 1.0,
        "volume": 1.0,
    }
