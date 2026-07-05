"""Tests for benchmark datasets."""
from __future__ import annotations

import pytest

from foundation.constants import Language
from foundation.exceptions import DatasetError
from voice_engine.datasets import DatasetManager, PromptCategory, PromptDataset, PromptItem
from voice_engine.datasets.manager import detect_scripts


@pytest.fixture(scope="module")
def manager() -> DatasetManager:
    return DatasetManager()


@pytest.mark.parametrize("language", list(Language))
def test_all_language_datasets_load_and_validate(manager: DatasetManager, language: Language) -> None:
    dataset = manager.load(language)
    assert len(dataset.items) >= 12
    assert dataset.language is language
    # Every dataset must cover the full category set for comparability.
    assert dataset.categories() == set(PromptCategory)


def test_real_estate_entities_present(manager: DatasetManager) -> None:
    en = manager.load(Language.ENGLISH)
    rera = en.by_category(PromptCategory.RERA_NUMBER)
    assert rera and "RERA" in rera[0].text
    pricing = en.by_category(PromptCategory.PRICING)
    assert any("lakh" in item.text.lower() or "crore" in item.text.lower() for item in pricing)


def test_hindi_is_devanagari(manager: DatasetManager) -> None:
    hi = manager.load(Language.HINDI)
    for item in hi.items:
        assert "Devanagari" in detect_scripts(item.text), item.item_id


def test_bengali_is_bengali_script(manager: DatasetManager) -> None:
    bn = manager.load(Language.BENGALI)
    for item in bn.items:
        assert "Bengali" in detect_scripts(item.text), item.item_id


def test_long_narration_prompts_are_long(manager: DatasetManager) -> None:
    for language in Language:
        narration = manager.load(language).by_category(PromptCategory.LONG_NARRATION)
        assert narration and all(item.char_count > 500 for item in narration), language


def test_validation_catches_duplicates_and_missing_categories() -> None:
    dataset = PromptDataset(language=Language.ENGLISH, description="x", version="1")
    item = PromptItem("dup", PromptCategory.PRICING, "text", Language.ENGLISH)
    dataset.items = [item, item]
    problems = DatasetManager.validate(dataset)
    assert any("duplicate id" in p for p in problems)
    assert any("missing required categories" in p for p in problems)


def test_script_expectation_mismatch_detected() -> None:
    dataset = PromptDataset(language=Language.HINDI, description="x", version="1")
    dataset.items = [
        PromptItem("h1", PromptCategory.PRICING, "latin only", Language.HINDI,
                   expected_scripts=("Devanagari",))
    ]
    problems = DatasetManager.validate(dataset)
    assert any("expected scripts" in p for p in problems)


def test_unreadable_dataset_raises(tmp_path) -> None:  # noqa: ANN001
    with pytest.raises(DatasetError):
        DatasetManager(data_dir=tmp_path).load(Language.ENGLISH)
