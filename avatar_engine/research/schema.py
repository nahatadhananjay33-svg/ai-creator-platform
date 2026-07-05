"""Research profile schema for avatar generation models.

Extends the platform-wide :class:`foundation.model_manager.ModelSpec`
(identity, license, hardware) with avatar-specific research facts: task
type, repository activity, installation complexity, and qualitative
research ratings. Ratings are ``source="static"`` knowledge — they come
from papers, demos, and community evidence, never from our own benchmark
(benchmark scores live in run results, not here).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from foundation.model_manager import ModelSpec


class AvatarTask(str, Enum):
    """What kind of avatar generation a model performs."""

    #: Animate a portrait image using a driving *video* (expression/pose transfer).
    PORTRAIT_REENACTMENT = "portrait_reenactment"
    #: Generate a talking head video from one image + driving audio.
    AUDIO_DRIVEN_HEAD = "audio_driven_head"
    #: Generate half/full-body animation (gestures) from image + audio.
    AUDIO_DRIVEN_BODY = "audio_driven_body"
    #: Re-sync the lips of an *existing* video to new audio (dubbing).
    VIDEO_LIP_SYNC = "video_lip_sync"


class MaintenanceStatus(str, Enum):
    """How alive the upstream repository is."""

    ACTIVE = "active"        # commits within ~3 months
    SLOWING = "slowing"      # commits within ~12 months, momentum fading
    STALE = "stale"          # no meaningful commits for over a year
    ABANDONED = "abandoned"  # explicitly discontinued or dead >2 years


class InstallComplexity(str, Enum):
    """Practical effort to stand the model up in an isolated venv."""

    LOW = "low"            # pip install + checkpoint download
    MODERATE = "moderate"  # repo clone, manual checkpoints, standard deps
    HIGH = "high"          # fragile pins, compiled deps (mmcv, TensorRT), GPU-only tooling
    SEVERE = "severe"      # known-broken on some platforms / research-grade scaffolding


@dataclass(frozen=True)
class RepositoryActivity:
    """Snapshot of upstream repository health (record the observation date)."""

    stars: int
    last_push: str  # ISO date of last observed push
    maintenance: MaintenanceStatus
    observed_on: str  # ISO date this snapshot was taken
    notes: str = ""


@dataclass(frozen=True)
class ResearchRatings:
    """Qualitative 1-5 ratings distilled from papers, demos, and community.

    These are research priors used for candidate triage and static
    comparison reports. The benchmark replaces them with measured values;
    reports must label them ``static`` so they are never mistaken for
    measurements.
    """

    lip_sync: int
    realism: int
    identity_consistency: int
    expressiveness: int
    motion_naturalness: int

    def overall(self) -> float:
        """Unweighted mean across dimensions."""
        values = (
            self.lip_sync,
            self.realism,
            self.identity_consistency,
            self.expressiveness,
            self.motion_naturalness,
        )
        return round(sum(values) / len(values), 2)


@dataclass(frozen=True)
class AvatarModelProfile:
    """Complete research profile of one candidate avatar model."""

    spec: ModelSpec
    task: AvatarTask
    activity: RepositoryActivity
    install_complexity: InstallComplexity
    #: Operating systems with a realistic install path ("linux", "windows", "wsl2", "macos").
    os_support: tuple[str, ...]
    #: Headline runtime dependencies that dominate install risk.
    dependencies: tuple[str, ...]
    ratings: ResearchRatings
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    #: True when the model can realistically serve production workloads today.
    production_candidate: bool
    #: Non-empty explanation when production_candidate is False.
    excluded_reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def model_id(self) -> str:
        return self.spec.model_id

    @property
    def display_name(self) -> str:
        return self.spec.display_name

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["task"] = self.task.value
        data["activity"]["maintenance"] = self.activity.maintenance.value
        data["install_complexity"] = self.install_complexity.value
        data["ratings"]["overall"] = self.ratings.overall()
        return data
