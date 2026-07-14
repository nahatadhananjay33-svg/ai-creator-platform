"""Hermetic fixtures: synthetic WAVs + network block (no ffmpeg, no Drive)."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

SR = 16000


def _wav(path: Path, x) -> Path:
    x = np.clip(np.asarray(x, dtype=np.float64), -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return Path(path)


def _clean():
    rng = np.random.default_rng(0)
    seg = []
    for _ in range(16):
        t = np.arange(int(SR * 0.5)) / SR
        seg.append(0.15 * (np.sin(2 * np.pi * 150 * t) + 0.4 * np.sin(2 * np.pi * 300 * t)))
        seg.append(1e-4 * rng.standard_normal(int(SR * 0.5)))
    return np.concatenate(seg)


def _silence():
    return 1e-4 * np.random.default_rng(2).standard_normal(SR * 4)


class Synth:
    write_clean = staticmethod(lambda p: _wav(p, _clean()))
    write_silence = staticmethod(lambda p: _wav(p, _silence()))


@pytest.fixture
def synth():
    return Synth()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
