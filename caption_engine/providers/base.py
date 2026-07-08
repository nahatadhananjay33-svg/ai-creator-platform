"""Timing-source interface + transcript model (Phase C4).

A *timing source* answers one question: for this speech, which words/phrases are
on screen when? The Caption Engine is provider-agnostic — a deterministic
heuristic (default, no ML), or later a real ASR aligner — behind one protocol.

The transcript is a lightweight, engine-local value type (NOT the Timeline IR):
the builder lowers a :class:`Transcript` into a frozen ``CaptionTrack``. Keeping
them separate means the timing source knows nothing about styles, animation, or
render layout.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TranscriptWord:
    """One word with an absolute time window (seconds from reel start)."""

    text: str
    start_s: float
    end_s: float


@dataclass(frozen=True)
class TranscriptSegment:
    """One phrase/sentence and its words."""

    text: str
    start_s: float
    end_s: float
    words: tuple = ()          # tuple[TranscriptWord, ...]


@dataclass(frozen=True)
class Transcript:
    """Ordered phrases covering ``[0, duration_s]``."""

    segments: tuple = ()        # tuple[TranscriptSegment, ...]
    duration_s: float = 0.0

    def words(self) -> tuple:
        return tuple(w for s in self.segments for w in s.words)


class TimingProvider(Protocol):
    """Produces a :class:`Transcript` for a piece of speech.

    ``text`` is the spoken script; ``duration_s`` is the authoritative audio/reel
    length the captions must fit inside (captions never exceed it). ``audio_path``
    is available to real ASR providers and ignored by the heuristic one.
    """

    def transcribe(self, *, text: str, duration_s: float,
                   audio_path: Path | None = None) -> Transcript: ...
