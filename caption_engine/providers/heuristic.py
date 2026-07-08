"""Deterministic heuristic timing source (Phase C4 default).

No ASR, no model, no GPU: distributes the known script across the known audio
duration so word/segment timings are plausible AND perfectly reproducible — the
same (text, duration) always yields byte-identical captions. That determinism is
exactly what the hermetic test suite and the render cache need.

Method: each word gets a time slice proportional to its length (a floor keeps
short words visible); sentences (via the shared splitter) become segments whose
window spans their words. Everything is clamped to ``[0, duration_s]`` and rounded
consistently, so the output is monotonic, non-overlapping, and never exceeds the
audio — the invariants the Timeline validator enforces.
"""
from __future__ import annotations

import re
from pathlib import Path

from foundation.shared_utils.text import split_sentences

from caption_engine.providers.base import (
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)

_WORD_RE = re.compile(r"\S+")
#: Per-word weight = characters + this floor, so 1-2 char words still get time.
_LENGTH_FLOOR = 2.0
_ROUND = 3


class HeuristicTimingProvider:
    """Length-proportional, deterministic word/segment timing."""

    def __init__(self, length_floor: float = _LENGTH_FLOOR) -> None:
        self.length_floor = length_floor

    def transcribe(self, *, text: str, duration_s: float,
                   audio_path: Path | None = None) -> Transcript:
        if duration_s <= 0:
            raise ValueError(f"duration_s must be positive, got {duration_s}")
        text = text.strip()
        if not text:
            return Transcript(segments=(), duration_s=round(duration_s, _ROUND))

        sentences = split_sentences(text) or [text]
        # Tokenize, keeping sentence grouping; drop sentences with no words.
        grouped = [(s, _WORD_RE.findall(s)) for s in sentences]
        grouped = [(s, ws) for s, ws in grouped if ws]
        total_weight = sum(len(w) + self.length_floor
                           for _, ws in grouped for w in ws)
        if total_weight <= 0:  # pragma: no cover - defensive
            return Transcript(segments=(), duration_s=round(duration_s, _ROUND))

        per_weight = duration_s / total_weight
        segments: list[TranscriptSegment] = []
        cursor = 0.0
        for sent_text, tokens in grouped:
            words: list[TranscriptWord] = []
            for tok in tokens:
                start = cursor
                cursor += (len(tok) + self.length_floor) * per_weight
                end = min(cursor, duration_s)
                words.append(TranscriptWord(
                    text=tok, start_s=round(start, _ROUND), end_s=round(end, _ROUND)))
            segments.append(TranscriptSegment(
                text=" ".join(tokens),
                start_s=words[0].start_s,
                end_s=words[-1].end_s,
                words=tuple(words),
            ))
        return Transcript(segments=tuple(segments), duration_s=round(duration_s, _ROUND))
