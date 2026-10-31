"""API 段階のテスト補助（fake_server の型）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeServer:
    url: str = ""
    routes: dict[tuple[str, str], tuple[int, object]] = field(default_factory=dict)
    requests: list[tuple[str, str, bytes]] = field(default_factory=list)

    def route(self, method: str, path: str, status: int, body: object) -> None:
        self.routes[(method.upper(), path)] = (status, body)
