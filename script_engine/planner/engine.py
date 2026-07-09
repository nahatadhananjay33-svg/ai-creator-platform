"""AI Prompt & Storyboard Engine facade (Phase C10).

The high-level, reusable API: turn a **prompt** into an :class:`AIStoryboard`
(via a configurable provider), validate it, and feed it into the EXISTING
deterministic Scene Engine — which owns all scene planning, timing, and visual
slotting. This engine's whole job is the front of the pipeline:

    prompt -> provider -> AIStoryboard -> validate -> script -> Scene Engine
           -> deterministic Storyboard -> Timeline IR -> existing pipeline

It never generates video, never modifies the Timeline IR, and never talks to the
renderer. It also does NOT re-implement any scene-planning logic — it lowers the
AI brief to a marker-delimited script and hands it to :class:`SceneEngine`.
"""
from __future__ import annotations

from foundation.logging import get_logger
from reel_engine.interfaces.types import Timeline
from scene_engine import SceneEngine
from scene_engine.storyboard.types import Storyboard as SceneStoryboard

from script_engine.config.settings import ScriptEngineConfig, load_script_engine_config
from script_engine.prompt_templates.registry import get_template
from script_engine.providers import GenerationRequest, StoryboardProvider, get_provider
from script_engine.storyboard.script import storyboard_to_script
from script_engine.storyboard.types import AIStoryboard
from script_engine.validator.validator import validate_or_raise

logger = get_logger("script_engine")


class ScriptEngine:
    """Prompt -> AI Storyboard -> (existing deterministic Scene Engine) -> Timeline."""

    def __init__(
        self,
        config: ScriptEngineConfig | None = None,
        *,
        provider: StoryboardProvider | None = None,
        scene_engine: SceneEngine | None = None,
    ) -> None:
        self.config = config or load_script_engine_config()
        self._provider = provider          # explicit instance overrides config.provider
        self.scene_engine = scene_engine or SceneEngine()

    # ---------------------------------------------------------- AI generation
    def _resolve_provider(self, name: str | None) -> StoryboardProvider:
        if name is None and self._provider is not None:
            return self._provider
        return get_provider(name or self.config.provider)

    def generate_storyboard(
        self,
        prompt: str,
        *,
        template: str | None = None,
        provider: str | None = None,
        validate: bool = True,
    ) -> AIStoryboard:
        """Generate (and validate) an :class:`AIStoryboard` from a ``prompt``.

        The provider comes from ``provider`` (a name), else the explicit provider
        instance passed at construction, else ``config.provider``. Validation
        raises :class:`ScriptValidationError` on a malformed brief."""
        tmpl = get_template(template or self.config.template)
        prov = self._resolve_provider(provider)
        request = GenerationRequest.build(prompt, tmpl, self.config)
        storyboard = prov.generate(request)
        if validate:
            validate_or_raise(storyboard, min_scenes=self.config.min_scenes,
                              max_scenes=self.config.max_scenes)
        logger.info("AI storyboard generated", extra={"context": {
            "provider": storyboard.provider, "model": storyboard.model,
            "template": storyboard.template, "scenes": storyboard.n_scenes,
            "words": storyboard.word_count}})
        return storyboard

    def to_script(self, storyboard: AIStoryboard) -> str:
        """Lower an :class:`AIStoryboard` to the marker-delimited Scene Engine script."""
        return storyboard_to_script(storyboard)

    # -------------------------------------------- hand-off to the Scene Engine
    def plan(
        self,
        prompt: str,
        *,
        template: str | None = None,
        provider: str | None = None,
    ) -> tuple[AIStoryboard, SceneStoryboard]:
        """Prompt -> AI Storyboard -> deterministic Scene-Planner Storyboard.

        The AI brief's scenes become hard boundaries; the existing Scene Engine
        does all the deterministic planning (segmentation, classification, timing,
        visual slots). No scene-planning logic is duplicated here."""
        ai_storyboard = self.generate_storyboard(prompt, template=template, provider=provider)
        script = self.to_script(ai_storyboard)
        scene_storyboard = self.scene_engine.plan(
            script, title=ai_storyboard.title,
            creator=self.config.creator, channel=self.config.channel)
        return ai_storyboard, scene_storyboard

    def plan_timeline(
        self,
        prompt: str,
        *,
        template: str | None = None,
        provider: str | None = None,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
    ) -> tuple[AIStoryboard, SceneStoryboard, Timeline]:
        """Convenience: prompt all the way to the existing, validated Timeline IR."""
        ai_storyboard, scene_storyboard = self.plan(
            prompt, template=template, provider=provider)
        timeline = self.scene_engine.build_timeline(
            scene_storyboard, width=width, height=height, fps=fps)
        return ai_storyboard, scene_storyboard, timeline
