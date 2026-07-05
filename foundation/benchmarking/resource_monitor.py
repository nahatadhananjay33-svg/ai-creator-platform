"""Background resource sampling (RAM/CPU, GPU when available).

Runs a daemon thread sampling process memory and CPU. Gracefully degrades to
a no-op when ``psutil`` is missing so benchmarks still run everywhere.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from types import TracebackType

from foundation.logging import get_logger

logger = get_logger("foundation.benchmarking.resources")


@dataclass(frozen=True)
class ResourceSample:
    rss_mb: float
    cpu_percent: float
    gpu_mem_mb: float | None = None


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

    def _sample_gpu_mb(self) -> float | None:
        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                return torch.cuda.memory_allocated() / (1024 * 1024)
        except ImportError:
            pass
        return None

    def _loop(self) -> None:
        assert self._process is not None
        while not self._stop.wait(self.interval_s):
            try:
                rss = self._process.memory_info().rss / (1024 * 1024)
                cpu = self._process.cpu_percent(interval=None)
                self.samples.append(
                    ResourceSample(rss_mb=rss, cpu_percent=cpu, gpu_mem_mb=self._sample_gpu_mb())
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
