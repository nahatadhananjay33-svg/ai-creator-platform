"""Run the Content Library benchmark and print a summary (Phase C15).

    python -m content_library.scripts.run_benchmark
    python -m content_library.scripts.run_benchmark --n-projects 500

Hermetic: local JSON only — no workflow generation, GPU, ffmpeg, or network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402

from content_library.benchmark.config import LibraryBenchmarkConfig  # noqa: E402
from content_library.benchmark.orchestrator import LibraryBenchmark, summarize  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Content Library benchmark")
    parser.add_argument("--n-projects", type=int, default=250)
    parser.add_argument("--n-queries", type=int, default=50)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--no-reports", action="store_true")
    args = parser.parse_args(argv)
    configure_logging()

    cfg = LibraryBenchmarkConfig(n_projects=max(1, args.n_projects),
                                 n_queries=max(1, args.n_queries),
                                 repetitions=max(1, args.repetitions))
    run, reports = LibraryBenchmark(cfg).run(write_reports=not args.no_reports)
    print(summarize(run))
    if reports:
        print("\nReports:")
        for kind, path in reports.items():
            print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
