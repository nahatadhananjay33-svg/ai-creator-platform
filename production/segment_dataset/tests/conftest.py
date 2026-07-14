"""Hermetic fixtures: synthetic speech/silence builders + network block."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

SR = 16000


def tone(seconds: float, f0: float = 150.0, amp: float = 0.15) -> np.ndarray:
    """Voiced-like periodic signal (fundamental + harmonic) at a given pitch."""
    t = np.arange(int(SR * seconds)) / SR
    return amp * (np.sin(2 * np.pi * f0 * t) + 0.4 * np.sin(2 * np.pi * 2 * f0 * t))


def quiet(seconds: float, amp: float = 1e-4, seed: int = 2) -> np.ndarray:
    return amp * np.random.default_rng(seed).standard_normal(int(SR * seconds))


def speech_with_pauses(spans) -> np.ndarray:
    """Concatenate (kind, seconds[, f0]) spans: 'v' voiced / 's' silence."""
    parts = []
    for span in spans:
        kind, seconds = span[0], span[1]
        if kind == "v":
            f0 = span[2] if len(span) > 2 else 150.0
            parts.append(tone(seconds, f0=f0))
        else:
            parts.append(quiet(seconds))
    return np.concatenate(parts)


def write_wav(path: Path, x: np.ndarray, sr: int = SR) -> Path:
    x = np.clip(np.asarray(x, dtype=np.float64), -1, 1)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return path


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
