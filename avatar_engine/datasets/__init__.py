"""Avatar benchmark datasets: scenarios, assets, loading and validation."""

from avatar_engine.datasets.manager import AvatarDatasetManager, DEFAULT_DATA_DIR
from avatar_engine.datasets.schema import (
    AvatarScenario,
    EvaluationFocus,
    ScenarioCategory,
    ScenarioDataset,
)

__all__ = [
    "AvatarDatasetManager",
    "AvatarScenario",
    "DEFAULT_DATA_DIR",
    "EvaluationFocus",
    "ScenarioCategory",
    "ScenarioDataset",
]
