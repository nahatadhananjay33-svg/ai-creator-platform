"""Artifact codecs (Phase C14) — persist / reload each artifact kind.

The workflow must be able to resume in a *fresh process*, so every artifact has
to survive a round-trip to disk. Rather than invent a new serialization format,
each codec reuses the owning engine's own serializer:

- ``storyboard`` -> ``script_engine.storyboard.serde`` (the C10 JSON schema),
- ``project``    -> the AI storyboard serde + the ReelProject presentation fields,
- ``timeline``   -> ``reel_engine.timeline.serde`` (the frozen Timeline IR schema),
- ``json``       -> the value is already JSON-able (media plans, asset registries,
                    scene-plan / avatar descriptors are all plain dicts),
- ``file`` / ``fileset`` -> already on disk; addressed by path (content-hashed).

Nothing here re-implements engine behaviour; codecs only marshal fields.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from editing_engine.project import ReelProject
from reel_engine.timeline.serde import timeline_from_json, timeline_to_json
from script_engine.storyboard.serde import (
    storyboard_from_dict,
    storyboard_from_json,
    storyboard_to_dict,
    storyboard_to_json,
)

from workflow_engine.core.artifact import (
    KIND_FILE,
    KIND_FILESET,
    KIND_JSON,
    KIND_PROJECT,
    KIND_STORYBOARD,
    KIND_TIMELINE,
    Artifact,
)

# The ReelProject presentation fields we persist (storyboard + revision handled apart).
_PROJECT_FIELDS = ("theme", "soundtrack", "caption_kind", "caption_preset",
                   "width", "height", "fps", "creator", "channel")


def _project_to_json(project: ReelProject) -> str:
    payload = {
        "revision": project.revision,
        "presentation": {f: getattr(project, f) for f in _PROJECT_FIELDS},
        "storyboard": storyboard_to_dict(project.storyboard),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _project_from_json(text: str) -> ReelProject:
    d = json.loads(text)
    storyboard = storyboard_from_dict(d.get("storyboard", {}))
    presentation = d.get("presentation", {})
    settings = {f: presentation[f] for f in _PROJECT_FIELDS if f in presentation}
    return ReelProject(storyboard=storyboard, revision=int(d.get("revision", 0)), **settings)


class Codec:
    """Encode an artifact's value to a run directory and decode it back."""

    #: filename extension for the payload written under the run dir
    ext = ".json"

    def encode(self, artifact: Artifact, run_dir: Path) -> dict[str, Any]:
        """Write the artifact's value under ``run_dir`` and return a payload ref."""
        raise NotImplementedError

    def decode(self, ref: dict[str, Any], run_dir: Path) -> Any:
        """Reconstruct the live value from a payload ref written by :meth:`encode`."""
        raise NotImplementedError


class _TextCodec(Codec):
    """Structured artifact serialized to a single text (JSON) payload file."""

    def __init__(self, dumps: Callable[[Any], str], loads: Callable[[str], Any]) -> None:
        self._dumps = dumps
        self._loads = loads

    def encode(self, artifact: Artifact, run_dir: Path) -> dict[str, Any]:
        payload = run_dir / f"{artifact.name}{self.ext}"
        payload.write_text(self._dumps(artifact.value), encoding="utf-8")
        return {"payload": payload.name}

    def decode(self, ref: dict[str, Any], run_dir: Path) -> Any:
        return self._loads((run_dir / ref["payload"]).read_text(encoding="utf-8"))


class _JsonCodec(Codec):
    """A plain JSON-able value (dict/list); persisted verbatim."""

    def encode(self, artifact: Artifact, run_dir: Path) -> dict[str, Any]:
        payload = run_dir / f"{artifact.name}.json"
        payload.write_text(json.dumps(artifact.value, indent=2, ensure_ascii=False,
                                      default=str), encoding="utf-8")
        return {"payload": payload.name}

    def decode(self, ref: dict[str, Any], run_dir: Path) -> Any:
        return json.loads((run_dir / ref["payload"]).read_text(encoding="utf-8"))


class _FileCodec(Codec):
    """A single file already on disk — addressed by its recorded path."""

    def encode(self, artifact: Artifact, run_dir: Path) -> dict[str, Any]:
        return {"path": str(artifact.path) if artifact.path is not None else None}

    def decode(self, ref: dict[str, Any], run_dir: Path) -> Any:
        return Path(ref["path"]) if ref.get("path") else None


class _FileSetCodec(Codec):
    """A tuple of files already on disk (voice WAVs, exports)."""

    def encode(self, artifact: Artifact, run_dir: Path) -> dict[str, Any]:
        paths = artifact.value or ()
        return {"paths": [str(p) for p in paths]}

    def decode(self, ref: dict[str, Any], run_dir: Path) -> Any:
        return tuple(Path(p) for p in ref.get("paths", []))


_CODECS: dict[str, Codec] = {
    KIND_STORYBOARD: _TextCodec(storyboard_to_json, storyboard_from_json),
    KIND_PROJECT: _TextCodec(_project_to_json, _project_from_json),
    KIND_TIMELINE: _TextCodec(timeline_to_json, timeline_from_json),
    KIND_JSON: _JsonCodec(),
    KIND_FILE: _FileCodec(),
    KIND_FILESET: _FileSetCodec(),
}


def get_codec(kind: str) -> Codec:
    try:
        return _CODECS[kind]
    except KeyError:
        raise KeyError(f"no artifact codec for kind {kind!r} "
                       f"(known: {sorted(_CODECS)})") from None
