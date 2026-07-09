"""Run the Asset Resolver benchmark (Phase C9).

    python -m asset_engine.scripts.run_resolver_benchmark
    python -m asset_engine.scripts.run_resolver_benchmark --catalog 120 --slots 20

Deterministic workload; measures catalog loading, lookup, ranking, selection, and
memory over a generated local library. Hermetic — no renderer, ffmpeg, GPU, or AI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from asset_engine.benchmark import (  # noqa: E402
    ResolverBenchmark,
    ResolverBenchmarkConfig,
)
from asset_engine.benchmark.resolver import summarize  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Asset Resolver benchmark")
    parser.add_argument("--catalog", type=int, default=60)
    parser.add_argument("--slots", type=int, default=12)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = ResolverBenchmarkConfig(catalog_size=args.catalog, n_slots=args.slots,
                                  repetitions=args.repetitions)
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = ResolverBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
