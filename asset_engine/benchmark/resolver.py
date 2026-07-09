"""Asset resolver benchmark (Phase C9).

Measures the deterministic retrieval pipeline over a generated local library:
catalog loading, per-slot lookup (provider gather), ranking, and full selection,
plus peak memory. Hermetic and pure-CPU — no renderer, ffmpeg, GPU, or network.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from foundation.benchmarking import (
    BenchmarkCase,
    BenchmarkRunner,
    CaseResult,
    Measurement,
    RunResult,
)
from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter, summarize_run
from foundation.shared_utils import Stopwatch
from foundation.shared_utils.text import new_run_id

from asset_engine.catalog.index import AssetCatalog
from asset_engine.providers.candidate import LocalLibraryProvider
from asset_engine.providers.placeholder import generate_image
from asset_engine.ranking.scorer import RankWeights, rank_candidates
from asset_engine.resolver.manager import ProviderManager
from asset_engine.resolver.query import build_query
from asset_engine.resolver.resolver import AssetResolver

logger = get_logger("asset_engine.resolver_benchmark")

#: The kinds the synthetic library + slots cover (a realistic retrieval spread).
_KINDS = ("image", "chart", "screenshot", "icon", "map")


@dataclass
class ResolverBenchmarkConfig:
    """One benchmark run: a fixed, deterministic retrieval workload."""

    catalog_size: int = 60           # library assets generated + indexed
    n_slots: int = 12                # slots resolved per case
    frame_width: int = 1080
    frame_height: int = 1920
    repetitions: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _Slot:
    """A minimal AssetSlot stand-in (structural — the resolver reads attributes)."""

    def __init__(self, i: int) -> None:
        kind = _KINDS[i % len(_KINDS)]
        self.slot_id = f"slot-{i:03d}"
        self.kind = kind
        self.hint = f"{kind}: topic {i % 7} scene detail view"
        self.layout = "full_screen" if i % 2 else "picture_in_picture"
        self.start_s = float(i)
        self.end_s = float(i) + 3.0
        self.z_index = 0
        self.required = True

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - best effort
        return 0.0


class ResolverBenchmarkCase(BenchmarkCase):
    """catalog load + lookup + ranking + selection timing over a local library."""

    def __init__(self, cfg: ResolverBenchmarkConfig, out_dir: Path, repetition: int = 0) -> None:
        super().__init__(case_id=f"resolve-n{cfg.catalog_size}-r{repetition}",
                         subject_id=f"resolve-n{cfg.catalog_size}",
                         scenario="asset_resolution")
        self.cfg = cfg
        self.out_dir = out_dir
        self.repetition = repetition

    def _build_library(self) -> Path:
        """Generate a deterministic on-disk library (once; reused across reps)."""
        root = self.out_dir / "library"
        if root.exists() and any(root.rglob("*.png")):
            return root
        for i in range(self.cfg.catalog_size):
            kind = _KINDS[i % len(_KINDS)]
            w, h = (1920, 1080) if i % 3 else (1080, 1920)
            generate_image(root / f"{kind}s" / f"{kind}_topic{i % 7}_view{i}.png",
                           width=w, height=h)
        return root

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        root = self._build_library()

        # 1) catalog loading: scan + index the library directory.
        with Stopwatch() as sw_load:
            catalog = AssetCatalog.from_directory(root)
        load_s = sw_load.elapsed_s

        manager = ProviderManager([LocalLibraryProvider(catalog)])
        resolver = AssetResolver(manager, weights=RankWeights())
        slots = [_Slot(i) for i in range(cfg.n_slots)]
        queries = [build_query(s, frame_width=cfg.frame_width,
                               frame_height=cfg.frame_height) for s in slots]

        # 2) lookup: gather candidates from providers for each query.
        with Stopwatch() as sw_lookup:
            candidate_sets = [manager.candidates(q) for q in queries]
        lookup_s = sw_lookup.elapsed_s

        # 3) ranking: score + sort each candidate set.
        with Stopwatch() as sw_rank:
            for q, cands in zip(queries, candidate_sets):
                rank_candidates(cands, q, resolver.weights)
        rank_s = sw_rank.elapsed_s

        # 4) selection: the full resolve (gather + rank + select) per slot.
        with Stopwatch() as sw_sel:
            resolutions = resolver.resolve_slots(
                slots, frame_width=cfg.frame_width, frame_height=cfg.frame_height)
        sel_s = sw_sel.elapsed_s
        satisfied = sum(1 for r in resolutions if r.satisfied)
        n = max(1, cfg.n_slots)

        result.add(Measurement("catalog_load_ms", round(load_s * 1000, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("lookup_ms_per_slot", round(lookup_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("ranking_ms_per_slot", round(rank_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("selection_ms_per_slot", round(sel_s / n * 1000, 4), "ms",
                               higher_is_better=False))
        result.add(Measurement("resolve_throughput", round(n / sel_s, 1) if sel_s else 0.0,
                               "slots/s", higher_is_better=True))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.add(Measurement("catalog_entries", catalog.size, "", source="static"))
        result.add(Measurement("slots_satisfied", satisfied, "", source="static"))
        result.metadata["all_satisfied"] = str(satisfied == cfg.n_slots)


class ResolverBenchmark:
    """Runs a fixed retrieval workload and reports loading/lookup/rank/select timing."""

    def __init__(self, config: ResolverBenchmarkConfig | None = None,
                 output_dir: Path | None = None) -> None:
        self.config = config or ResolverBenchmarkConfig()
        self.output_dir = output_dir or (REEL_OUTPUT_DIR / "resolver_runs")

    def build_cases(self, work_dir: Path) -> list[ResolverBenchmarkCase]:
        return [ResolverBenchmarkCase(self.config, work_dir, repetition=i)
                for i in range(max(1, self.config.repetitions))]

    def run(self, write_reports: bool = True) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("resolver-bench")
        run_dir = ensure_dir(self.output_dir / run_id)
        cases = self.build_cases(ensure_dir(run_dir / "work"))
        runner = BenchmarkRunner(title="Asset resolver benchmark",
                                 config=self.config.to_dict(), monitor_resources=True)
        run = runner.run(cases, run_id=run_id)
        reports: dict[str, Path] = {}
        if write_reports:
            reports["json"] = JsonReporter().write(run, run_dir)
            reports["csv"] = CsvReporter().write(run, run_dir)
        logger.info("Resolver benchmark finished",
                    extra={"context": {"run_id": run_id, "cases": len(cases)}})
        return run, reports


def summarize(run: RunResult) -> str:
    """One-line-per-metric text summary of a completed run."""
    summary = summarize_run(run)
    lines = [f"Run {run.run_id}: {run.title}"]
    for subject in summary.subjects:
        lines.append(f"  {subject.subject_id}: {subject.passed} passed, "
                     f"{subject.failed} failed")
        for name in ("catalog_load_ms", "lookup_ms_per_slot", "ranking_ms_per_slot",
                     "selection_ms_per_slot", "resolve_throughput", "rss_mb",
                     "catalog_entries", "slots_satisfied"):
            val = subject.metric_means.get(name)
            if val is not None:
                lines.append(f"      {name:24} {val}")
    return "\n".join(lines)
