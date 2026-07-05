"""Adapter runtime diagnostics report (Phase A3.7).

Answers *why* each avatar adapter is or is not runnable — replacing a bare
``available=False``. Unlike ``validate_models`` (which must run inside each
model's venv to generate a smoke video), this probes every adapter's venv
**from a single launcher** (e.g. the Colab main kernel) and writes:

    avatar_engine/output/validation/adapter_validation_report.md
    avatar_engine/output/validation/adapter_validation_report.json

Usage:
    python -m avatar_engine.scripts.validate_adapters
    python -m avatar_engine.scripts.validate_adapters --adapters sadtalker liveportrait
    python -m avatar_engine.scripts.validate_adapters --all --device cuda
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from avatar_engine.models import ADAPTER_CLASSES, create_adapter  # noqa: E402
from avatar_engine.models.diagnostics import write_adapter_validation_report  # noqa: E402

VALIDATION_DIR = Path(__file__).resolve().parents[1] / "output" / "validation"

#: Default focus set: the real adapters + the A3.6 priority pipeline + mock.
DEFAULT_ADAPTERS = ("mock", "sadtalker", "liveportrait", "musetalk", "echomimic-v3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avatar adapter runtime diagnostics")
    parser.add_argument("--adapters", nargs="+", default=None, choices=sorted(ADAPTER_CLASSES),
                        help=f"Adapters to probe (default: {', '.join(DEFAULT_ADAPTERS)})")
    parser.add_argument("--all", action="store_true", help="Probe every registered adapter")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    configure_logging()
    if args.all:
        adapter_ids = sorted(ADAPTER_CLASSES)
    else:
        adapter_ids = args.adapters or [a for a in DEFAULT_ADAPTERS if a in ADAPTER_CLASSES]

    diags = []
    for adapter_id in adapter_ids:
        adapter = create_adapter(adapter_id, device=args.device)
        diag = adapter.diagnostics(force=True)
        diags.append(diag)
        mark = "AVAILABLE" if diag.available else "unavailable"
        print(f"[{mark:11}] {adapter_id:16} {diag.reason}")

    out_dir = Path(args.output_dir) if args.output_dir else VALIDATION_DIR
    reports = write_adapter_validation_report(diags, out_dir)
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    available = sum(1 for d in diags if d.available)
    print(f"\n{available}/{len(diags)} adapters available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
