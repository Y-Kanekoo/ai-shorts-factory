"""秘密情報スキャン（テスト標準の static 段階）。標準ライブラリのみ。

Git の追跡対象と未追跡（.gitignore 対象外）のテキストから、
既知形式のトークン・秘密鍵・Webhook URL を探す。
検出値は表示せず、ファイル名・行番号・種類だけを出す。
誤検知は行末に `secret-scan: allow` を付けて抑止する
（抑止の追加はレビュー対象）。
詳しい検査には gitleaks（無料）を併用する: `gitleaks dir . --redact`。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

DISCORD = r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com"
SLACK_HOOK = r"https://hooks\.slack\.com/services/"
PATTERNS = {
    "秘密鍵": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
    ),
    "AWS アクセスキー": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "GitHub トークン": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b",
    ),
    "Slack トークン": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "OpenAI/Anthropic 形式の API キー": re.compile(
        r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{32,}\b",
    ),
    "Google API キー": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Discord Webhook URL": re.compile(
        DISCORD + r"/api/webhooks/\d+/[A-Za-z0-9_-]{20,}",
    ),
    "Slack Webhook URL": re.compile(SLACK_HOOK + r"[A-Za-z0-9/]{20,}"),
    "認証情報付き URL": re.compile(
        r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]{6,}@",
    ),
}
ALLOW = "secret-scan: allow"
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".lock",
}


def candidate_files(root: Path) -> list[Path]:
    try:
        command = ["git", "-C", str(root), "ls-files", "-z"]
        command += ["--cached", "--others", "--exclude-standard"]
        # 固定の git コマンドだけを実行する（利用者の入力を引数に渡さない）。
        result = subprocess.run(command, capture_output=True, check=True)
        names = [name for name in result.stdout.decode().split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        ignored = {".git", ".venv", "node_modules", "__pycache__"}
        names = []
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if path.is_file() and not ignored & set(relative.parts):
                names.append(relative.as_posix())
    files = []
    for name in sorted(names):
        if Path(name).suffix.lower() not in SKIP_SUFFIXES:
            files.append(root / name)
    return files


def scan(root: Path) -> list[tuple[str, int, str]]:
    findings = []
    for path in candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if ALLOW in line:
                continue
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    relative = path.relative_to(root).as_posix()
                    findings.append((relative, number, kind))
    return findings


def main(argv: list[str] | None = None) -> int:
    root = Path((argv or sys.argv[1:] or ["."])[0]).resolve()
    findings = scan(root)
    for name, number, kind in findings:
        message = f"{name}:{number}: {kind}の可能性（値は表示しません）"
        print(message, file=sys.stderr)
    if findings:
        summary = f"秘密情報スキャン: {len(findings)} 件を検出しました"
        print(summary, file=sys.stderr)
        return 1
    print("秘密情報スキャン: 検出なし")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
