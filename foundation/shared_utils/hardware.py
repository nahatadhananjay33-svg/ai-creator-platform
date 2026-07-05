"""Hardware probing for benchmark reproducibility and adapter placement.

Every benchmark run records the hardware profile it executed on, so results
from different machines are never compared silently. GPU detection tries
``torch`` first (authoritative when installed), then falls back to
``nvidia-smi``.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class GpuInfo:
    name: str
    vram_total_mb: int | None = None


@dataclass(frozen=True)
class HardwareProfile:
    os_name: str
    os_version: str
    machine: str
    python_version: str
    cpu_name: str
    cpu_cores_logical: int | None
    ram_total_mb: int | None
    gpus: tuple[GpuInfo, ...] = field(default_factory=tuple)

    @property
    def has_gpu(self) -> bool:
        return len(self.gpus) > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _probe_gpus_via_torch() -> tuple[GpuInfo, ...] | None:
    try:
        import torch  # type: ignore[import-not-found]
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return ()
    gpus = []
    for idx in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(idx)
        gpus.append(GpuInfo(name=props.name, vram_total_mb=props.total_memory // (1024 * 1024)))
    return tuple(gpus)


def _probe_gpus_via_nvidia_smi() -> tuple[GpuInfo, ...]:
    if shutil.which("nvidia-smi") is None:
        return ()
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return ()
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if not parts or not parts[0]:
            continue
        vram = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        gpus.append(GpuInfo(name=parts[0], vram_total_mb=vram))
    return tuple(gpus)


def _probe_ram_and_cores() -> tuple[int | None, int | None]:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.virtual_memory().total // (1024 * 1024), psutil.cpu_count(logical=True)
    except ImportError:
        import os

        return None, os.cpu_count()


def probe_hardware() -> HardwareProfile:
    """Collect a hardware profile for the current machine."""
    ram_mb, cores = _probe_ram_and_cores()
    gpus = _probe_gpus_via_torch()
    if gpus is None:
        gpus = _probe_gpus_via_nvidia_smi()
    return HardwareProfile(
        os_name=platform.system(),
        os_version=platform.version(),
        machine=platform.machine(),
        python_version=platform.python_version(),
        cpu_name=platform.processor() or "unknown",
        cpu_cores_logical=cores,
        ram_total_mb=ram_mb,
        gpus=gpus,
    )
