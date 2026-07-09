"""Run the Scene Planning Engine benchmark (Phase C7).

    python -m scene_engine.scripts.run_benchmark                     # hermetic
    python -m scene_engine.scripts.run_benchmark --repeats 16 --repetitions 5

Deterministic, pure-CPU workload; measures planning time, scene-generation time,
timeline generation, memory, and planner throughput (scenes/sec, words/sec). No
renderer, no FFmpeg, no GPU, no model, no network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from scene_engine.benchmark import (  # noqa: E402
    SceneBenchmark,
    SceneBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scene Planning Engine benchmark")
    parser.add_argument("--repeats", type=int, default=8,
                        help="times the ~10-scene base script is repeated")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-captions", action="store_true")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = SceneBenchmarkConfig(
        script_repeats=args.repeats, width=args.width, height=args.height,
        fps=args.fps, with_captions=not args.no_captions,
        repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = SceneBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
