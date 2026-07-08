"""Run the Visual Asset Engine benchmark (Phase C6).

    python -m asset_engine.scripts.run_benchmark                    # mock, hermetic
    python -m asset_engine.scripts.run_benchmark --renderer ffmpeg  # real composite
    python -m asset_engine.scripts.run_benchmark --layout split_screen --assets 6

Deterministic workload; measures asset loading, timeline generation, render
overhead (with vs without assets), export, memory, and FPS. No AI, no GPU.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from asset_engine.benchmark import (  # noqa: E402
    AssetBenchmark,
    AssetBenchmarkConfig,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visual Asset Engine benchmark")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--layout", default="picture_in_picture")
    parser.add_argument("--assets", type=int, default=4)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    cfg = AssetBenchmarkConfig(
        renderer=args.renderer, layout=args.layout, n_assets=args.assets,
        width=args.width, height=args.height, fps=args.fps, repetitions=args.repetitions,
    )
    output_dir = Path(args.output_dir) if args.output_dir else None
    run, reports = AssetBenchmark(cfg, output_dir=output_dir).run()

    print("\n" + summarize(run))
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    failed = sum(1 for c in run.cases if c.status.value == "failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
