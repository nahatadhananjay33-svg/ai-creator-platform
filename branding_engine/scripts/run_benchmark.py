"""Run the Branding Engine benchmark (Phase C5).

    python -m branding_engine.scripts.run_benchmark                    # mock, hermetic
    python -m branding_engine.scripts.run_benchmark --renderer ffmpeg  # real MP4 composite
    python -m branding_engine.scripts.run_benchmark --theme finance

Deterministic workload (fixed theme + timeline); measures startup, branding
generation, render overhead (with vs without branding), export, and memory.
No AI, no GPU.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from branding_engine.benchmark import (  # noqa: E402
    BrandingBenchmark,
    BrandingBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Branding Engine benchmark")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--theme", default="corporate")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = BrandingBenchmarkConfig(
        renderer=args.renderer, theme=args.theme, width=args.width,
        height=args.height, fps=args.fps, repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = BrandingBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
