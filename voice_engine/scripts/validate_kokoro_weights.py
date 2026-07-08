"""Report Kokoro pretrained-weight status (Phase B2.1).

For every manifest file, prints Validated / Missing / Corrupted and writes
``kokoro_weights_report.{md,json}``. Exit code is non-zero if any required
weight is not valid. Resolves files against the HF cache — offline, no network.

Run inside the Kokoro venv (needs ``huggingface_hub``):

    .venvs/kokoro/bin/python -m voice_engine.scripts.validate_kokoro_weights
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils.timing import utc_now_iso  # noqa: E402
from voice_engine.models.kokoro_weights import (  # noqa: E402
    KOKORO_REPO_ID,
    all_required_valid,
    check_weights,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "validation"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Kokoro weights")
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    configure_logging()

    statuses = check_weights()
    for s in statuses:
        flag = "req" if s.required else "opt"
        print(f"[{s.status:10}] ({flag}) {s.relpath:24} {s.reason}")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "kokoro_weights_report.json").write_text(
        json.dumps({"generated_at": utc_now_iso(), "repo_id": KOKORO_REPO_ID,
                    "weights": [s.to_dict() for s in statuses]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = ["# Kokoro Weights Report", "", f"Generated: {utc_now_iso()}",
             f"HF repo: `{KOKORO_REPO_ID}` (resolved against the HF cache)", "",
             "| Weight | Required | Purpose | Status | Detail |", "|---|:--:|---|---|---|"]
    for s in statuses:
        lines.append(f"| `{s.relpath}` | {'yes' if s.required else 'no'} | "
                     f"{s.purpose} | {s.status} | {s.reason} |")
    req_ok = sum(s.ok for s in statuses if s.required)
    req_total = sum(1 for s in statuses if s.required)
    lines += ["", f"**{req_ok}/{req_total} required weights verified.**"]
    (out_dir / "kokoro_weights_report.md").write_text("\n".join(lines) + "\n",
                                                      encoding="utf-8")

    print(f"\n{req_ok}/{req_total} required weights verified. "
          f"Report: {out_dir / 'kokoro_weights_report.md'}")
    return 0 if all_required_valid(statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
