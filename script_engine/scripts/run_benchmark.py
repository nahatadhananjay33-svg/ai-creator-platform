"""Run the AI Prompt & Storyboard Engine benchmark (Phase C10).

    python -m script_engine.scripts.run_benchmark               # mock, hermetic
    python -m script_engine.scripts.run_benchmark --template finance

Deterministic workload; measures provider latency, storyboard generation,
validation, scene generation, timeline generation, total pipeline time, and
memory. Hermetic (MockProvider) — no AI, no GPU, no network, no API key.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from script_engine.benchmark import (  # noqa: E402
    ScriptBenchmark,
    ScriptBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Prompt & Storyboard Engine benchmark")
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--template", default="general")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = ScriptBenchmarkConfig(provider=args.provider, template=args.template,
                                repetitions=args.repetitions)
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = ScriptBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
