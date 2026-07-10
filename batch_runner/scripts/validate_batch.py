"""Batch generator acceptance check (Phase C20).

Proves the stop condition end to end: five sample reels generate sequentially,
all pass, produce upload-ready metadata, have no duplicate outputs, and **resume**
works (an interrupted batch skips completed reels and finishes the rest).

    python -m batch_runner.scripts.validate_batch

Hermetic (mock renderer into a temporary workspace: no GPU, no FFmpeg, no
network). Exit 0 = ACCEPTED, exit 1 = REJECTED.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from batch_runner.input import load_entries
from batch_runner.report import write_reports
from batch_runner.runner import BatchRunner

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample_reels.yaml"


def _has_metadata(output_dir: str) -> bool:
    out = Path(output_dir)
    return (out / "metadata.json").is_file() and (out / "upload_preview.md").is_file()


def validate() -> bool:
    entries = load_entries(SAMPLE)
    print(f"Batch acceptance check — {len(entries)} sample reels (mock renderer)\n")

    with tempfile.TemporaryDirectory(prefix="batch_v1_") as tmp:
        ws = Path(tmp) / "workspace"

        # Phase 1 — simulate an interrupted batch that only got through 3 reels.
        print("Phase 1: generate the first 3 reels (simulated interruption) …")
        r1 = BatchRunner(entries[:3], workspace_root=ws, out=lambda s: None).run()

        # Phase 2 — resume with the full batch of 5.
        print("Phase 2: resume with all 5 reels …\n")
        r2 = BatchRunner(entries, workspace_root=ws, out=lambda s: None).run()

        json_path, md_path = write_reports(r2, Path(r2.batch_dir))

        output_dirs = [o.output_dir for o in r2.outcomes]
        all_have_metadata = all(_has_metadata(d) for d in output_dirs)
        unique_outputs = len(set(output_dirs)) == len(entries)

        checks: list[tuple[str, bool]] = [
            ("phase 1 generated 3 reels", r1.passed == 3 and r1.failed == 0),
            ("resume skipped the 3 completed reels", r2.skipped == 3),
            ("resume generated the 2 remaining reels", r2.passed == 2),
            ("no reel failed", r2.failed == 0),
            ("all 5 reels completed (quality PASS + metadata)", all_have_metadata),
            ("no duplicate outputs", unique_outputs),
            ("batch_report.json written", json_path.is_file()),
            ("batch_summary.md written", md_path.is_file()),
        ]

        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

        accepted = all(ok for _, ok in checks)
        print(f"\n=== BATCH GENERATOR VALIDATION: "
              f"{'ACCEPTED' if accepted else 'REJECTED'} ===")
        return accepted


def main() -> int:
    return 0 if validate() else 1


if __name__ == "__main__":
    raise SystemExit(main())
