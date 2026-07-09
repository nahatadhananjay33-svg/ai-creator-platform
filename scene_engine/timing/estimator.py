"""Deterministic timing estimation (Phase C7).

At planning time the narration audio does not exist yet, so scene durations are
*estimated* from word count at a configured pace (words-per-minute) — the same
length-proportional idea the Caption Engine's heuristic provider uses, applied
one level up (per scene instead of per word). The estimate is:

    speech_s = clamp(word_count / wpm * 60, speech_min_s, speech_max_s)
    scene_s  = max(speech_s, min_scene_duration_s, preferred floor for CTA/outro)

Scenes are then laid end-to-end in absolute reel time with a configurable
transition gap (0.0 = hard cut), which guarantees **no overlaps and no gaps**.

Reusing real timing: :func:`plan_timings` accepts ``known_durations`` — a map of
scene index -> measured seconds (e.g. from the Voice Engine once audio exists) —
which overrides the estimate for those scenes while everything else is still
estimated. That is how the planner "reuses existing timing data whenever possible".
"""
from __future__ import annotations

from scene_engine.config.settings import SceneEngineConfig
from scene_engine.storyboard.types import SceneType, TimingPlan


def estimate_speech_s(word_count: int, cfg: SceneEngineConfig) -> float:
    """Estimated narration seconds for ``word_count`` words, clamped to config."""
    raw = (word_count / cfg.words_per_minute) * 60.0
    clamped = max(cfg.speech_min_s, min(raw, cfg.speech_max_s))
    return round(clamped, 3)


def _floor_for(scene_type: SceneType, cfg: SceneEngineConfig) -> float:
    """The minimum scene-window length for a type (preferred CTA/outro length)."""
    if scene_type == SceneType.CALL_TO_ACTION:
        return max(cfg.min_scene_duration_s, cfg.preferred_cta_duration_s)
    if scene_type == SceneType.OUTRO:
        return max(cfg.min_scene_duration_s, cfg.preferred_outro_duration_s)
    return cfg.min_scene_duration_s


def scene_window_s(
    word_count: int,
    scene_type: SceneType,
    cfg: SceneEngineConfig,
    *,
    known_duration_s: float | None = None,
) -> tuple[float, float]:
    """Return ``(speech_s, window_s)`` for one scene.

    ``window_s`` is the on-screen duration: the estimated speech padded up to the
    type's floor. A ``known_duration_s`` (measured audio) replaces the estimate.
    """
    speech = known_duration_s if known_duration_s is not None else estimate_speech_s(
        word_count, cfg)
    window = round(max(speech, _floor_for(scene_type, cfg)), 3)
    return round(speech, 3), window


def plan_timings(
    scenes: list[tuple[int, SceneType]],
    cfg: SceneEngineConfig,
    *,
    known_durations: dict[int, float] | None = None,
) -> list[TimingPlan]:
    """Lay scenes end-to-end in absolute reel time.

    ``scenes`` is ``[(word_count, scene_type), ...]`` in play order. Returns one
    :class:`TimingPlan` per scene, contiguous (``start_s[i] == end_s[i-1]``) with
    a ``transition_s`` gap of zero by default — so the result has no overlaps and
    no gaps. ``known_durations`` maps a scene index to a measured window length.
    """
    known = known_durations or {}
    plans: list[TimingPlan] = []
    cursor = 0.0
    gap = max(0.0, cfg.transition_s)
    for i, (word_count, scene_type) in enumerate(scenes):
        speech, window = scene_window_s(
            word_count, scene_type, cfg, known_duration_s=known.get(i))
        start = round(cursor, 3)
        end = round(start + window, 3)
        plans.append(TimingPlan(
            start_s=start, end_s=end, speech_duration_s=speech,
            transition_in_s=(gap if i > 0 else 0.0),
            transition_out_s=(gap if i < len(scenes) - 1 else 0.0),
        ))
        cursor = end + gap
    return plans
