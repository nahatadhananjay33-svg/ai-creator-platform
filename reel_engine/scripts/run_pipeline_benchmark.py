"""Benchmark the end-to-end AI Creator Platform pipeline (Phase C3).

    # Hermetic by default: mock voice + mock avatar + real ffmpeg MP4
    python -m reel_engine.scripts.run_pipeline_benchmark

    # Profile real production stages (needs the models installed)
    python -m reel_engine.scripts.run_pipeline_benchmark \
        --voice-model kokoro --avatar-model musetalk --repetitions 5

Measures, per stage: voice / avatar / timeline / render / export / total wall-
clock, plus process RSS and (on GPU hosts) peak GPU memory + utilisation via the
runner's resource monitor. Writes JSON + CSV reports.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from reel_engine.orchestrator.benchmark import (  # noqa: E402
    PipelineBenchmark,
    PipelineBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="End-to-end pipeline benchmark")
    p.add_argument("--voice-model", default="mock")
    p.add_argument("--avatar-model", default="mock")
    p.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--height", type=int, default=1280)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--profiles", nargs="+", default=["reel_9x16"])
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--output-dir", default=None)
    args = p.parse_args(argv)
    configure_logging()

    cfg = PipelineBenchmarkConfig(
        voice_model=args.voice_model, avatar_model=args.avatar_model,
        renderer=args.renderer, width=args.width, height=args.height, fps=args.fps,
        profiles=args.profiles, repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = PipelineBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
