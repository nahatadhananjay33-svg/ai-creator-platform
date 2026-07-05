"""Frame-level video statistics.

Dependency-free on the platform's raw-AVI interchange format; real codec
files (MP4/H.264 model outputs) are decoded through the optional OpenCV
backend. All metrics run on downsampled grayscale frames so cost stays
bounded regardless of source resolution.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from foundation.exceptions import MetricUnavailableError, PlatformError
from foundation.logging import get_logger
from foundation.shared_utils.video_io import VideoFrames, read_raw_avi

logger = get_logger("avatar_engine.evaluation.video_metrics")

#: Cap on frames analyzed per video (uniform sampling beyond this).
MAX_ANALYZED_FRAMES = 120
#: Grayscale frames are downsampled to at most this many pixels per side.
ANALYSIS_SIZE = 96
#: Mean-luma delta below this counts as a frozen frame pair.
FROZEN_DELTA_THRESHOLD = 0.05


@dataclass(frozen=True)
class VideoStats:
    """Automatic frame statistics of one generated video."""

    n_frames: int
    fps: float
    width: int
    height: int
    duration_s: float
    mean_frame_difference: float
    flicker_index: float
    frozen_frame_ratio: float
    mean_sharpness: float
    sharpness_drift: float
    mean_brightness: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_grayscale_frames(path: Path) -> tuple[list[list[int]], int, int, float, int]:
    """Sampled grayscale frames + (width, height, fps, total_frames)."""
    try:
        video = read_raw_avi(path)
        return _sample_raw(video)
    except PlatformError:
        return _load_with_opencv(path)


def _sample_raw(video: VideoFrames) -> tuple[list[list[int]], int, int, float, int]:
    step = max(1, video.n_frames // MAX_ANALYZED_FRAMES)
    xs = max(1, video.width // ANALYSIS_SIZE)
    ys = max(1, video.height // ANALYSIS_SIZE)
    frames: list[list[int]] = []
    for i in range(0, video.n_frames, step):
        gray = video.grayscale_frame(i)
        frames.append(
            [gray[y * video.width + x]
             for y in range(0, video.height, ys)
             for x in range(0, video.width, xs)]
        )
    w = len(range(0, video.width, xs))
    h = len(range(0, video.height, ys))
    return frames, w, h, video.fps, video.n_frames


def _load_with_opencv(path: Path) -> tuple[list[list[int]], int, int, float, int]:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise MetricUnavailableError(
            "Decoding this codec requires OpenCV: pip install .[video]",
            metric="video_stats",
            path=str(path),
        ) from exc
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise PlatformError(f"OpenCV cannot open video: {path}", path=str(path))
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        step = max(1, total // MAX_ANALYZED_FRAMES) if total else 1
        frames: list[list[int]] = []
        w = h = 0
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gh, gw = gray.shape
                scale = max(1, max(gw, gh) // ANALYSIS_SIZE)
                small = gray[::scale, ::scale]
                h, w = small.shape
                frames.append([int(v) for v in small.flatten()])
            index += 1
        return frames, w, h, fps, total or index
    finally:
        cap.release()


def _laplacian_energy(frame: list[int], width: int, height: int) -> float:
    """Mean absolute 4-neighbor Laplacian — cheap sharpness proxy."""
    if width < 3 or height < 3:
        return 0.0
    total = 0
    count = 0
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            i = row + x
            lap = 4 * frame[i] - frame[i - 1] - frame[i + 1] - frame[i - width] - frame[i + width]
            total += abs(lap)
            count += 1
    return total / count if count else 0.0


def compute_video_stats(path: Path | str) -> VideoStats:
    """Compute automatic frame statistics for a generated video.

    Raises :class:`MetricUnavailableError` when the codec needs the missing
    OpenCV backend, and :class:`PlatformError` for unreadable files.
    """
    path = Path(path)
    frames, width, height, fps, total_frames = _load_grayscale_frames(path)
    if len(frames) < 2:
        raise PlatformError(f"Video too short to analyze: {path}", frames=len(frames))

    n_px = width * height
    means = [sum(f) / n_px for f in frames]

    deltas: list[float] = []
    frozen = 0
    for a, b in zip(frames, frames[1:]):
        delta = sum(abs(pa - pb) for pa, pb in zip(a, b)) / n_px
        deltas.append(delta)
        if delta < FROZEN_DELTA_THRESHOLD:
            frozen += 1
    mean_delta = sum(deltas) / len(deltas)
    flicker = (sum((d - mean_delta) ** 2 for d in deltas) / len(deltas)) ** 0.5

    sharpness = [_laplacian_energy(f, width, height) for f in frames]
    mean_sharp = sum(sharpness) / len(sharpness)
    third = max(1, len(sharpness) // 3)
    first_third = sum(sharpness[:third]) / third
    last_third = sum(sharpness[-third:]) / third
    drift = (last_third - first_third) / first_third if first_third else 0.0

    return VideoStats(
        n_frames=total_frames,
        fps=round(fps, 3),
        width=width,
        height=height,
        duration_s=round(total_frames / fps, 3) if fps else 0.0,
        mean_frame_difference=round(mean_delta, 4),
        flicker_index=round(flicker, 4),
        frozen_frame_ratio=round(frozen / len(deltas), 4),
        mean_sharpness=round(mean_sharp, 4),
        sharpness_drift=round(drift, 4),
        mean_brightness=round(sum(means) / len(means), 2),
    )
