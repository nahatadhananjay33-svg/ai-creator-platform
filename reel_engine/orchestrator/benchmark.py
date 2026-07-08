"""End-to-end pipeline benchmark (Phase C3 walking skeleton).

Subclasses :class:`foundation.benchmarking.BenchmarkCase` so it inherits the
platform's timing, resource monitoring (peak RSS + GPU memory/utilisation via the
runner's :class:`ResourceMonitor`), and CSV/JSON reporting for free — the same
mechanism the Voice/Avatar/Reel benchmarks use.

One case runs the FULL pipeline once (script -> voice -> avatar -> Timeline ->
render -> export) and records each stage's wall-clock plus the total, from the
:class:`PipelineResult` the orchestrator already reports. Default subjects are
the dependency-free ``mock`` voice + avatar so the benchmark runs anywhere; point
``--voice-model``/``--avatar-model`` at real models to profile production stages.
The render backend defaults to ffmpeg (real MP4) and SKIPS cleanly when ffmpeg is
absent, so render/export timings are the true master-render vs scale-export split.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from foundation.benchmarking import BenchmarkCase, BenchmarkRunner, CaseResult, Measurement, RunResult
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.exceptions import AdapterNotAvailableError
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils.text import new_run_id

from reel_engine.orchestrator.adapters import EngineAvatarStage, EngineVoiceStage
from reel_engine.orchestrator.config import load_pipeline_config
from reel_engine.orchestrator.pipeline import CreatorPipeline
from reel_engine.render import ffprobe_available

logger = get_logger("reel_engine.orchestrator.benchmark")

#: A short, fixed script keeps every stage fast and the workload deterministic.
DEFAULT_SCRIPT = "This reel was generated end to end by the AI Creator Platform."


def _rss_mb() -> float:
    """Direct RSS snapshot (0.0 without psutil) so a memory figure is always
    recorded even for cases too short for the runner's async sampler."""
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


@dataclass
class PipelineBenchmarkConfig:
    """One benchmark run: a fixed end-to-end workload for a model/renderer combo.

    The *workload* (script, resolution, fps, profiles) is deterministic; the
    wall-clock stage timings are not (that is the point of a benchmark)."""

    voice_model: str = "mock"
    avatar_model: str = "mock"
    renderer: str = "ffmpeg"
    width: int = 720
    height: int = 1280
    fps: int = 30
    bitrate: str = "2M"
    profiles: list[str] = field(default_factory=lambda: ["reel_9x16"])
    script: str = DEFAULT_SCRIPT
    repetitions: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def pipeline_overrides(self, output_dir: Path) -> dict[str, Any]:
        return {
            "voice": {"model": self.voice_model},
            "avatar": {"model": self.avatar_model},
            "render": {"renderer": self.renderer, "width": self.width,
                       "height": self.height, "fps": self.fps, "bitrate": self.bitrate},
            "export": {"profiles": list(self.profiles)},
            "output_dir": str(output_dir),
        }


class PipelineRunCase(BenchmarkCase):
    """Per-stage + total timing for one full end-to-end pipeline run."""

    def __init__(self, cfg: PipelineBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        subject = f"{cfg.voice_model}+{cfg.avatar_model}+{cfg.renderer}"
        super().__init__(case_id=f"{subject}-r{repetition}", subject_id=subject,
                         scenario="e2e_pipeline")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        if cfg.renderer == "ffmpeg" and not ffprobe_available():
            # Convention: AdapterNotAvailableError -> the case is SKIPPED, not FAILED.
            raise AdapterNotAvailableError(
                "ffmpeg/ffprobe not installed; rerun with --renderer mock",
                adapter="ffmpeg")

        pcfg = load_pipeline_config(overrides=cfg.pipeline_overrides(self.out_dir))
        pipeline = CreatorPipeline(
            pcfg,
            voice_stage=EngineVoiceStage(pcfg.voice),
            avatar_stage=EngineAvatarStage(pcfg.avatar),
        )
        res = pipeline.run(script=cfg.script, output_name=f"bench_r{self.repetition}")
        t = res.timings

        # Stage wall-clocks (the pipeline reports them in seconds).
        for stage in ("voice", "avatar", "timeline", "render", "export", "total"):
            result.add(Measurement(f"{stage}_ms", round(t[f"{stage}_s"] * 1000, 2),
                                   "ms", higher_is_better=False))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("output_duration_s", res.duration_s, "s", source="static"))
        result.add(Measurement("n_exports", len(res.exports), "", source="static"))
        result.metadata["timeline_hash"] = res.render.timeline_hash
        result.metadata["voice_engine"] = res.voice.engine_id
        result.metadata["avatar_engine"] = res.avatar.engine_id
        result.artifacts["master"] = str(res.output_path)


class PipelineBenchmark:
    """Runs the end-to-end pipeline workload and reports per-stage timing/memory/GPU."""

    def __init__(self, config: PipelineBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or PipelineBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "pipeline_runs")

    def build_cases(self, work_dir: Path) -> list[PipelineRunCase]:
        return [PipelineRunCase(self.config, work_dir, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("pipeline-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases(ensure_dir(run_dir / "work"))
        runner = BenchmarkRunner(title="End-to-end pipeline benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Pipeline benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    """One-line-per-metric text summary of a completed run."""
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.skipped} skipped, {subject.failed} failed")
        for name in ("voice_ms", "avatar_ms", "timeline_ms", "render_ms", "export_ms",
                     "total_ms", "output_duration_s", "rss_mb", "peak_rss_mb",
                     "peak_gpu_mem_mb", "gpu_utilization_percent"):
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:24} {val}")
    return "\n".join(lines)
