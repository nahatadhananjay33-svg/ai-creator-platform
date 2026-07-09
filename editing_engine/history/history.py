"""Edit history — append-only, undo/redo, deterministic replay (Phase C11).

Because patches are immutable and each application yields a NEW
:class:`ReelProject`, an edit history is just an ordered list of (patch, resulting
snapshot). :class:`EditHistory` keeps the base project plus every applied patch,
supports undo/redo, and can **replay** the whole patch sequence from the base to
reproduce the current state deterministically — the audit trail a future Creator
Studio needs. Applying a new patch after an undo discards the redo stack (standard
linear history).
"""
from __future__ import annotations

from editing_engine.patches.base import Patch
from editing_engine.project import ReelProject
from editing_engine.validation.validate import apply_patch


class EditHistory:
    """An append-only, undoable sequence of patches over a base project."""

    def __init__(self, base: ReelProject) -> None:
        self._base = base
        self._snapshots: list[ReelProject] = [base]   # snapshots[0] == base
        self._patches: list[Patch] = []               # patches[i] produced snapshots[i+1]
        self._redo: list[tuple[Patch, ReelProject]] = []

    # ---------------------------------------------------------------- state
    @property
    def base(self) -> ReelProject:
        return self._base

    @property
    def current(self) -> ReelProject:
        return self._snapshots[-1]

    @property
    def n_patches(self) -> int:
        return len(self._patches)

    @property
    def patches(self) -> tuple[Patch, ...]:
        return tuple(self._patches)

    @property
    def can_undo(self) -> bool:
        return len(self._snapshots) > 1

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    # ---------------------------------------------------------------- edits
    def apply(self, patch: Patch, *, validate: bool = True) -> ReelProject:
        """Validate + apply ``patch`` to the current project; record it. Clears redo."""
        result = apply_patch(patch, self.current, validate=validate)
        self._patches.append(patch)
        self._snapshots.append(result)
        self._redo.clear()
        return result

    def undo(self) -> ReelProject:
        """Revert the last applied patch (raises if there is nothing to undo)."""
        if not self.can_undo:
            raise IndexError("nothing to undo")
        snap = self._snapshots.pop()
        patch = self._patches.pop()
        self._redo.append((patch, snap))
        return self.current

    def redo(self) -> ReelProject:
        """Re-apply the most recently undone patch (raises if nothing to redo)."""
        if not self.can_redo:
            raise IndexError("nothing to redo")
        patch, snap = self._redo.pop()
        self._patches.append(patch)
        self._snapshots.append(snap)
        return self.current

    # ---------------------------------------------------------------- replay
    def replay(self, *, validate: bool = True) -> ReelProject:
        """Re-apply every recorded patch from the base and return the result.

        For deterministic patches (all of them with the mock provider) this
        reproduces :attr:`current` exactly — the basis for reproducible edits."""
        project = self._base
        for patch in self._patches:
            project = apply_patch(patch, project, validate=validate)
        return project

    def log(self) -> list[str]:
        """Human-readable one-line summary per applied patch (revision + describe)."""
        return [f"r{i + 1}: {p.describe()}" for i, p in enumerate(self._patches)]
