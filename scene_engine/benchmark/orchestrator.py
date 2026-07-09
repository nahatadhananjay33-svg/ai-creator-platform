"""Scene planning benchmark orchestrator (Phase C7).

Builds the deterministic case set and runs it through the generic
:class:`foundation.benchmarking.BenchmarkRunner`, then writes JSON/CSV reports.
Fully hermetic (pure-CPU planning; no renderer, FFmpeg, GPU, or model).
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkRunner, RunResult
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils.text import new_run_id

from scene_engine.benchmark.cases import SceneBenchmarkCase
from scene_engine.benchmark.config import SceneBenchmarkConfig

logger = get_logger("scene_engine.benchmark")


class SceneBenchmark:
    """Runs a fixed planning workload and reports planning/timeline/throughput."""

    def __init__(self, config: SceneBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or SceneBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "scene_runs")

    def build_cases(self) -> list[SceneBenchmarkCase]:
        return [SceneBenchmarkCase(self.config, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("scene-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases()
        runner = BenchmarkRunner(title="Scene planning benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Scene benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    """One-line-per-metric text summary of a completed run."""
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.failed} failed")
        for name in ("planning_ms", "scene_gen_ms", "timeline_gen_ms",
                     "scenes_per_s", "words_per_s", "rss_mb",
                     "n_scenes", "n_words", "plan_duration_s"):
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:18} {val}")
    return "\n".join(lines)
