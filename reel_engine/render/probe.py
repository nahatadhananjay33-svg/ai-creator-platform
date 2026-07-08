"""ffprobe wrapper (Phase C2) — verify rendered output is real and playable.

Self-contained (subprocess to ``ffprobe``); does NOT import avatar_engine's
OpenCV probe, keeping reel_engine free of the avatar dependency. Used by the
demo/benchmark validation, not by the hermetic unit tests (those read the mock's
raw-AVI back with the stdlib reader instead).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from foundation.exceptions import PlatformError
from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path


@dataclass(frozen=True)
class MediaProbe:
    duration_s: float
    width: int
    height: int
    fps: float
    n_frames: int
    has_audio: bool
    readable: bool


def ffprobe_available() -> bool:
    ensure_ffmpeg_on_path()
    return shutil.which("ffprobe") is not None


def _parse_fps(rate: str) -> float:
    try:
        num, den = rate.split("/")
        return round(float(num) / float(den), 3) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def probe_media(path: Path | str) -> MediaProbe:
    """Probe a media file with ffprobe. Raises if unreadable."""
    ensure_ffmpeg_on_path()
    path = Path(path)
    if shutil.which("ffprobe") is None:
        raise PlatformError("ffprobe not found on PATH")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise PlatformError(f"ffprobe failed: {proc.stderr[-300:]}", path=str(path))
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    if not vstreams:
        raise PlatformError("no video stream in output", path=str(path))
    v = vstreams[0]
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or v.get("duration") or 0.0)
    fps = _parse_fps(v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1")
    n_frames = int(v.get("nb_frames") or 0) or (int(round(duration * fps)) if fps else 0)
    return MediaProbe(
        duration_s=round(duration, 3), width=int(v.get("width", 0)),
        height=int(v.get("height", 0)), fps=fps, n_frames=n_frames,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        readable=int(v.get("width", 0)) > 0,
    )
