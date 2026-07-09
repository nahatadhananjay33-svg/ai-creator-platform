"""Run the Review & Editing Engine benchmark (Phase C11).

    python -m editing_engine.scripts.run_benchmark
    python -m editing_engine.scripts.run_benchmark --patches 16 --template finance

Deterministic workload (MockProvider); measures patch application, incremental
regeneration, timeline validation, incremental-plan diff, and memory. Hermetic —
no AI, no GPU, no ffmpeg, no network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from editing_engine.benchmark import EditBenchmark, EditBenchmarkConfig, summarize  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review & Editing Engine benchmark")
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--patches", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = EditBenchmarkConfig(template=args.template, n_patches=args.patches,
                              repetitions=args.repetitions)
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = EditBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
