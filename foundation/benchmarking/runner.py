"""Benchmark runner: executes cases, times them, records resources & errors.

The runner is deliberately generic. A *case* is any callable that fills a
:class:`CaseResult`. Engine benchmarks subclass :class:`BenchmarkCase` (or
build cases programmatically) and hand them to :class:`BenchmarkRunner`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Sequence

from foundation.benchmarking.resource_monitor import ResourceMonitor
from foundation.benchmarking.results import CaseResult, CaseStatus, Measurement, RunResult
from foundation.exceptions import AdapterNotAvailableError, PlatformError
from foundation.logging import get_logger
from foundation.shared_utils.hardware import probe_hardware
from foundation.shared_utils.timing import Stopwatch, utc_now_iso
from foundation.shared_utils.text import new_run_id

logger = get_logger("foundation.benchmarking.runner")


class BenchmarkCase(ABC):
    """One benchmarkable unit of work."""

    def __init__(self, case_id: str, subject_id: str, scenario: str) -> None:
        self.case_id = case_id
        self.subject_id = subject_id
        self.scenario = scenario

    @abstractmethod
    def execute(self, result: CaseResult) -> None:
        """Run the case, adding measurements/artifacts to ``result``.

        Raise :class:`AdapterNotAvailableError` to mark the case SKIPPED,
        any other exception to mark it FAILED.
        """


class BenchmarkRunner:
    """Executes a sequence of cases into a :class:`RunResult`."""

    def __init__(
        self,
        title: str,
        config: dict[str, Any] | None = None,
        monitor_resources: bool = True,
        on_case_finished: Callable[[CaseResult], None] | None = None,
    ) -> None:
        self.title = title
        self.config = config or {}
        self.monitor_resources = monitor_resources
        self.on_case_finished = on_case_finished

    def run(self, cases: Sequence[BenchmarkCase], run_id: str | None = None) -> RunResult:
        run = RunResult(
            run_id=run_id or new_run_id("bench"),
            title=self.title,
            environment=probe_hardware().to_dict(),
            config=dict(self.config),
        )
        logger.info(
            "Benchmark run started",
            extra={"context": {"run_id": run.run_id, "cases": len(cases)}},
        )
        for case in cases:
            run.cases.append(self._run_case(case))
        run.finished_at = utc_now_iso()
        counts = {status.value: 0 for status in CaseStatus}
        for c in run.cases:
            counts[c.status.value] += 1
        logger.info("Benchmark run finished", extra={"context": {"run_id": run.run_id, **counts}})
        return run

    def _run_case(self, case: BenchmarkCase) -> CaseResult:
        result = CaseResult(
            case_id=case.case_id,
            subject_id=case.subject_id,
            scenario=case.scenario,
            status=CaseStatus.PASSED,
        )
        monitor = ResourceMonitor() if self.monitor_resources else None
        stopwatch = Stopwatch()
        try:
            if monitor is not None:
                monitor.start()
            with stopwatch:
                case.execute(result)
        except AdapterNotAvailableError as exc:
            result.status = CaseStatus.SKIPPED
            result.error = str(exc)
            logger.warning(
                "Case skipped", extra={"context": {"case": case.case_id, "reason": str(exc)}}
            )
        except PlatformError as exc:
            result.status = CaseStatus.FAILED
            result.error = str(exc)
            logger.error(
                "Case failed", extra={"context": {"case": case.case_id, "error": str(exc)}}
            )
        except Exception as exc:  # noqa: BLE001 - benchmark must survive any case
            result.status = CaseStatus.FAILED
            result.error = f"{type(exc).__name__}: {exc}"
            logger.exception("Case crashed", extra={"context": {"case": case.case_id}})
        finally:
            if monitor is not None:
                monitor.stop()
        result.duration_s = stopwatch.elapsed_s
        if monitor is not None and monitor.peak is not None:
            result.add(Measurement("peak_rss_mb", round(monitor.peak.rss_mb, 1), "MB"))
            # GPU metrics (device-wide via nvidia-smi) — present only on GPU hosts.
            if monitor.peak_gpu_mem_mb is not None:
                result.add(Measurement("peak_gpu_mem_mb", round(monitor.peak_gpu_mem_mb, 1), "MB"))
                result.add(Measurement("avg_gpu_mem_mb", round(monitor.avg_gpu_mem_mb, 1), "MB"))
            if monitor.avg_gpu_util_percent is not None:
                result.add(Measurement("gpu_utilization_percent",
                                       round(monitor.avg_gpu_util_percent, 1), "%"))
            if monitor.max_gpu_temp_c is not None:
                result.add(Measurement("gpu_temp_c", round(monitor.max_gpu_temp_c, 1), "C"))
        if self.on_case_finished is not None:
            self.on_case_finished(result)
        return result
