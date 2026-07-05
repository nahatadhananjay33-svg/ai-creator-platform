"""Report LivePortrait pretrained-weight status (A3.9).

For every required weight, prints Validated / Missing / Corrupted /
Checksum-mismatch and writes ``liveportrait_weights_report.{md,json}``. Exit
code is non-zero if any weight is not valid.

Usage:
    python -m avatar_engine.scripts.validate_liveportrait_weights
    python -m avatar_engine.scripts.validate_liveportrait_weights --repo-dir <path>
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
from avatar_engine.models.liveportrait_weights import (  # noqa: E402
    HF_REPO_ID,
    check_weights,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "validation"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate LivePortrait weights")
    parser.add_argument("--repo-dir", default=str(REPOS_DIR / "liveportrait"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    configure_logging()

    repo_dir = Path(args.repo_dir)
    statuses = check_weights(repo_dir)
    for s in statuses:
        print(f"[{s.status:18}] {s.relpath:60} {s.reason}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "liveportrait_weights_report.json").write_text(
        json.dumps({"generated_at": utc_now_iso(), "repo_id": HF_REPO_ID,
                    "repo_dir": str(repo_dir), "weights": [s.to_dict() for s in statuses]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# LivePortrait Weights Report", "", f"Generated: {utc_now_iso()}",
             f"Source: `{HF_REPO_ID}` -> `{repo_dir}/pretrained_weights/`", "",
             "| Weight | Purpose | Status | Detail |", "|---|---|---|---|"]
    for s in statuses:
        lines.append(f"| `{s.relpath}` | {s.purpose} | {s.status} | {s.reason} |")
    valid = sum(s.ok for s in statuses)
    lines += ["", f"**{valid}/{len(statuses)} weights validated.**"]
    (out_dir / "liveportrait_weights_report.md").write_text("\n".join(lines) + "\n",
                                                            encoding="utf-8")

    print(f"\n{valid}/{len(statuses)} weights validated. "
          f"Report: {out_dir / 'liveportrait_weights_report.md'}")
    return 0 if valid == len(statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
