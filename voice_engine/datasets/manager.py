"""Dataset loading and validation."""
from __future__ import annotations

from pathlib import Path

from foundation.config import load_yaml
from foundation.constants import Language
from foundation.exceptions import ConfigError
from foundation.constants.languages import SCRIPT_RANGES
from foundation.exceptions import DatasetError
from foundation.logging import get_logger
from voice_engine.datasets.schema import PromptCategory, PromptDataset, PromptItem

logger = get_logger("voice_engine.datasets")

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"

_LANGUAGE_FILES: dict[Language, str] = {
    Language.ENGLISH: "english.yaml",
    Language.HINDI: "hindi.yaml",
    Language.HINGLISH: "hinglish.yaml",
    Language.BENGALI: "bengali.yaml",
}


def detect_scripts(text: str) -> set[str]:
    """Detect which writing scripts appear in ``text``."""
    found: set[str] = set()
    for ch in text:
        cp = ord(ch)
        for script, ranges in SCRIPT_RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                found.add(script)
                break
    return found


class DatasetManager:
    """Loads, validates, and serves benchmark prompt datasets."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DEFAULT_DATA_DIR

    def load(self, language: Language) -> PromptDataset:
        filename = _LANGUAGE_FILES.get(language)
        if filename is None:
            raise DatasetError(f"No dataset defined for language {language.value}")
        try:
            raw = load_yaml(self.data_dir / filename)
        except ConfigError as exc:
            raise DatasetError(
                f"Dataset file missing or unreadable: {filename}", file=filename
            ) from exc
        try:
            dataset = PromptDataset(
                language=Language.from_code(raw["language"]),
                description=raw.get("description", ""),
                version=str(raw.get("version", "0")),
            )
            for entry in raw["items"]:
                dataset.items.append(
                    PromptItem(
                        item_id=entry["id"],
                        category=PromptCategory(entry["category"]),
                        text=entry["text"].strip(),
                        language=dataset.language,
                        expected_scripts=tuple(entry.get("expected_scripts", [])),
                        notes=entry.get("notes", ""),
                    )
                )
        except (KeyError, ValueError) as exc:
            raise DatasetError(
                f"Malformed dataset file: {filename}", file=filename
            ) from exc
        problems = self.validate(dataset)
        if problems:
            raise DatasetError(
                f"Dataset validation failed for {filename}: {problems[:3]}",
                file=filename,
                problem_count=len(problems),
            )
        if dataset.language is not language:
            raise DatasetError(
                f"Dataset file {filename} declares language "
                f"{dataset.language.value!r}, expected {language.value!r}"
            )
        logger.info(
            "Dataset loaded",
            extra={"context": {"language": language.value, "items": len(dataset.items)}},
        )
        return dataset

    def load_all(self) -> dict[Language, PromptDataset]:
        return {lang: self.load(lang) for lang in _LANGUAGE_FILES}

    @staticmethod
    def validate(dataset: PromptDataset) -> list[str]:
        """Structural + script validation. Returns problem descriptions."""
        problems: list[str] = []
        seen_ids: set[str] = set()
        for item in dataset.items:
            if item.item_id in seen_ids:
                problems.append(f"duplicate id: {item.item_id}")
            seen_ids.add(item.item_id)
            if not item.text:
                problems.append(f"empty text: {item.item_id}")
            if item.expected_scripts:
                found = detect_scripts(item.text)
                missing = set(item.expected_scripts) - found
                if missing:
                    problems.append(
                        f"{item.item_id}: expected scripts {sorted(missing)} not found in text"
                    )
        required = {
            PromptCategory.PROPERTY_DISCUSSION,
            PromptCategory.RERA_NUMBER,
            PromptCategory.PRICING,
            PromptCategory.LONG_NARRATION,
            PromptCategory.CONVERSATION,
        }
        missing_categories = required - dataset.categories()
        if missing_categories:
            problems.append(
                f"missing required categories: {sorted(c.value for c in missing_categories)}"
            )
        return problems
