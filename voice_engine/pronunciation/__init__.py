"""Pronunciation control: lexicon overrides applied to text before synthesis.

Covers builder/project names, RERA numbers, and unit abbreviations. The A1
dataset's named-entity prompts are this layer's acceptance tests.
"""

from voice_engine.pronunciation.manager import (
    DEFAULT_LEXICON_PATH,
    LexiconEntry,
    PronunciationManager,
)

__all__ = [
    "DEFAULT_LEXICON_PATH",
    "LexiconEntry",
    "PronunciationManager",
]
