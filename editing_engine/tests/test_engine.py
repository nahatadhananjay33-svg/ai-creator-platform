"""Review & Editing Engine regression tests (Phase C11).

Fully hermetic and deterministic: MockProvider only — NO API key, NO network, NO
model, NO GPU. Covers the immutable patch operations, patch/project validation,
edit history (undo/redo/replay), the review step, the incremental-render plan, and
the EditingEngine facade. The Timeline is validated after every patch so an edit
can never yield an unrenderable reel.
"""
from __future__ import annotations

import dataclasses

import pytest

from reel_engine.timeline.validate import validate_timeline

from editing_engine import (
    CaptionPatch,
    DeleteScenePatch,
    DurationPatch,
    EditHistory,
    EditingEngine,
    InsertScenePatch,
    MoveScenePatch,
    MusicPatch,
    PATCH_TYPES,
    PatchError,
    RegenerateScenePatch,
    ReelProject,
    ReplaceAssetPatch,
    ReplaceNarrationPatch,
    ThemePatch,
    apply_patch,
    plan_incremental,
    review_project,
    validate_patch,
)
from script_engine import ScriptEngine, storyboard_to_json

PROMPT = "Why investing in real estate early is beneficial"


@pytest.fixture
def project() -> ReelProject:
    sb = ScriptEngine().generate_storyboard(PROMPT, template="real_estate")
    return ReelProject(storyboard=sb)


@pytest.fixture(scope="module")
def engine() -> EditingEngine:
    return EditingEngine()


# ------------------------------------------------------------------- patches
def test_ten_patch_types_exist():
    assert len(PATCH_TYPES) == 10


def test_patches_are_immutable_and_bump_revision(project):
    edited = apply_patch(ThemePatch("finance"), project)
    assert edited is not project and edited.revision == project.revision + 1
    assert project.theme == "modern" and edited.theme == "finance"   # base untouched
    with pytest.raises(Exception):
        edited.theme = "x"                                            # frozen


def test_insert_delete_move_reorder_scenes(project):
    n = project.n_scenes
    ins = apply_patch(InsertScenePatch(2, "A new inserted scene here.", "explanation"), project)
    assert ins.n_scenes == n + 1 and ins.scenes[2].narration == "A new inserted scene here."
    dele = apply_patch(DeleteScenePatch(0), project)
    assert dele.n_scenes == n - 1 and dele.scenes[0] == project.scenes[1]
    mov = apply_patch(MoveScenePatch(0, n - 1), project)
    assert mov.scenes[-1] == project.scenes[0] and mov.n_scenes == n


def test_replace_narration_and_asset_and_duration(project):
    rn = apply_patch(ReplaceNarrationPatch(1, "New narration for scene one here."), project)
    assert rn.scenes[1].narration == "New narration for scene one here."
    ra = apply_patch(ReplaceAssetPatch(1, asset_type="chart", layout="full_screen"), project)
    assert ra.scenes[1].asset_type == "chart" and ra.scenes[1].layout == "full_screen"
    du = apply_patch(DurationPatch(1, 7.5), project)
    assert du.scenes[1].duration_estimate_s == 7.5


def test_theme_music_caption_settings(project):
    p = apply_patch(ThemePatch("dark"), project)
    p = apply_patch(MusicPatch("cinematic"), p)
    p = apply_patch(CaptionPatch(kind="karaoke", preset="tiktok"), p)
    assert p.theme == "dark" and p.soundtrack == "cinematic"
    assert p.caption_kind == "karaoke" and p.caption_preset == "tiktok"


def test_regenerate_scene_via_provider_is_deterministic(project):
    patch = RegenerateScenePatch(1, provider="mock", instruction="Explain the tax advantages")
    a = apply_patch(patch, project)
    b = apply_patch(patch, project)
    assert a.scenes[1].narration == b.scenes[1].narration          # deterministic
    assert a.scenes[1].narration != project.scenes[1].narration    # actually changed


# --------------------------------------------------------------- validation
@pytest.mark.parametrize("patch,needle", [
    (DeleteScenePatch(99), "out of range"),
    (MoveScenePatch(0, 99), "out of range"),
    (ReplaceNarrationPatch(0, "   "), "empty narration"),
    (ThemePatch("rainbow"), "unknown theme"),
    (MusicPatch("dubstep"), "unknown soundtrack"),
    (CaptionPatch(kind="bogus"), "unknown kind"),
    (DurationPatch(0, -1.0), "must be positive"),
    (ReplaceAssetPatch(0, asset_type="hologram"), "unknown asset_type"),
    (InsertScenePatch(0, "", "hook"), "empty narration"),
])
def test_invalid_patches_are_rejected(project, patch, needle):
    assert any(needle in p for p in validate_patch(patch, project))
    with pytest.raises(PatchError):
        apply_patch(patch, project)


def test_delete_last_remaining_scene_rejected(project):
    single = project.with_scenes(project.scenes[:1])
    with pytest.raises(PatchError):
        apply_patch(DeleteScenePatch(0), single)


# ----------------------------------------------------------------- history
def test_history_apply_undo_redo(project):
    h = EditHistory(project)
    h.apply(ReplaceNarrationPatch(0, "First edit narration here."))
    h.apply(ThemePatch("finance"))
    assert h.n_patches == 2 and h.current.theme == "finance"
    h.undo()
    assert h.current.theme == "modern" and h.can_redo
    h.redo()
    assert h.current.theme == "finance" and not h.can_redo
    assert len(h.log()) == 2


def test_history_replay_is_deterministic(project):
    h = EditHistory(project)
    h.apply(MoveScenePatch(1, 3))
    h.apply(ReplaceNarrationPatch(0, "A rewritten opening line here."))
    h.apply(ThemePatch("dark"))
    replayed = h.replay()
    assert storyboard_to_json(replayed.storyboard) == storyboard_to_json(h.current.storyboard)
    assert replayed.theme == h.current.theme and replayed.revision == h.current.revision


def test_new_patch_after_undo_clears_redo(project):
    h = EditHistory(project)
    h.apply(ThemePatch("finance"))
    h.undo()
    h.apply(ThemePatch("dark"))
    assert not h.can_redo and h.current.theme == "dark"


def test_undo_with_no_history_raises(project):
    with pytest.raises(IndexError):
        EditHistory(project).undo()


# ------------------------------------------------------------------ review
def test_review_clean_storyboard_has_no_warnings(project):
    report = review_project(project)
    assert report.ok                                                # no warnings
    assert isinstance(report.findings, tuple)


def test_review_flags_long_scene(project):
    long_text = "word " * 60
    edited = apply_patch(ReplaceNarrationPatch(1, long_text), project,
                         validate_result=False)
    report = review_project(edited)
    assert any("long" in f.message and f.severity == "warning" for f in report.findings)


def test_review_flags_missing_cta():
    # a storyboard whose last scene is not a CTA
    sb = ScriptEngine().generate_storyboard(PROMPT, template="real_estate")
    no_cta = dataclasses.replace(
        sb, scenes=tuple(dataclasses.replace(s, scene_type="explanation", cta=False)
                         for s in sb.scenes))
    report = review_project(ReelProject(storyboard=no_cta))
    assert any("call to action" in f.message for f in report.findings)


# -------------------------------------------------------------- incremental
def test_incremental_plan_identifies_only_changed_scene(project, engine):
    _, base_tl = engine.build_timeline(project, with_branding=False, with_music=False)
    edited = apply_patch(
        ReplaceNarrationPatch(2, "A completely rewritten third scene with new content."), project)
    _, new_tl = engine.build_timeline(edited, with_branding=False, with_music=False)
    plan = plan_incremental(base_tl, new_tl)
    assert plan.changed == (2,) and plan.n_reused == project.n_scenes - 1
    assert plan.reuse_fraction > 0.8 and plan.needs_render


def test_incremental_plan_no_change_needs_no_render(project, engine):
    _, tl = engine.build_timeline(project, with_branding=False, with_music=False)
    plan = plan_incremental(tl, tl)
    assert plan.n_changed == 0 and not plan.needs_render and plan.reuse_fraction == 1.0


def test_incremental_plan_partitions_and_reuses(project, engine):
    _, base_tl = engine.build_timeline(project, with_branding=False, with_music=False)
    # a reorder: the deterministic Scene Engine re-classifies by content+position,
    # so some scenes genuinely change — the plan reports the honest diff.
    edited = apply_patch(MoveScenePatch(2, 4), project)
    _, new_tl = engine.build_timeline(edited, with_branding=False, with_music=False)
    plan = plan_incremental(base_tl, new_tl)
    assert set(plan.changed) | set(plan.reused) == set(range(plan.total))  # partition
    assert not (set(plan.changed) & set(plan.reused))                      # disjoint
    assert set(plan.reused).issubset(set(plan.cacheable))                  # reused ⊆ cacheable
    assert plan.n_reused >= 1                                              # untouched scenes remain


# ------------------------------------------------------------------- facade
def test_facade_new_project_and_full_timeline(engine, tmp_path):
    project = engine.new_project(PROMPT, template="finance")
    assert project.n_scenes > 0 and project.storyboard.provider == "mock"
    _, tl = engine.build_timeline(project, asset_dir=tmp_path)
    assert tl.has_captions and tl.has_branding and tl.has_music
    assert validate_timeline(tl) == []


def test_timeline_valid_after_every_patch(engine, project):
    patches = [
        ReplaceNarrationPatch(1, "Fresh narration for the second scene here."),
        MoveScenePatch(2, 0),
        InsertScenePatch(1, "An added scene in the middle of the reel.", "explanation"),
        ThemePatch("dark"), MusicPatch("lofi"),
        CaptionPatch(kind="word", preset="youtube"),
        DeleteScenePatch(0),
    ]
    p = project
    for patch in patches:
        p = apply_patch(patch, p)
        _, tl = engine.build_timeline(p, with_branding=False, with_music=False)
        assert validate_timeline(tl) == [], patch.op
