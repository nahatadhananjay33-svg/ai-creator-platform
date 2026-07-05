"""Platform-managed FFmpeg location (moved from voice_engine.scripts in A3.5).

torch 2.9+ audio I/O (torchcodec) and every avatar repo (SadTalker,
LivePortrait, ...) need the FFmpeg binaries/DLLs. Phase A1.5 provisioned a
shared build under ``.venvs/_tools/ffmpeg``; this helper prepends it to
PATH so subprocesses inherit it.
"""
from __future__ import annotations

import os

from foundation.constants.paths import PROJECT_ROOT

FFMPEG_BIN = PROJECT_ROOT / ".venvs" / "_tools" / "ffmpeg" / "bin"


def ensure_ffmpeg_on_path() -> bool:
    """Prepend the platform FFmpeg to PATH if present. Returns availability."""
    if FFMPEG_BIN.is_dir():
        current = os.environ.get("PATH", "")
        if str(FFMPEG_BIN) not in current:
            os.environ["PATH"] = f"{FFMPEG_BIN}{os.pathsep}{current}"
        return True
    return False
