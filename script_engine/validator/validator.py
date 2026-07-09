"""AI Storyboard validation (Phase C10).

AI output is untrusted: before a generated :class:`AIStoryboard` is fed into the
deterministic pipeline it must pass explicit checks. Validation returns a list of
human-readable problems (empty == valid); :func:`validate_or_raise` turns a
non-empty list into a single :class:`ScriptValidationError`. Pure inspection — no
provider call, no I/O.

Checks (per the objective):
  - required fields (title, non-empty scenes)
  - scene count within ``[min_scenes, max_scenes]``
  - duration estimates non-negative (and total within a sane bound)
  - no empty narration
  - no duplicate scenes (identical narration)
  - only supported scene types
"""
from __future__ import annotations

from script_engine.storyboard.types import (
    SUPPORTED_SCENE_TYPES,
    AIStoryboard,
)

#: A generated brief longer than this (estimated) is almost certainly malformed;
#: flagged as a problem so it never reaches the renderer.
_MAX_TOTAL_DURATION_S = 600.0
_MAX_SCENE_WORDS = 200


class ScriptValidationError(Exception):
    """An AI-generated storyboard failed validation (carries every problem)."""

    def __init__(self, message: str, problems: list[str]) -> None:
        super().__init__(message + ":\n  " + "\n  ".join(problems))
        self.problems = problems


def validate_storyboard(sb: AIStoryboard, *, min_scenes: int = 1,
                        max_scenes: int = 20) -> list[str]:
    """Return a list of problems; empty means the storyboard is usable."""
    problems: list[str] = []

    # required top-level fields
    if not (sb.title and sb.title.strip()):
        problems.append("missing required field: title")
    if not sb.scenes:
        problems.append("storyboard has no scenes")

    # scene count bounds
    n = sb.n_scenes
    if n and n < min_scenes:
        problems.append(f"too few scenes: {n} < min {min_scenes}")
    if n > max_scenes:
        problems.append(f"too many scenes: {n} > max {max_scenes}")

    # per-scene checks
    seen: dict[str, int] = {}
    for i, scene in enumerate(sb.scenes):
        where = f"scene[{i}]"
        text = (scene.narration or "").strip()
        if not text:
            problems.append(f"{where}: empty narration")
        else:
            key = " ".join(text.lower().split())
            if key in seen:
                problems.append(
                    f"{where}: duplicate scene (identical narration to scene[{seen[key]}])")
            else:
                seen[key] = i
            if scene.word_count > _MAX_SCENE_WORDS:
                problems.append(
                    f"{where}: narration too long ({scene.word_count} words > {_MAX_SCENE_WORDS})")
        if scene.scene_type not in SUPPORTED_SCENE_TYPES:
            problems.append(
                f"{where}: unsupported scene_type {scene.scene_type!r} "
                f"(expected one of {SUPPORTED_SCENE_TYPES})")
        if scene.duration_estimate_s < 0:
            problems.append(
                f"{where}: negative duration_estimate_s {scene.duration_estimate_s}")

    # total duration sanity (only meaningful when the AI supplied estimates)
    total = sb.total_duration_estimate_s
    if total > _MAX_TOTAL_DURATION_S:
        problems.append(
            f"total duration estimate {total}s exceeds {_MAX_TOTAL_DURATION_S}s")

    return problems


def validate_or_raise(sb: AIStoryboard, *, min_scenes: int = 1,
                      max_scenes: int = 20) -> AIStoryboard:
    """Return ``sb`` if valid, else raise :class:`ScriptValidationError` listing
    every problem at once."""
    problems = validate_storyboard(sb, min_scenes=min_scenes, max_scenes=max_scenes)
    if problems:
        raise ScriptValidationError("AI storyboard is invalid", problems)
    return sb
