"""Command-line entry points for the avatar research framework.

Importing this package prepends the platform-managed FFmpeg to PATH —
avatar repos (SadTalker, LivePortrait) shell out to ffmpeg/ffprobe.
"""
from __future__ import annotations

from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path

ensure_ffmpeg_on_path()
