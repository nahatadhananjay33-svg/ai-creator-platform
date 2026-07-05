"""Media probing helpers shared by real avatar adapters and validation.

Uses OpenCV (present in every avatar model venv via _PLATFORM_CORE) to read
codec videos; falls back to a clear error, never a fake value.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from foundation.exceptions import ModelError


@dataclass(frozen=True)
class VideoProbe:
    duration_s: float
    fps: float
    width: int
    height: int
    frame_count: int
    readable: bool  # True when frames actually decode (playability check)


def probe_video(path: Path) -> VideoProbe:
    """Probe a video file with OpenCV; verifies the first frame decodes."""
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - venvs always have cv2
        raise ModelError("OpenCV required to probe video output") from exc

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ModelError(f"Video not readable: {path}", path=str(path))
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, _ = cap.read()
        duration = frames / fps if fps > 0 else 0.0
        return VideoProbe(
            duration_s=round(duration, 3), fps=round(fps, 3), width=width,
            height=height, frame_count=frames, readable=bool(ok),
        )
    finally:
        cap.release()
