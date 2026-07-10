"""Engine-stage regression tests (Phase C14) — the real pipeline, hermetically.

Runs the full default ``prompt -> export`` workflow with the dependency-free mock
voice adapter and the mock (raw-AVI proxy) renderer — no GPU, model, ffmpeg, or
network. A low fps keeps the proxy render fast. Asserts every stage executes, the
Timeline is valid, the master + exports are produced, media patches are applied,
the run is deterministic, and it resumes cold.
"""
from __future__ import annotations

import pytest

from reel_engine.timeline.validate import validate_timeline

from workflow_engine import Presentation, WorkflowEngine
from workflow_engine.stages.base import patch_from_spec, patch_to_spec
from editing_engine.patches import MusicPatch, ReplaceAssetPatch

PROMPT = "Why investing in real estate early is beneficial"
PRES = Presentation(theme="finance", soundtrack="upbeat", fps=8)


@pytest.fixture(scope="module")
def produced(tmp_path_factory):
    root = tmp_path_factory.mktemp("wf")
    engine = WorkflowEngine(root=root)
    wf = engine.build(PROMPT, template="real_estate", presentation=PRES, renderer="mock")
    result = engine.run(wf, run_id="job")
    return engine, wf, result


def test_all_stages_execute(produced):
    _engine, wf, result = produced
    assert result.ok
    assert set(result.executed()) == set(wf.order())     # every stage ran
    assert len(wf.order()) == 10


def test_expected_artifacts_present(produced):
    _engine, _wf, result = produced
    for name in ("storyboard", "scene_plan", "voice", "avatar", "assets",
                 "media_plan", "project", "timeline", "master", "exports"):
        assert name in result.artifacts


def test_timeline_is_valid(produced):
    _engine, _wf, result = produced
    timeline = result.artifact("timeline").value
    assert validate_timeline(timeline) == []
    assert timeline.has_captions and timeline.has_branding and timeline.has_music


def test_master_and_exports_are_written(produced):
    _engine, _wf, result = produced
    master = result.artifact("master").value
    assert master.exists()
    exports = result.artifact("exports").value
    assert len(exports) == 2 and all(p.exists() for p in exports)


def test_media_patches_applied(produced):
    _engine, _wf, result = produced
    project = result.artifact("project").value
    assert result.artifact("project").meta["patches_applied"] >= 1
    # the media plan recommended the applied edits
    assert result.artifact("media_plan").meta["n_patches"] >= 1
    assert project.revision >= 1


def test_voice_synthesized_per_scene(produced):
    _engine, _wf, result = produced
    n_scenes = result.artifact("scene_plan").value["n_scenes"]
    voice = result.artifact("voice").value
    assert len(voice) == n_scenes and all(p.exists() for p in voice)


def test_avatar_plan_is_deterministic_descriptor(produced):
    _engine, _wf, result = produced
    plan = result.artifact("avatar").value
    assert plan["clips"] and all(c["status"] == "planned" for c in plan["clips"])


def test_run_is_deterministic(tmp_path):
    # Two independent runs must yield identical artifact content hashes. Music is
    # disabled here because the procedural-music track embeds the (run-specific)
    # generated-WAV file paths — a property of the Music Engine, not the workflow;
    # every other artifact, and the whole IR, is content-pure and reproducible.
    e1 = WorkflowEngine(root=tmp_path / "a")
    e2 = WorkflowEngine(root=tmp_path / "b")
    opts = dict(template="real_estate", presentation=PRES, renderer="mock",
                with_music=False)
    r1 = e1.run(e1.build(PROMPT, **opts), run_id="x")
    r2 = e2.run(e2.build(PROMPT, **opts), run_id="x")
    assert set(r1.artifacts) == set(r2.artifacts)
    for name in r1.artifacts:
        assert r1.artifact(name).content_hash == r2.artifact(name).content_hash, name


def test_cold_resume_reuses_everything(produced):
    engine, wf, _result = produced
    r2 = engine.run(wf, run_id="job")             # same run id -> resume
    assert r2.status_counts()["cached"] == 10
    assert r2.artifact("timeline").value.n_scenes >= 1


def test_patch_spec_roundtrip():
    for patch in (ReplaceAssetPatch(2, asset_type="chart", layout="full_screen"),
                  MusicPatch("cinematic")):
        assert patch_from_spec(patch_to_spec(patch)) == patch
