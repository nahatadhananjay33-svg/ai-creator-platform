"""Tests for the adapter layer: interface, mock, registry, install specs."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.exceptions import AdapterNotAvailableError, ModelError, ModelNotFoundError
from foundation.shared_utils import generate_sine_wav, write_wav
from foundation.shared_utils.video_io import read_raw_avi

from avatar_engine.models import (
    ADAPTER_CLASSES,
    MockAvatarAdapter,
    all_model_specs,
    commercial_ready_specs,
    create_adapter,
)
from avatar_engine.models.install_specs import INSTALL_SPECS
from avatar_engine.models.interface import GenerationRequest
from avatar_engine.research import production_candidates


@pytest.fixture()
def inputs(tmp_path: Path) -> GenerationRequest:
    audio = tmp_path / "drive.wav"
    write_wav(audio, generate_sine_wav(0.4))
    image = tmp_path / "face.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    return GenerationRequest(
        source_image=image,
        driving_audio=audio,
        output_path=tmp_path / "out" / "clip.mp4",
        scenario_id="test",
    )


def test_mock_generates_readable_video(inputs: GenerationRequest) -> None:
    result = MockAvatarAdapter().generate(inputs)
    assert result.engine_id == "mock"
    assert result.video_path.exists()
    video = read_raw_avi(result.video_path)
    assert video.n_frames == round(0.4 * MockAvatarAdapter.FPS)
    assert result.real_time_factor is not None


def test_missing_input_rejected(tmp_path: Path) -> None:
    image = tmp_path / "face.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ModelError, match="requires driving_audio"):
        MockAvatarAdapter().generate(GenerationRequest(source_image=image))
    with pytest.raises(ModelError, match="not found"):
        MockAvatarAdapter().generate(
            GenerationRequest(source_image=tmp_path / "nope.png")
        )


def test_registry_covers_all_production_candidates() -> None:
    for profile in production_candidates():
        assert profile.model_id in ADAPTER_CLASSES, profile.model_id


def test_planned_adapter_reports_unavailable_with_reason() -> None:
    # `ditto` is still a planned placeholder (latentsync became real in A4.7).
    adapter = create_adapter("ditto")
    assert not adapter.is_available()
    with pytest.raises(AdapterNotAvailableError, match="Phase A4"):
        adapter.load()


def test_unknown_adapter_rejected() -> None:
    with pytest.raises(ModelNotFoundError):
        create_adapter("no-such-model")


def test_spec_views() -> None:
    specs = all_model_specs()
    assert all(s.family == "avatar" for s in specs)
    ready = {s.model_id for s in commercial_ready_specs()}
    assert "echomimic-v3" in ready and "sonic" not in ready


def test_install_specs_reference_known_models() -> None:
    known = {p.model_id for p in production_candidates()}
    for model_id, spec in INSTALL_SPECS.items():
        assert spec.model_id == model_id
        assert model_id in known, f"install spec for unknown model {model_id}"
        assert spec.approx_download_gb > 0
