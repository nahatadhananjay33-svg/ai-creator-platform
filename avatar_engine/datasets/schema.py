"""Avatar benchmark dataset schema.

A *scenario* pairs a source portrait, a driving audio clip (generated with
the Phase A1 voice engine so the two engines stay coupled), and the
evaluation dimensions the scenario is designed to stress. Scenario scripts
mirror the voice benchmark's real-estate domain so future end-to-end
creator-content tests reuse the same material.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ScenarioCategory(str, Enum):
    """What each benchmark scenario stresses."""

    NEUTRAL_SPEECH = "neutral_speech"          # baseline lip-sync accuracy
    EXPRESSIVE_SPEECH = "expressive_speech"    # emotion / expression range
    LONG_NARRATION = "long_narration"          # identity + temporal drift over 60s+
    FAST_SPEECH = "fast_speech"                # lip-sync under rapid phonemes
    HINDI_SPEECH = "hindi_speech"              # non-English phoneme coverage
    HEAD_MOVEMENT = "head_movement"            # natural head motion amplitude
    SIDE_POSE_SOURCE = "side_pose_source"      # non-frontal source image robustness
    SILENCE_SEGMENTS = "silence_segments"      # mouth closure during pauses
    STYLIZED_SOURCE = "stylized_source"        # illustration/3D-render source images


class EvaluationFocus(str, Enum):
    """Evaluation dimension a scenario is designed to probe."""

    LIP_SYNC = "lip_sync"
    IDENTITY_CONSISTENCY = "identity_consistency"
    EXPRESSION_QUALITY = "expression_quality"
    HEAD_MOVEMENT = "head_movement"
    MOTION_REALISM = "motion_realism"
    TEMPORAL_CONSISTENCY = "temporal_consistency"
    VIDEO_QUALITY = "video_quality"
    PERFORMANCE = "performance"


@dataclass(frozen=True)
class AvatarScenario:
    """One benchmark scenario."""

    scenario_id: str
    category: ScenarioCategory
    script_text: str                 # what the driving audio says
    language: str                    # BCP-47-ish code matching voice datasets
    target_duration_s: float
    #: Asset file names relative to the assets directory ("" = use default).
    source_image: str = ""
    driving_audio: str = ""
    evaluation_focus: tuple[EvaluationFocus, ...] = ()
    notes: str = ""


@dataclass
class ScenarioDataset:
    """All scenarios for the avatar benchmark."""

    description: str
    version: str
    scenarios: list[AvatarScenario] = field(default_factory=list)

    def by_category(self, category: ScenarioCategory) -> list[AvatarScenario]:
        return [s for s in self.scenarios if s.category is category]

    def categories(self) -> set[ScenarioCategory]:
        return {s.category for s in self.scenarios}
