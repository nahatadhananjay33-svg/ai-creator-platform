"""Shared helpers for the engine stages (Phase C14).

The concrete stages compose the existing engines around a single document — the
editable :class:`~editing_engine.ReelProject`. This module holds the small,
engine-free glue every stage reuses:

- :class:`Presentation` — the reel-wide presentation settings (theme / soundtrack /
  caption style / dimensions / brand facts) carried as an immutable stage param, so
  changing any of them re-keys the affected stages' caches;
- :func:`base_project` — build the base ``ReelProject`` from a storyboard + settings
  (just the ReelProject constructor — no engine logic);
- :func:`patch_to_spec` / :func:`patch_from_spec` — marshal an editing-engine
  :class:`Patch` to/from a JSON-able spec so a media plan is fully serializable and
  therefore resumable.

Nothing here re-implements engine behaviour; it only marshals values between the
existing public types.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from editing_engine.patches import PATCH_TYPES, Patch
from editing_engine.project import ReelProject
from script_engine.storyboard.types import AIStoryboard

#: op string -> concrete Patch class, built from the editing engine's own registry.
_OP_TO_CLS: dict[str, type[Patch]] = {cls.op: cls for cls in PATCH_TYPES}


@dataclass(frozen=True)
class Presentation:
    """Reel-wide presentation settings (a value the stages agree on)."""

    theme: str = "modern"
    soundtrack: str = "ambient"
    caption_kind: str = "sentence"
    caption_preset: str = "modern"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    creator: str = ""
    channel: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def base_project(storyboard: AIStoryboard, presentation: Presentation) -> ReelProject:
    """The base editable project for a storyboard + settings (the constructor only)."""
    return ReelProject(storyboard=storyboard, **presentation.to_dict())


def patch_to_spec(patch: Patch) -> dict[str, Any]:
    """A JSON-able spec for an editing-engine patch (``op`` + its fields)."""
    return {"op": patch.op, **dataclasses.asdict(patch)}


def patch_from_spec(spec: dict[str, Any]) -> Patch:
    """Reconstruct a patch from :func:`patch_to_spec` output."""
    d = dict(spec)
    op = d.pop("op")
    try:
        cls = _OP_TO_CLS[op]
    except KeyError:
        raise KeyError(f"unknown patch op {op!r} (known: {sorted(_OP_TO_CLS)})") from None
    return cls(**d)
