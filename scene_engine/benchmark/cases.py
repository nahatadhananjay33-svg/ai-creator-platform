"""Scene planning benchmark cases (Phase C7).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`, inheriting timing,
resource monitoring (peak RSS), and reporting. One case measures the full
deterministic planning path over a fixed script:

    planning (script -> Storyboard)
      = segmentation + classification
      + timing estimation
      + timeline generation (Storyboard -> Timeline IR + captions)

and reports throughput (scenes/sec, words/sec) plus peak memory. No renderer, no
FFmpeg, no model, no GPU — planning is pure CPU and fully hermetic.
"""
from __future__ import annotations

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch

from scene_engine.benchmark.config import SceneBenchmarkConfig
from scene_engine.config.settings import SceneEngineConfig
from scene_engine.planner.planner import plan_storyboard
from scene_engine.rules.segmentation import segment_scenes
from scene_engine.timeline.builder import build_timeline

#: A fixed ~10-scene base script that exercises every scene-type rule path.
_BASE_SCRIPT = (
    "Did you know most short videos fail in the first three seconds?\n\n"
    "Let me show you why. The data shows that 65% of viewers scroll away.\n\n"
    "Look at this chart of retention over time. It drops off a cliff.\n\n"
    "Compared to long videos, short reels demand a much stronger hook.\n\n"
    "Here are three ways to fix it. First, open with a question. "
    "Second, cut the intro. Third, show the payoff early.\n\n"
    "As the saying goes, 'show, do not tell.'\n\n"
    "Watch how this creator nails the opening in one clip.\n\n"
    "So if this helped, subscribe and follow for more tips.\n\n"
    "Thanks for watching, see you in the next one.\n\n"
)


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


class SceneBenchmarkCase(BenchmarkCase):
    """Segmentation + classification + timing + timeline-gen timing/throughput."""

    def __init__(self, cfg: SceneBenchmarkConfig, repetition: int = 0) -> None:
        super().__init__(case_id=f"plan-x{cfg.script_repeats}-r{repetition}",
                         subject_id=f"plan-x{cfg.script_repeats}",
                         scenario="scene_planning")
        self.cfg = cfg
        self.repetition = repetition
        self.script = _BASE_SCRIPT * max(1, cfg.script_repeats)
        self.engine_cfg = SceneEngineConfig()

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        word_count = len(self.script.split())

        # 1) scene generation only: segmentation + classification cost.
        with Stopwatch() as sw_seg:
            scenes_text = segment_scenes(self.script, self.engine_cfg)
        seg_s = sw_seg.elapsed_s
        n_scenes = len(scenes_text)

        # 2) full planning: script -> Storyboard (segment + classify + time + plan).
        with Stopwatch() as sw_plan:
            storyboard = plan_storyboard(self.script, self.engine_cfg, title="bench")
        plan_s = sw_plan.elapsed_s

        # 3) timeline generation: Storyboard -> Timeline IR (+ captions), validated.
        with Stopwatch() as sw_tl:
            timeline = build_timeline(
                storyboard, width=cfg.width, height=cfg.height, fps=cfg.fps,
                with_captions=cfg.with_captions)
        tl_s = sw_tl.elapsed_s

        plan_throughput = n_scenes / plan_s if plan_s > 0 else 0.0
        word_throughput = word_count / plan_s if plan_s > 0 else 0.0

        result.add(Measurement("planning_ms", round(plan_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("scene_gen_ms", round(seg_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("timeline_gen_ms", round(tl_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("scenes_per_s", round(plan_throughput, 1), "scenes/s",
                               higher_is_better=True))
        result.add(Measurement("words_per_s", round(word_throughput, 1), "words/s",
                               higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB",
                               higher_is_better=False))
        result.add(Measurement("n_scenes", n_scenes, "", source="static"))
        result.add(Measurement("n_words", word_count, "", source="static"))
        result.add(Measurement("plan_duration_s", storyboard.duration_s, "s",
                               source="static"))
        result.add(Measurement("n_asset_slots", len(storyboard.all_asset_slots), "",
                               source="static"))
        result.metadata["scene_types"] = ",".join(
            t.value for t in storyboard.scene_types()[:12])
        result.metadata["timeline_valid"] = str(timeline.n_scenes == n_scenes)
