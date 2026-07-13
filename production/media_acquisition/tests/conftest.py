"""Hermetic test setup: block outbound network for the whole module."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
