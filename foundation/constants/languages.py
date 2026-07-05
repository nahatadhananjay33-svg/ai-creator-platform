"""Language definitions used across all engines.

The platform targets Indian content creation and voice AI, so Hindi,
Hinglish (Hindi-English code-switching, usually romanized), and Bengali are
first-class citizens alongside English.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Language(str, Enum):
    """BCP-47-ish language codes used platform-wide."""

    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hi-en"  # Hindi-English code-switched speech
    BENGALI = "bn"

    @classmethod
    def from_code(cls, code: str) -> "Language":
        for lang in cls:
            if lang.value == code.lower():
                return lang
        raise ValueError(f"Unknown language code: {code!r}")


@dataclass(frozen=True)
class LanguageInfo:
    """Descriptive metadata for a supported language."""

    language: Language
    display_name: str
    scripts: tuple[str, ...]
    is_code_switched: bool = False


LANGUAGE_INFO: dict[Language, LanguageInfo] = {
    Language.ENGLISH: LanguageInfo(Language.ENGLISH, "English", ("Latin",)),
    Language.HINDI: LanguageInfo(Language.HINDI, "Hindi", ("Devanagari",)),
    Language.HINGLISH: LanguageInfo(
        Language.HINGLISH, "Hinglish", ("Latin", "Devanagari"), is_code_switched=True
    ),
    Language.BENGALI: LanguageInfo(Language.BENGALI, "Bengali", ("Bengali",)),
}

# Unicode block ranges used for script detection (metrics, dataset validation).
SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "Latin": ((0x0041, 0x024F),),
    "Devanagari": ((0x0900, 0x097F),),
    "Bengali": ((0x0980, 0x09FF),),
}
