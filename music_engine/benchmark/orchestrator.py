"""Music benchmark orchestrator (Phase C8).

Builds the deterministic case set and runs it through the generic
:class:`foundation.benchmarking.BenchmarkRunner`, then writes JSON/CSV reports.
Hermetic by default (mock renderer): pure-CPU mixing, no FFmpeg/GPU/model.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkRunner, RunResult
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils.text import new_run_id

from music_engine.benchmark.cases import MusicBenchmarkCase
from music_engine.benchmark.config import MusicBenchmarkConfig

logger = get_logger("music_engine.benchmark")


class MusicBenchmark:
    """Runs a fixed music workload and reports loading/mixing/render/export timing."""

    def __init__(self, config: MusicBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or MusicBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "music_runs")

    def build_cases(self, work_dir: Path) -> list[MusicBenchmarkCase]:
        return [MusicBenchmarkCase(self.config, work_dir, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("music-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases(ensure_dir(run_dir / "work"))
        runner = BenchmarkRunner(title="Music mixing render benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Music benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    """One-line-per-metric text summary of a completed run."""
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.failed} failed")
        for name in ("music_load_ms", "mix_ms", "render_base_ms", "render_music_ms",
                     "music_render_overhead_ms", "export_ms", "render_fps", "rss_mb",
                     "output_duration_s"):
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:26} {val}")
    return "\n".join(lines)
