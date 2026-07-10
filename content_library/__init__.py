"""Content Library (Phase C15) — a lightweight, local, single-user content store.

Local folders + JSON metadata only: no cloud, no database server, no auth, no
multi-user. It manages creative **projects** (immutable manifests + their Workflow
Engine run directories) and shared content **pools** (assets, voices, avatars,
music, brands, exports), with deterministic search and Workflow Engine integration.

    content_library/data/
      index.json
      projects/<id>/{project.json, run/}
      assets/ voices/ avatars/ music/ brands/ exports/ cache/

Public API (grows across milestones):
- :class:`ContentLibrary` — open/create a library, manage projects
- :class:`ProjectRecord` / :class:`OutputRef` — the immutable project model
"""
from __future__ import annotations

from content_library.library import ContentLibrary, ProjectNotFound
from content_library.project import (
    STATUSES,
    OutputRef,
    ProjectRecord,
    make_project_id,
)

__version__ = "1.0.0"

__all__ = [
    "ContentLibrary",
    "ProjectNotFound",
    "ProjectRecord",
    "OutputRef",
    "make_project_id",
    "STATUSES",
]
