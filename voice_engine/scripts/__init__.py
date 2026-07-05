"""Executable entry points for the Voice Engine.

Importing this package prepares the process environment for model
execution: the platform-managed FFmpeg build is prepended to PATH (helper
moved to foundation.shared_utils.ffmpeg in Phase A3.5; re-exported here for
backward compatibility).
"""
from __future__ import annotations

from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path

ensure_ffmpeg_on_path()

__all__ = ["ensure_ffmpeg_on_path"]
