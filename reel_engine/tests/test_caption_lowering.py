"""Caption lowering tests (Phase C4). Pure, hermetic — no renderer, no ffmpeg.

Pins how a native ``CaptionTrack`` is lowered to timed draw ops: one shape per
caption kind (sentence/word/karaoke/static), word-wrap, uppercase transform,
karaoke base+highlight layering, and the opacity animation curve. This is the
contract both renderer backends share.
"""
from __future__ import annotations

from reel_engine.interfaces.types import (
    CaptionAnimation,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    Timeline,
    TimelineMeta,
    WordTiming,
)
from reel_engine.render.captions import (
    caption_alpha,
    lower_caption_track,
    lower_caption_tracks,
    wrap_text,
)

W = 1080


def _seg(text, s, e, words=()):
    return CaptionSegment(f"seg-{s}", int(s), text, s, e,
                          words=tuple(WordTiming(t, a, b) for t, a, b in words))


def _kara_seg():
    return _seg("hello world", 0.0, 2.0,
                words=[("hello", 0.0, 1.0), ("world", 1.0, 2.0)])


# ------------------------------------------------------------------ per kind
def test_sentence_lowers_one_draw_per_segment():
    track = CaptionTrack("c", kind="sentence",
                         segments=(_seg("first line", 0.0, 1.0),
                                   _seg("second line", 1.0, 2.0)))
    draws = lower_caption_track(track, W)
    assert [d.text for d in draws] == ["first line", "second line"]
    assert all(d.layer == 0 and d.x_frac is None for d in draws)
    assert all(d.color == track.style.primary_color for d in draws)


def test_word_lowers_one_centred_draw_per_word():
    track = CaptionTrack("c", kind="word", segments=(_kara_seg(),))
    draws = lower_caption_track(track, W)
    assert [d.text for d in draws] == ["hello", "world"]
    # each word is visible only in its own window
    assert (draws[0].start_s, draws[0].end_s) == (0.0, 1.0)
    assert (draws[1].start_s, draws[1].end_s) == (1.0, 2.0)


def test_karaoke_lowers_base_plus_highlight_per_word():
    track = CaptionTrack("c", kind="karaoke", segments=(_kara_seg(),),
                         style=CaptionStyle(highlight_color=(1, 2, 3)))
    draws = lower_caption_track(track, W)
    assert len(draws) == 4                                   # 2 words x (base+highlight)
    base = [d for d in draws if d.layer == 0]
    hi = [d for d in draws if d.layer == 1]
    # base words span the whole segment; highlights span each word window
    assert all((d.start_s, d.end_s) == (0.0, 2.0) for d in base)
    assert {(d.start_s, d.end_s) for d in hi} == {(0.0, 1.0), (1.0, 2.0)}
    assert all(d.color == (1, 2, 3) for d in hi)             # highlight colour
    # every karaoke word carries an explicit horizontal centre, in reading order
    xs = [d.x_frac for d in base]
    assert all(x is not None for x in xs) and xs == sorted(xs)


def test_static_lowers_single_card():
    track = CaptionTrack("c", kind="static",
                         segments=(_seg("all the words here", 0.0, 4.0),))
    draws = lower_caption_track(track, W)
    assert all(d.start_s == 0.0 and d.end_s == 4.0 for d in draws)


# ------------------------------------------------------------------ transforms
def test_uppercase_style_transforms_text():
    track = CaptionTrack("c", kind="sentence", segments=(_seg("quiet", 0.0, 1.0),),
                         style=CaptionStyle(uppercase=True))
    assert lower_caption_track(track, W)[0].text == "QUIET"


def test_word_wrap_stacks_lines_with_indices():
    lines = wrap_text("one two three four five six", 8)
    assert all(len(ln) <= 8 for ln in lines) and len(lines) >= 3
    track = CaptionTrack("c", kind="sentence",
                         segments=(_seg("one two three four five six", 0.0, 2.0),),
                         style=CaptionStyle(max_chars_per_line=8))
    draws = lower_caption_track(track, W)
    assert len(draws) == len(lines)
    assert [d.line_index for d in draws] == list(range(len(lines)))
    assert all(d.line_count == len(lines) for d in draws)


# ------------------------------------------------------------------ animation
def test_alpha_none_is_opaque_inside_zero_outside():
    a = CaptionAnimation("none")
    assert caption_alpha(a, 0.0, 2.0, 1.0) == 1.0
    assert caption_alpha(a, 0.0, 2.0, 2.5) == 0.0


def test_alpha_fade_ramps_in_and_out():
    a = CaptionAnimation("fade", 0.5)
    assert caption_alpha(a, 0.0, 4.0, 0.0) == 0.0            # start: invisible
    assert caption_alpha(a, 0.0, 4.0, 0.25) == 0.5          # mid ramp-in
    assert caption_alpha(a, 0.0, 4.0, 2.0) == 1.0           # fully in
    assert caption_alpha(a, 0.0, 4.0, 4.0) == 0.0           # end: invisible
    assert 0.0 < caption_alpha(a, 0.0, 4.0, 3.75) < 1.0     # ramp-out


def test_alpha_pop_ramps_in_then_holds():
    a = CaptionAnimation("pop", 0.5)
    assert caption_alpha(a, 0.0, 4.0, 0.0) == 0.0
    assert caption_alpha(a, 0.0, 4.0, 0.5) == 1.0
    assert caption_alpha(a, 0.0, 4.0, 4.0) == 1.0           # holds (no fade-out)


# ------------------------------------------------------------------ multi-track
def test_lower_tracks_sorts_by_time_then_layer():
    tl = Timeline(meta=TimelineMeta(width=W, height=1920),
                  caption_tracks=(CaptionTrack("c", kind="karaoke",
                                               segments=(_kara_seg(),)),))
    draws = lower_caption_tracks(tl)
    keys = [(d.start_s, d.layer) for d in draws]
    assert keys == sorted(keys)
