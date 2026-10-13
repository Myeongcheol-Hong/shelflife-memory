import socket
from datetime import UTC, datetime

import pytest

from shelflife.store import Store

NOW = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never touch the live network (CLAUDE.md). Fetchers are injected instead."""

    def refuse(*args, **kwargs):
        raise RuntimeError("tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(tmp_path, clock):
    with Store(tmp_path / "shelflife.db", now=clock) as s:
        yield s
