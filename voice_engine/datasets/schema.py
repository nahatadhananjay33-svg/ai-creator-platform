"""Dataset schema types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from foundation.constants import Language


class PromptCategory(str, Enum):
    """Content categories exercised by the benchmark.

    Real-estate categories stress named entities, numbers, and units — the
    places TTS models mispronounce first. Narration/conversation categories
    stress long-form stability and dialogue naturalness.
    """

    PROPERTY_DISCUSSION = "property_discussion"
    BUILDER_NAME = "builder_name"
    PROJECT_NAME = "project_name"
    RERA_NUMBER = "rera_number"
    SITE_VISIT = "site_visit"
    APPOINTMENT = "appointment"
    ADDRESS = "address"
    PHONE_NUMBER = "phone_number"
    PRICING = "pricing"
    LOAN = "loan"
    LONG_NARRATION = "long_narration"
    CONVERSATION = "conversation"
    CODE_SWITCHING = "code_switching"


@dataclass(frozen=True)
class PromptItem:
    """One benchmark prompt."""

    item_id: str
    category: PromptCategory
    text: str
    language: Language
    expected_scripts: tuple[str, ...] = ()
    notes: str = ""

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class PromptDataset:
    """All prompts for one language."""

    language: Language
    description: str
    version: str
    items: list[PromptItem] = field(default_factory=list)

    def by_category(self, category: PromptCategory) -> list[PromptItem]:
        return [i for i in self.items if i.category is category]

    def categories(self) -> set[PromptCategory]:
        return {i.category for i in self.items}
