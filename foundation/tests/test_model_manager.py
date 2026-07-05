"""Tests for foundation.model_manager."""
from __future__ import annotations

import pytest

from foundation.exceptions import ModelNotFoundError
from foundation.model_manager import (
    Device,
    HardwareRequirements,
    LicenseInfo,
    ModelRegistry,
    ModelSpec,
    resolve_device,
)


def _spec(model_id: str = "test-model", **kwargs: object) -> ModelSpec:
    return ModelSpec(
        model_id=model_id,
        display_name="Test Model",
        family="tts",
        version="1.0",
        repo_url="https://example.com/repo",
        weights_source="example/weights",
        license=LicenseInfo("MIT", "MIT", commercial_use=True),
        hardware=HardwareRequirements(
            min_vram_gb=4, recommended_vram_gb=8, min_ram_gb=8,
            cpu_realtime_capable=False, disk_size_gb=2,
        ),
        **kwargs,  # type: ignore[arg-type]
    )


def test_register_and_get() -> None:
    reg = ModelRegistry()
    spec = _spec()
    reg.register(spec)
    assert reg.get("test-model") is spec
    assert "test-model" in reg
    assert len(reg) == 1


def test_duplicate_registration_rejected() -> None:
    reg = ModelRegistry()
    reg.register(_spec())
    with pytest.raises(ValueError):
        reg.register(_spec())
    reg.register(_spec(), replace=True)  # explicit replace allowed


def test_missing_model_raises() -> None:
    reg = ModelRegistry()
    with pytest.raises(ModelNotFoundError):
        reg.get("nope")


def test_family_and_tag_queries() -> None:
    reg = ModelRegistry()
    reg.register(_spec("a", tags=("streaming",)))
    reg.register(_spec("b", tags=("zero-shot",)))
    assert {s.model_id for s in reg.by_family("tts")} == {"a", "b"}
    assert [s.model_id for s in reg.by_tag("streaming")] == ["a"]


def test_resolve_device_explicit() -> None:
    assert resolve_device("cpu") is Device.CPU
    assert resolve_device(Device.CUDA) is Device.CUDA
    assert resolve_device(Device.AUTO) in (Device.CPU, Device.CUDA, Device.MPS)
