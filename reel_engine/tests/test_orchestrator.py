"""End-to-end pipeline orchestration tests (Phase C3 walking skeleton).

Almost everything here is hermetic: the Voice/Avatar stages are injected fakes
that write a tiny WAV / raw-AVI, and the mock renderer lowers the Timeline with
no ffmpeg — so orchestration, Timeline generation, configuration, error handling,
and renderer integration are all pinned without a single model weight or GPU.

Exactly one test (``test_end_to_end_real_engine_stack``) exercises the *real*
engine stack — the production VoiceEngine + avatar adapter registry + the real
ffmpeg renderer — via the dependency-free ``mock`` model ids, and is skipped when
ffmpeg is absent. It is the one integration test that runs the actual engines.
"""
from __future__ import annotations

import pytest

from foundation.exceptions import ConfigError
from foundation.shared_utils import generate_sine_wav, read_wav, write_wav
from foundation.shared_utils.video_io import generate_test_pattern_video
from reel_engine.orchestrator import (
    CreatorPipeline,
    PipelineError,
    load_pipeline_config,
)
from reel_engine.orchestrator.adapters import (
    AvatarResult,
    EngineAvatarStage,
    EngineVoiceStage,
    VoiceResult,
)
from reel_engine.orchestrator.config import DEMO_FACE_PATH
from reel_engine.render import ffprobe_available, probe_media
from reel_engine.timeline.validate import validate_timeline


# ------------------------------------------------------------------- fakes
class FakeVoiceStage:
    """Writes a short sine WAV; records the text it was asked to speak."""

    def __init__(self, duration_s: float = 1.0) -> None:
        self.duration_s = duration_s
        self.calls: list[str] = []

    def synthesize(self, text, output_path) -> VoiceResult:
        self.calls.append(text)
        write_wav(output_path, generate_sine_wav(self.duration_s, 220.0, 24000))
        return VoiceResult(audio_path=output_path, sample_rate=24000,
                           duration_s=self.duration_s, engine_id="fake-voice")


class FakeAvatarStage:
    """Writes a raw-AVI 'talking head' sized to the driving audio."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def generate(self, reference, audio_path, output_path) -> AvatarResult:
        self.calls.append((reference, audio_path))
        dur = read_wav(audio_path).duration_s
        avi = output_path.with_suffix(".avi")
        generate_test_pattern_video(avi, width=48, height=64,
                                    n_frames=max(2, int(dur * 25)), fps=25.0)
        return AvatarResult(video_path=avi, duration_s=dur, fps=25.0,
                            width=48, height=64, engine_id="fake-avatar")


def _hermetic_config(tmp_path, **render):
    r = {"renderer": "mock", "width": 180, "height": 320, "fps": 24, **render}
    return load_pipeline_config(overrides={"render": r, "output_dir": str(tmp_path)})


def _pipeline(tmp_path, voice=None, avatar=None, **render):
    return CreatorPipeline(
        _hermetic_config(tmp_path, **render),
        voice_stage=voice or FakeVoiceStage(),
        avatar_stage=avatar or FakeAvatarStage(),
    )


# --------------------------------------------------------------- configuration
def test_config_defaults():
    cfg = load_pipeline_config()
    assert cfg.voice.model == "kokoro"
    assert cfg.avatar.model == "musetalk"
    assert cfg.render.renderer == "ffmpeg"
    assert (cfg.render.width, cfg.render.height, cfg.render.fps) == (1080, 1920, 30)
    assert cfg.export.profiles == ["reel_9x16"]


def test_config_overrides_and_reuses_render_schema():
    cfg = load_pipeline_config(overrides={
        "voice": {"model": "chatterbox"}, "avatar": {"model": "latentsync"},
        "render": {"width": 720, "height": 1280}, "export": {"profiles": ["square_1x1"]}})
    assert cfg.voice.model == "chatterbox" and cfg.avatar.model == "latentsync"
    # reel_config() surfaces the SAME render/export objects for the renderer.
    reel = cfg.reel_config()
    assert reel.render is cfg.render and reel.export is cfg.export
    assert (reel.render.width, reel.render.height) == (720, 1280)


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("AICP__render__fps", "48")
    monkeypatch.setenv("AICP__voice__model", "mock")
    cfg = load_pipeline_config()
    assert cfg.render.fps == 48 and cfg.voice.model == "mock"


def test_config_rejects_unknown_key():
    with pytest.raises(ConfigError):
        load_pipeline_config(overrides={"voice": {"nope": 1}})


# --------------------------------------------------------- orchestration + IR
def test_pipeline_produces_reel_and_timings(tmp_path):
    voice, avatar = FakeVoiceStage(1.5), FakeAvatarStage()
    res = _pipeline(tmp_path, voice, avatar).run(script="Hello world", output_name="r")
    assert res.output_path.exists() and res.output_path.stat().st_size > 0
    # every stage timed, and total is the largest single number reported
    assert set(res.timings) == {"voice_s", "avatar_s", "timeline_s",
                                "render_s", "export_s", "total_s"}
    assert res.timings["total_s"] >= res.timings["render_s"]
    assert res.voice.engine_id == "fake-voice" and res.avatar.engine_id == "fake-avatar"


def test_timeline_generation_is_single_video_scene(tmp_path):
    voice = FakeVoiceStage(2.0)
    res = _pipeline(tmp_path, voice, width=540, height=960, fps=25).run(
        script="One scene only")
    tl = res.timeline
    assert tl.n_scenes == 1
    assert (tl.meta.width, tl.meta.height, tl.meta.fps) == (540, 960, 25)
    scene = tl.scenes[0]
    assert scene.video_clip() is not None            # real footage, not a solid card
    assert scene.audio_file_clip() is not None        # authoritative speech WAV
    assert abs(scene.duration_s - 2.0) < 0.05         # follows the avatar footage
    assert validate_timeline(tl) == []


def test_project_json_is_written_and_valid(tmp_path):
    from reel_engine.timeline.serde import timeline_from_json
    res = _pipeline(tmp_path).run(script="Persisted", output_name="proj")
    assert res.project_path.exists()
    restored = timeline_from_json(res.project_path.read_text())
    assert restored == res.timeline                   # round-trips the built IR


def test_stages_run_in_order_with_wired_inputs(tmp_path):
    voice, avatar = FakeVoiceStage(), FakeAvatarStage()
    res = _pipeline(tmp_path, voice, avatar).run(script="Wire me", reference=DEMO_FACE_PATH)
    assert voice.calls == ["Wire me"]                 # voice saw the script
    (ref, audio), = avatar.calls
    assert ref == DEMO_FACE_PATH                       # avatar got the reference...
    assert audio == res.voice.audio_path               # ...and the voice's WAV


def test_renderer_integration_reports_scene_and_dims(tmp_path):
    res = _pipeline(tmp_path, width=180, height=320, fps=24).run(script="Render me")
    assert res.render.n_scenes == 1
    assert res.render.renderer == "mock"
    assert res.render.duration_s > 0


def test_export_profiles_via_mock_fallback(tmp_path):
    # MockRenderer has no export_master(); the pipeline falls back to a profiles
    # render and still surfaces the requested exports.
    res = _pipeline(tmp_path, **{}).run(script="Export me")
    # default profile set for hermetic config is inherited from defaults (reel_9x16)
    assert all(e.profile for e in res.exports)


# --------------------------------------------------------------- error handling
def test_error_on_no_script(tmp_path):
    with pytest.raises(PipelineError, match="No script"):
        _pipeline(tmp_path).run()


def test_error_on_empty_script(tmp_path):
    with pytest.raises(PipelineError, match="empty"):
        _pipeline(tmp_path).run(script="   \n  ")


def test_error_on_missing_script_file(tmp_path):
    with pytest.raises(PipelineError, match="not found"):
        _pipeline(tmp_path).run(script_path=tmp_path / "nope.txt")


def test_error_on_missing_reference(tmp_path):
    with pytest.raises(PipelineError, match="Reference"):
        _pipeline(tmp_path).run(script="hi", reference=tmp_path / "no_face.png")


# --------------------------------------- one real-engine integration test (ffmpeg)
@pytest.mark.integration
@pytest.mark.skipif(not ffprobe_available(), reason="ffmpeg/ffprobe not installed")
def test_end_to_end_real_engine_stack(tmp_path):
    """The actual VoiceEngine + avatar registry + real ffmpeg renderer, wired via
    the dependency-free ``mock`` model ids — the single full-stack integration."""
    cfg = load_pipeline_config(overrides={
        "voice": {"model": "mock"}, "avatar": {"model": "mock"},
        "render": {"renderer": "ffmpeg", "width": 180, "height": 320,
                   "fps": 24, "bitrate": "800k"},
        "export": {"profiles": ["reel_9x16"]},
        "output_dir": str(tmp_path)})
    pipeline = CreatorPipeline(
        cfg,
        voice_stage=EngineVoiceStage(cfg.voice),
        avatar_stage=EngineAvatarStage(cfg.avatar),
    )
    res = pipeline.run(script="End to end from a single line of text.",
                       output_name="e2e")
    p = probe_media(res.output_path)
    assert p.readable and p.has_audio                  # real muxed audio+video
    assert (p.width, p.height) == (180, 320)           # correct resolution
    assert p.duration_s > 0.3                          # non-trivial reel
    assert res.render.aspect == "9:16"
    (export,) = res.exports
    ep = probe_media(export.path)
    assert (ep.width, ep.height) == (1080, 1920)       # profile export produced


# --------------------------------------------------------------- benchmark wiring
def test_pipeline_benchmark_records_stage_timings(tmp_path):
    """The benchmark harness runs the pipeline (mock renderer, hermetic) and
    records every stage timing + memory metric the runner attaches."""
    from reel_engine.orchestrator.benchmark import PipelineBenchmark, PipelineBenchmarkConfig

    cfg = PipelineBenchmarkConfig(renderer="mock", width=180, height=320, fps=12,
                                  profiles=["reel_9x16"], repetitions=1)
    run, reports = PipelineBenchmark(cfg, output_dir=tmp_path).run()
    (case,) = run.cases
    assert case.status.value == "passed"
    names = {m.name for m in case.measurements}
    assert {"voice_ms", "avatar_ms", "timeline_ms", "render_ms", "export_ms",
            "total_ms", "rss_mb"} <= names
    assert reports["json"].exists() and reports["csv"].exists()
