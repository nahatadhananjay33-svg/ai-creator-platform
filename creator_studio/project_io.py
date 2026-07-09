"""Creator Studio project persistence (Phase C12) — open / save a ReelProject.

The Project Manager needs to write an editable reel to disk and read it back
byte-stably. A Studio project file is just the editable model serialized: the AI
storyboard (reusing the C10 storyboard serializer — no schema duplicated) plus the
reel-wide presentation settings and the current revision. Deterministic field
order keeps saves reproducible and diff-friendly.

This is an interface-layer concern only: it serializes the SAME immutable
:class:`~editing_engine.ReelProject` the engine owns and reconstructs it exactly
(revision preserved), never inventing new model state.
"""
from __future__ import annotations

import json
from pathlib import Path

from script_engine.storyboard.serde import storyboard_from_dict, storyboard_to_dict

from editing_engine.project import ReelProject

#: Bumped only if the Studio project envelope changes incompatibly. The nested
#: storyboard carries its own ``schema_version`` (owned by the Script Engine).
STUDIO_PROJECT_SCHEMA_VERSION = 1

#: The presentation settings the Studio persists (everything on ReelProject that
#: is not the storyboard or the revision). Kept as an explicit allow-list so a
#: future ReelProject field is a deliberate, reviewed addition here.
_PRESENTATION_FIELDS = (
    "theme", "soundtrack", "caption_kind", "caption_preset",
    "width", "height", "fps", "creator", "channel",
)


def project_to_dict(project: ReelProject) -> dict:
    """Serialize a :class:`ReelProject` to a plain, deterministic mapping."""
    return {
        "schema_version": STUDIO_PROJECT_SCHEMA_VERSION,
        "revision": project.revision,
        "presentation": {f: getattr(project, f) for f in _PRESENTATION_FIELDS},
        "storyboard": storyboard_to_dict(project.storyboard),
    }


def project_from_dict(d: dict) -> ReelProject:
    """Reconstruct a :class:`ReelProject` from :func:`project_to_dict` output.

    The revision is preserved so an opened project keeps its edit-count identity;
    unknown presentation keys are ignored and missing ones fall back to the
    ReelProject defaults."""
    storyboard = storyboard_from_dict(d.get("storyboard", {}))
    presentation = d.get("presentation", {})
    settings = {f: presentation[f] for f in _PRESENTATION_FIELDS if f in presentation}
    return ReelProject(
        storyboard=storyboard, revision=int(d.get("revision", 0)), **settings)


def project_to_json(project: ReelProject, *, indent: int | None = 2) -> str:
    """Serialize a project to a JSON string (stable field order)."""
    return json.dumps(project_to_dict(project), indent=indent, ensure_ascii=False)


def project_from_json(text: str) -> ReelProject:
    """Parse a project from a JSON string."""
    return project_from_dict(json.loads(text))


def save_project(project: ReelProject, path: Path | str) -> Path:
    """Write ``project`` to ``path`` as JSON and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project_to_json(project), encoding="utf-8")
    return path


def load_project(path: Path | str) -> ReelProject:
    """Read a :class:`ReelProject` back from ``path``."""
    return project_from_json(Path(path).read_text(encoding="utf-8"))
