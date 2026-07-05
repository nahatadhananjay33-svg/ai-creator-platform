"""Generate the static model comparison reports from the research catalog.

Usage:
    python -m avatar_engine.scripts.generate_research_report [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from foundation.constants.paths import AVATAR_ENGINE_DIR
from foundation.logging import configure_logging

from avatar_engine.reporting import ResearchReportGenerator

DEFAULT_OUTPUT_DIR = AVATAR_ENGINE_DIR / "output" / "research"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avatar research comparison reports")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    configure_logging()
    paths = ResearchReportGenerator().write_all(Path(args.output_dir))
    for kind, path in paths.items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
