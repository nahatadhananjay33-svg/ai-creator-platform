"""Creator Studio regression tests (Phase C12) — hermetic UI integration.

Fully hermetic and deterministic: MockProvider + the mock renderer only — NO API
key, NO network, NO model, NO GPU, NO ffmpeg. Covers the UI controller end to end:
project open/save, the storyboard/timeline/inspector/incremental/history/preview
panels, patch generation + validation surfacing, undo/redo, incremental-plan
visualization, and the prompt → review → edit → preview → export loop.

The invariants the phase requires are asserted directly: no direct mutation of a
ReelProject (every edit is a patch routed through the engine), the Timeline IR and
renderer are untouched, and the incremental plan accurately reflects the changed
scenes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from reel_engine.timeline.validate import validate_timeline

from editing_engine import ReelProject
from script_engine import ScriptEngine, storyboard_to_json

from creator_studio import (
    CommandResult,
    StudioSession,
    StudioView,
    load_project,
    project_from_json,
    project_to_json,
    save_project,
)

PROMPT = "Why investing in real estate early is beneficial"


@pytest.fixture
def session(tmp_path) -> StudioSession:
    return StudioSession.new(PROMPT, template="real_estate", workspace=tmp_path)


# ------------------------------------------------------------- project manager
def test_new_session_opens_a_project(session):
    assert session.project.n_scenes > 0
    assert session.revision == 0
    assert session.project.storyboard.provider == "mock"       # deterministic
    view = session.view()
    assert isinstance(view, StudioView)
    assert view.project.revision == 0 and not view.project.dirty


def test_save_and_open_roundtrip_preserves_project(session, tmp_path):
    session.set_theme("finance")
    session.set_narration(1, "A crisp rewritten second line for the reel.")
    path = tmp_path / "reel.studio.json"
    session.save(path)
    assert not session.view().project.dirty                    # save clears dirty
    reopened = StudioSession.open(path, workspace=tmp_path)
    assert reopened.project.theme == "finance"
    assert reopened.project.scenes[1].narration == "A crisp rewritten second line for the reel."
    assert reopened.revision == session.revision               # revision preserved


def test_project_json_roundtrip_is_byte_stable(session):
    session.set_music("cinematic")
    text = project_to_json(session.project)
    again = project_to_json(project_from_json(text))
    assert text == again


def test_save_without_path_raises(session):
    with pytest.raises(ValueError):
        session.save()


# ------------------------------------------------------------- storyboard panel
def test_storyboard_panel_reflects_scenes_and_selection(session):
    session.select_scene(2)
    panel = session.view().storyboard
    assert panel.n_scenes == session.project.n_scenes
    assert panel.selected_index == 2
    assert panel.scenes[2].selected and not panel.scenes[0].selected
    assert panel.scenes[0].preview                              # truncated narration present


def test_select_scene_out_of_range_is_rejected(session):
    result = session.select_scene(999)
    assert not result.ok and result.problems


def test_insert_delete_move_are_patch_backed(session):
    n = session.project.n_scenes
    assert session.insert_scene(1, "An inserted middle scene for the reel.").ok
    assert session.project.n_scenes == n + 1
    assert session.delete_scene(0).ok
    assert session.project.n_scenes == n
    moved = session.move_scene(0, 3)                            # drag-and-drop reorder
    assert moved.ok and moved.patch_op == "move_scene"


# --------------------------------------------------------------- timeline view
def test_timeline_panel_has_bars_playhead_and_offsets(session):
    panel = session.view().timeline
    assert len(panel.bars) == session.build_timeline().n_scenes
    assert panel.total_duration_s > 0 and panel.aspect == "9:16"
    # bars are contiguous: each bar starts where the previous ended
    for a, b in zip(panel.bars, panel.bars[1:]):
        assert b.start_s == pytest.approx(a.end_s)


def test_playback_controls_move_the_playhead(session):
    session.seek_scene(2)
    assert session.view().timeline.playhead_scene == 2
    session.next_scene()
    assert session.view().timeline.playhead_scene == 3
    session.prev_scene()
    assert session.view().timeline.playhead_scene == 2
    session.seek(0.0)
    assert session.view().timeline.playhead_s == 0.0


# --------------------------------------------------------------- inspector panel
def test_inspector_exposes_selected_scene_and_valid_options(session):
    session.select_scene(1)
    insp = session.view().inspector
    assert insp.scene_index == 1
    assert insp.narration == session.project.scenes[1].narration
    assert "finance" in insp.theme_options and "cinematic" in insp.soundtrack_options
    assert "chart" in insp.asset_kind_options and "full_screen" in insp.asset_layout_options


def test_inspector_edits_produce_the_right_patch_types(session):
    assert session.set_narration(0, "A rewritten opening hook line here.").patch_op == "replace_narration"
    assert session.set_duration(0, 5.5).patch_op == "adjust_duration"
    assert session.replace_asset(0, asset_type="chart", layout="full_screen").patch_op == "replace_asset"
    assert session.set_theme("dark").patch_op == "change_theme"
    assert session.set_music("lofi").patch_op == "change_music"
    assert session.set_caption(kind="karaoke", preset="tiktok").patch_op == "change_caption"
    p = session.project
    assert p.theme == "dark" and p.soundtrack == "lofi"
    assert p.caption_kind == "karaoke" and p.caption_preset == "tiktok"


def test_caption_visibility_toggle_is_not_a_project_edit(session):
    rev = session.revision
    result = session.toggle_captions()
    assert result.ok and result.patch_op == ""                 # no patch
    assert session.revision == rev                             # no revision bump
    assert not session.captions_enabled
    # the toggle changes the rendered timeline (caption track omitted)
    assert session.build_timeline().has_captions is False
    session.toggle_captions()
    assert session.build_timeline().has_captions is True


# --------------------------------------------------------- patch / validation
def test_invalid_edits_surface_problems_and_do_not_change_state(session):
    before = storyboard_to_json(session.project.storyboard)
    rev = session.revision
    bad = session.set_theme("rainbow")
    assert not bad.ok and any("unknown theme" in p for p in bad.problems)
    assert session.revision == rev                             # unchanged
    assert storyboard_to_json(session.project.storyboard) == before


@pytest.mark.parametrize("call,needle", [
    (lambda s: s.delete_scene(99), "out of range"),
    (lambda s: s.move_scene(0, 99), "out of range"),
    (lambda s: s.set_narration(0, "   "), "empty narration"),
    (lambda s: s.set_music("dubstep"), "unknown soundtrack"),
    (lambda s: s.set_duration(0, -1.0), "must be positive"),
    (lambda s: s.replace_asset(0, asset_type="hologram"), "unknown asset_type"),
])
def test_each_invalid_command_is_rejected(session, call, needle):
    result = call(session)
    assert not result.ok and any(needle in p for p in result.problems)


def test_session_never_mutates_the_project_object(session):
    original = session.project                                 # frozen snapshot
    session.set_theme("finance")
    assert original.theme == "modern"                          # base object untouched
    assert session.project is not original                     # a NEW project
    with pytest.raises(Exception):
        original.theme = "x"                                   # frozen dataclass


# ------------------------------------------------------------------- history
def test_undo_redo_through_the_controller(session):
    session.set_theme("finance")
    session.set_music("cinematic")
    assert session.revision == 2
    assert session.undo().ok and session.project.soundtrack == "ambient"
    hist = session.view().history
    assert hist.can_redo and hist.n_patches == 1
    assert session.redo().ok and session.project.soundtrack == "cinematic"
    assert not session.view().history.can_redo


def test_undo_redo_with_nothing_to_do_is_reported_not_raised(session):
    assert not session.undo().ok                               # nothing to undo yet
    assert not session.redo().ok                               # nothing to redo yet
    session.set_theme("dark")
    assert session.undo().ok                                   # now there is
    assert session.redo().ok                                   # and it can be redone
    assert not session.redo().ok                               # but only once


def test_history_panel_is_the_patch_timeline(session):
    session.set_narration(0, "A rewritten opening beat for the reel.")
    session.move_scene(1, 3)
    session.set_theme("dark")
    panel = session.view().history
    assert [e.op for e in panel.entries] == ["replace_narration", "move_scene", "change_theme"]
    assert panel.entries[-1].current and panel.cursor == 2


def test_replay_is_deterministic(session):
    session.set_narration(0, "A rewritten opening beat for the reel.")
    session.move_scene(1, 3)
    session.set_theme("dark")
    replayed = session.replay()
    assert storyboard_to_json(replayed.storyboard) == storyboard_to_json(session.project.storyboard)
    assert replayed.theme == session.project.theme and replayed.revision == session.revision


def test_new_edit_after_undo_clears_redo(session):
    session.set_theme("finance")
    session.undo()
    session.set_theme("dark")
    assert not session.view().history.can_redo
    assert session.project.theme == "dark"


# --------------------------------------------------- incremental visualization
def test_incremental_panel_flags_only_changed_scene(session):
    session.set_narration(2, "A completely rewritten third scene with brand new content here.")
    inc = session.view().incremental
    assert inc.changed == (2,)
    assert inc.n_reused == session.project.n_scenes - 1
    assert inc.reuse_fraction > 0.8 and inc.needs_render
    assert inc.cache_hits == inc.n_reused and inc.cache_misses == inc.n_changed


def test_incremental_scene_status_aligns_with_timeline_bars(session):
    session.move_scene(2, 4)
    view = session.view()
    inc, timeline = view.incremental, view.timeline
    assert len(inc.scene_status) == len(timeline.bars)
    for bar, status in zip(timeline.bars, inc.scene_status):
        assert bar.status == status                            # bar highlight == plan
    # partition: every scene is either reused or changed, disjointly
    assert set(inc.changed) | set(inc.reused) == set(range(inc.total))
    assert not (set(inc.changed) & set(inc.reused))
    assert set(inc.reused).issubset(set(inc.cacheable))


def test_no_edits_means_full_reuse(session):
    inc = session.view().incremental
    assert inc.n_changed == 0 and not inc.needs_render and inc.reuse_fraction == 1.0


def test_overlay_only_edit_is_reflected(session):
    session.set_theme("finance")                               # overlay change, no scene change
    inc = session.view().incremental
    assert inc.overlays_changed and inc.needs_render


# --------------------------------------------------------- preview & export
def test_preview_renders_current_project(session):
    preview = session.preview()
    assert Path(preview["media_path"]).exists()
    view = session.view()
    assert view.preview.ready and view.preview.duration_s > 0
    assert len(view.preview.scene_offsets) == session.build_timeline().n_scenes


def test_editing_invalidates_a_stale_preview(session):
    session.preview()
    assert session.view().preview.ready
    session.set_theme("dark")                                  # edit after render
    assert not session.view().preview.ready                   # preview no longer matches


def test_export_uses_the_existing_renderer(session, tmp_path):
    out = tmp_path / "final.avi"
    result = session.export(out, renderer="mock", export_profiles=("reel_9x16",))
    assert out.exists() and result.renderer == "mock"
    assert result.n_scenes == session.build_timeline().n_scenes
    assert len(result.exports) == 1 and result.exports[0].profile == "reel_9x16"


# ------------------------------------------------------- invariants / IR safety
def test_timeline_ir_valid_after_every_command(session):
    commands = [
        lambda s: s.set_narration(1, "Fresh narration for the second scene here."),
        lambda s: s.move_scene(2, 0),
        lambda s: s.insert_scene(1, "An added scene in the middle of the reel."),
        lambda s: s.set_theme("dark"),
        lambda s: s.set_music("lofi"),
        lambda s: s.set_caption(kind="word", preset="youtube"),
        lambda s: s.delete_scene(0),
    ]
    for cmd in commands:
        assert cmd(session).ok
        assert validate_timeline(session.build_timeline()) == []


def test_full_view_is_deterministic(tmp_path):
    def run():
        s = StudioSession.new(PROMPT, template="real_estate", workspace=tmp_path)
        s.set_theme("finance")
        s.set_narration(1, "A stable deterministic rewrite for the second scene.")
        s.move_scene(2, 4)
        return s.view()
    a, b = run(), run()
    # storyboard + timeline + incremental panels are byte-identical across runs
    assert a.storyboard == b.storyboard
    assert a.timeline.bars == b.timeline.bars
    assert a.incremental == b.incremental
    assert [e.describe for e in a.history.entries] == [e.describe for e in b.history.entries]


# ----------------------------------------------------------- end-to-end loop
def test_end_to_end_prompt_review_edit_preview_export(tmp_path):
    # 1) prompt -> project
    session = StudioSession.new(PROMPT, template="real_estate", workspace=tmp_path)
    base_rev = session.revision
    # 2) review
    report = session.review()
    assert isinstance(report.findings, tuple)
    # 3) edit (a representative patch set), Timeline valid after each
    assert session.set_narration(1, "Here is the single biggest reason to start early.").ok
    assert session.move_scene(2, 4).ok
    assert session.insert_scene(3, "Picture the compounding growth over ten years.").ok
    assert session.delete_scene(5).ok
    assert session.set_theme("finance").ok
    assert session.set_music("cinematic").ok
    assert session.set_caption(preset="tiktok").ok
    assert validate_timeline(session.build_timeline()) == []
    assert session.revision == base_rev + 7
    # 4) incremental regeneration reflects the edits
    inc = session.view().incremental
    assert inc.needs_render and inc.n_reused >= 1
    # 5) preview + export an updated reel
    assert Path(session.preview()["media_path"]).exists()
    out = tmp_path / "updated.avi"
    result = session.export(out, renderer="mock", export_profiles=("reel_9x16", "square_1x1"))
    assert out.exists() and len(result.exports) == 2
    # the edit history replays byte-identically (deterministic revisions)
    assert storyboard_to_json(session.replay().storyboard) == \
        storyboard_to_json(session.project.storyboard)


def test_wrapping_an_existing_storyboard_project(tmp_path):
    sb = ScriptEngine().generate_storyboard(PROMPT, template="real_estate")
    session = StudioSession(ReelProject(storyboard=sb), workspace=tmp_path)
    assert session.project.n_scenes == sb.n_scenes
    assert isinstance(session.set_theme("finance"), CommandResult)
