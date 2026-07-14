"""CLI: evaluate a video folder for avatar suitability.

    python -m production.avatar_dataset_evaluator.evaluate

Reads D:\\AI_CREATOR_DATA\\Tanshi\\raw_videos (recursive), writes the dataset +
reports to ...\\avatar_dataset. Resumable, CPU-only, offline.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional, Sequence

from .config import Config, Paths
from .pipeline import evaluate_dataset
from .report import build_report, format_report
from .storage import write_csv, write_sqlite, write_xlsx


def _sample_print(records, accepted: bool, n: int, seed: int, label: str) -> None:
    pool = [r for r in records if r.accepted == accepted]
    rng = random.Random(seed)
    sample = rng.sample(pool, min(n, len(pool)))
    print(f"\n{label} sample ({len(sample)} of {len(pool)}):")
    for r in sample:
        reason = r.accept_reason if accepted else r.reject_reason
        print(f"  {r.filename[:34]:34} {r.duration:6.1f}s  score={r.avatar_score:5.1f}  "
              f"{r.quality:9}  {reason[:46]}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m production.avatar_dataset_evaluator.evaluate",
                                 description="Evaluate videos for digital-avatar suitability.")
    ap.add_argument("--base", default=None, help="data root (default D:\\AI_CREATOR_DATA\\Tanshi or $AVATAR_EVAL_BASE)")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--sample-n", type=int, default=30)
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    cfg = Config()
    root = Path(args.base) if args.base else cfg.base_dir()
    paths = Paths.make(root).ensure()
    if not paths.source.exists():
        print(f"Source folder not found: {paths.source}")
        return 1

    print(f"Evaluating videos under: {paths.source}")
    records = evaluate_dataset(paths, cfg, resume=not args.no_resume, progress=True)

    write_sqlite(records, paths.out / "dataset.sqlite")
    write_csv(records, paths.out / "dataset.csv")
    write_xlsx(records, paths.out / "dataset.xlsx")

    rep = build_report(records)
    (paths.reports / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (paths.reports / "report.txt").write_text(format_report(rep), encoding="utf-8")

    print("\n" + format_report(rep))
    _sample_print(records, True, args.sample_n, 0, "ACCEPTED")
    _sample_print(records, False, args.sample_n, 1, "REJECTED")
    print(f"\nOutputs: {paths.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
