"""Pronunciation dictionary applied to text before synthesis.

Rewrites graphemes the engines mispronounce (builder/project names, RERA
numbers, unit abbreviations) into speakable forms. Entries are whole-word
and case-insensitive by default; raw-regex entries cover patterns like
"3BHK". Per-language entries only fire for that language.

Lexicons are YAML (see ``default_lexicon.yaml``); the Phase A1 dataset's
named-entity prompt categories are the acceptance tests for this layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from foundation.config import load_yaml
from foundation.constants import Language
from foundation.exceptions import ConfigError
from foundation.logging import get_logger

logger = get_logger("voice_engine.pronunciation")

DEFAULT_LEXICON_PATH: Path = Path(__file__).resolve().parent / "default_lexicon.yaml"


@dataclass(frozen=True)
class LexiconEntry:
    """One grapheme -> speakable-form rewrite rule."""

    grapheme: str
    replacement: str
    language: Language | None = None  # None -> applies to every language
    is_regex: bool = False
    case_sensitive: bool = False

    def compiled(self) -> re.Pattern[str]:
        flags = 0 if self.case_sensitive else re.IGNORECASE
        if self.is_regex:
            return re.compile(self.grapheme, flags)
        # Whole-word match; \b fails at non-alphanumeric edges ("sq.ft."),
        # so fall back to lookarounds against word characters.
        escaped = re.escape(self.grapheme)
        return re.compile(rf"(?<!\w){escaped}(?!\w)", flags)


def _entry_from_mapping(raw: dict[str, Any], source: str) -> LexiconEntry:
    try:
        grapheme = str(raw["grapheme"])
        replacement = str(raw["replacement"])
    except KeyError as exc:
        raise ConfigError(
            f"Lexicon entry missing {exc} in {source}", entry=raw, source=source
        ) from None
    language = raw.get("language")
    return LexiconEntry(
        grapheme=grapheme,
        replacement=replacement,
        language=Language.from_code(language) if language else None,
        is_regex=bool(raw.get("regex", False)),
        case_sensitive=bool(raw.get("case_sensitive", False)),
    )


class PronunciationManager:
    """Ordered collection of lexicon entries with an ``apply`` step."""

    def __init__(self, entries: Iterable[LexiconEntry] = ()) -> None:
        self._entries: list[LexiconEntry] = []
        self._patterns: list[re.Pattern[str]] = []
        for entry in entries:
            self.add_entry(entry)

    @classmethod
    def from_lexicons(
        cls,
        paths: Iterable[Path | str],
        include_default: bool = True,
    ) -> "PronunciationManager":
        """Build a manager from lexicon files (later files win by ordering)."""
        manager = cls()
        all_paths = ([DEFAULT_LEXICON_PATH] if include_default else []) + [Path(p) for p in paths]
        for path in all_paths:
            manager.load_lexicon(path)
        return manager

    @property
    def entries(self) -> tuple[LexiconEntry, ...]:
        return tuple(self._entries)

    def add(
        self,
        grapheme: str,
        replacement: str,
        language: Language | str | None = None,
        is_regex: bool = False,
        case_sensitive: bool = False,
    ) -> None:
        """Register one rewrite rule programmatically."""
        if isinstance(language, str):
            language = Language.from_code(language)
        self.add_entry(
            LexiconEntry(grapheme, replacement, language, is_regex, case_sensitive)
        )

    def add_entry(self, entry: LexiconEntry) -> None:
        try:
            pattern = entry.compiled()
        except re.error as exc:
            raise ConfigError(
                f"Invalid lexicon regex {entry.grapheme!r}: {exc}", grapheme=entry.grapheme
            ) from exc
        self._entries.append(entry)
        self._patterns.append(pattern)

    def load_lexicon(self, path: Path | str) -> int:
        """Load entries from a YAML lexicon file. Returns entries added."""
        data = load_yaml(path)
        raw_entries = data.get("entries", [])
        if not isinstance(raw_entries, list):
            raise ConfigError(f"Lexicon 'entries' must be a list: {path}", path=str(path))
        for raw in raw_entries:
            self.add_entry(_entry_from_mapping(raw, source=str(path)))
        logger.debug(
            "Lexicon loaded",
            extra={"context": {"path": str(path), "entries": len(raw_entries)}},
        )
        return len(raw_entries)

    def apply(self, text: str, language: Language) -> str:
        """Rewrite ``text`` with every entry applicable to ``language``."""
        for entry, pattern in zip(self._entries, self._patterns):
            if entry.language is not None and entry.language is not language:
                continue
            text = pattern.sub(entry.replacement, text)
        return text
