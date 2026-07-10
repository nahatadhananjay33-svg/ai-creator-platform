"""Run the Workflow Engine benchmark and print a summary (Phase C14).

    python -m workflow_engine.scripts.run_benchmark
    python -m workflow_engine.scripts.run_benchmark --repetitions 3

Hermetic (mock voice + mock renderer): no GPU, model, ffmpeg, or network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402

from workflow_engine.benchmark.config import WorkflowBenchmarkConfig  # noqa: E402
from workflow_engine.benchmark.orchestrator import WorkflowBenchmark, summarize  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow Engine benchmark")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--no-reports", action="store_true")
    args = parser.parse_args(argv)
    configure_logging()

    cfg = WorkflowBenchmarkConfig(template=args.template, renderer=args.renderer,
                                  repetitions=max(1, args.repetitions))
    run, reports = WorkflowBenchmark(cfg).run(write_reports=not args.no_reports)
    print(summarize(run))
    if reports:
        print("\nReports:")
        for kind, path in reports.items():
            print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
