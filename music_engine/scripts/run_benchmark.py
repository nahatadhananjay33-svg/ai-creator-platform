"""Run the Music & Audio Mixing Engine benchmark (Phase C8).

    python -m music_engine.scripts.run_benchmark                     # mock, hermetic
    python -m music_engine.scripts.run_benchmark --soundtrack upbeat
    python -m music_engine.scripts.run_benchmark --duration 40 --scenes 6

Deterministic workload; measures music loading, mixing overhead, render overhead
(with vs without music), export, memory, and FPS. No AI, no GPU, no downloads.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from music_engine.benchmark import (  # noqa: E402
    MusicBenchmark,
    MusicBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Music & Audio Mixing Engine benchmark")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--soundtrack", default="ambient")
    parser.add_argument("--duration", type=float, default=24.0)
    parser.add_argument("--scenes", type=int, default=4)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--sample-rate", type=int, default=44100)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = MusicBenchmarkConfig(
        renderer=args.renderer, soundtrack=args.soundtrack,
        reel_duration_s=args.duration, n_scenes=args.scenes,
        width=args.width, height=args.height, fps=args.fps,
        sample_rate=args.sample_rate, repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = MusicBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
