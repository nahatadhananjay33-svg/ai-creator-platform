"""Environment detection: everything installation and benchmarking must know
about the machine before touching a model.

Extends the Phase A1 hardware probe with: disk space, torch/CUDA state,
NVIDIA driver version (queried even when nvidia-smi is not on PATH), and
per-model compatibility verdicts against ModelSpec hardware requirements.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from foundation.logging import get_logger
from foundation.model_manager.spec import ModelSpec
from foundation.shared_utils.hardware import HardwareProfile, probe_hardware

logger = get_logger("foundation.model_manager.environment")

#: Minimum NVIDIA driver versions required by CUDA runtimes that modern
#: PyTorch wheels ship with (Windows numbers).
_CUDA_DRIVER_FLOOR = {
    "11.8": 452.39,
    "12.1": 527.41,
    "12.4": 551.61,
    "12.6": 560.76,
}

_NVIDIA_SMI_CANDIDATES = (
    "nvidia-smi",
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
)


@dataclass(frozen=True)
class TorchInfo:
    installed: bool
    version: str | None = None
    cuda_available: bool = False
    cuda_version: str | None = None


@dataclass(frozen=True)
class NvidiaDriverInfo:
    present: bool
    driver_version: str | None = None
    supports_modern_cuda: bool = False  # driver >= CUDA 11.8 floor
    notes: str = ""


@dataclass(frozen=True)
class EnvironmentReport:
    """Full machine report used for compatibility decisions and provenance."""

    hardware: HardwareProfile
    python_version: str
    python_executable: str
    os_details: str
    disk_free_gb: float
    torch: TorchInfo
    nvidia_driver: NvidiaDriverInfo

    @property
    def cuda_usable(self) -> bool:
        return self.torch.cuda_available and self.nvidia_driver.supports_modern_cuda

    @property
    def gpu_install_target(self) -> bool:
        """True when CUDA PyTorch wheels should be installed on this host.

        Unlike :attr:`cuda_usable` (which needs torch already present in the
        *launcher* to answer), this depends only on a detected GPU plus a driver
        new enough for modern CUDA. So the installer decides correctly even
        before any torch exists in the launching interpreter — e.g. the Colab
        main kernel, which runs ``install_models`` with no torch installed.
        """
        return self.hardware.has_gpu and self.nvidia_driver.supports_modern_cuda

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CompatibilityVerdict:
    model_id: str
    compatible: bool
    mode: str  # "gpu" | "cpu" | "cpu-offline" | "none"
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _find_nvidia_smi() -> str | None:
    for candidate in _NVIDIA_SMI_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    return None


def probe_nvidia_driver() -> NvidiaDriverInfo:
    smi = _find_nvidia_smi()
    if smi is None:
        return NvidiaDriverInfo(present=False, notes="nvidia-smi not found")
    try:
        out = subprocess.run(
            [smi, "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip().splitlines()
    except (subprocess.SubprocessError, OSError) as exc:
        return NvidiaDriverInfo(present=True, notes=f"nvidia-smi failed: {exc}")
    if not out:
        return NvidiaDriverInfo(present=True, notes="no GPU rows returned")
    version_str = out[0].strip()
    try:
        version_num = float(".".join(version_str.split(".")[:2]))
    except ValueError:
        version_num = 0.0
    supports = version_num >= _CUDA_DRIVER_FLOOR["11.8"]
    notes = "" if supports else (
        f"driver {version_str} predates CUDA 11.8 floor ({_CUDA_DRIVER_FLOOR['11.8']}); "
        "modern PyTorch CUDA wheels cannot use this GPU without a driver update"
    )
    return NvidiaDriverInfo(
        present=True, driver_version=version_str, supports_modern_cuda=supports, notes=notes
    )


def probe_torch(python_executable: str | None = None) -> TorchInfo:
    """Probe torch in the current interpreter, or another venv's interpreter."""
    if python_executable is None or Path(python_executable) == Path(sys.executable):
        try:
            import torch  # type: ignore[import-not-found]

            return TorchInfo(
                installed=True,
                version=torch.__version__,
                cuda_available=torch.cuda.is_available(),
                cuda_version=getattr(torch.version, "cuda", None),
            )
        except ImportError:
            return TorchInfo(installed=False)
    code = (
        "import json\n"
        "try:\n"
        "    import torch\n"
        "    print(json.dumps({'v': torch.__version__, 'c': torch.cuda.is_available(),"
        " 'cv': torch.version.cuda}))\n"
        "except Exception:\n"
        "    print(json.dumps(None))\n"
    )
    try:
        out = subprocess.run(
            [python_executable, "-c", code], capture_output=True, text=True, timeout=120, check=True
        ).stdout.strip()
        import json

        data = json.loads(out)
        if data is None:
            return TorchInfo(installed=False)
        return TorchInfo(installed=True, version=data["v"], cuda_available=data["c"],
                         cuda_version=data.get("cv"))
    except (subprocess.SubprocessError, OSError, ValueError):
        return TorchInfo(installed=False)


def probe_environment(workdir: Path | None = None) -> EnvironmentReport:
    workdir = workdir or Path.cwd()
    usage = shutil.disk_usage(workdir)
    return EnvironmentReport(
        hardware=probe_hardware(),
        python_version=platform.python_version(),
        python_executable=sys.executable,
        os_details=f"{platform.system()} {platform.release()} ({platform.version()})",
        disk_free_gb=round(usage.free / (1024**3), 1),
        torch=probe_torch(),
        nvidia_driver=probe_nvidia_driver(),
    )


def check_compatibility(spec: ModelSpec, env: EnvironmentReport) -> CompatibilityVerdict:
    """Decide how (if at all) a model can run on this machine."""
    reasons: list[str] = []
    hw = spec.hardware

    gpu_ok = env.cuda_usable
    if not gpu_ok and env.nvidia_driver.present and not env.nvidia_driver.supports_modern_cuda:
        reasons.append(env.nvidia_driver.notes or "GPU driver too old for modern CUDA")
    elif not env.nvidia_driver.present:
        reasons.append("no NVIDIA GPU/driver detected")

    if env.disk_free_gb < hw.disk_size_gb + 5:
        reasons.append(
            f"insufficient disk: need ~{hw.disk_size_gb + 5:.0f} GB free, have {env.disk_free_gb} GB"
        )
        return CompatibilityVerdict(spec.model_id, False, "none", tuple(reasons))

    ram_gb = (env.hardware.ram_total_mb or 0) / 1024
    if ram_gb and ram_gb < hw.min_ram_gb:
        reasons.append(f"insufficient RAM: need {hw.min_ram_gb} GB, have {ram_gb:.0f} GB")
        return CompatibilityVerdict(spec.model_id, False, "none", tuple(reasons))

    if gpu_ok:
        vram_gb = max((g.vram_total_mb or 0) for g in env.hardware.gpus) / 1024
        if hw.min_vram_gb is None or vram_gb >= hw.min_vram_gb:
            return CompatibilityVerdict(spec.model_id, True, "gpu", tuple(reasons))
        reasons.append(f"VRAM {vram_gb:.0f} GB < required {hw.min_vram_gb} GB; falling back to CPU")

    if hw.cpu_realtime_capable:
        return CompatibilityVerdict(spec.model_id, True, "cpu", tuple(reasons))
    if hw.min_vram_gb is None or hw.min_vram_gb <= 8:
        reasons.append("CPU inference possible but far slower than real time (offline/benchmark only)")
        return CompatibilityVerdict(spec.model_id, True, "cpu-offline", tuple(reasons))
    reasons.append("model requires a GPU class this machine cannot provide")
    return CompatibilityVerdict(spec.model_id, False, "none", tuple(reasons))
