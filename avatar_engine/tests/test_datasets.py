"""Tests for scenario datasets and asset management."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.exceptions import DatasetError

from avatar_engine.datasets import (
    AvatarDatasetManager,
    AvatarScenario,
    EvaluationFocus,
    ScenarioCategory,
    ScenarioDataset,
)


@pytest.fixture()
def manager(tmp_path: Path) -> AvatarDatasetManager:
    return AvatarDatasetManager(assets_dir=tmp_path / "assets")


def test_shipped_dataset_loads_and_validates(manager: AvatarDatasetManager) -> None:
    dataset = manager.load()
    assert len(dataset.scenarios) >= 10
    assert not AvatarDatasetManager.validate(dataset)
    # Every core evaluation dimension is exercised by at least one scenario.
    focuses = {f for s in dataset.scenarios for f in s.evaluation_focus}
    assert {
        EvaluationFocus.LIP_SYNC,
        EvaluationFocus.IDENTITY_CONSISTENCY,
        EvaluationFocus.TEMPORAL_CONSISTENCY,
        EvaluationFocus.HEAD_MOVEMENT,
        EvaluationFocus.MOTION_REALISM,
    } <= focuses


def test_hindi_scenario_present(manager: AvatarDatasetManager) -> None:
    dataset = manager.load()
    hindi = dataset.by_category(ScenarioCategory.HINDI_SPEECH)
    assert hindi and any("न" in s.script_text for s in hindi)  # Devanagari


def test_validation_catches_problems() -> None:
    bad = ScenarioDataset(description="bad", version="1")
    bad.scenarios.append(
        AvatarScenario("dup", ScenarioCategory.NEUTRAL_SPEECH, "", "en", -1.0)
    )
    bad.scenarios.append(
        AvatarScenario("dup", ScenarioCategory.NEUTRAL_SPEECH, "hi", "en", 5.0)
    )
    problems = AvatarDatasetManager.validate(bad)
    joined = " | ".join(problems)
    assert "duplicate id" in joined
    assert "empty script" in joined
    assert "non-positive duration" in joined
    assert "no evaluation focus" in joined
    assert "missing required categories" in joined


def test_missing_assets_then_placeholders(manager: AvatarDatasetManager) -> None:
    dataset = manager.load()
    missing = manager.missing_assets(dataset)
    assert len(missing) == len(dataset.scenarios)  # fresh assets dir: all missing

    created = manager.generate_placeholder_assets(dataset)
    assert created
    assert not manager.missing_assets(dataset)
    # Placeholder portrait must be a readable, valid PNG.
    portrait = manager.resolve_assets(dataset.scenarios[0]).source_image
    assert portrait.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(DatasetError):
        AvatarDatasetManager(data_dir=tmp_path).load()
