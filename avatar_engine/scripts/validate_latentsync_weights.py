"""Report LatentSync pretrained-weight status (A4.7).

For every required checkpoint, prints Verified / Missing / Corrupted and writes
``latentsync_weights_report.{md,json}``. Exit code is non-zero if any required
inference weight is not valid.

Usage:
    python -m avatar_engine.scripts.validate_latentsync_weights
    python -m avatar_engine.scripts.validate_latentsync_weights --repo-dir <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from foundation.model_manager.installer import REPOS_DIR  # noqa: E402
from foundation.shared_utils.timing import utc_now_iso  # noqa: E402
from avatar_engine.models.latentsync_weights import all_required_valid, check_weights  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "validation"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate LatentSync weights")
    parser.add_argument("--repo-dir", default=str(REPOS_DIR / "latentsync"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    configure_logging()

    repo_dir = Path(args.repo_dir)
    statuses = check_weights(repo_dir)
    for s in statuses:
        flag = "req" if s.required else "opt"
        print(f"[{s.status:10}] ({flag}) {s.relpath:32} {s.reason}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latentsync_weights_report.json").write_text(
        json.dumps({"generated_at": utc_now_iso(), "repo_dir": str(repo_dir),
                    "weights": [s.to_dict() for s in statuses]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# LatentSync Weights Report", "", f"Generated: {utc_now_iso()}",
             f"Weights dir: `{repo_dir}/checkpoints/`", "",
             "| Weight | Required | Purpose | Status | Detail |", "|---|:--:|---|---|---|"]
    for s in statuses:
        lines.append(f"| `{s.relpath}` | {'yes' if s.required else 'no'} | "
                     f"{s.purpose} | {s.status} | {s.reason} |")
    req_ok = sum(s.ok for s in statuses if s.required)
    req_total = sum(1 for s in statuses if s.required)
    lines += ["", f"**{req_ok}/{req_total} required inference weights verified.**"]
    (out_dir / "latentsync_weights_report.md").write_text("\n".join(lines) + "\n",
                                                          encoding="utf-8")

    print(f"\n{req_ok}/{req_total} required weights verified. "
          f"Report: {out_dir / 'latentsync_weights_report.md'}")
    return 0 if all_required_valid(statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
