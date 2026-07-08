"""Run the Reels Engine render benchmark (Phase C2).

    python -m reel_engine.scripts.run_benchmark                       # mock, hermetic
    python -m reel_engine.scripts.run_benchmark --renderer ffmpeg     # real MP4 encode

Deterministic workload (fixed demo timeline); measures startup / render / export
/ FPS / memory / output duration. No AI, no GPU.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from reel_engine.benchmark import ReelBenchmark, ReelBenchmarkConfig, summarize  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reels Engine render benchmark")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--scenes", type=int, default=3)
    parser.add_argument("--scene-duration", type=float, default=2.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = ReelBenchmarkConfig(
        renderer=args.renderer, n_scenes=args.scenes, scene_duration_s=args.scene_duration,
        width=args.width, height=args.height, fps=args.fps, repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = ReelBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
