"""Run the Caption Engine benchmark (Phase C4).

    python -m caption_engine.scripts.run_benchmark                    # mock, hermetic
    python -m caption_engine.scripts.run_benchmark --renderer ffmpeg  # real MP4 burn-in
    python -m caption_engine.scripts.run_benchmark --kind sentence    # any caption kind

Deterministic workload (fixed script + timeline); measures caption generation,
render overhead (with vs without captions), export, subtitle export, and memory.
No AI, no GPU.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from caption_engine.benchmark import (  # noqa: E402
    CaptionBenchmark,
    CaptionBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Caption Engine benchmark")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--kind", default="karaoke",
                        choices=["sentence", "word", "karaoke", "static"])
    parser.add_argument("--preset", default="tiktok")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = CaptionBenchmarkConfig(
        renderer=args.renderer, kind=args.kind, preset=args.preset,
        duration_s=args.duration, width=args.width, height=args.height,
        fps=args.fps, repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = CaptionBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
