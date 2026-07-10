"""Shared fixtures for the Quality Engine tests (Phase C16).

Everything is hermetic and deterministic: reels are rendered with the ``mock``
backend (stdlib raw-AVI proxy + WAV/SRT sidecars) into pytest's tmp_path — no GPU,
no ffmpeg, no network, no models. A fixed Timeline always renders byte-identical
output, so the checker's verdict is reproducible.
"""
from __future__ import annotations

from array import array

import pytest

from foundation.shared_utils import WavData, write_wav

from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.interfaces.types import (
    BrandingTrack,
    CaptionSegment,
    CaptionTrack,
    Logo,
    RenderRequest,
    Scene,
    Timeline,
    TimelineMeta,
)
from reel_engine.render import get_renderer

from quality_engine.checker.model import ReelArtifacts


def make_timeline(*, with_captions: bool = True, with_branding: bool = True,
                  n_scenes: int = 2, scene_s: float = 3.0) -> Timeline:
    """A small but complete Timeline: coloured scenes + optional captions/branding."""
    scenes = tuple(
        Scene.simple(i, color=(20 * (i + 1), 40, 90), text=f"Scene {i}", duration_s=scene_s)
        for i in range(n_scenes)
    )
    caption_tracks = ()
    if with_captions:
        segs = tuple(
            CaptionSegment(segment_id=f"c{i}", index=i, text=f"Line {i}",
                           start_s=i * scene_s, end_s=(i + 1) * scene_s)
            for i in range(n_scenes)
        )
        caption_tracks = (CaptionTrack(track_id="captions", kind="sentence", segments=segs),)
    branding = BrandingTrack(logo=Logo(text="BR")) if with_branding else None
    return Timeline(meta=TimelineMeta(title="test", width=1080, height=1920, fps=24),
                    scenes=scenes, caption_tracks=caption_tracks, branding=branding)


@pytest.fixture
def mock_config() -> ReelEngineConfig:
    return ReelEngineConfig(render=RenderConfig(width=1080, height=1920, fps=24,
                                                renderer="mock"))


@pytest.fixture
def voice_clip(tmp_path):
    """A short non-silent narration WAV (so voice detection passes)."""
    path = tmp_path / "voice_000.wav"
    samples = array("h", [1000, -1000] * 2000)
    write_wav(path, WavData(samples=samples, sample_rate=24_000, channels=1))
    return path


@pytest.fixture
def render_reel(tmp_path, mock_config):
    """Render a Timeline with the mock backend -> (RenderResult, Timeline)."""
    def _render(timeline=None, profiles=("reel_9x16", "square_1x1")):
        tl = timeline or make_timeline()
        out = tmp_path / "render" / "master.avi"
        result = get_renderer("mock", mock_config).render(RenderRequest(
            timeline=tl, output_path=out, renderer="mock", export_profiles=tuple(profiles)))
        return result, tl
    return _render


@pytest.fixture
def reel_artifacts(render_reel, voice_clip):
    """A fully-populated ReelArtifacts for a rendered mock reel."""
    result, tl = render_reel()
    return ReelArtifacts.from_render_result(
        result, timeline=tl, voice_clips=(voice_clip,),
        avatar={"enabled": True, "clips": [{"index": 0, "status": "planned"}]})
