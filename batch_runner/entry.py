"""One reel's request in a batch (Phase C20).

A :class:`BatchEntry` is pure data: what to generate and where it lands. It
carries the two things every reel needs — a ``prompt`` and a ``template`` — an
``output`` folder name (its stable identity for resume + de-duplication), and an
optional nested ``overrides`` mapping shaped exactly like ``creator/config.yaml``
(``generation`` / ``branding`` / ``quality`` / ``paths``).

The entry never runs anything; :mod:`batch_runner.runner` turns it into a
``CreatorConfig`` and hands it to ``creator.run`` unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from foundation.config.loader import deep_merge
from foundation.shared_utils.text import slugify


@dataclass(frozen=True)
class BatchEntry:
    """A single reel to generate."""

    prompt: str
    template: str | None = None
    output: str | None = None
    overrides: Mapping[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Stable identity: the output folder / run name (a filesystem-safe slug).

        Repeat runs of the same entry reuse this folder, and two entries with the
        same name are rejected as duplicates at load time.
        """
        return slugify(self.output or self.prompt) or "reel"

    def config_overrides(self) -> dict[str, Any]:
        """The nested overrides to feed ``load_creator_config`` for this reel.

        Layers the entry's prompt/template under ``generation`` and merges any
        extra ``overrides`` on top (so a per-entry ``renderer`` etc. wins).
        """
        gen: dict[str, Any] = {"prompt": self.prompt}
        if self.template:
            gen["template"] = self.template
        return deep_merge({"generation": gen}, dict(self.overrides))
