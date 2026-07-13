"""Audio extraction (Step 2).

WAV inputs pass through unchanged (original sample rate preserved). Other audio
or video inputs are decoded to WAV with ffmpeg, keeping the source sample rate
and channel count. ffmpeg is only required when a non-WAV file is present, so
WAV-only runs (and the test suite) need no external binaries.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import AUDIO_EXTS, VIDEO_EXTS


class ExtractionError(Exception):
    """Raised when a source file could not be turned into a WAV."""


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def extract_audio(src: Path, out_dir: Path) -> Path:
    """Produce a WAV for ``src`` in ``out_dir`` and return its path."""
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / (src.stem + ".wav")
    ext = src.suffix.lower()

    if ext == ".wav":                      # passthrough, keep original sample rate
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        return dst

    if ext not in (AUDIO_EXTS | VIDEO_EXTS):
        raise ExtractionError(f"unsupported input type: {src.name}")

    if not has_ffmpeg():
        raise ExtractionError(
            f"ffmpeg is required to extract audio from '{src.name}'. "
            "Install ffmpeg, or export your media to WAV first."
        )

    # -vn drop video; keep source sample rate (no -ar) and channels (no -ac).
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(src), "-vn", "-acodec", "pcm_s16le", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dst.exists():
        raise ExtractionError(f"ffmpeg failed for '{src.name}': {proc.stderr.strip()[:200]}")
    return dst
