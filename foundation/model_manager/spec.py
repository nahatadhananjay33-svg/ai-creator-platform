"""Model specification dataclasses.

A :class:`ModelSpec` is the single source of truth about a model: identity,
source, license, and hardware needs. Voice adapters, the benchmark, reports,
and (later) production serving all read the same spec — never duplicate this
information elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class LicenseInfo:
    """License and commercial-use posture of a model.

    ``commercial_use`` is the practical answer for *our* platform, taking the
    checkpoint license into account, not just the code license (they often
    differ — e.g. MIT code with CC-BY-NC weights).
    """

    code_license: str
    weights_license: str
    commercial_use: bool
    notes: str = ""


@dataclass(frozen=True)
class HardwareRequirements:
    """Practical hardware envelope for running the model."""

    min_vram_gb: float | None  # None -> runs on CPU
    recommended_vram_gb: float | None
    min_ram_gb: float
    cpu_realtime_capable: bool
    disk_size_gb: float
    notes: str = ""


@dataclass(frozen=True)
class ModelSpec:
    """Complete static description of a model."""

    model_id: str  # platform-unique, e.g. "f5-tts"
    display_name: str
    family: str  # e.g. "tts", "face", "llm"
    version: str
    repo_url: str
    weights_source: str  # HF repo id or URL
    license: LicenseInfo
    hardware: HardwareRequirements
    parameters_millions: float | None = None
    languages: tuple[str, ...] = ()
    tags: tuple[str, ...] = field(default_factory=tuple)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
