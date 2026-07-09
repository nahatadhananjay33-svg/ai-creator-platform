"""Deterministic review (Phase C11) — the human-in-the-loop inspection step.

The *review* step of the pipeline (``AI Storyboard -> Review -> Patch Set``): a
deterministic pass over a :class:`ReelProject` that surfaces findings a human (or
a future Creator Studio) can act on — long-winded scenes, a missing hook or
call-to-action, duplicate lines, and structural problems from the validator. Each
finding optionally names a concrete suggested patch. No AI, no I/O, no randomness:
the same project always yields the same review.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from editing_engine.patches.base import Patch
from editing_engine.project import ReelProject
from editing_engine.validation.validate import validate_project

#: A narration line longer than this reads as a wall of text for a short reel.
_LONG_SCENE_WORDS = 40
#: ...and shorter than this is probably too thin to stand as its own scene.
_SHORT_SCENE_WORDS = 3


@dataclass(frozen=True)
class ReviewFinding:
    """One reviewer note: a severity, an optional scene index, a message, and an
    optional concrete patch that would address it."""

    severity: str                        # "info" | "warning"
    message: str
    scene_index: int | None = None
    suggestion: Patch | None = None


@dataclass(frozen=True)
class ReviewReport:
    """The result of reviewing a project: an ordered list of findings."""

    findings: tuple[ReviewFinding, ...] = ()

    @property
    def warnings(self) -> tuple[ReviewFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "warning")

    @property
    def infos(self) -> tuple[ReviewFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "info")

    @property
    def ok(self) -> bool:
        """True when the review found no warnings (infos are advisory)."""
        return not self.warnings

    @property
    def suggested_patches(self) -> tuple[Patch, ...]:
        return tuple(f.suggestion for f in self.findings if f.suggestion is not None)


def review_project(project: ReelProject) -> ReviewReport:
    """Deterministically review a project and return a :class:`ReviewReport`."""
    findings: list[ReviewFinding] = []
    scenes = project.scenes

    # structural problems from the shared validator become warnings.
    for problem in validate_project(project):
        findings.append(ReviewFinding("warning", f"validation: {problem}"))

    # opening beat should be a hook; closing beat should be a call to action.
    if scenes:
        if scenes[0].scene_type != "hook":
            findings.append(ReviewFinding(
                "info", "the reel does not open with a hook scene", scene_index=0))
        if not (scenes[-1].cta or scenes[-1].scene_type == "call_to_action"):
            findings.append(ReviewFinding(
                "info", "the reel does not end with a call to action",
                scene_index=len(scenes) - 1))

    # per-scene length checks (with a concrete suggested patch where useful).
    for i, scene in enumerate(scenes):
        wc = scene.word_count
        if wc > _LONG_SCENE_WORDS:
            findings.append(ReviewFinding(
                "warning", f"scene {i} narration is long ({wc} words) — consider tightening",
                scene_index=i))
        elif 0 < wc < _SHORT_SCENE_WORDS:
            findings.append(ReviewFinding(
                "info", f"scene {i} narration is very short ({wc} words)", scene_index=i))

    return ReviewReport(findings=tuple(findings))
