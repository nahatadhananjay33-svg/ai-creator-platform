"""Regression tests for Phase A3.8 GPU enablement.

Pins the behaviour the phase requires: the installer selects CUDA wheels on a
GPU host and CPU wheels otherwise (never hardcoded), the GPU-capability signal
is torch-independent, adapters/diagnostics report the actual device + VRAM, and
the benchmark records GPU metrics. Deterministic on any host (no real GPU).
"""
from __future__ import annotations

import sys

from foundation.benchmarking.resource_monitor import ResourceMonitor, ResourceSample
from foundation.model_manager.environment import (
    EnvironmentReport,
    NvidiaDriverInfo,
    TorchInfo,
)
from foundation.model_manager.installer import (
    TORCH_CPU_INDEX,
    InstallSpec,
    InstallationManager,
)
from foundation.shared_utils.hardware import GpuInfo, HardwareProfile
from avatar_engine.models.diagnostics import diagnose
from avatar_engine.models.install_specs import INSTALL_SPECS


# --------------------------------------------------------------- installer torch selection
def _resolve(spec, gpu):
    return InstallationManager.resolve_torch_install(spec, gpu_target=gpu)


def test_sadtalker_cpu_host_uses_cpu_index():
    args, label = _resolve(INSTALL_SPECS["sadtalker"], gpu=False)
    assert label == "cpu"
    assert "--index-url" in args and TORCH_CPU_INDEX in args
    assert "torch==2.0.1" in args  # version pin preserved


def test_sadtalker_gpu_host_uses_cuda_index():
    args, label = _resolve(INSTALL_SPECS["sadtalker"], gpu=True)
    assert "cu118" in label
    assert "https://download.pytorch.org/whl/cu118" in args
    assert TORCH_CPU_INDEX not in args  # never hardcode CPU on a GPU host
    assert "torch==2.0.1" in args


def test_liveportrait_gpu_host_uses_default_cuda_pypi():
    args, label = _resolve(INSTALL_SPECS["liveportrait"], gpu=True)
    assert "cuda" in label
    assert "--index-url" not in args  # default PyPI ships the CUDA build on Linux
    assert "torchvision" in args


def test_liveportrait_cpu_host_uses_cpu_index():
    args, _ = _resolve(INSTALL_SPECS["liveportrait"], gpu=False)
    assert TORCH_CPU_INDEX in args


def test_forced_cpu_spec_ignores_gpu():
    spec = InstallSpec(model_id="x", torch="cpu")
    args, label = _resolve(spec, gpu=True)
    assert label == "cpu" and TORCH_CPU_INDEX in args


def test_default_torch_flavor_is_auto():
    assert InstallSpec(model_id="x").torch == "auto"


def test_no_avatar_spec_hardcodes_cpu_index_in_pip_groups():
    # The whole point of A3.8: torch flavor is chosen by the installer, not
    # frozen to CPU inside a pip group.
    for mid, spec in INSTALL_SPECS.items():
        for group in spec.pip_groups:
            assert TORCH_CPU_INDEX not in group, f"{mid} hardcodes CPU torch in a pip group"


# --------------------------------------------------------------- gpu_install_target
def _env(*, has_gpu: bool, modern_driver: bool, torch_cuda: bool) -> EnvironmentReport:
    gpus = (GpuInfo(name="Tesla T4", vram_total_mb=15360),) if has_gpu else ()
    return EnvironmentReport(
        hardware=HardwareProfile(
            os_name="Linux", os_version="1", machine="x86_64", python_version="3.10",
            cpu_name="cpu", cpu_cores_logical=8, ram_total_mb=13000, gpus=gpus,
        ),
        python_version="3.10", python_executable=sys.executable, os_details="Linux",
        disk_free_gb=100.0,
        torch=TorchInfo(installed=torch_cuda, cuda_available=torch_cuda),
        nvidia_driver=NvidiaDriverInfo(present=has_gpu, driver_version="535.0",
                                       supports_modern_cuda=modern_driver),
    )


def test_gpu_install_target_true_on_capable_gpu_without_launcher_torch():
    # Torch NOT installed in the launcher (Colab main kernel) — still detects GPU.
    env = _env(has_gpu=True, modern_driver=True, torch_cuda=False)
    assert env.gpu_install_target is True
    assert env.cuda_usable is False  # cuda_usable needs launcher torch; this doesn't


def test_gpu_install_target_false_when_driver_too_old():
    env = _env(has_gpu=True, modern_driver=False, torch_cuda=False)
    assert env.gpu_install_target is False


def test_gpu_install_target_false_without_gpu():
    env = _env(has_gpu=False, modern_driver=False, torch_cuda=False)
    assert env.gpu_install_target is False


# --------------------------------------------------------------- diagnostics device fields
def test_diagnose_reports_actual_device_and_fields():
    d = diagnose(
        "probe", packages=("json",), required_paths=[], expected_device="cuda",
        runs_in_venv=True, venv_python=sys.executable, venv_dir=sys.executable,
    )
    # No CUDA torch in this interpreter -> actual device is cpu, mismatch flagged.
    assert d.actual_device == "cpu"
    assert d.device_matches_expectation is False
    assert hasattr(d, "cuda_total_mem_mb")


# --------------------------------------------------------------- resource monitor GPU aggregates
def test_resource_monitor_gpu_aggregates():
    mon = ResourceMonitor()
    mon.samples = [
        ResourceSample(rss_mb=100, cpu_percent=1, gpu_mem_mb=1000,
                       gpu_util_percent=40, gpu_temp_c=55),
        ResourceSample(rss_mb=120, cpu_percent=1, gpu_mem_mb=3000,
                       gpu_util_percent=90, gpu_temp_c=61),
    ]
    assert mon.peak_gpu_mem_mb == 3000
    assert mon.avg_gpu_mem_mb == 2000
    assert mon.avg_gpu_util_percent == 65
    assert mon.max_gpu_temp_c == 61


def test_resource_monitor_gpu_aggregates_none_without_samples():
    mon = ResourceMonitor()
    mon.samples = [ResourceSample(rss_mb=100, cpu_percent=1)]  # no GPU fields
    assert mon.peak_gpu_mem_mb is None
    assert mon.avg_gpu_util_percent is None
