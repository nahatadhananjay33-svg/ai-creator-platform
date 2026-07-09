"""Scene & Storyboard Planning Engine facade (Phase C7).

The high-level, reusable API: turn a finished script into a deterministic
:class:`Storyboard`, and lower that storyboard into the existing Timeline IR. It
wires the rule layers —

    segmentation -> classification -> timing -> visual planning  (planner)
    storyboard -> Timeline + captions                            (timeline builder)

— and nothing else. It produces *plan data* and Timeline-native structures; it
never generates a script, never retrieves an asset, and never touches the
renderer. Everything is configuration-driven and deterministic: the same
(script, config) is always the same storyboard, byte for byte.
"""
from __future__ import annotations

from foundation.logging import get_logger
from reel_engine.interfaces.types import CaptionStyle, Timeline

from scene_engine.config.settings import SceneEngineConfig, load_scene_engine_config
from scene_engine.planner.planner import plan_storyboard
from scene_engine.storyboard.types import Storyboard
from scene_engine.timeline.builder import build_timeline

logger = get_logger("scene_engine")


class SceneEngine:
    """Script -> Storyboard -> Timeline-compatible plan (deterministic, no AI)."""

    def __init__(self, config: SceneEngineConfig | None = None) -> None:
        self.config = config or load_scene_engine_config()

    def plan(
        self,
        script: str,
        *,
        title: str = "untitled",
        known_durations: dict[int, float] | None = None,
        creator: str = "",
        channel: str = "",
    ) -> Storyboard:
        """Plan a :class:`Storyboard` from a finished ``script``.

        ``known_durations`` (scene index -> measured seconds) lets real Voice
        Engine timings replace the per-scene estimate when audio already exists.
        """
        sb = plan_storyboard(
            script, self.config, title=title, known_durations=known_durations,
            creator=creator, channel=channel)
        logger.info("Storyboard planned", extra={"context": {
            "scenes": sb.n_scenes, "duration_s": sb.duration_s,
            "words": sb.word_count, "asset_slots": len(sb.all_asset_slots),
            "types": [t.value for t in sb.scene_types()]}})
        return sb

    def build_timeline(
        self,
        storyboard: Storyboard,
        *,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        with_captions: bool = True,
        caption_style: CaptionStyle | None = None,
        show_labels: bool = True,
        validate: bool = True,
    ) -> Timeline:
        """Lower a :class:`Storyboard` into the existing, validated Timeline IR."""
        tl = build_timeline(
            storyboard, width=width, height=height, fps=fps,
            with_captions=with_captions, caption_kind=self.config.caption_kind,
            caption_style=caption_style, show_labels=show_labels, validate=validate)
        logger.info("Timeline built from storyboard", extra={"context": {
            "scenes": tl.n_scenes, "duration_s": tl.duration_s,
            "captions": tl.has_captions}})
        return tl

    def plan_timeline(
        self,
        script: str,
        *,
        title: str = "untitled",
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        known_durations: dict[int, float] | None = None,
        creator: str = "",
        channel: str = "",
    ) -> tuple[Storyboard, Timeline]:
        """Convenience: plan a storyboard and lower it in one call."""
        sb = self.plan(script, title=title, known_durations=known_durations,
                       creator=creator, channel=channel)
        tl = self.build_timeline(sb, width=width, height=height, fps=fps)
        return sb, tl
