"""Merge multiple benchmark runs into one combined report.

Models install in isolated venvs, so each benchmarks in its own run; this
merges their results for cross-model comparison — reusing the existing
RunResult model and reporters (no duplicate reporting logic).

    python -m voice_engine.scripts.merge_runs --runs run-id-1 run-id-2 --title "CPU baseline"
    python -m voice_engine.scripts.merge_runs --latest-per-adapter
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.benchmarking import RunResult  # noqa: E402
from foundation.constants.paths import BENCHMARK_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils.text import new_run_id  # noqa: E402
from voice_engine.reporting import CsvReporter, JsonReporter, MarkdownReporter, summarize_run  # noqa: E402


def load_run(run_dir: Path) -> RunResult:
    data = json.loads((run_dir / "run_full.json").read_text(encoding="utf-8"))
    return RunResult.from_dict(data)


def find_runs() -> list[Path]:
    if not BENCHMARK_OUTPUT_DIR.exists():
        return []
    return sorted(
        (d for d in BENCHMARK_OUTPUT_DIR.iterdir() if (d / "run_full.json").exists()),
        key=lambda d: d.name,
    )


def latest_per_adapter(run_dirs: list[Path]) -> list[Path]:
    """Newest run containing each adapter (excluding mock-only runs)."""
    chosen: dict[str, Path] = {}
    for run_dir in run_dirs:  # sorted ascending -> later overwrites
        run = load_run(run_dir)
        for subject in run.by_subject():
            if subject != "mock":
                chosen[subject] = run_dir
    return sorted(set(chosen.values()), key=lambda d: d.name)


def merge(run_dirs: list[Path], title: str) -> RunResult:
    merged = RunResult(run_id=new_run_id("merged"), title=title)
    for run_dir in run_dirs:
        run = load_run(run_dir)
        merged.cases.extend(run.cases)
        merged.config[f"source:{run.run_id}"] = {
            "title": run.title,
            "environment_cpu": run.environment.get("cpu_name"),
            "config": {k: v for k, v in run.config.items() if not k.startswith("source:")},
        }
        if not merged.environment:
            merged.environment = run.environment
        merged.started_at = min(merged.started_at, run.started_at)
        merged.finished_at = max(merged.finished_at or "", run.finished_at or "")
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge benchmark runs")
    parser.add_argument("--runs", nargs="*", default=[], help="Run ids (directory names)")
    parser.add_argument("--latest-per-adapter", action="store_true")
    parser.add_argument("--title", default="Merged voice benchmark")
    args = parser.parse_args(argv)

    configure_logging()
    if args.latest_per_adapter:
        run_dirs = latest_per_adapter(find_runs())
    else:
        run_dirs = [BENCHMARK_OUTPUT_DIR / r for r in args.runs]
        missing = [d for d in run_dirs if not (d / "run_full.json").exists()]
        if missing:
            print(f"Missing runs: {[d.name for d in missing]}")
            return 1
    if not run_dirs:
        print("No runs to merge.")
        return 1

    merged = merge(run_dirs, args.title)
    out_dir = ensure_dir(BENCHMARK_OUTPUT_DIR / merged.run_id)
    reports = {
        "csv": CsvReporter().write(merged, out_dir),
        "json": JsonReporter().write(merged, out_dir),
        "markdown": MarkdownReporter().write(merged, out_dir),
    }
    print(f"Merged {len(run_dirs)} runs -> {merged.run_id}")
    for subject in summarize_run(merged).subjects:
        print(f"  {subject.subject_id}: {subject.passed}P/{subject.failed}F/{subject.skipped}S")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
