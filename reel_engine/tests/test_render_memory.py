"""Mock renderer memory-optimization tests (Phase C17).

Verifies the output-preserving memory optimizations: overlay passes are true
no-ops (return the SAME list — no redundant full-frame copy) when their track is
absent, the master frame count is still reported correctly after the master frame
list is released, and the rendered bytes are unchanged (deterministic). Fully
hermetic — no FFmpeg, no GPU.
"""
from __future__ import annotations

import pytest

from foundation.shared_utils.video_io import read_raw_avi
from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces import RenderRequest
from reel_engine.render import MockRenderer
from reel_engine.timeline import build_demo_timeline

FPS = 25


@pytest.fixture
def cfg():
    return ReelEngineConfig(render=RenderConfig(mock_max_dim=64, audio_sample_rate=8000))


@pytest.fixture
def demo():
    return build_demo_timeline(width=1080, height=1920, fps=FPS, duration_s=1.0)


def test_absent_track_overlays_are_identity_passthrough(cfg, demo):
    """A plain timeline (no assets/captions/branding) must not copy frame lists."""
    r = MockRenderer(cfg)
    frames = [b"\x00\x00\x00"] * 10
    assert r._overlay_assets(frames, 4, 4, FPS, demo) is frames
    assert r._overlay_captions(frames, 4, 4, FPS, demo) is frames
    assert r._overlay_branding(frames, 4, 4, FPS, demo) is frames


def test_total_frames_metadata_correct_after_release(cfg, demo, tmp_path):
    req = RenderRequest(timeline=demo, output_path=tmp_path / "reel.avi", renderer="mock")
    res = MockRenderer(cfg).render(req)
    video = read_raw_avi(res.output_path)
    # total_frames (captured before the frame list is released) equals the frames
    # actually written to the master.
    assert res.metadata["total_frames"] == video.n_frames > 0


def test_output_is_byte_deterministic_with_exports(cfg, demo, tmp_path):
    def render(dirname):
        out = tmp_path / dirname / "reel.avi"
        out.parent.mkdir(parents=True)
        return MockRenderer(cfg).render(RenderRequest(
            timeline=demo, output_path=out, renderer="mock",
            export_profiles=("reel_9x16", "square_1x1")))

    a, b = render("a"), render("b")
    assert a.output_path.read_bytes() == b.output_path.read_bytes()
    for ea, eb in zip(a.exports, b.exports):
        assert ea.path.read_bytes() == eb.path.read_bytes()   # exports identical too
