"""Renderer contract + shared helpers (Phase C2).

A renderer is a pure function ``RenderRequest -> RenderResult``. Two backends
implement it: :class:`~reel_engine.render.mock_renderer.MockRenderer` (hermetic,
raw-AVI proxy, no external deps) and
:class:`~reel_engine.render.ffmpeg_renderer.FFmpegRenderer` (real MP4). Both
share the frame-count/dimension math here so timing stays identical between them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from reel_engine.config.settings import ReelEngineConfig
from reel_engine.interfaces.types import RenderRequest, RenderResult


def scene_frame_count(duration_s: float, fps: int) -> int:
    """Frames for a scene — the single definition both renderers use so the mock
    proxy and the real MP4 have identical frame counts."""
    return max(1, int(round(duration_s * fps)))


def even(n: int) -> int:
    n = int(round(n))
    return n - (n % 2)


def proxy_dimensions(width: int, height: int, max_dim: int) -> tuple:
    """Downscale (width, height) so the longest side == ``max_dim`` while
    preserving aspect ratio; both results are even. Used by the mock renderer to
    keep hermetic raw-AVI output tiny while honouring the target aspect."""
    longest = max(width, height)
    if longest <= max_dim:
        return (max(2, even(width)), max(2, even(height)))
    scale = max_dim / longest
    return (max(2, even(width * scale)), max(2, even(height * scale)))


class TimelineRenderer(ABC):
    """Renders a :class:`Timeline` to a video file."""

    name: str = "base"

    def __init__(self, config: ReelEngineConfig | None = None) -> None:
        self.config = config or ReelEngineConfig()

    @abstractmethod
    def render(self, request: RenderRequest) -> RenderResult:
        """Render ``request.timeline`` to ``request.output_path`` and emit any
        requested export profiles. Must be deterministic for a given Timeline."""
