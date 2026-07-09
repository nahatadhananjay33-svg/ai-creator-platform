"""Patch & project validation (Phase C11).

A patch is validated BEFORE it is applied (the objective: "Each patch should
validate before application"), and the resulting project's content is validated
against the same rules the AI Prompt & Storyboard Engine uses — so an edit can
never produce an unrenderable reel. :func:`apply_patch` is the single safe entry
point: validate the patch, apply it, then (optionally) validate the result.
"""
from __future__ import annotations

from script_engine.validator.validator import validate_storyboard

from editing_engine.patches.base import Patch
from editing_engine.project import ReelProject


class PatchError(Exception):
    """A patch could not be applied (carries every problem)."""

    def __init__(self, message: str, problems: list[str]) -> None:
        super().__init__(message + ":\n  " + "\n  ".join(problems))
        self.problems = problems


def validate_patch(patch: Patch, project: ReelProject) -> list[str]:
    """Return the patch's problems against ``project`` (empty == applicable)."""
    return patch.validate(project)


def validate_project(project: ReelProject, *, min_scenes: int = 1,
                     max_scenes: int = 40) -> list[str]:
    """Validate a project's content (its AI storyboard). Empty == usable."""
    return validate_storyboard(project.storyboard, min_scenes=min_scenes,
                               max_scenes=max_scenes)


def apply_patch(patch: Patch, project: ReelProject, *, validate: bool = True,
                validate_result: bool = True) -> ReelProject:
    """Validate ``patch`` against ``project``, apply it, and return the new project.

    With ``validate`` the patch's preconditions are checked first; with
    ``validate_result`` the resulting project's content is re-validated. Either
    failure raises :class:`PatchError` with every problem."""
    if validate:
        problems = patch.validate(project)
        if problems:
            raise PatchError(f"patch {patch.op!r} is invalid", problems)
    result = patch.apply(project)
    if validate_result:
        problems = validate_project(result)
        if problems:
            raise PatchError(f"patch {patch.op!r} produced an invalid project", problems)
    return result
