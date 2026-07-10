"""Artifacts — immutable, content-addressed outputs of a workflow stage (Phase C14).

An :class:`Artifact` is the unit of data that flows between stages. It is a pure,
immutable value identified by ``(name, content_hash)``: two artifacts with the
same content hash are interchangeable, which is exactly what the incremental
executor relies on to decide "unchanged -> reuse". The in-memory ``value`` is
excluded from equality/identity so a reconstructed-from-disk artifact compares
equal to the one that produced it.

Artifacts are *serializable*: every artifact declares a ``kind`` whose codec (see
:mod:`workflow_engine.core.codecs`) can write it to a run directory and read it
back, so a workflow can resume in a fresh process. Structured artifacts (the AI
storyboard, the editable project, the Timeline) round-trip through the engines'
own JSON serializers; file artifacts (voice WAVs, the rendered master, exports)
are already on disk and are addressed by path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from foundation.shared_utils.hashing import sha256_file, sha256_text

# ---- artifact kinds (each maps to a codec) --------------------------------
KIND_STORYBOARD = "storyboard"     # script_engine.AIStoryboard
KIND_PROJECT = "project"           # editing_engine.ReelProject
KIND_TIMELINE = "timeline"         # reel_engine Timeline
KIND_JSON = "json"                 # any JSON-able mapping/list (the value itself)
KIND_FILE = "file"                 # a single file on disk (value is a Path)
KIND_FILESET = "fileset"           # a tuple of files on disk (value is tuple[Path])


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact, UTF-8 preserved, stable for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def hash_json(obj: Any) -> str:
    """Stable SHA-256 of a JSON-able object's canonical form."""
    return sha256_text(canonical_json(obj))


def hash_files(paths: tuple[Path, ...]) -> str:
    """Stable SHA-256 over an ordered set of files (name + content)."""
    parts = [f"{p.name}:{sha256_file(p)}" for p in paths if Path(p).exists()]
    return sha256_text("|".join(parts))


@dataclass(frozen=True)
class Artifact:
    """One immutable, content-addressed stage output.

    ``value`` (the live Python object) and ``meta`` are excluded from equality so
    an artifact decoded from disk on resume is considered identical to the one a
    live run produced — identity is the ``content_hash`` alone.
    """

    name: str
    kind: str
    content_hash: str
    value: Any = field(default=None, compare=False, repr=False)
    path: Path | None = field(default=None, compare=False)
    meta: dict[str, Any] = field(default_factory=dict, compare=False)
    producer: str = field(default="", compare=False)

    def with_value(self, value: Any) -> "Artifact":
        return replace(self, value=value)

    def with_producer(self, producer: str) -> "Artifact":
        return replace(self, producer=producer)

    def descriptor(self) -> dict[str, Any]:
        """The small, JSON-able record persisted in the run journal (no live value)."""
        return {
            "name": self.name,
            "kind": self.kind,
            "content_hash": self.content_hash,
            "path": str(self.path) if self.path is not None else None,
            "meta": self.meta,
            "producer": self.producer,
        }
