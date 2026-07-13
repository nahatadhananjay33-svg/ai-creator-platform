"""CLI entry point.

    python -m production.voice_dataset.build [--base DIR] [--creator NAME]

Builds the dataset from local media and writes dataset.sqlite / .csv / .xlsx
plus a summary. Fully local and deterministic.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from .config import Config, Paths
from .pipeline import build_dataset
from .storage import write_csv, write_sqlite, write_xlsx
from .summary import format_summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m production.voice_dataset.build",
        description="Build a local, deterministic speech dataset from your own exported media.",
    )
    ap.add_argument("--base", default=None,
                    help="production_assets base dir (default: ./production_assets "
                         "or $VOICE_DATASET_BASE)")
    ap.add_argument("--creator", default="tanshi",
                    help="creator sub-folder name (default: tanshi)")
    args = ap.parse_args(argv)

    cfg = Config()
    base = Path(args.base) if args.base else cfg.base_dir()
    paths = Paths.for_creator(base, args.creator).ensure()

    records = build_dataset(paths, cfg)

    write_sqlite(records, paths.metadata / "dataset.sqlite")
    write_csv(records, paths.metadata / "dataset.csv")
    write_xlsx(records, paths.metadata / "dataset.xlsx")

    print(format_summary(records))
    print(f"\nRaw media       : {paths.raw}")
    print(f"Datasets written: {paths.metadata}")
    print(f"Accepted audio  : {paths.accepted}")
    print(f"Rejected audio  : {paths.rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
