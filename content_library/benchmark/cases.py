"""Content Library benchmark cases (Phase C15).

One case measures the metadata operations the milestone asks for — project **save**,
**load**, **search**, and **metadata indexing** — over a synthetic library of N
projects. Fully hermetic: local JSON only, no workflow generation, no GPU/API/ffmpeg.
"""
from __future__ import annotations

import tempfile

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.shared_utils import Stopwatch

from content_library.benchmark.config import LibraryBenchmarkConfig
from content_library.library import ContentLibrary


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - best effort
        return 0.0


_TEMPLATES = ("real_estate", "product", "education", "finance")
_TAGSETS = (("finance", "invest"), ("product", "launch"), ("education", "how-to"),
            ("finance", "property"))


class LibraryBenchmarkCase(BenchmarkCase):
    """Save + load + search + index-rebuild timing over N synthetic projects."""

    def __init__(self, cfg: LibraryBenchmarkConfig, repetition: int = 0) -> None:
        super().__init__(case_id=f"lib-n{cfg.n_projects}-r{repetition}",
                         subject_id=f"lib-n{cfg.n_projects}", scenario="content_library")
        self.cfg = cfg
        self.repetition = repetition

    def execute(self, result: CaseResult) -> None:
        cfg = self.cfg
        n = max(1, cfg.n_projects)
        counter = iter(range(1, 10 ** 9))
        clock = lambda: f"2026-01-01T00:{next(counter) % 60:02d}:00Z"  # noqa: E731
        library = ContentLibrary(tempfile.mkdtemp(), clock=clock)

        # 1) save: create + persist N projects (manifest write + index upsert).
        with Stopwatch() as sw_save:
            ids = []
            for i in range(n):
                rec = library.create_project(
                    f"Project {i:05d}", prompt=f"prompt number {i}",
                    template=_TEMPLATES[i % len(_TEMPLATES)],
                    tags=_TAGSETS[i % len(_TAGSETS)], project_id=f"proj-{i:05d}")
                ids.append(rec.project_id)
        save_s = sw_save.elapsed_s

        # 2) load: read every manifest back.
        with Stopwatch() as sw_load:
            for pid in ids:
                library.load(pid)
        load_s = sw_load.elapsed_s

        # 3) search: run a mix of queries over the index.
        q = max(1, cfg.n_queries)
        with Stopwatch() as sw_search:
            for i in range(q):
                library.search(template=_TEMPLATES[i % len(_TEMPLATES)],
                               tag=_TAGSETS[i % len(_TAGSETS)][0], sort="modified_desc")
        search_s = sw_search.elapsed_s

        # 4) metadata indexing: rebuild the whole index from the manifests.
        with Stopwatch() as sw_index:
            library.rebuild_index()
        index_s = sw_index.elapsed_s

        def ms(v: float, d: int = 4) -> float:
            return round(v * 1000, d)

        result.add(Measurement("save_ms_per_project", ms(save_s / n), "ms",
                               higher_is_better=False))
        result.add(Measurement("load_ms_per_project", ms(load_s / n), "ms",
                               higher_is_better=False))
        result.add(Measurement("search_ms_per_query", ms(search_s / q), "ms",
                               higher_is_better=False))
        result.add(Measurement("index_rebuild_ms", ms(index_s, 3), "ms",
                               higher_is_better=False))
        result.add(Measurement("save_projects_per_s",
                               round(n / save_s, 1) if save_s else 0.0, "proj/s",
                               higher_is_better=True))
        result.add(Measurement("load_projects_per_s",
                               round(n / load_s, 1) if load_s else 0.0, "proj/s",
                               higher_is_better=True))
        result.add(Measurement("n_projects", n, "", source="static"))
        result.add(Measurement("rss_mb", round(_rss_mb(), 1), "MB", higher_is_better=False))
        result.metadata["index_size"] = str(len(library.index))
