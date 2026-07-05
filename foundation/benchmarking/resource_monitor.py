"""Background resource sampling (RAM/CPU, GPU when available).

Runs a daemon thread sampling process memory/CPU and — when an NVIDIA GPU is
present — GPU memory, utilization, and temperature via ``nvidia-smi``.

GPU sampling uses ``nvidia-smi`` rather than in-process ``torch`` on purpose:
avatar inference runs in a per-model venv **subprocess**, so torch in the
launcher (a) may not be installed and (b) would only see the launcher's own
allocations. ``nvidia-smi`` reports device-wide usage, which on a dedicated
(e.g. Colab) GPU captures the subprocess's real footprint. Gracefully degrades
to a no-op when ``psutil`` / ``nvidia-smi`` are missing so benchmarks still run
everywhere.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from foundation.logging import get_logger

logger = get_logger("foundation.benchmarking.resources")

#: Minimum seconds between nvidia-smi spawns (they cost ~30 ms each).
_GPU_SAMPLE_MIN_INTERVAL_S = 1.0
_NVIDIA_SMI_CANDIDATES = (
    "nvidia-smi",
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
)


def _find_nvidia_smi() -> str | None:
    for candidate in _NVIDIA_SMI_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    return None


@dataclass(frozen=True)
class ResourceSample:
    rss_mb: float
    cpu_percent: float
    gpu_mem_mb: float | None = None
    gpu_util_percent: float | None = None
    gpu_temp_c: float | None = None


class ResourceMonitor:
    """Samples process resource usage while a benchmark case runs.

    Usage::

        with ResourceMonitor(interval_s=0.2) as mon:
            run_case()
        peak = mon.peak  # ResourceSample or None if psutil unavailable
    """

    def __init__(self, interval_s: float = 0.25) -> None:
        self.interval_s = interval_s
        self.samples: list[ResourceSample] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process = None
        self._nvidia_smi = _find_nvidia_smi()
        self._last_gpu: tuple[float | None, float | None, float | None] = (None, None, None)
        self._last_gpu_ts = 0.0
        try:
            import psutil  # type: ignore[import-not-found]

            self._process = psutil.Process()
        except ImportError:
            logger.warning("psutil not installed; resource monitoring disabled")

    @property
    def available(self) -> bool:
        return self._process is not None

    @property
    def peak(self) -> ResourceSample | None:
        if not self.samples:
            return None
        return max(self.samples, key=lambda s: s.rss_mb)

    # ------------------------------------------------------------------ GPU aggregates
    def _gpu_values(self, attr: str) -> list[float]:
        return [v for s in self.samples if (v := getattr(s, attr)) is not None]

    @property
    def peak_gpu_mem_mb(self) -> float | None:
        vals = self._gpu_values("gpu_mem_mb")
        return max(vals) if vals else None

    @property
    def avg_gpu_mem_mb(self) -> float | None:
        vals = self._gpu_values("gpu_mem_mb")
        return sum(vals) / len(vals) if vals else None

    @property
    def avg_gpu_util_percent(self) -> float | None:
        vals = self._gpu_values("gpu_util_percent")
        return sum(vals) / len(vals) if vals else None

    @property
    def max_gpu_temp_c(self) -> float | None:
        vals = self._gpu_values("gpu_temp_c")
        return max(vals) if vals else None

    def _sample_gpu(self) -> tuple[float | None, float | None, float | None]:
        """(mem_used_mb, util_percent, temp_c) via nvidia-smi, rate-limited."""
        if self._nvidia_smi is None:
            return (None, None, None)
        now = time.monotonic()
        if now - self._last_gpu_ts < _GPU_SAMPLE_MIN_INTERVAL_S:
            return self._last_gpu  # reuse recent reading; don't spawn every loop
        try:
            out = subprocess.run(
                [self._nvidia_smi,
                 "--query-gpu=memory.used,utilization.gpu,temperature.gpu",
                 "--format=csv,noheader,nounits", "-i", "0"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip().splitlines()
            parts = [p.strip() for p in out[0].split(",")] if out else []
            reading = tuple(float(p) if p not in ("", "[N/A]") else None for p in parts[:3])
            reading = reading + (None,) * (3 - len(reading))  # pad if fewer fields
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            reading = (None, None, None)
        self._last_gpu, self._last_gpu_ts = reading, now  # type: ignore[assignment]
        return self._last_gpu

    def _loop(self) -> None:
        assert self._process is not None
        while not self._stop.wait(self.interval_s):
            try:
                rss = self._process.memory_info().rss / (1024 * 1024)
                cpu = self._process.cpu_percent(interval=None)
                gpu_mem, gpu_util, gpu_temp = self._sample_gpu()
                self.samples.append(
                    ResourceSample(rss_mb=rss, cpu_percent=cpu, gpu_mem_mb=gpu_mem,
                                   gpu_util_percent=gpu_util, gpu_temp_c=gpu_temp)
                )
            except Exception:  # process may be shutting down
                break

    def start(self) -> "ResourceMonitor":
        if self._process is not None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="resource-monitor")
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def __enter__(self) -> "ResourceMonitor":
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
