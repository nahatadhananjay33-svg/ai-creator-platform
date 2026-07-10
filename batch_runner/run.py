"""The batch command (Phase C20):

    python -m batch_runner.run reels.csv

Read a batch of reels from CSV / JSON / YAML and generate them **one at a time**
by reusing ``creator.run`` — with resume, per-reel failure handling, live
progress, and a final ``batch_report.json`` + ``batch_summary.md``.

Examples::

    python -m batch_runner.run reels.csv
    python -m batch_runner.run reels.yaml --workspace ./my_workspace
    python -m batch_runner.run reels.json --config my_channel.yaml   # shared defaults
    python -m batch_runner.run reels.csv --quiet                     # only the summary

Re-run the same command after an interruption to resume: completed reels are
skipped, and the batch continues from the first unfinished reel.

Exit codes: 0 = all reels passed · 2 = one or more reels failed · 1 = a
user/environment mistake (shown as a plain message, no traceback).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from foundation.exceptions import PlatformError
from foundation.logging import configure_logging

from creator.paths import DEFAULT_WORKSPACE

from batch_runner.errors import BatchError
from batch_runner.input import load_entries
from batch_runner.report import write_reports
from batch_runner.runner import BatchRunner, ReelRunner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m batch_runner.run",
        description="Generate many reels sequentially from a CSV / JSON / YAML batch.",
    )
    parser.add_argument("input", help="batch file (.csv, .json, or .yaml)")
    parser.add_argument("--workspace", default=None,
                        help="workspace root for the reels (default: <repo>/workspace)")
    parser.add_argument("--config", default=None,
                        help="a base creator config layered under every reel")
    parser.add_argument("--batch-dir", default=None,
                        help="where state + reports live (default: <workspace>/batch)")
    parser.add_argument("--quiet", action="store_true",
                        help="print only the final summary")
    parser.add_argument("--verbose", action="store_true",
                        help="show detailed engine logs (INFO) on stderr")
    return parser


def _report_error(message: str, hint: str = "") -> int:
    print(f"\nError: {message}", file=sys.stderr)
    if hint:
        print(f"Hint:  {hint}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None, *, reel_runner: ReelRunner | None = None) -> int:
    """Run the batch CLI. ``reel_runner`` is an injection seam for tests/embedding."""
    args = _build_parser().parse_args(argv)
    configure_logging(level=logging.INFO if args.verbose else logging.WARNING)

    try:
        entries = load_entries(args.input)
        workspace_root = args.workspace or DEFAULT_WORKSPACE
        runner = BatchRunner(
            entries,
            workspace_root=workspace_root,
            base_config=args.config,
            batch_dir=args.batch_dir,
            reel_runner=reel_runner,
            out=(lambda _s: None) if args.quiet else print,
        )
        result = runner.run()
    except BatchError as exc:
        return _report_error(exc.message, exc.hint)
    except PlatformError as exc:
        hint = getattr(exc, "hint", "") or "Re-run with --verbose for details."
        return _report_error(exc.message, hint)

    report_dir = Path(args.batch_dir) if args.batch_dir else Path(result.batch_dir)
    json_path, md_path = write_reports(result, report_dir)

    print("\n=== BATCH COMPLETE ===")
    print(f"Total {result.total}  |  ✅ {result.passed} passed  "
          f"❌ {result.failed} failed  ⤼ {result.skipped} skipped  "
          f"in {round(result.elapsed_s, 1)}s")
    print(f"Report : {json_path}")
    print(f"Summary: {md_path}")
    if result.failed:
        print("Some reels failed — see the summary for per-reel errors and logs.")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
