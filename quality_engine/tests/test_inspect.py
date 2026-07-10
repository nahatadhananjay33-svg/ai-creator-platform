"""Media-inspection tests (Phase C16) — probing is deterministic and hermetic."""
from __future__ import annotations

from quality_engine.checker.inspect import inspect_reel
from quality_engine.checker.model import ReelArtifacts


def test_inspect_reads_mock_master_and_sidecars(reel_artifacts):
    insp = inspect_reel(reel_artifacts)
    assert insp.master_exists and insp.video_readable
    assert insp.width > 0 and insp.height > 0
    assert insp.n_frames == round(6.0 * 24)          # 2 scenes x 3s x 24fps
    assert abs(insp.video_duration_s - 6.0) < 0.05
    assert insp.aspect == "9:16"                      # proxy preserves aspect
    assert not insp.errors


def test_inspect_audio_sidecar(reel_artifacts):
    insp = inspect_reel(reel_artifacts)
    assert insp.audio_present and insp.audio_source == "sidecar"
    assert insp.audio_duration_s is not None
    assert abs(insp.audio_duration_s - insp.video_duration_s) < 0.05


def test_inspect_caption_cues(reel_artifacts):
    insp = inspect_reel(reel_artifacts)
    assert insp.captions_sidecar_exists
    assert insp.n_caption_cues == 2                   # one per scene text


def test_inspect_exports_carry_expected_aspect(reel_artifacts):
    insp = inspect_reel(reel_artifacts)
    by_profile = {e.profile: e for e in insp.exports}
    assert by_profile["reel_9x16"].expected_aspect == "9:16"
    assert by_profile["reel_9x16"].aspect_ok
    assert by_profile["square_1x1"].expected_aspect == "1:1"
    assert by_profile["square_1x1"].aspect_ok


def test_inspect_missing_master_records_error(tmp_path):
    insp = inspect_reel(ReelArtifacts(master_path=tmp_path / "nope.avi"))
    assert not insp.master_exists and not insp.video_readable
    assert any("missing" in e for e in insp.errors)


def test_inspect_is_deterministic(render_reel):
    result, tl = render_reel()
    a = ReelArtifacts.from_render_result(result, timeline=tl)
    assert inspect_reel(a).video_duration_s == inspect_reel(a).video_duration_s
    assert inspect_reel(a).n_frames == inspect_reel(a).n_frames
