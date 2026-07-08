"""Transcript -> CaptionTrack builder (Phase C4).

Lowers a provider :class:`Transcript` into the frozen Timeline IR
:class:`CaptionTrack`. This is where the caption *type* is applied:

- ``sentence`` / ``word`` / ``karaoke`` — one IR segment per transcript segment
  (words carried through; word/karaoke need them, sentence ignores them).
- ``static`` — the whole transcript collapsed into ONE segment shown for the
  entire track (a single caption card).

Pure and deterministic: no I/O, no timing invented here (the provider owns
timing). The result is validated by the Timeline validator before rendering.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    WordTiming,
)

from caption_engine.providers.base import Transcript, TranscriptSegment

CAPTION_KINDS = ("sentence", "word", "karaoke", "static")


def _word_timings(seg: TranscriptSegment) -> tuple:
    return tuple(WordTiming(text=w.text, start_s=w.start_s, end_s=w.end_s)
                 for w in seg.words)


def _segment(seg: TranscriptSegment, index: int) -> CaptionSegment:
    return CaptionSegment(
        segment_id=f"seg-{index:03d}", index=index, text=seg.text,
        start_s=seg.start_s, end_s=seg.end_s, words=_word_timings(seg),
    )


def build_caption_track(
    transcript: Transcript,
    *,
    kind: str = "sentence",
    style: CaptionStyle | None = None,
    animation: CaptionAnimation | None = None,
    track_id: str = "captions",
) -> CaptionTrack:
    """Assemble a :class:`CaptionTrack` from a transcript for the given ``kind``."""
    if kind not in CAPTION_KINDS:
        raise ValueError(f"Unknown caption kind {kind!r}; expected one of {CAPTION_KINDS}")
    style = style or CaptionStyle()
    animation = animation or CaptionAnimation()

    if kind == "static":
        segments = (_static_segment(transcript),) if transcript.segments else ()
    else:
        segments = tuple(_segment(s, i) for i, s in enumerate(transcript.segments))

    return CaptionTrack(track_id=track_id, kind=kind, segments=segments,
                        style=style, animation=animation)


def _static_segment(transcript: Transcript) -> CaptionSegment:
    """Collapse every phrase into one card spanning the whole transcript."""
    segs = transcript.segments
    full_text = " ".join(s.text for s in segs)
    start = segs[0].start_s
    end = segs[-1].end_s
    words = tuple(WordTiming(text=w.text, start_s=w.start_s, end_s=w.end_s)
                  for w in transcript.words())
    return CaptionSegment(segment_id="seg-000", index=0, text=full_text,
                          start_s=start, end_s=end, words=words)
