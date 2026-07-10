"""Quality Checker configuration (Phase C16).

The thresholds and limits that turn a measurement into PASS/WARN/FAIL. Kept as a
tiny frozen dataclass (not a YAML-layered config) because the checker is a small,
local, single-user QA step — the defaults are sensible reel limits and the caller
can override any field explicitly. Changing a limit is a config change, never a
code change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityConfig:
    """Thresholds for the deterministic reel checks.

    Duration limits are the vertical-reel norm (>=3s, <=90s). ``audio_sync_tolerance_s``
    is the allowed gap between the audio and video durations. ``expected_width`` /
    ``expected_height`` pin an exact master resolution; when left ``None`` the
    checker verifies the master's *aspect ratio* against the Timeline instead (the
    mock renderer writes an aspect-preserving proxy, so aspect is the invariant
    that holds for both backends)."""

    min_duration_s: float = 3.0
    max_duration_s: float = 90.0
    audio_sync_tolerance_s: float = 0.5
    expected_width: int | None = None
    expected_height: int | None = None

    def __post_init__(self) -> None:
        if self.min_duration_s < 0 or self.max_duration_s <= 0:
            raise ValueError("duration limits must be positive")
        if self.min_duration_s > self.max_duration_s:
            raise ValueError("min_duration_s must be <= max_duration_s")
        if self.audio_sync_tolerance_s < 0:
            raise ValueError("audio_sync_tolerance_s must be >= 0")
