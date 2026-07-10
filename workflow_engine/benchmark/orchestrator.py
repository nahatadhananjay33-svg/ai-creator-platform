"""Workflow benchmark orchestrator (Phase C14).

Builds the deterministic case set and runs it through the generic
:class:`foundation.benchmarking.BenchmarkRunner`, then writes JSON/CSV reports.
Hermetic (mock voice + mock renderer): pure-CPU, no ffmpeg/GPU/model/network.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkRunner, RunResult
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils.text import new_run_id

from workflow_engine.benchmark.cases import WorkflowBenchmarkCase
from workflow_engine.benchmark.config import REPORTED_STAGES, WorkflowBenchmarkConfig

logger = get_logger("workflow_engine.benchmark")


class WorkflowBenchmark:
    """Runs the fixed orchestration workload and reports startup / cache / throughput."""

    def __init__(self, config: WorkflowBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or WorkflowBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "workflow_bench_runs")

    def build_cases(self) -> list[WorkflowBenchmarkCase]:
        return [WorkflowBenchmarkCase(self.config, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("wf-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases()
        runner = BenchmarkRunner(title="Workflow orchestration benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Workflow benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    """One-line-per-metric text summary of a completed run."""
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    headline = ("startup_ms", "cold_run_ms", "warm_run_ms", "incremental_ms",
                "speedup_warm_vs_cold", "throughput_stages_per_s", "cache_hits_warm",
                "cache_misses_cold", "incremental_rebuilt", "incremental_reused", "rss_mb")
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.failed} failed")
        for name in headline:
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:26} {val}")
        lines.append("      -- per-stage cold execution (ms) --")
        for name in REPORTED_STAGES:
            val = subject.metric_means.get(f"stage_{name}_ms")
            if val is not None:
                lines.append(f"      stage_{name:20} {val}")
    return "\n".join(lines)
