"""The immutable project record (Phase C15) — the Content Library's core document.

A :class:`ProjectRecord` is a pure, immutable value describing one creative project:
its prompt and settings, the workflow state of its last run, and references to its
generated outputs. Like every other document on the platform, a record is never
mutated in place — an update returns a NEW record with a bumped ``modified_at`` —
so a saved project is a stable, reproducible snapshot.

Times are supplied by the caller (the library injects a clock), which keeps the
whole model deterministic and testable: a fixed clock yields byte-identical
manifests.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any

from foundation.shared_utils.hashing import short_hash
from foundation.shared_utils.text import slugify

SCHEMA_VERSION = 1

#: Project lifecycle statuses (used by search).
STATUS_DRAFT = "draft"          # created, not yet generated
STATUS_RENDERED = "rendered"    # a workflow run produced playable outputs
STATUS_EXPORTED = "exported"    # deliverables copied into the exports pool
STATUS_ARCHIVED = "archived"    # retired, kept for history
STATUSES = (STATUS_DRAFT, STATUS_RENDERED, STATUS_EXPORTED, STATUS_ARCHIVED)


def make_project_id(title: str, prompt: str = "") -> str:
    """A deterministic, readable id: ``<title-slug>-<6-hex of title|prompt>``."""
    return f"{slugify(title, 48)}-{short_hash(f'{title}|{prompt}', 6)}"


@dataclass(frozen=True)
class OutputRef:
    """A reference to one generated output file (relative to the project directory)."""

    kind: str                    # "master" | "export"
    path: str                    # POSIX-style path relative to the project dir
    content_hash: str = ""       # the workflow artifact's content hash (logical identity)
    profile: str = ""            # export profile name, e.g. "reel_9x16"
    width: int = 0
    height: int = 0
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutputRef":
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in fields})


@dataclass(frozen=True)
class ProjectRecord:
    """An immutable project manifest.

    ``storyboard`` / ``workflow_state`` are compact JSON summaries (the full
    artifacts live in the project's workflow run directory); ``outputs`` reference
    the generated master + exports. Every field is JSON-serializable so the whole
    record round-trips deterministically."""

    project_id: str
    title: str
    prompt: str = ""
    template: str = ""
    tags: tuple[str, ...] = ()
    status: str = STATUS_DRAFT
    presentation: dict[str, Any] = field(default_factory=dict)
    storyboard: dict[str, Any] = field(default_factory=dict)
    workflow_state: dict[str, Any] = field(default_factory=dict)
    outputs: tuple[OutputRef, ...] = ()
    created_at: str = ""
    modified_at: str = ""
    schema_version: int = SCHEMA_VERSION

    # ---- immutable updates ---------------------------------------------------
    def evolve(self, *, now: str, **changes: Any) -> "ProjectRecord":
        """A new record with ``changes`` applied and ``modified_at`` set to ``now``."""
        return dataclasses.replace(self, modified_at=now, **changes)

    def with_tags(self, tags, *, now: str) -> "ProjectRecord":
        return self.evolve(tags=tuple(dict.fromkeys(tags)), now=now)

    # ---- serde ---------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "title": self.title,
            "prompt": self.prompt,
            "template": self.template,
            "tags": list(self.tags),
            "status": self.status,
            "presentation": self.presentation,
            "storyboard": self.storyboard,
            "workflow_state": self.workflow_state,
            "outputs": [o.to_dict() for o in self.outputs],
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProjectRecord":
        return cls(
            project_id=d["project_id"],
            title=d.get("title", ""),
            prompt=d.get("prompt", ""),
            template=d.get("template", ""),
            tags=tuple(d.get("tags", ())),
            status=d.get("status", STATUS_DRAFT),
            presentation=dict(d.get("presentation", {})),
            storyboard=dict(d.get("storyboard", {})),
            workflow_state=dict(d.get("workflow_state", {})),
            outputs=tuple(OutputRef.from_dict(o) for o in d.get("outputs", [])),
            created_at=d.get("created_at", ""),
            modified_at=d.get("modified_at", ""),
            schema_version=int(d.get("schema_version", SCHEMA_VERSION)),
        )

    @classmethod
    def from_json(cls, text: str) -> "ProjectRecord":
        return cls.from_dict(json.loads(text))

    # ---- search-facing summary ----------------------------------------------
    def summary(self) -> dict[str, Any]:
        """The compact record the library index stores for fast search."""
        return {
            "project_id": self.project_id,
            "title": self.title,
            "tags": list(self.tags),
            "status": self.status,
            "template": self.template,
            "n_outputs": len(self.outputs),
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }
