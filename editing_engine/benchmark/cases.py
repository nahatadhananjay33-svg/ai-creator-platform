"""Editing benchmark cases (Phase C11).

Subclasses :class:`foundation.benchmarking.BenchmarkCase`. One case measures the
deterministic edit loop with the MockProvider:

    patch application  ->  incremental regeneration (project -> Timeline)
    ->  timeline validation  ->  incremental-plan diff

and reports each stage's time plus peak memory. Hermetic and pure-CPU — no
renderer, ffmpeg, GPU, model, or network (music/branding tracks are skipped so the
loop stays fast and file-free; scenes + captions are the regenerated content).
"""
from __future__ import annotations

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch
from reel_engine.timeline.validate import validate_timeline

from editing_engine.benchmark.config import EditBenchmarkConfig
from editing_engine.engine import EditingEngine
from editing_engine.incremental import plan_incremental
from editing_engine.patches import (
    CaptionPatch,
    DurationPatch,
    InsertScenePatch,
    MoveScenePatch,
    MusicPatch,
    ReplaceNarrationPatch,
    ThemePatch,
)
from editing_engine.validation.validate import apply_patch


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - best effort
        return 0.0


def _patch_set(n: int) -> list:
    """A fixed, deterministic patch sequence (cycled to ``n`` patches)."""
    seq = [
        ReplaceNarrationPatch(1, "A freshly rewritten second scene with new content here."),
        MoveScenePatch(2, 4),
        InsertScenePatch(3, "An inserted scene adds a new beat to the reel.", "explanation"),
        DurationPatch(0, 5.5),
        ThemePatch("finance"),
        MusicPatch("upbeat"),
        CaptionPatch(kind="karaoke", preset="tiktok"),
        ReplaceNarrationPatch(0, "A brand new opening hook for the whole reel."),
    ]
    return [seq[i % len(seq)] for i in range(n)]


class EditBenchmarkCase(BenchmarkCase):
    """Patch application + incremental regeneration + validation + diff timing."""

    def __init__(self, cfg: EditBenchmarkConfig, repetition: int = 0) -> None:
        super().__init__(case_id=f"edit-{cfg.template}-n{cfg.n_patches}-r{repetition}",
                         subject_id=f"edit-{cfg.template}-n{cfg.n_patches}",
                         scenario="reel_editing")
        self.cfg = cfg
        self.repetition = repetition

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        engine = EditingEngine()
        project = engine.new_project(cfg.prompt, template=cfg.template,
                                     width=cfg.width, height=cfg.height, fps=cfg.fps)
        _, base_tl = engine.build_timeline(project, with_branding=False, with_music=False)
        patches = _patch_set(cfg.n_patches)
        n = max(1, cfg.n_patches)

        # 1) patch application (validate + apply) — the core edit op.
        with Stopwatch() as sw_patch:
            edited = project
            for patch in patches:
                edited = apply_patch(patch, edited)
        patch_s = sw_patch.elapsed_s

        # 2) incremental regeneration: rebuild the timeline from the edited project.
        with Stopwatch() as sw_regen:
            _, new_tl = engine.build_timeline(edited, with_branding=False, with_music=False)
        regen_s = sw_regen.elapsed_s

        # 3) timeline validation (the invariant checked after every edit).
        with Stopwatch() as sw_valid:
            problems = validate_timeline(new_tl)
        valid_s = sw_valid.elapsed_s

        # 4) incremental-plan diff (which scenes actually changed).
        with Stopwatch() as sw_plan:
            plan = plan_incremental(base_tl, new_tl)
        plan_s = sw_plan.elapsed_s

        result.add(Measurement("patch_apply_ms", round(patch_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("incremental_regen_ms", round(regen_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("timeline_validation_ms", round(valid_s * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("incremental_plan_ms", round(plan_s * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("patches_per_s", round(n / patch_s, 1) if patch_s else 0.0,
                               "patches/s", higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("n_patches", n, "", source="static"))
        result.add(Measurement("scenes_changed", plan.n_changed, "", source="static"))
        result.add(Measurement("scenes_reused", plan.n_reused, "", source="static"))
        result.metadata["timeline_valid"] = str(problems == [])
        result.metadata["reuse_fraction"] = str(plan.reuse_fraction)
