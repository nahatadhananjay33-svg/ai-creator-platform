"""Hermetic fixtures: synthetic WAVs + network block (no ffmpeg/ffprobe needed)."""
from __future__ import annotations

import io
import wave

import numpy as np
import pytest

SR = 16000


def wav_bytes(x) -> bytes:
    x = np.clip(np.asarray(x, dtype=np.float64), -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def clean_speech(seconds: float = 16.0) -> bytes:
    rng = np.random.default_rng(0)
    seg = []
    for _ in range(int(seconds)):
        t = np.arange(int(SR * 0.5)) / SR
        seg.append(0.15 * (np.sin(2 * np.pi * 150 * t) + 0.4 * np.sin(2 * np.pi * 300 * t)))
        seg.append(1e-4 * rng.standard_normal(int(SR * 0.5)))
    return wav_bytes(np.concatenate(seg))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
