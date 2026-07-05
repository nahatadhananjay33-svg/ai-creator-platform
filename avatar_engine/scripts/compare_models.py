"""Generate the SadTalker vs LivePortrait comparison report (A3.9).

Reads existing benchmark run JSONs (``run_full.json``) — no re-execution — and
writes a measured side-by-side comparison to
``avatar_engine/output/comparisons/``.

Usage:
    python -m avatar_engine.scripts.compare_models                 # latest per model
    python -m avatar_engine.scripts.compare_models --runs <dirA> <dirB>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.benchmarking import RunResult  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from avatar_engine.reporting.comparison import write_comparison_report  # noqa: E402

RUNS_DIR = Path(__file__).resolve().parents[1] / "output" / "runs"
OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "comparisons"
_MODELS = ("sadtalker", "liveportrait")


def _load(run_dir: Path) -> RunResult | None:
    import json

    p = run_dir / "run_full.json"
    if not p.exists():
        return None
    return RunResult.from_dict(json.loads(p.read_text(encoding="utf-8")))


def _latest_per_model(models=_MODELS) -> list[Path]:
    """Newest run dir that contains each model's cases."""
    dirs = sorted([d for d in RUNS_DIR.glob("avatar-bench-*") if d.is_dir()],
                  key=lambda d: d.stat().st_mtime, reverse=True)
    chosen: list[Path] = []
    for model in models:
        for d in dirs:
            run = _load(d)
            if run and any(c.subject_id == model for c in run.cases):
                chosen.append(d)
                break
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SadTalker vs LivePortrait comparison")
    parser.add_argument("--runs", nargs="+", default=None, help="Run dirs to compare")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)
    configure_logging()

    run_dirs = [Path(r) for r in args.runs] if args.runs else _latest_per_model()
    runs = [r for r in (_load(d) for d in run_dirs) if r is not None]
    if not runs:
        print("No benchmark runs found to compare. Run the benchmark first.")
        return 1

    reports = write_comparison_report(runs, Path(args.output_dir) if args.output_dir else OUT_DIR)
    print("Comparison report:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    print("\n" + reports["markdown"].read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
