"""Content Library benchmark orchestrator (Phase C15).

Runs the deterministic case set through the generic
:class:`foundation.benchmarking.BenchmarkRunner` and writes JSON/CSV reports.
Hermetic: local JSON only — no workflow generation, GPU, ffmpeg, or network.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkRunner, RunResult
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils.text import new_run_id

from content_library.benchmark.cases import LibraryBenchmarkCase
from content_library.benchmark.config import LibraryBenchmarkConfig

logger = get_logger("content_library.benchmark")


class LibraryBenchmark:
    """Runs the fixed metadata workload and reports load/save/search/indexing timing."""

    def __init__(self, config: LibraryBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or LibraryBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "content_library_bench_runs")

    def build_cases(self) -> list[LibraryBenchmarkCase]:
        return [LibraryBenchmarkCase(self.config, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("lib-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases()
        runner = BenchmarkRunner(title="Content Library benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Content Library benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    metrics = ("save_ms_per_project", "load_ms_per_project", "search_ms_per_query",
               "index_rebuild_ms", "save_projects_per_s", "load_projects_per_s", "rss_mb")
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.failed} failed")
        for name in metrics:
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:24} {val}")
    return "\n".join(lines)
