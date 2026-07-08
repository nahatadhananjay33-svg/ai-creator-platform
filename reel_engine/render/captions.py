"""Caption lowering (Phase C4) — ``CaptionTrack`` → timed draw ops.

The renderer must *consume* caption tracks, never special-case them: this module
is the single place that turns the declarative :class:`CaptionTrack` IR into
concrete, absolutely-timed :class:`CaptionDraw` operations. Both backends (the
hermetic mock proxy and the real FFmpeg MP4) lower with the SAME code, so they
draw the SAME captions from the SAME data — a renderer only needs to know how to
paint one ``CaptionDraw``, not how to interpret a track ``kind``.

Caption kinds lower like this (all in absolute reel time):

- ``sentence`` — one draw per segment, word-wrapped to ``max_chars_per_line``.
- ``static``   — the single collapsed segment, shown for the whole window.
- ``word``     — one centred draw per word, visible only in its window.
- ``karaoke``  — the whole phrase laid out on one line (base, ``primary_color``)
  plus a per-word ``highlight_color`` overlay enabled during each word.

Positions/colours are resolution-independent (fractions + RGB), so the mock's
tiny proxy frame and the full-resolution master place captions identically.
Pure and deterministic: no I/O, no randomness.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from reel_engine.interfaces.types import (
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    Timeline,
    WordTiming,
)

#: Rough glyph advance as a fraction of font size — used only for the karaoke
#: single-line layout (an approximation of real font metrics; see the docs'
#: Limitations). Deterministic, so karaoke word positions never drift.
_GLYPH_ADVANCE = 0.52
#: Line height as a multiple of font size, for stacking wrapped lines.
LINE_HEIGHT_FACTOR = 1.28


@dataclass(frozen=True)
class CaptionDraw:
    """One paint operation: a run of text over an absolute ``[start_s, end_s]``.

    ``x_frac`` is ``None`` for normal single-line captions (the backend places
    them with ``style.alignment`` + horizontal safe margin) or a 0..1 horizontal
    *centre* fraction for karaoke words (explicitly laid out). ``line_index`` /
    ``line_count`` let the backend stack wrapped lines. ``layer`` is the draw
    order (0 = base text, 1 = highlight overlay drawn on top)."""

    text: str
    start_s: float
    end_s: float
    color: tuple
    style: CaptionStyle
    animation: CaptionAnimation = field(default_factory=CaptionAnimation)
    x_frac: float | None = None
    line_index: int = 0
    line_count: int = 1
    layer: int = 0

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


# --------------------------------------------------------------------- helpers
def _transform(text: str, style: CaptionStyle) -> str:
    return text.upper() if style.uppercase else text


def wrap_text(text: str, max_chars: int) -> list[str]:
    """Greedy word-wrap into lines of at most ``max_chars`` characters."""
    if max_chars <= 0:
        return [text]
    lines: list[str] = []
    cur = ""
    for word in text.split():
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= max_chars:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def caption_alpha(animation: CaptionAnimation, start_s: float, end_s: float,
                  t: float) -> float:
    """Opacity (0..1) for a caption at absolute time ``t``.

    v1 animation is intentionally opacity-only (see the docs' Limitations):
    ``none`` is fully opaque; ``fade`` ramps in and out; ``pop`` ramps in fast
    and holds (a snappy entrance). ``t`` outside the window yields 0.
    """
    if t < start_s or t > end_s:
        return 0.0
    kind = animation.kind
    if kind == "none":
        return 1.0
    window = end_s - start_s
    d = min(max(animation.duration_s, 0.0), window / 2.0 if window > 0 else 0.0)
    if d <= 0:
        return 1.0
    if kind == "pop":
        # Fast ramp-in only, then hold — a simple "pop".
        return min(1.0, (t - start_s) / d)
    # fade: symmetric ramp in and out.
    if t < start_s + d:
        return max(0.0, min(1.0, (t - start_s) / d))
    if t > end_s - d:
        return max(0.0, min(1.0, (end_s - t) / d))
    return 1.0


def _karaoke_centres(words: tuple, style: CaptionStyle, frame_w: int) -> list[float]:
    """Horizontal *centre* fraction (0..1) for each word on one centred line."""
    advance = max(1.0, style.font_size * _GLYPH_ADVANCE)
    space = advance
    widths = [max(1, len(w.text)) * advance for w in words]
    total = sum(widths) + space * (len(words) - 1)
    x = (frame_w - total) / 2.0
    centres: list[float] = []
    for width in widths:
        centres.append((x + width / 2.0) / frame_w)
        x += width + space
    return centres


# --------------------------------------------------------------------- lowering
def _lower_line_segment(seg: CaptionSegment, style: CaptionStyle,
                        animation: CaptionAnimation) -> list[CaptionDraw]:
    """A word-wrapped, single-caption draw (sentence/static/word text)."""
    lines = wrap_text(_transform(seg.text, style), style.max_chars_per_line)
    n = len(lines)
    return [
        CaptionDraw(text=line, start_s=seg.start_s, end_s=seg.end_s,
                    color=style.primary_color, style=style, animation=animation,
                    line_index=i, line_count=n)
        for i, line in enumerate(lines)
    ]


def _lower_word_segment(seg: CaptionSegment, style: CaptionStyle,
                        animation: CaptionAnimation) -> list[CaptionDraw]:
    """One centred draw per word, visible only during that word's window."""
    return [
        CaptionDraw(text=_transform(w.text, style), start_s=w.start_s, end_s=w.end_s,
                    color=style.primary_color, style=style, animation=animation)
        for w in seg.words
    ]


def _lower_karaoke_segment(seg: CaptionSegment, style: CaptionStyle,
                           animation: CaptionAnimation, frame_w: int) -> list[CaptionDraw]:
    """Whole phrase on one line (base) + per-word highlight overlay.

    The base words are all shown for the full segment window in
    ``primary_color``; each word is redrawn at the same position in
    ``highlight_color`` during its own window (``layer=1`` → painted on top), so
    the active word lights up as it is spoken."""
    words: tuple[WordTiming, ...] = seg.words
    centres = _karaoke_centres(words, style, frame_w)
    draws: list[CaptionDraw] = []
    for w, cx in zip(words, centres):
        text = _transform(w.text, style)
        draws.append(CaptionDraw(  # base: primary for the whole segment
            text=text, start_s=seg.start_s, end_s=seg.end_s,
            color=style.primary_color, style=style, animation=animation,
            x_frac=cx, layer=0))
        draws.append(CaptionDraw(  # highlight: while this word is spoken
            text=text, start_s=w.start_s, end_s=w.end_s,
            color=style.highlight_color, style=style,
            animation=CaptionAnimation(),  # no re-animation on the highlight
            x_frac=cx, layer=1))
    return draws


def lower_caption_track(track, frame_w: int) -> list[CaptionDraw]:
    """Lower a single :class:`CaptionTrack` into ordered draw ops."""
    style, anim, kind = track.style, track.animation, track.kind
    draws: list[CaptionDraw] = []
    for seg in track.segments:
        if kind == "karaoke":
            draws.extend(_lower_karaoke_segment(seg, style, anim, frame_w))
        elif kind == "word":
            draws.extend(_lower_word_segment(seg, style, anim))
        else:  # sentence | static
            draws.extend(_lower_line_segment(seg, style, anim))
    return draws


def lower_caption_tracks(timeline: Timeline) -> list[CaptionDraw]:
    """Flatten every caption track in ``timeline`` into paint order.

    Returned draws are sorted by ``(start_s, layer)`` so base text is painted
    before its highlight overlay and earlier captions before later ones.
    """
    frame_w = timeline.meta.width
    draws: list[CaptionDraw] = []
    for track in timeline.caption_tracks:
        draws.extend(lower_caption_track(track, frame_w))
    draws.sort(key=lambda d: (d.start_s, d.layer))
    return draws
