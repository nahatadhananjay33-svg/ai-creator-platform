"""AI Prompt & Storyboard benchmark cases (Phase C10).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`. One case measures the
full prompt->reel path with the deterministic MockProvider:

    provider (prompt -> AIStoryboard) -> validation -> script -> scene generation
    -> timeline generation  =  total pipeline

and reports each stage's time plus peak memory. Hermetic and pure-CPU — no
renderer, FFmpeg, GPU, model, or network.
"""
from __future__ import annotations

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch
from scene_engine import SceneEngine

from script_engine.benchmark.config import ScriptBenchmarkConfig
from script_engine.config.settings import ScriptEngineConfig
from script_engine.prompt_templates.registry import get_template
from script_engine.providers import GenerationRequest, get_provider
from script_engine.storyboard.script import storyboard_to_script
from script_engine.validator.validator import validate_storyboard


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - best effort
        return 0.0


class ScriptBenchmarkCase(BenchmarkCase):
    """Provider + validation + script + scene + timeline generation timing."""

    def __init__(self, cfg: ScriptBenchmarkConfig, repetition: int = 0) -> None:
        super().__init__(case_id=f"{cfg.provider}-{cfg.template}-r{repetition}",
                         subject_id=f"{cfg.provider}-{cfg.template}",
                         scenario="prompt_to_reel")
        self.cfg = cfg
        self.repetition = repetition
        self.engine_cfg = ScriptEngineConfig(provider=cfg.provider, template=cfg.template)

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        provider = get_provider(cfg.provider)
        template = get_template(cfg.template)
        scene_engine = SceneEngine()

        prov_s = valid_s = script_s = scene_s = tl_s = 0.0
        ai_scenes = scene_scenes = words = 0

        with Stopwatch() as sw_total:
            for prompt in cfg.prompts:
                request = GenerationRequest.build(prompt, template, self.engine_cfg)
                with Stopwatch() as sw:
                    storyboard = provider.generate(request)
                prov_s += sw.elapsed_s
                with Stopwatch() as sw:
                    validate_storyboard(storyboard, min_scenes=self.engine_cfg.min_scenes,
                                        max_scenes=self.engine_cfg.max_scenes)
                valid_s += sw.elapsed_s
                with Stopwatch() as sw:
                    script = storyboard_to_script(storyboard)
                script_s += sw.elapsed_s
                with Stopwatch() as sw:
                    scene_sb = scene_engine.plan(script, title=storyboard.title)
                scene_s += sw.elapsed_s
                with Stopwatch() as sw:
                    scene_engine.build_timeline(scene_sb)
                tl_s += sw.elapsed_s
                ai_scenes += storyboard.n_scenes
                scene_scenes += scene_sb.n_scenes
                words += storyboard.word_count
        total_s = sw_total.elapsed_s
        n = max(1, len(cfg.prompts))

        result.add(Measurement("provider_ms", round(prov_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("storyboard_gen_ms", round(prov_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("validation_ms", round(valid_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("scene_gen_ms", round(scene_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("timeline_gen_ms", round(tl_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("total_pipeline_ms", round(total_s / n * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("prompts_per_s", round(n / total_s, 1) if total_s else 0.0,
                               "prompts/s", higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("ai_scenes", ai_scenes, "", source="static"))
        result.add(Measurement("scene_scenes", scene_scenes, "", source="static"))
        result.add(Measurement("words", words, "", source="static"))
        result.metadata["prompts"] = str(len(cfg.prompts))
