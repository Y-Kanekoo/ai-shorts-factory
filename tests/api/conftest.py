"""API 段階の共通fixture（development-hub テスト標準）。

- 外部ネットワークへの接続を遮断する（ループバックだけ許可）。
- `fake_server`: 外部APIの代わりに 127.0.0.1 の空きポートで
  JSON を返すフェイクサーバー。
  `fake_server.route("GET", "/v1/items", 200, {...})` で応答を登録し、
  `fake_server.url` をテスト対象のクライアントへ渡す。
  受けたリクエストは `fake_server.requests` に残る。
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from .api_support import FakeServer

LOOPBACK = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    original = socket.socket.connect

    def guarded(self: socket.socket, address: object) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0] if isinstance(address, tuple) else address
            if host not in LOOPBACK:
                raise RuntimeError(
                    "テストから外部ネットワークへの接続は禁止です（fake_server を使う）"
                )
        original(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield


@pytest.fixture
def fake_server() -> Iterator[FakeServer]:
    fake = FakeServer()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            fake.requests.append((self.command, self.path, self.rfile.read(length)))
            status, body = fake.routes.get(
                (self.command, self.path.split("?", 1)[0]),
                (404, {"error": "未登録の経路"}),
            )
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _reply

        def log_message(self, format: str, *args: object) -> None:
            """アクセスログを出さない。"""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield fake
    finally:
        server.shutdown()
        server.server_close()
