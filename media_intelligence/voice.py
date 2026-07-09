"""Voice Recommendation (Phase C13) — deterministic narrator suggestions (metadata).

Recommends a narrator voice for a project from a small, deterministic voice
catalogue, matching the storyboard's tone/style and a target language (English,
Hindi, Hinglish, Bengali — the platform's first-class languages). This is
**metadata only**: it surfaces which voice fits and why; it makes NO renderer
changes and produces no patch (the ``ReelProject`` carries no voice field in this
phase). NO model, NO audio, NO randomness — the same project + language always
yields the same recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from foundation.constants import Language

from editing_engine.project import ReelProject


@dataclass(frozen=True)
class VoiceMeta:
    """Descriptive metadata for one selectable narrator voice (no audio)."""

    voice_id: str
    display_name: str
    language: str                        # a Language value ("en" | "hi" | "hi-en" | "bn")
    gender: str                          # "female" | "male" | "neutral"
    styles: tuple[str, ...] = ()         # tone/style tags this voice suits
    description: str = ""
    provider: str = "mock"

    @property
    def language_name(self) -> str:
        try:
            from foundation.constants.languages import LANGUAGE_INFO
            return LANGUAGE_INFO[Language.from_code(self.language)].display_name
        except Exception:  # noqa: BLE001
            return self.language


#: A small, deterministic, offline voice catalogue spanning the platform's
#: first-class languages. Purely metadata — a real voice library plugs in later.
VOICE_CATALOG: tuple[VoiceMeta, ...] = (
    VoiceMeta("en_aria", "Aria", "en", "female",
              ("informative", "professional", "calm"), "Warm, clear English narrator"),
    VoiceMeta("en_leo", "Leo", "en", "male",
              ("energetic", "playful", "upbeat"), "Punchy, upbeat English narrator"),
    VoiceMeta("en_nova", "Nova", "en", "neutral",
              ("inspirational", "dramatic", "cinematic"), "Cinematic, resonant English narrator"),
    VoiceMeta("hi_kavya", "Kavya", "hi", "female",
              ("informative", "calm", "professional"), "Clear Hindi narrator"),
    VoiceMeta("hi_arjun", "Arjun", "hi", "male",
              ("energetic", "inspirational"), "Energetic Hindi narrator"),
    VoiceMeta("hien_isha", "Isha", "hi-en", "female",
              ("playful", "energetic", "informative"), "Hinglish code-switching narrator"),
    VoiceMeta("bn_riya", "Riya", "bn", "female",
              ("informative", "calm"), "Gentle Bengali narrator"),
)


@dataclass(frozen=True)
class VoiceRecommendation:
    """A recommended voice + confidence + reasons, plus ranked alternatives."""

    voice: VoiceMeta | None
    confidence: float
    language: str
    reasons: tuple[str, ...] = ()
    alternatives: tuple[VoiceMeta, ...] = field(default_factory=tuple)


class VoiceRecommender:
    """Deterministically recommends a narrator voice (metadata only)."""

    def __init__(self, catalog: tuple[VoiceMeta, ...] = VOICE_CATALOG) -> None:
        self.catalog = tuple(catalog)

    def voices(self, language: str | None = None) -> tuple[VoiceMeta, ...]:
        """Catalogue voices, optionally filtered by language (stable order)."""
        items = self.catalog if language is None else tuple(
            v for v in self.catalog if v.language == language)
        return tuple(sorted(items, key=lambda v: v.voice_id))

    def languages(self) -> tuple[str, ...]:
        return tuple(sorted({v.language for v in self.catalog}))

    def _score(self, voice: VoiceMeta, tone: str) -> float:
        """Style/tone affinity in [0, 1] (fraction of a tone match + a small base)."""
        return 1.0 if tone in voice.styles else 0.25

    def recommend_voice(self, project: ReelProject, *, language: str = "en") -> VoiceRecommendation:
        tone = (project.storyboard.tone or "informative").lower()
        candidates = self.voices(language)
        if not candidates:
            return VoiceRecommendation(
                voice=None, confidence=0.0, language=language,
                reasons=(f"no voice available for language '{language}'",))
        ranked = sorted(candidates, key=lambda v: (-self._score(v, tone), v.voice_id))
        best = ranked[0]
        confidence = round(self._score(best, tone), 6)
        reasons = (
            f"language '{best.language_name}'",
            (f"style matches tone '{tone}'" if tone in best.styles
             else f"closest available for tone '{tone}'"),
            f"{best.gender} voice — {best.description}",
        )
        return VoiceRecommendation(
            voice=best, confidence=confidence, language=language,
            reasons=reasons, alternatives=tuple(ranked[1:]))
