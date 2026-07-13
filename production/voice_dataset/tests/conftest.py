"""Hermetic test fixtures for the voice dataset builder.

Generates deterministic synthetic WAVs in-process (no ffmpeg, no media files)
and blocks outbound network so the suite is provably offline.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

SR = 16000


def write_wav(path: Path, x, sr: int = SR, channels: int = 1, sampwidth: int = 2) -> Path:
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0)
    if channels > 1:
        x = np.repeat(x[:, None], channels, axis=1).reshape(-1)
    if sampwidth == 2:
        pcm = (x * 32767).astype("<i2").tobytes()
    elif sampwidth == 1:
        pcm = np.clip(x * 128 + 128, 0, 255).astype(np.uint8).tobytes()
    elif sampwidth == 4:
        pcm = (x * 2147483647).astype("<i4").tobytes()
    else:
        raise ValueError("unsupported width")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sr)
        w.writeframes(pcm)
    return Path(path)


def tone(f: float, dur: float, amp: float = 0.15, sr: int = SR) -> np.ndarray:
    t = np.arange(int(sr * dur)) / sr
    return amp * (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t))


def bursts(f: float, n: int, on: float = 0.5, off: float = 0.5,
           amp: float = 0.15, sr: int = SR) -> np.ndarray:
    rng = np.random.default_rng(0)          # fixed seed -> deterministic
    seg = []
    for _ in range(n):
        seg.append(tone(f, on, amp, sr))
        seg.append(1e-4 * rng.standard_normal(int(sr * off)))
    return np.concatenate(seg)


def two_speakers(n: int = 30) -> np.ndarray:
    rng = np.random.default_rng(0)
    seg = []
    for i in range(n):
        seg.append(tone(130 if i % 2 == 0 else 260, 0.8))
        seg.append(1e-4 * rng.standard_normal(int(SR * 0.4)))
    return np.concatenate(seg)


def noisy(f: float = 150.0, n: int = 10) -> np.ndarray:
    base = bursts(f, n)
    return base + 0.08 * np.random.default_rng(1).standard_normal(base.size)


class Synth:
    SR = SR
    write_wav = staticmethod(write_wav)
    tone = staticmethod(tone)
    bursts = staticmethod(bursts)
    two_speakers = staticmethod(two_speakers)
    noisy = staticmethod(noisy)
    silence = staticmethod(lambda secs=5: 1e-4 * np.random.default_rng(2).standard_normal(SR * secs))


@pytest.fixture
def synth() -> Synth:
    return Synth()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Fail loudly if any test attempts an outbound connection."""
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network access is disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
