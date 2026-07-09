"""AI Prompt & Storyboard benchmark orchestrator (Phase C10).

Builds the deterministic case set and runs it through the generic
:class:`foundation.benchmarking.BenchmarkRunner`, then writes JSON/CSV reports.
Hermetic by default (MockProvider): pure-CPU, no FFmpeg/GPU/model/network.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkRunner, RunResult
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils.text import new_run_id

from script_engine.benchmark.cases import ScriptBenchmarkCase
from script_engine.benchmark.config import ScriptBenchmarkConfig

logger = get_logger("script_engine.benchmark")


class ScriptBenchmark:
    """Runs a fixed prompt->reel workload and reports per-stage timing + memory."""

    def __init__(self, config: ScriptBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or ScriptBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "script_runs")

    def build_cases(self) -> list[ScriptBenchmarkCase]:
        return [ScriptBenchmarkCase(self.config, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("script-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases()
        runner = BenchmarkRunner(title="AI prompt-to-reel benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Script benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    """One-line-per-metric text summary of a completed run."""
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.failed} failed")
        for name in ("provider_ms", "storyboard_gen_ms", "validation_ms",
                     "scene_gen_ms", "timeline_gen_ms", "total_pipeline_ms",
                     "prompts_per_s", "rss_mb", "ai_scenes", "scene_scenes"):
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:20} {val}")
    return "\n".join(lines)
