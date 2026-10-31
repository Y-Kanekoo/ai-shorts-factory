"""API 段階の土台（ネットワーク遮断と fake_server）が働くことの確認。

対象プロジェクトの API・外部連携の契約テストは、このファイルを参考に
`tests/api/test_<対象>_contract.py` として追加する。
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

import pytest

from .api_support import FakeServer


def test_external_network_is_blocked() -> None:
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(RuntimeError, match="外部ネットワーク"),
    ):
        sock.connect(("192.0.2.1", 80))  # TEST-NET-1（RFC 5737）


def test_fake_server_returns_registered_json(fake_server: FakeServer) -> None:
    fake_server.route("GET", "/v1/items", 200, {"items": [1, 2]})
    with urllib.request.urlopen(
        f"{fake_server.url}/v1/items?page=1", timeout=5
    ) as response:
        assert response.status == 200
        assert json.load(response) == {"items": [1, 2]}
    assert fake_server.requests == [("GET", "/v1/items?page=1", b"")]


def test_fake_server_rejects_unregistered_route(fake_server: FakeServer) -> None:
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(f"{fake_server.url}/unknown", timeout=5)
    assert caught.value.code == 404
