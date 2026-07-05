"""Text helpers."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 64) -> str:
    """Lowercase, ASCII-safe slug for filenames and identifiers."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug[:max_length].rstrip("-") or "untitled"


def new_run_id(prefix: str = "run") -> str:
    """Sortable unique identifier for benchmark/evaluation runs."""
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:6]}"


# Sentence terminators: Latin punctuation plus Devanagari danda/double danda
# (Hindi/Bengali prose) and the ellipsis character.
_SENTENCE_END_RE = re.compile(r"(?<=[.!?।॥…])\s+")


def split_sentences(text: str, max_chars: int | None = None) -> list[str]:
    """Split prose into sentences for chunked synthesis.

    Splits on Latin (``.!?``) and Devanagari (``।॥``) terminators. This is a
    lightweight rule-based splitter: abbreviations like "Mr." produce an
    extra split, which is harmless for TTS chunking (engines re-join prosody
    per chunk anyway).

    Args:
        text: Input prose (any supported language/script).
        max_chars: If set, sentences longer than this are further split at
            the last comma or space before the limit so no chunk exceeds it.
    """
    sentences = [part.strip() for part in _SENTENCE_END_RE.split(text.strip()) if part.strip()]
    if max_chars is None:
        return sentences
    if max_chars < 1:
        raise ValueError(f"max_chars must be >= 1, got {max_chars}")
    chunks: list[str] = []
    for sentence in sentences:
        while len(sentence) > max_chars:
            window = sentence[: max_chars + 1]
            cut = max(window.rfind(","), window.rfind(" "))
            if cut <= 0:
                cut = max_chars
            chunks.append(sentence[:cut].strip().rstrip(","))
            sentence = sentence[cut:].strip().lstrip(",").strip()
        if sentence:
            chunks.append(sentence)
    return chunks
