"""Workflow benchmark cases (Phase C14).

One case exercises the whole orchestration lifecycle hermetically (mock voice +
mock renderer — no GPU, no network, no ffmpeg) and reports the numbers the
milestone asks for:

    startup ─► cold run (cache miss) ─► warm run (cache hit / resume)
            ─► incremental rebuild (force one stage) ─► throughput + memory

The cold run is the full ``prompt -> export`` execution; the warm run resumes the
same run id (every stage reused); the incremental run forces one stage and measures
rebuilding only it plus its downstream. Peak RSS is captured by the generic runner;
this case adds a direct ``rss_mb`` sample too.
"""
from __future__ import annotations

import tempfile

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch

from workflow_engine.engine import WorkflowEngine
from workflow_engine.stages.base import Presentation
from workflow_engine.benchmark.config import REPORTED_STAGES, WorkflowBenchmarkConfig


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - best effort
        return 0.0


class WorkflowBenchmarkCase(BenchmarkCase):
    """Startup + cold/warm/incremental execution + throughput + memory."""

    def __init__(self, cfg: WorkflowBenchmarkConfig, repetition: int = 0) -> None:
        super().__init__(case_id=f"wf-{cfg.template}-{cfg.renderer}-r{repetition}",
                         subject_id=f"wf-{cfg.template}-{cfg.renderer}",
                         scenario="reel_production")
        self.cfg = cfg
        self.repetition = repetition

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine = WorkflowEngine(root=tempfile.mkdtemp())

        # 1) startup: build + statically validate the workflow.
        with Stopwatch() as sw_build:
            wf = engine.build(cfg.prompt, template=cfg.template, provider=cfg.provider,
                              voice_model=cfg.voice_model, renderer=cfg.renderer,
                              profiles=cfg.profiles, presentation=Presentation(fps=cfg.fps))
            valid = engine.validate(wf).ok
        startup_s = sw_build.elapsed_s
        n_stages = len(wf.order())

        # 2) cold run (every stage a cache miss).
        with Stopwatch() as sw_cold:
            cold = engine.run(wf, run_id="bench")
        cold_s = sw_cold.elapsed_s

        # 3) warm run (resume: every stage a cache hit).
        with Stopwatch() as sw_warm:
            warm = engine.run(wf, run_id="bench")
        warm_s = sw_warm.elapsed_s

        # 4) incremental rebuild (force one stage -> it + its downstream re-run).
        with Stopwatch() as sw_inc:
            inc = engine.rebuild(wf, run_id="bench", stages=[cfg.rebuild_stage])
        inc_s = sw_inc.elapsed_s

        cold_hits = len(cold.cached())
        warm_hits = len(warm.cached())
        rebuilt = len(inc.executed())
        reused = len(inc.cached())

        def ms(v: float) -> float:
            return round(v * 1000, 3)

        result.add(Measurement("startup_ms", ms(startup_s), "ms", higher_is_better=False))
        result.add(Measurement("cold_run_ms", ms(cold_s), "ms", higher_is_better=False))
        result.add(Measurement("warm_run_ms", ms(warm_s), "ms", higher_is_better=False))
        result.add(Measurement("incremental_ms", ms(inc_s), "ms", higher_is_better=False))
        result.add(Measurement("speedup_warm_vs_cold",
                               round(cold_s / warm_s, 2) if warm_s else 0.0, "x",
                               higher_is_better=True))
        result.add(Measurement("throughput_stages_per_s",
                               round(n_stages / cold_s, 1) if cold_s else 0.0,
                               "stages/s", higher_is_better=True))
        result.add(Measurement("cache_hits_warm", warm_hits, "", source="static"))
        result.add(Measurement("cache_misses_cold", n_stages - cold_hits, "", source="static"))
        result.add(Measurement("incremental_rebuilt", rebuilt, "", source="static"))
        result.add(Measurement("incremental_reused", reused, "", source="static"))
        result.add(Measurement("stages_total", n_stages, "", source="static"))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))

        # per-stage cold execution timings (the "stage execution" measurement).
        for name in REPORTED_STAGES:
            sr = cold.stage_results.get(name)
            if sr is not None:
                result.add(Measurement(f"stage_{name}_ms", ms(sr.duration_s), "ms",
                                       higher_is_better=False))

        result.metadata["valid"] = str(valid)
        result.metadata["ok"] = str(cold.ok and warm.ok and inc.ok)
        result.metadata["warm_all_cached"] = str(warm_hits == n_stages)
