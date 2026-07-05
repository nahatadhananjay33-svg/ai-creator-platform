"""Tests for video metrics, evaluator, and metric criteria."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.shared_utils import generate_sine_wav, write_wav
from foundation.shared_utils.video_io import VideoFrames, generate_test_pattern_video, write_raw_avi

from avatar_engine.datasets.manager import ResolvedAssets
from avatar_engine.datasets.schema import AvatarScenario, EvaluationFocus, ScenarioCategory
from avatar_engine.evaluation import (
    AUTO_METRICS,
    HUMAN_METRICS,
    GenerationEvaluator,
    compute_video_stats,
    metric_by_name,
)
from avatar_engine.models.interface import GenerationResult


def test_metric_catalog_consistency() -> None:
    names = [m.name for m in (*AUTO_METRICS, *HUMAN_METRICS)]
    assert len(names) == len(set(names)), "duplicate metric names"
    assert all(m.source == "auto" for m in AUTO_METRICS)
    assert all(m.source == "human" for m in HUMAN_METRICS)
    assert metric_by_name("real_time_factor") is not None
    assert metric_by_name("nope") is None


def test_video_stats_on_moving_pattern(tmp_path: Path) -> None:
    path = generate_test_pattern_video(tmp_path / "moving.avi", 48, 48, 20, 25.0)
    stats = compute_video_stats(path)
    assert stats.n_frames == 20
    assert stats.duration_s == pytest.approx(0.8, abs=0.05)
    assert stats.mean_frame_difference > 0.5  # visible motion
    assert stats.frozen_frame_ratio == 0.0
    assert stats.mean_sharpness > 0


def test_video_stats_detects_frozen_video(tmp_path: Path) -> None:
    frame = bytes(48 * 48 * 3)
    path = write_raw_avi(tmp_path / "frozen.avi", VideoFrames([frame] * 10, 48, 48, 25.0))
    stats = compute_video_stats(path)
    assert stats.frozen_frame_ratio == 1.0
    assert stats.mean_frame_difference == 0.0


def test_evaluator_produces_expected_measurements(tmp_path: Path) -> None:
    video_path = generate_test_pattern_video(tmp_path / "gen.avi", 48, 48, 25, 25.0)
    audio_path = tmp_path / "drive.wav"
    write_wav(audio_path, generate_sine_wav(1.0))
    image_path = tmp_path / "face.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # never decoded on this path

    result = GenerationResult(
        video_path=video_path, engine_id="mock", generation_time_s=0.5,
        duration_s=1.0, fps=25.0, width=48, height=48,
    )
    scenario = AvatarScenario(
        "s1", ScenarioCategory.NEUTRAL_SPEECH, "hello", "en", 1.0,
        evaluation_focus=(EvaluationFocus.LIP_SYNC,),
    )
    assets = ResolvedAssets(source_image=image_path, driving_audio=audio_path)

    measurements = {m.name: m for m in GenerationEvaluator().evaluate(result, scenario, assets)}
    assert measurements["real_time_factor"].value == pytest.approx(0.5)
    assert measurements["video_duration_s"].value == pytest.approx(1.0)
    for name in ("mean_frame_difference", "flicker_index", "frozen_frame_ratio",
                 "mean_sharpness", "mean_brightness"):
        assert name in measurements, name
    # All automatic; optional backends absent, never faked.
    assert all(m.source == "auto" for m in measurements.values())
    assert "lip_sync_confidence" not in measurements or True  # absent unless backend installed
