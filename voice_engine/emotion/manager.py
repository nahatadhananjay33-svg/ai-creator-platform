"""Emotion and style control normalized across engines.

Callers express emotion once (:class:`Emotion` + intensity); the manager
translates it into whatever the target engine understands:

- ``exaggeration``: Chatterbox-style numeric emotion exaggeration knob.
- ``instruct``: natural-language style instruction (CosyVoice 2 instruct
  mode, Parler-style description conditioning).
- ``hint``: pass the emotion name through ``SynthesisRequest.emotion`` and
  let the adapter interpret it.
- ``none``: engine has no emotion control; the request passes unchanged.

Strategies are per-engine configuration (``emotion.strategies``), with
sensible defaults for the Phase A1.5 engines.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from foundation.exceptions import ConfigError
from foundation.logging import get_logger
from voice_engine.interfaces import SynthesisRequest, TTSEngine

logger = get_logger("voice_engine.emotion")


class Emotion(str, Enum):
    """Engine-agnostic emotion vocabulary."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    EXCITED = "excited"
    CALM = "calm"
    SAD = "sad"
    ANGRY = "angry"
    SERIOUS = "serious"


@dataclass(frozen=True)
class EmotionSpec:
    """An emotion plus how strongly to render it (0.0 = barely, 1.0 = max)."""

    emotion: Emotion
    intensity: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.intensity <= 1.0:
            raise ConfigError(f"Emotion intensity must be in [0, 1], got {self.intensity}")


#: Strategy names accepted in configuration.
STRATEGIES = ("exaggeration", "instruct", "hint", "none")

#: Defaults for engines whose controls are known from A1 research/validation.
DEFAULT_ENGINE_STRATEGIES: dict[str, str] = {
    "chatterbox": "exaggeration",
    "cosyvoice2": "instruct",
    "indic-parler": "instruct",
}

#: Chatterbox exaggeration baseline (0.5 is the model's neutral default).
_NEUTRAL_EXAGGERATION = 0.5


def resolve_emotion(value: "Emotion | EmotionSpec | str | None") -> EmotionSpec | None:
    """Normalize the public API's emotion argument to an :class:`EmotionSpec`."""
    if value is None:
        return None
    if isinstance(value, EmotionSpec):
        return value
    if isinstance(value, Emotion):
        return EmotionSpec(value)
    try:
        return EmotionSpec(Emotion(value.lower()))
    except ValueError:
        raise ConfigError(
            f"Unknown emotion {value!r}", known=[e.value for e in Emotion]
        ) from None


class EmotionManager:
    """Maps engine-agnostic emotions onto per-engine controls."""

    def __init__(self, strategies: dict[str, str] | None = None) -> None:
        merged = {**DEFAULT_ENGINE_STRATEGIES, **(strategies or {})}
        for engine_id, strategy in merged.items():
            if strategy not in STRATEGIES:
                raise ConfigError(
                    f"Unknown emotion strategy {strategy!r} for engine {engine_id!r}",
                    known=STRATEGIES,
                )
        self.strategies = merged

    def strategy_for(self, engine: TTSEngine) -> str:
        configured = self.strategies.get(engine.engine_id)
        if configured is not None:
            return configured
        return "hint" if engine.capabilities.emotion_control else "none"

    def apply(self, request: SynthesisRequest, engine: TTSEngine) -> SynthesisRequest:
        """Render ``request.emotion`` (a name string) for ``engine``."""
        return self.render(request, engine, resolve_emotion(request.emotion))

    def render(
        self,
        request: SynthesisRequest,
        engine: TTSEngine,
        spec: EmotionSpec | None,
    ) -> SynthesisRequest:
        """Return a request whose emotion controls match ``engine``'s strategy.

        ``request.emotion`` carries the engine-agnostic emotion name; the
        strategy decides what additionally lands in ``request.extra``.
        """
        if spec is None or spec.emotion is Emotion.NEUTRAL:
            return request
        strategy = self.strategy_for(engine)
        if strategy == "none":
            logger.debug(
                "Engine has no emotion control; ignoring emotion",
                extra={"context": {"engine": engine.engine_id, "emotion": spec.emotion.value}},
            )
            return replace(request, emotion=None)
        if strategy == "hint":
            return replace(request, emotion=spec.emotion.value)
        if strategy == "exaggeration":
            # Map intensity onto the knob's expressive half [neutral, 1.0];
            # calm/sad reduce exaggeration below neutral instead.
            if spec.emotion in (Emotion.CALM, Emotion.SAD, Emotion.SERIOUS):
                value = _NEUTRAL_EXAGGERATION * (1.0 - 0.6 * spec.intensity)
            else:
                value = _NEUTRAL_EXAGGERATION + (1.0 - _NEUTRAL_EXAGGERATION) * spec.intensity
            extra = {**request.extra, "exaggeration": round(value, 3)}
            return replace(request, emotion=spec.emotion.value, extra=extra)
        # strategy == "instruct"
        degree = "slightly" if spec.intensity < 0.34 else (
            "very" if spec.intensity > 0.67 else ""
        )
        tone = f"{degree} {spec.emotion.value}".strip()
        extra = {**request.extra, "instruct": f"Speak in a {tone} tone."}
        return replace(request, emotion=spec.emotion.value, extra=extra)
