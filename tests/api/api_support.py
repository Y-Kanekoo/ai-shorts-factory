"""API 段階のテスト補助（fake_server の型）。"""

from __future__ import annotations

from dataclasses import dataclass, field

Route = tuple[str, str]
Reply = tuple[int, object]
Request = tuple[str, str, bytes]


@dataclass
class FakeServer:
    url: str = ""
    routes: dict[Route, Reply] = field(default_factory=dict)
    requests: list[Request] = field(default_factory=list)

    def route(self, method: str, path: str, status: int, body: object) -> None:
        self.routes[(method.upper(), path)] = (status, body)
