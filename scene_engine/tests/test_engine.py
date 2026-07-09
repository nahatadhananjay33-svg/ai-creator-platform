"""Scene & Storyboard Planning Engine regression tests (Phase C7).

Fully hermetic and deterministic: NO renderer, NO ffmpeg, NO GPU, NO model, NO
network, NO downloads. Covers the whole deterministic surface — segmentation,
classification, timing, the storyboard IR, timeline generation, configuration,
and validation — and asserts the plan/lowered-timeline invariants the renderer
relies on (correct scene count/ordering/timing, no gaps, no overlaps). Every
built timeline is run through the shared Timeline validator so the engine can
never emit an unrenderable plan.
"""
from __future__ import annotations

import pytest

from reel_engine.timeline.validate import validate_timeline

from scene_engine import (
    SceneEngine,
    SceneType,
    Storyboard,
    build_timeline,
    load_scene_engine_config,
    plan_storyboard,
)
from scene_engine.config.settings import SceneEngineConfig
from scene_engine.rules.classification import (
    asset_hint,
    classify_scene,
    refine_asset_kind,
)
from scene_engine.rules.profiles import PROFILES, profile_for
from scene_engine.rules.segmentation import segment_scenes
from scene_engine.storyboard.serde import storyboard_from_dict, storyboard_to_json
from scene_engine.timeline.builder import build_caption_track
from scene_engine.timing.estimator import estimate_speech_s, plan_timings, scene_window_s

CFG = SceneEngineConfig()

# A finished script that exercises many rule paths: hook, data/chart, comparison,
# bullet list, quote, video insert, and a closing CTA. Blank line = paragraph.
SCRIPT = (
    "Ever wondered why most reels flop in the first three seconds?\n\n"
    "The data shows that 65% of viewers scroll away before the payoff.\n\n"
    "Look at this chart of retention over time.\n\n"
    "Compared to long videos, a reel must earn attention immediately.\n\n"
    "Here are three fixes. First, open with a question. "
    "Second, cut the intro. Third, show the payoff early.\n\n"
    "Watch how this creator nails the opening in one clip.\n\n"
    "So subscribe and follow for a new tip every week.\n\n"
)


# ------------------------------------------------------------- segmentation ---
def test_segments_are_whole_sentences_and_nonempty():
    scenes = segment_scenes(SCRIPT, CFG)
    assert scenes and all(scene for scene in scenes)
    # every unit is a full sentence string, never a blank
    assert all(s.strip() for scene in scenes for s in scene)


def test_manual_marker_forces_a_break():
    script = "First scene here.\n---\nSecond scene here."
    scenes = segment_scenes(script, CFG)
    assert len(scenes) == 2
    assert scenes[0] == ["First scene here."]
    assert scenes[1] == ["Second scene here."]


def test_paragraph_boundary_never_spanned():
    # sentences are substantial (above min_words) so no small-tail merge fires;
    # the blank line then keeps the two paragraphs in separate scenes.
    script = ("Alpha paragraph sentence number one here.\n\n"
              "Beta paragraph sentence number two here.")
    scenes = segment_scenes(script, CFG)
    assert len(scenes) == 2
    assert scenes[0] == ["Alpha paragraph sentence number one here."]
    assert scenes[1] == ["Beta paragraph sentence number two here."]


def test_max_words_splits_within_a_paragraph():
    cfg = SceneEngineConfig(max_words_per_scene=6, min_words_per_scene=1)
    # three 5-word sentences -> cannot combine two (10 > 6) -> three scenes
    script = "One two three four five. Six seven eight nine ten. A b c d e."
    scenes = segment_scenes(script, cfg)
    assert len(scenes) == 3


def test_oversize_sentence_is_its_own_scene_never_split():
    cfg = SceneEngineConfig(max_words_per_scene=3, min_words_per_scene=1)
    script = "This single sentence has clearly more than three words in it."
    scenes = segment_scenes(script, cfg)
    assert len(scenes) == 1                    # rule #3 beats the word cap
    assert len(scenes[0]) == 1


def test_small_trailing_fragment_merges_back():
    cfg = SceneEngineConfig(max_words_per_scene=6, min_words_per_scene=4)
    # a 2-word tail is below min_words -> folds into the previous scene
    script = "One two three four five six. Hi there."
    scenes = segment_scenes(cfg=cfg, script=script)
    assert len(scenes) == 1
    assert scenes[0][-1] == "Hi there."


def test_segmentation_is_deterministic():
    assert segment_scenes(SCRIPT, CFG) == segment_scenes(SCRIPT, CFG)


# ------------------------------------------------------------ classification --
@pytest.mark.parametrize("index,text,expected", [
    (0, "Anything at all here.", SceneType.HOOK),                # first = hook
    (2, "Subscribe and follow for more.", SceneType.CALL_TO_ACTION),
    (2, "The data shows 65% growth this quarter.", SceneType.CHART),
    (2, "This costs more compared to the other option.", SceneType.COMPARISON),
    (2, "As the saying goes, 'less is more here'.", SceneType.QUOTE),
    (2, "Here are three ways to do it.", SceneType.BULLET_LIST),
    (2, "Watch this clip of the launch.", SceneType.VIDEO_INSERT),
    (2, "Take a look at this photo of the result.", SceneType.IMAGE_INSERT),
])
def test_classification_rules(index, text, expected):
    got = classify_scene(text, index=index, n_scenes=6,
                         word_count=len(text.split()))
    assert got == expected


def test_cta_beats_hook_even_on_first_scene():
    got = classify_scene("Subscribe now for more.", index=0, n_scenes=4,
                         word_count=4)
    assert got == SceneType.CALL_TO_ACTION


def test_last_scene_is_outro_when_nothing_stronger():
    got = classify_scene("And that is the whole story today.", index=3,
                         n_scenes=4, word_count=7)
    assert got == SceneType.OUTRO


def test_explanation_vs_talking_head_by_length():
    long = "word " * 30
    short = "word " * 5
    assert classify_scene(long, index=1, n_scenes=4, word_count=30,
                          explanation_min_words=24) == SceneType.EXPLANATION
    assert classify_scene(short, index=1, n_scenes=4, word_count=5,
                          explanation_min_words=24) == SceneType.TALKING_HEAD


def test_classification_is_deterministic():
    kwargs = dict(index=2, n_scenes=5, word_count=6)
    a = classify_scene("Watch this clip now.", **kwargs)
    b = classify_scene("Watch this clip now.", **kwargs)
    assert a == b


def test_refine_asset_kind_and_hint():
    assert refine_asset_kind("image", "shown on the map of europe") == "map"
    assert refine_asset_kind("image", "here on the screen") == "screenshot"
    assert refine_asset_kind("chart", "anything") == "chart"    # non-image passes through
    hint = asset_hint("The rocket engine burns fuel fast", "image")
    assert hint.startswith("image:") and "rocket" in hint


# -------------------------------------------------------------------- timing --
def test_estimate_speech_clamped_to_config():
    cfg = SceneEngineConfig(words_per_minute=150.0, speech_min_s=1.0, speech_max_s=5.0)
    assert estimate_speech_s(0, cfg) == 1.0        # floor
    assert estimate_speech_s(10_000, cfg) == 5.0   # ceiling
    assert estimate_speech_s(150, cfg) == 5.0      # 150 words @150wpm -> 60s -> clamped


def test_scene_window_honours_floor_and_known_duration():
    cfg = SceneEngineConfig()
    speech, window = scene_window_s(2, SceneType.CALL_TO_ACTION, cfg)
    assert window >= cfg.preferred_cta_duration_s  # padded up to preferred CTA length
    speech2, window2 = scene_window_s(50, SceneType.TALKING_HEAD, cfg,
                                      known_duration_s=9.0)
    assert speech2 == 9.0 and window2 == 9.0       # measured audio overrides estimate


def test_plan_timings_contiguous_no_gaps_no_overlaps():
    scenes = [(10, SceneType.HOOK), (20, SceneType.EXPLANATION),
              (5, SceneType.CALL_TO_ACTION)]
    timings = plan_timings(scenes, SceneEngineConfig())
    assert timings[0].start_s == 0.0
    for i in range(1, len(timings)):
        assert timings[i].start_s == timings[i - 1].end_s   # no gap, no overlap
    assert all(t.duration_s > 0 for t in timings)


def test_plan_timings_transition_gap_is_still_gapless_by_construction():
    cfg = SceneEngineConfig(transition_s=0.5)
    timings = plan_timings([(10, SceneType.HOOK), (10, SceneType.OUTRO)], cfg)
    # with a transition gap, scene 2 starts exactly one gap after scene 1 ends
    assert timings[1].start_s == round(timings[0].end_s + 0.5, 3)


def test_known_durations_override_only_named_scenes():
    scenes = [(10, SceneType.HOOK), (10, SceneType.EXPLANATION)]
    timings = plan_timings(scenes, SceneEngineConfig(), known_durations={1: 12.0})
    assert timings[1].speech_duration_s == 12.0


# ---------------------------------------------------------------- storyboard --
def test_storyboard_shape_and_derived_props():
    sb = plan_storyboard(SCRIPT, CFG, title="t", creator="Alex", channel="Chan")
    assert isinstance(sb, Storyboard) and sb.n_scenes > 0
    assert sb.scenes[0].scene_type == SceneType.HOOK
    # duration is derived from scenes (never drifts)
    assert sb.duration_s == round(sum(s.duration_s for s in sb.scenes), 6)
    # scene ids sequential, indices contiguous
    assert [s.index for s in sb.scenes] == list(range(sb.n_scenes))
    assert all(s.scene_id == f"scene-{i:03d}" for i, s in enumerate(sb.scenes))
    # first scene gets intro + lower-third from creator; last gets outro
    assert sb.scenes[0].visual.branding.intro and sb.scenes[0].visual.branding.lower_third
    assert sb.scenes[0].visual.branding.lower_third_title == "Alex"
    assert sb.scenes[-1].visual.branding.outro
    # type_mix fractions sum to ~1
    assert abs(sum(sb.type_mix().values()) - 1.0) < 1e-6


def test_storyboard_is_immutable():
    sb = plan_storyboard(SCRIPT, CFG)
    with pytest.raises(Exception):
        sb.scenes[0].timing.start_s = 99.0        # frozen dataclass


def test_planning_is_byte_identical_deterministic():
    a = storyboard_to_json(plan_storyboard(SCRIPT, CFG, title="x"))
    b = storyboard_to_json(plan_storyboard(SCRIPT, CFG, title="x"))
    assert a == b


def test_storyboard_serde_round_trips():
    sb = plan_storyboard(SCRIPT, CFG, title="rt")
    import json
    from scene_engine.storyboard.serde import storyboard_to_dict
    rebuilt = storyboard_from_dict(json.loads(storyboard_to_json(sb)))
    assert storyboard_to_dict(rebuilt) == storyboard_to_dict(sb)


def test_asset_slots_are_requests_only_with_valid_kinds():
    from reel_engine.interfaces.types import ASSET_KINDS
    sb = plan_storyboard(SCRIPT, CFG)
    slots = sb.all_asset_slots
    assert slots                                   # this script requests assets
    for slot in slots:
        # a slot is a request: an id, a window, a keyword hint — no file path
        assert slot.slot_id and slot.end_s > slot.start_s
        assert not hasattr(slot, "path")
        # image-like kinds must be renderable asset kinds (logo is branding-only)
        if slot.kind != "logo":
            assert slot.kind in ASSET_KINDS


def test_comparison_scene_requests_two_side_by_side_slots():
    sb = plan_storyboard(SCRIPT, CFG)
    comp = [s for s in sb.scenes if s.scene_type == SceneType.COMPARISON]
    assert comp, "expected a comparison scene in the fixture script"
    assets = comp[0].visual.assets
    assert len(assets) == 2 and all(a.layout == CFG.comparison_layout for a in assets)


def test_profiles_cover_every_scene_type():
    for st in SceneType:
        assert st in PROFILES
        prof = profile_for(st)
        assert isinstance(prof.background, tuple) and len(prof.background) == 3


def test_empty_script_yields_empty_storyboard():
    sb = plan_storyboard("   \n\n  ", CFG)
    assert sb.n_scenes == 0 and sb.duration_s == 0.0 and sb.type_mix() == {}


# ------------------------------------------------------- timeline generation --
def _plan_and_lower(script=SCRIPT, cfg=CFG, **kw):
    sb = plan_storyboard(script, cfg)
    tl = build_timeline(sb, **kw)
    return sb, tl


def test_timeline_mirrors_storyboard_and_validates():
    sb, tl = _plan_and_lower()
    assert tl.n_scenes == sb.n_scenes
    assert abs(tl.duration_s - sb.duration_s) < 1e-6
    assert tl.has_captions
    assert validate_timeline(tl) == []            # the renderer's invariants hold


def test_timeline_captions_one_per_narrated_scene_aligned():
    sb, tl = _plan_and_lower()
    track = tl.caption_tracks[0]
    narrated = [s for s in sb.scenes if s.narration.text.strip()]
    assert len(track.segments) == len(narrated)
    for seg, sc in zip(track.segments, narrated):
        assert seg.start_s == sc.timing.start_s and seg.end_s == sc.timing.end_s
        assert seg.text == sc.narration.text.strip()


def test_timeline_scenes_have_no_gaps_or_overlaps():
    sb, tl = _plan_and_lower()
    # scene cards are laid contiguously; validator would flag any gap/overlap
    cursor = 0.0
    for sc in sb.scenes:
        assert abs(sc.timing.start_s - cursor) < 1e-6
        cursor = sc.timing.end_s


def test_build_without_captions():
    sb, tl = _plan_and_lower(with_captions=False)
    assert not tl.has_captions and validate_timeline(tl) == []


def test_caption_track_skips_empty_narration_scenes():
    # a storyboard scene with blank narration should not emit a caption segment
    sb = plan_storyboard(SCRIPT, CFG)
    track = build_caption_track(sb)
    assert all(seg.text.strip() for seg in track.segments)


def test_show_labels_toggle_keeps_timeline_valid():
    sb = plan_storyboard(SCRIPT, CFG)
    tl = build_timeline(sb, show_labels=False)
    assert validate_timeline(tl) == []


# ------------------------------------------------------------------- config ---
def test_config_defaults():
    cfg = load_scene_engine_config()
    assert cfg.words_per_minute == 150.0 and cfg.max_words_per_scene == 30
    assert cfg.caption_kind == "sentence" and cfg.comparison_layout == "side_by_side"


def test_config_overrides_and_env(monkeypatch):
    cfg = load_scene_engine_config(overrides={"scene": {
        "words_per_minute": 200.0, "max_words_per_scene": 12}})
    assert cfg.words_per_minute == 200.0 and cfg.max_words_per_scene == 12
    monkeypatch.setenv("AICP__scene__caption_preset", "tiktok")
    assert load_scene_engine_config().caption_preset == "tiktok"


def test_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        SceneEngineConfig(words_per_minute=0)
    with pytest.raises(ValueError):
        SceneEngineConfig(max_words_per_scene=0)
    with pytest.raises(ValueError):
        SceneEngineConfig(max_scene_duration_s=0)


def test_config_changes_change_the_plan():
    fast = plan_storyboard(SCRIPT, SceneEngineConfig(words_per_minute=300.0))
    slow = plan_storyboard(SCRIPT, SceneEngineConfig(words_per_minute=100.0))
    # a faster pace => shorter estimated reel
    assert fast.duration_s < slow.duration_s


# ------------------------------------------------------------------- facade ---
def test_engine_plan_timeline_end_to_end():
    engine = SceneEngine()
    sb, tl = engine.plan_timeline(SCRIPT, title="e2e")
    assert sb.n_scenes == tl.n_scenes > 0
    assert validate_timeline(tl) == []


def test_engine_known_durations_reused():
    engine = SceneEngine()
    sb = engine.plan(SCRIPT, known_durations={0: 6.5})
    assert sb.scenes[0].timing.speech_duration_s == 6.5
