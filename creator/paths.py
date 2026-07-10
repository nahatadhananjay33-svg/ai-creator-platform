"""Standardized single-user workspace layout (Version 1.0).

Version 1.0 gives a single creator ONE predictable place for everything they
produce and reuse: a ``workspace/`` directory with a fixed, documented set of
folders. On a fresh clone you always know where your reels, exports, and logs
land — no hunting through per-engine output directories.

    workspace/
      projects/   one folder per `creator.run` invocation — the full
                  Workflow Engine run (storyboard, voice, timeline, render).
      exports/    finished, platform-ready renditions + upload metadata,
                  copied out of the run for you to upload.
      cache/      content-addressed intermediate artifacts (safe to delete;
                  the workflow rebuilds them on demand).
      assets/     your input images / b-roll / logos.
      voices/     voice reference clips.
      avatars/    avatar portraits.
      music/      background music tracks.
      logs/       per-run logs.

This is purely the user-facing layer the ``creator.run`` command writes into;
it does not move or replace any existing engine paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from foundation.constants.paths import PROJECT_ROOT, ensure_dir

#: The standardized workspace subfolders, in display order.
WORKSPACE_DIRS: tuple[str, ...] = (
    "projects",
    "exports",
    "cache",
    "assets",
    "voices",
    "avatars",
    "music",
    "logs",
)

#: Default workspace root when the user does not configure one.
DEFAULT_WORKSPACE: Path = PROJECT_ROOT / "workspace"


@dataclass(frozen=True)
class Workspace:
    """A single-user workspace rooted at ``root`` with standardized folders."""

    root: Path

    @property
    def projects(self) -> Path:
        return self.root / "projects"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def assets(self) -> Path:
        return self.root / "assets"

    @property
    def voices(self) -> Path:
        return self.root / "voices"

    @property
    def avatars(self) -> Path:
        return self.root / "avatars"

    @property
    def music(self) -> Path:
        return self.root / "music"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    def path(self, name: str) -> Path:
        """Return the standardized subfolder ``name`` (must be a known folder)."""
        if name not in WORKSPACE_DIRS:
            raise KeyError(f"Unknown workspace folder: {name!r}")
        return self.root / name

    def ensure(self) -> "Workspace":
        """Create the workspace root and every standardized subfolder."""
        ensure_dir(self.root)
        for name in WORKSPACE_DIRS:
            ensure_dir(self.root / name)
        return self


def resolve_workspace(root: str | Path | None = None) -> Workspace:
    """Resolve a :class:`Workspace` from ``root`` (defaults to ``<repo>/workspace``).

    An empty string is treated the same as ``None`` so a blank ``paths.root`` in
    the config file falls back to the default.
    """
    base = Path(root).expanduser() if root else DEFAULT_WORKSPACE
    return Workspace(root=base)
