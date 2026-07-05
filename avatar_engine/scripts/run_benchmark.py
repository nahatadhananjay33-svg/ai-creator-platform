"""Run the avatar model benchmark.

Usage:
    python -m avatar_engine.scripts.run_benchmark
    python -m avatar_engine.scripts.run_benchmark --adapters mock sadtalker
    python -m avatar_engine.scripts.run_benchmark --categories neutral_speech fast_speech
"""
from __future__ import annotations

import argparse
import sys

from foundation.logging import configure_logging

from avatar_engine.benchmark import AvatarBenchmark, AvatarBenchmarkConfig
from avatar_engine.evaluation import AvatarHumanEvalProtocol
from avatar_engine.models import benchmarkable_model_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avatar model benchmark")
    parser.add_argument(
        "--adapters", nargs="+", default=["mock"],
        help=f"Adapter ids to benchmark. Known: {', '.join(benchmarkable_model_ids())}",
    )
    parser.add_argument("--categories", nargs="+", default=[],
                        help="Scenario categories to include (default: all)")
    parser.add_argument("--max-scenarios", type=int, default=0)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--no-placeholders", action="store_true",
                        help="Fail instead of generating placeholder assets")
    parser.add_argument("--human-eval-sheet", action="store_true",
                        help="Also write the blind human-eval score sheet")
    args = parser.parse_args(argv)

    configure_logging()
    config = AvatarBenchmarkConfig(
        adapters=args.adapters,
        categories=args.categories,
        max_scenarios=args.max_scenarios,
        repetitions=args.repetitions,
        device=args.device,
        allow_placeholder_assets=not args.no_placeholders,
    )
    if args.output_dir:
        config.output_dir = args.output_dir

    run, reports = AvatarBenchmark(config).run()
    print(f"Run {run.run_id}: {len(run.cases)} cases")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    if args.human_eval_sheet:
        sheet, key = AvatarHumanEvalProtocol().write_score_sheet(
            run, reports["markdown"].parent
        )
        print(f"  human-eval sheet: {sheet}")
        print(f"  human-eval key (CONFIDENTIAL): {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
