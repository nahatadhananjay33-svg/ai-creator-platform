"""Reels Engine rendering: the deterministic back-end that lowers a Timeline to
video. Two backends share one contract (``TimelineRenderer``): ``mock`` (hermetic
raw-AVI proxy) and ``ffmpeg`` (real MP4).
"""
from __future__ import annotations

from pathlib import Path

from reel_engine.config.settings import ReelEngineConfig
from reel_engine.interfaces.types import RenderRequest, RenderResult, Timeline
from reel_engine.render.base import TimelineRenderer, proxy_dimensions, scene_frame_count
from reel_engine.render.mock_renderer import MockRenderer
from reel_engine.render.probe import MediaProbe, ffprobe_available, probe_media

__all__ = [
    "TimelineRenderer",
    "MockRenderer",
    "MediaProbe",
    "probe_media",
    "ffprobe_available",
    "proxy_dimensions",
    "scene_frame_count",
    "get_renderer",
    "render_timeline",
]


def get_renderer(name: str, config: ReelEngineConfig | None = None) -> TimelineRenderer:
    """Instantiate a renderer by name (``"mock"`` | ``"ffmpeg"``).

    The FFmpeg backend is imported lazily so the mock path (and the whole
    hermetic test suite) never needs ffmpeg present just to import the package.
    """
    if name == "mock":
        return MockRenderer(config)
    if name == "ffmpeg":
        from reel_engine.render.ffmpeg_renderer import FFmpegRenderer
        return FFmpegRenderer(config)
    raise ValueError(f"Unknown renderer {name!r}; expected 'mock' or 'ffmpeg'")


def render_timeline(
    timeline: Timeline,
    output_path: Path | str,
    *,
    config: ReelEngineConfig | None = None,
    renderer: str | None = None,
    export_profiles: tuple | None = None,
) -> RenderResult:
    """Convenience: render a Timeline with the configured (or named) backend."""
    config = config or ReelEngineConfig()
    backend = renderer or config.render.renderer
    profiles = tuple(export_profiles if export_profiles is not None else config.export.profiles)
    request = RenderRequest(timeline=timeline, output_path=Path(output_path),
                            renderer=backend, export_profiles=profiles)
    return get_renderer(backend, config).render(request)
