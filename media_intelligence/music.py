"""Music Recommendation (Phase C13) — deterministic soundtrack selection.

Recommends one of the existing procedural soundtracks (``ambient`` / ``cinematic``
/ ``lofi`` / ``upbeat``) for a project from its **tone**, **pacing**, and
**duration** — a fixed, interpretable scoring table, NO model and NO randomness.
The recommendation is advisory: it becomes an immutable ``MusicPatch`` applied
through the Editing Engine (see :meth:`MusicRecommendation.to_patch`), so the
Music Engine, Timeline IR, and renderer are all untouched.
"""
from __future__ import annotations

from dataclasses import dataclass

from music_engine import soundtrack_names

from editing_engine.patches.operations import MusicPatch
from editing_engine.project import ReelProject

#: Base affinity of each tone for each soundtrack (0..1). Tones not listed fall
#: back to a neutral profile. Keys are lowercase storyboard ``tone`` words.
_TONE_AFFINITY = {
    "informative": {"ambient": 0.9, "lofi": 0.6, "cinematic": 0.5, "upbeat": 0.4},
    "educational": {"ambient": 0.9, "lofi": 0.7, "cinematic": 0.5, "upbeat": 0.4},
    "professional": {"ambient": 0.85, "cinematic": 0.6, "lofi": 0.5, "upbeat": 0.4},
    "inspirational": {"cinematic": 0.95, "ambient": 0.6, "upbeat": 0.6, "lofi": 0.4},
    "dramatic": {"cinematic": 0.95, "ambient": 0.5, "lofi": 0.4, "upbeat": 0.3},
    "energetic": {"upbeat": 0.95, "cinematic": 0.6, "ambient": 0.4, "lofi": 0.3},
    "playful": {"upbeat": 0.9, "lofi": 0.6, "ambient": 0.4, "cinematic": 0.4},
    "calm": {"lofi": 0.9, "ambient": 0.8, "cinematic": 0.4, "upbeat": 0.2},
    "relaxed": {"lofi": 0.9, "ambient": 0.8, "cinematic": 0.4, "upbeat": 0.2},
}
_NEUTRAL = {"ambient": 0.7, "cinematic": 0.6, "lofi": 0.6, "upbeat": 0.5}
#: How much pacing nudges the score toward energetic vs calm soundtracks.
_PACING_WEIGHT = 0.4


@dataclass(frozen=True)
class MusicRecommendation:
    """A recommended soundtrack + confidence + the pacing/tone reasoning."""

    soundtrack: str
    confidence: float
    tone: str
    pacing: str                          # "slow" | "medium" | "fast"
    words_per_second: float
    reasons: tuple[str, ...]
    alternatives: tuple[tuple[str, float], ...] = ()   # (name, score) runners-up

    def to_patch(self) -> MusicPatch:
        """The immutable edit that applies this recommendation."""
        return MusicPatch(soundtrack=self.soundtrack)


def _pacing_bucket(wps: float) -> str:
    if wps >= 2.6:
        return "fast"
    if wps <= 1.8:
        return "slow"
    return "medium"


#: Which soundtracks a pacing bucket rewards (energetic beds for fast reels, etc.).
_PACING_BONUS = {
    "fast": {"upbeat": 1.0, "cinematic": 0.5},
    "slow": {"lofi": 1.0, "ambient": 0.7},
    "medium": {"ambient": 0.5, "cinematic": 0.4},
}


class MusicRecommender:
    """Deterministically recommends a soundtrack from tone + pacing + duration."""

    def __init__(self) -> None:
        self._names = set(soundtrack_names())

    def words_per_second(self, project: ReelProject) -> float:
        """Reel pacing = spoken words / estimated duration (deterministic)."""
        words = project.storyboard.word_count
        duration = project.storyboard.total_duration_estimate_s
        if duration <= 0:
            # fall back to a nominal 2.5 wps to estimate duration from word count
            duration = max(1.0, words / 2.5)
        return round(words / duration, 4) if duration else 0.0

    def recommend_music(self, project: ReelProject) -> MusicRecommendation:
        tone = (project.storyboard.tone or "informative").lower()
        affinity = _TONE_AFFINITY.get(tone, _NEUTRAL)
        wps = self.words_per_second(project)
        pacing = _pacing_bucket(wps)
        bonus = _PACING_BONUS.get(pacing, {})

        scores: dict[str, float] = {}
        for name in sorted(self._names):
            base = affinity.get(name, _NEUTRAL.get(name, 0.4))
            scores[name] = round(base + _PACING_WEIGHT * bonus.get(name, 0.0), 6)

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        best, best_score = ranked[0]
        max_possible = 1.0 + _PACING_WEIGHT
        confidence = round(min(1.0, best_score / max_possible), 6)
        reasons = (
            f"tone '{tone}' favours {best}",
            f"{pacing} pacing ({wps:.1f} words/s)",
            f"reel duration {project.storyboard.total_duration_estimate_s:.0f}s",
        )
        return MusicRecommendation(
            soundtrack=best, confidence=confidence, tone=tone, pacing=pacing,
            words_per_second=wps, reasons=reasons,
            alternatives=tuple((n, s) for n, s in ranked[1:]))
