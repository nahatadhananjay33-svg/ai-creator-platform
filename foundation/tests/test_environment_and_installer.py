"""Tests for foundation.model_manager.environment and installer (offline paths)."""
from __future__ import annotations

from pathlib import Path

from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from foundation.model_manager.environment import (
    CompatibilityVerdict,
    EnvironmentReport,
    NvidiaDriverInfo,
    TorchInfo,
    check_compatibility,
    probe_environment,
)
from foundation.model_manager.installer import InstallationManager, InstallSpec
from foundation.shared_utils.hardware import GpuInfo, HardwareProfile


def _spec(min_vram: float | None, cpu_realtime: bool, disk: float = 2.0,
          min_ram: float = 8.0) -> ModelSpec:
    return ModelSpec(
        model_id="m", display_name="M", family="tts", version="1",
        repo_url="", weights_source="",
        license=LicenseInfo("MIT", "MIT", True),
        hardware=HardwareRequirements(
            min_vram_gb=min_vram, recommended_vram_gb=min_vram, min_ram_gb=min_ram,
            cpu_realtime_capable=cpu_realtime, disk_size_gb=disk,
        ),
    )


def _env(ram_gb: int = 16, disk_gb: float = 100.0, cuda: bool = False,
         vram_gb: int = 0, old_driver: bool = False) -> EnvironmentReport:
    gpus = (GpuInfo(name="test-gpu", vram_total_mb=vram_gb * 1024),) if vram_gb else ()
    return EnvironmentReport(
        hardware=HardwareProfile(
            os_name="Windows", os_version="10", machine="AMD64", python_version="3.12.0",
            cpu_name="test-cpu", cpu_cores_logical=8, ram_total_mb=ram_gb * 1024, gpus=gpus,
        ),
        python_version="3.12.0", python_executable="python", os_details="Windows 10",
        disk_free_gb=disk_gb,
        torch=TorchInfo(installed=True, version="2.9.0", cuda_available=cuda),
        nvidia_driver=NvidiaDriverInfo(
            present=bool(vram_gb),
            driver_version="398.35" if old_driver else "560.94",
            supports_modern_cuda=bool(vram_gb) and not old_driver,
            notes="driver too old" if old_driver else "",
        ),
    )


def test_probe_environment_smoke() -> None:
    env = probe_environment()
    assert env.disk_free_gb > 0
    assert env.python_version
    assert isinstance(env.to_dict(), dict)


def test_cpu_realtime_model_compatible_without_gpu() -> None:
    verdict = check_compatibility(_spec(min_vram=None, cpu_realtime=True), _env())
    assert verdict.compatible and verdict.mode == "cpu"


def test_gpu_model_falls_back_to_cpu_offline() -> None:
    verdict = check_compatibility(_spec(min_vram=6, cpu_realtime=False), _env())
    assert verdict.compatible and verdict.mode == "cpu-offline"


def test_old_driver_blocks_gpu_mode() -> None:
    env = _env(cuda=True, vram_gb=4, old_driver=True)
    verdict = check_compatibility(_spec(min_vram=4, cpu_realtime=False), env)
    assert verdict.mode != "gpu"
    assert any("driver" in r for r in verdict.reasons)


def test_gpu_mode_when_cuda_usable_and_vram_sufficient() -> None:
    env = _env(cuda=True, vram_gb=12)
    verdict = check_compatibility(_spec(min_vram=6, cpu_realtime=False), env)
    assert verdict == CompatibilityVerdict("m", True, "gpu", ())


def test_insufficient_disk_blocks_install() -> None:
    verdict = check_compatibility(_spec(min_vram=None, cpu_realtime=True, disk=50), _env(disk_gb=10))
    assert not verdict.compatible and verdict.mode == "none"


def test_insufficient_ram_blocks() -> None:
    verdict = check_compatibility(_spec(min_vram=None, cpu_realtime=True, min_ram=32), _env(ram_gb=8))
    assert not verdict.compatible


def test_installer_skips_unsupported_platform(tmp_path: Path) -> None:
    manager = InstallationManager(venvs_dir=tmp_path)
    spec = InstallSpec(model_id="nope", supported_on_this_platform=False,
                       platform_notes="requires WSL2")
    result = manager.install(spec, _env())
    assert result.status == "skipped"
    assert "WSL2" in (result.error or "")
    # status persisted for the report
    assert manager.status("nope")["status"] == "skipped"
