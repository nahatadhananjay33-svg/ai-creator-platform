"""Timeline construction helpers (Phase C2).

Thin, deterministic builders over the frozen interfaces — no planning, no AI
(that is Phase C3's scene planner). ``storyboard`` turns a list of
``(color, text, duration)`` tuples into a validated Timeline;
``build_demo_timeline`` is the canonical blue/green/red validation reel used by
the demo script, the benchmark, and the tests.
"""
from __future__ import annotations

from reel_engine.interfaces.types import Scene, Timeline, TimelineMeta
from reel_engine.timeline.validate import validate_or_raise

#: Named colours used by the walking-skeleton demo (RGB).
COLORS: dict[str, tuple] = {
    "black": (0, 0, 0), "white": (255, 255, 255),
    "red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255),
    "yellow": (255, 215, 0), "gray": (128, 128, 128),
}


def new_timeline(
    scenes: list[Scene],
    *,
    title: str = "untitled",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    background_default: tuple = (0, 0, 0),
    validate: bool = True,
) -> Timeline:
    """Build a Timeline from ordered scenes and global metadata."""
    tl = Timeline(
        meta=TimelineMeta(title=title, width=width, height=height, fps=fps,
                          background_default=tuple(background_default)),
        scenes=tuple(scenes),
    )
    return validate_or_raise(tl) if validate else tl


def storyboard(
    beats: list[tuple],
    *,
    title: str = "untitled",
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Timeline:
    """Build a Timeline from ``(color, text, duration_s)`` beats.

    ``color`` may be an RGB tuple or a name from :data:`COLORS`.
    """
    scenes: list[Scene] = []
    for i, beat in enumerate(beats):
        color, text, duration = beat
        rgb = COLORS[color] if isinstance(color, str) else tuple(color)
        role = "title" if i == 0 else ("cta" if i == len(beats) - 1 else "subtitle")
        scenes.append(Scene.simple(index=i, color=rgb, text=text,
                                   duration_s=duration, text_role=role))
    return new_timeline(scenes, title=title, width=width, height=height, fps=fps)


def build_demo_timeline(
    *,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    duration_s: float = 2.0,
) -> Timeline:
    """The canonical 3-scene walking-skeleton reel:

        blue "Title" → green "Subtitle" → red "Call To Action"
    """
    return storyboard(
        [
            ("blue", "Title", duration_s),
            ("green", "Subtitle", duration_s),
            ("red", "Call To Action", duration_s),
        ],
        title="reel_engine C2 demo", width=width, height=height, fps=fps,
    )
