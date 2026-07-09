"""Creator Studio export (Phase C12) — render the latest revision, unmodified.

Export lowers a project's Timeline through the **existing** renderer with no
changes to the renderer or the Timeline IR. It is a thin adapter: the Studio has
already lowered the project to a Timeline (via ``EditingEngine.build_timeline``),
and this module hands that Timeline to ``reel_engine.render.get_renderer`` — the
same ``mock`` (hermetic raw-AVI proxy) and ``ffmpeg`` (real MP4) backends every
other engine uses. Nothing here special-cases a codec or a track; the renderer
stays the single lowering authority.
"""
from __future__ import annotations

from pathlib import Path

from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import RenderRequest, RenderResult, Timeline
from reel_engine.render import get_renderer

#: Master container per backend (mock writes a raw-AVI proxy; ffmpeg a real MP4).
_SUFFIX = {"mock": ".avi", "ffmpeg": ".mp4"}


def render_timeline_to(
    timeline: Timeline,
    output_path: Path | str,
    *,
    renderer: str = "mock",
    export_profiles: tuple[str, ...] = (),
    sample_rate: int | None = None,
) -> RenderResult:
    """Render ``timeline`` to ``output_path`` with the named backend (unmodified).

    The render config's dimensions/fps come from the timeline meta so the output
    matches the project. Returns the engine's :class:`RenderResult` verbatim."""
    meta = timeline.meta
    sr = sample_rate or ReelEngineConfig().render.audio_sample_rate
    config = ReelEngineConfig(render=RenderConfig(
        width=meta.width, height=meta.height, fps=meta.fps,
        renderer=renderer, audio_sample_rate=sr))
    request = RenderRequest(
        timeline=timeline, output_path=Path(output_path),
        renderer=renderer, export_profiles=tuple(export_profiles))
    return get_renderer(renderer, config).render(request)


def default_output_path(directory: Path | str, stem: str, renderer: str) -> Path:
    """The conventional master path for a backend (``<stem><suffix>``)."""
    return Path(directory) / f"{stem}{_SUFFIX.get(renderer, '.mp4')}"
